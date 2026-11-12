#!/usr/bin/env python3
"""Daily public-source monitor. No credentials, no X scraping."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
import hashlib
import html
import json
import os
import pathlib
import re
import time
import xml.etree.ElementTree as ET
from sentiment import classify, VERSION as SENTIMENT_VERSION

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "monitor.json"
ARCHIVE = "https://arctic-shift.photon-reddit.com"
BLUESKY = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
HN = "https://hn.algolia.com/api/v1/search_by_date"
NEWS = "https://news.google.com/rss/search"
USER_AGENT = "LockScreenSignals/1.0 (+https://github.com/creamtown0420/lockscreen-voice-monitor; personal-research)"
SUBS = ("motorola", "xiaomi", "realme", "AndroidQuestions")
REDDIT_WORDS = ("Glance", "lock screen ads", "Unity Aura")
SEARCHES = ('"Glance" "lock screen"', '"Glance" "Motorola"', '"Glance" "ads"',
            '"Unity Aura"', '"lock screen ads"')


def now():
    return datetime.now(timezone.utc)


def iso(t):
    return t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(value)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def brief(value, limit=240):
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()
    return s[:limit] + ("…" if len(s) > limit else "")


def relevant_excerpt(value, brand, limit=320):
    """Keep the discussion around the relevant service, not a generic preamble."""
    cleaned = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()
    if len(cleaned) <= limit:
        return cleaned
    term = {"Glance": r"\bglance\b", "Unity Aura": r"\bunity aura\b",
            "Industry": r"\block[\s-]?screen\b"}.get(brand)
    hit = re.search(term, cleaned, re.I) if term else None
    start = min(max(0, hit.start() - 85), len(cleaned) - limit) if hit else 0
    segment = cleaned[start:start + limit]
    return ("…" if start else "") + segment + ("…" if start + limit < len(cleaned) else "")


def brand_for(text):
    s = str(text or "").casefold()
    if re.search(r"\bunity aura\b|\baura from unity\b", s):
        return "Unity Aura"
    if re.search(r"\bglance\b", s):
        # "at a glance" is an everyday English expression, not this product.
        idiom = bool(re.search(r"\b(at a|at first|at one|at a quick|in a|one|first|a quick|single|just one) glance\b|\bglance (?:at|over|away|through)\b", s))
        product = bool(re.search(
            r"\bglance\s+(?:app|for mi|ads?|advertis\w*|lock[\s-]?screen|wallpaper|service|feed|news)\b"
            r"|\b(?:motorola|xiaomi|samsung|realme|inmobi)\s+glance\b"
            r"|\b(?:disabl\w*|enabl\w*|uninstall\w*|remov\w*|re[- ]?enabl\w*|delet\w*|block\w*|debloat\w*)\s+(?:the\s+)?glance\b"
            r"|\bglance\b.{0,45}\b(?:disable|uninstall|remove|removed|deleted|adware|bullshit|spam|intrusive|lock[\s-]?screen)\b",
            s))
        if product:
            return "Glance"
        if not idiom and re.search(r"\b(?:android|motorola|xiaomi|samsung|realme|inmobi|myhub|lock[\s-]?screen|phone|device)\b", s):
            return "Glance"
    if re.search(r"\block[\s-]?screen\s+(?:ads?|advertis\w*)\b", s):
        return "Industry"
    return None


def get(url, attempts=2):
    for n in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=18) as r:
                return r.read(2_000_000)
        except HTTPError as e:
            if n + 1 == attempts or e.code not in (500, 502, 503, 504):
                raise
            time.sleep(3 * (n + 1))
        except (URLError, TimeoutError):
            if n + 1 == attempts:
                raise
            time.sleep(2 * (n + 1))
    raise RuntimeError("HTTP request failed")


def record(id, source, text, title, url, date, observed, kind="reaction", historical=False, **extra):
    brand = brand_for((title or "") + " " + (text or ""))
    if not brand or not date or date > observed + timedelta(days=1):
        return None
    if not historical and date < observed - timedelta(days=28 if source == "Reddit" else 14):
        return None
    analysis = classify((title or "") + " " + (text or ""), brand=brand) if kind == "reaction" else {
        "sentiment": "not_applicable", "score": 0.0, "topic": "ニュース",
        "reason": "ニュースは感情分析の集計対象外", "classifier": "not_applicable"}
    return {"id": id, "source": source, "brand": brand, "kind": kind,
            "published_at": iso(date), "first_seen": iso(observed),
            "title": brief(title or text, 170), "excerpt": relevant_excerpt(text, brand),
            "url": url, **analysis, **extra}


def collect_reddit(observed):
    """Third-party archive. Queries are always scoped to a subreddit."""
    if os.getenv("LOCKSCREEN_REDDIT_ENABLED", "1").lower() in ("0", "false", "no"):
        return [], 0, []
    found, ok, errors = [], 0, []
    after = (observed - timedelta(days=14)).strftime("%Y-%m-%d")
    # Relatively small workload for a volunteer-operated service.
    tasks = [("posts", sub, "Glance", "query") for sub in SUBS if sub != "AndroidQuestions"]
    tasks += [("comments", sub, "Glance", "body") for sub in SUBS]
    tasks += [("comments", "androidapps", "Unity Aura", "body")]
    for typ, sub, word, key in tasks:
        params = {"subreddit": sub, key: word, "after": after, "sort": "desc", "limit": 40}
        path = f"/api/{typ}/search?"
        try:
            try:
                payload = json.loads(get(ARCHIVE + path + urlencode(params)))
            except HTTPError as e:
                if e.code != 422:
                    raise
                # Keyword queries may exceed archive search timeouts. Fall back
                # to the latest entries in this community and filter locally.
                params.pop(key)
                params["limit"] = 40
                payload = json.loads(get(ARCHIVE + path + urlencode(params)))
                errors.append(f"{typ} r/{sub}: keyword timeout; recent-only fallback")
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError(str(payload.get("error", "unexpected response")))
            ok += 1
            for obj in payload["data"]:
                rid = str(obj.get("id") or "")
                community = str(obj.get("subreddit") or sub)
                if not re.fullmatch(r"[A-Za-z0-9]{4,16}", rid) or not re.fullmatch(r"[A-Za-z0-9_]{1,28}", community):
                    continue
                title = obj.get("title") if typ == "posts" else ""
                body = obj.get("selftext") if typ == "posts" else obj.get("body")
                if not isinstance(title or "", str) or not isinstance(body or "", str):
                    continue
                if (body or "").strip().lower() in ("[deleted]", "[removed]"):
                    continue
                if typ == "comments":
                    parent = str(obj.get("link_id") or "").removeprefix("t3_")
                    if not re.fullmatch(r"[A-Za-z0-9]{4,16}", parent):
                        continue
                    url = f"https://www.reddit.com/r/{community}/comments/{parent}/_/{rid}/"
                else:
                    url = f"https://www.reddit.com/r/{community}/comments/{rid}/"
                item = record("reddit:" + ("c:" if typ == "comments" else "p:") + rid,
                              "Reddit", body or "", title or "", url,
                              parse_date(obj.get("created_utc")), observed,
                              community="r/" + community, via="Arctic Shift")
                if item:
                    found.append(item)
        except HTTPError as e:
            errors.append(f"Reddit {typ} r/{sub}: HTTP {e.code}")
            if e.code == 429:
                errors.append("Reddit rate limited; skipped remaining requests")
                break
        except (ValueError, URLError, TimeoutError, TypeError) as e:
            errors.append(f"Reddit {typ} r/{sub}: {str(e)[:90]}")
        time.sleep(2.25)
    return found, ok, errors


def collect_bluesky(observed):
    found, ok, errors = [], 0, []
    for term in SEARCHES:
        try:
            payload = json.loads(get(BLUESKY + "?" + urlencode({"q": term, "sort": "latest", "limit": 50})))
            ok += 1
            for p in payload.get("posts", []):
                uri = str(p.get("uri") or "")
                body = str((p.get("record") or {}).get("text") or "")
                if not uri.startswith("at://"):
                    continue
                did = (p.get("author") or {}).get("did") or uri.split("/")[2]
                url = f"https://bsky.app/profile/{did}/post/{uri.rsplit('/', 1)[-1]}"
                item = record("bsky:" + uri, "Bluesky", body, "", url,
                              parse_date((p.get("record") or {}).get("createdAt") or p.get("indexedAt")), observed)
                if item:
                    found.append(item)
        except (ValueError, HTTPError, URLError, TimeoutError) as e:
            errors.append(f"Bluesky {term}: {str(e)[:90]}")
        time.sleep(0.35)
    return found, ok, errors


def collect_hn(observed):
    found, ok, errors = [], 0, []
    for term in ("Glance lock screen", "Unity Aura", "lockscreen ads"):
        try:
            payload = json.loads(get(HN + "?" + urlencode({"query": term, "tags": "(story,comment)", "hitsPerPage": 50})))
            ok += 1
            for p in payload.get("hits", []):
                oid = str(p.get("objectID") or "")
                if not oid.isdecimal():
                    continue
                body = brief(p.get("comment_text") or p.get("title") or p.get("story_title") or "", 400)
                item = record("hn:" + oid, "Hacker News", body, "",
                              "https://news.ycombinator.com/item?id=" + oid,
                              parse_date(p.get("created_at")), observed)
                if item:
                    found.append(item)
        except (ValueError, HTTPError, URLError, TimeoutError) as e:
            errors.append(f"HN {term}: {str(e)[:90]}")
    return found, ok, errors


def collect_news(observed):
    found, ok, errors = [], 0, []
    for term in SEARCHES:
        try:
            blob = get(NEWS + "?" + urlencode({"q": term + " when:14d", "hl": "en-US", "gl": "US", "ceid": "US:en"}))
            root = ET.fromstring(blob)
            ok += 1
            for entry in root.findall("./channel/item"):
                title = entry.findtext("title") or ""
                url = entry.findtext("link") or ""
                if not url.startswith("https://"):
                    continue
                rid = hashlib.sha256((entry.findtext("guid") or url).encode()).hexdigest()[:24]
                item = record("news:" + rid, "Google News RSS", "", title, url,
                              parse_date(entry.findtext("pubDate")), observed, kind="news")
                if item:
                    found.append(item)
        except (ValueError, HTTPError, URLError, TimeoutError, ET.ParseError) as e:
            errors.append(f"News {term}: {str(e)[:90]}")
    return found, ok, errors


def main():
    observed = now()
    if DATA.exists():
        store = json.loads(DATA.read_text(encoding="utf-8"))
    else:
        store = {"schema": 1, "items": [], "daily": [], "runs": []}
    total, good, errors = [], 0, []
    for name, collect in (("Reddit", collect_reddit), ("Bluesky", collect_bluesky),
                          ("Hacker News", collect_hn), ("Google News RSS", collect_news)):
        items, count, failures = collect(observed)
        total.extend(items)
        good += count
        errors.extend(failures)
        print(f"{name}: {len(items)} candidates, {count} successful searches, {len(failures)} warnings", flush=True)
    if good == 0:
        raise RuntimeError("Every source failed; preserving prior data")
    # Keep historical observations instead of deleting posts after 30 days.
    saved = {}
    for p in store.get("items", []):
        if not p.get("id"):
            continue
        text = (p.get("title") or "") + " " + (p.get("excerpt") or "")
        if brand_for(text) != p.get("brand"):
            # Historical false positives (e.g. "at a glance") must not count.
            continue
        if p.get("kind") == "reaction" and p.get("classifier") != SENTIMENT_VERSION:
            p.update(classify(text, brand=p.get("brand")))
        elif p.get("kind") != "reaction":
            p.update({"sentiment": "not_applicable", "topic": "ニュース"})
        saved[p["id"]] = p
    fresh = []
    for p in total:
        if p["id"] not in saved:
            saved[p["id"]] = p
            fresh.append(p)
    day = observed.date().isoformat()
    history = {x["date"]: x for x in store.get("daily", [])}
    counters = history.setdefault(day, {"date": day, "new_reactions": 0, "new_news": 0})
    counters["new_reactions"] += sum(x["kind"] == "reaction" for x in fresh)
    counters["new_news"] += sum(x["kind"] == "news" for x in fresh)
    store = {
        "schema": 1, "updated_at": iso(observed),
        "backfill": store.get("backfill", {}),
        "items": sorted(saved.values(), key=lambda x: x["published_at"], reverse=True)[:30000],
        "daily": sorted(history.values(), key=lambda x: x["date"])[-730:],
        "runs": (store.get("runs", []) + [{
            "at": iso(observed), "sources_ok": good,
            "sources_total": (len(SUBS)-1) + len(SUBS) + 1 + len(SEARCHES) * 2 + 3,
            "new": len(fresh), "errors": errors[:40],
        }])[-90:]
    }
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(store['items'])} entries; new {len(fresh)}", flush=True)


if __name__ == "__main__":
    main()
