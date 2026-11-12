"""Incremental Arctic Shift historical Reddit backfill, 2022 to present.

Small, bounded monthly queries. Resumes capped windows across scheduled runs.
Completed means query pagination was exhausted, not that Reddit is exhaustive.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import json
import os
import re
import time
import collector

START_YEAR = 2022
MONTHLY_TARGETS = (
    ("posts", "motorola", "title", "Glance"),
    ("comments", "motorola", "body", "Glance"),
    ("posts", "xiaomi", "title", "Glance"),
    ("comments", "xiaomi", "body", "Glance"),
    ("posts", "androidapps", "title", "Unity Aura"),
)
MAX_TASKS = max(1, min(24, int(os.getenv("HISTORY_TASKS_PER_RUN", "20"))))
LIMIT_KEYWORD = 50
LIMIT_FALLBACK = 100
MAX_FALLBACK_PAGES = 2


def month_start(year, month):
    return f"{year:04d}-{month:02d}-01"


def next_month(year, month):
    return month_start(year + 1, 1) if month == 12 else month_start(year, month + 1)


def tasks_for(now):
    """Round-robin across years before covering later months."""
    out = []
    for month in range(1, 13):
        for year in range(START_YEAR, now.year + 1):
            if year == now.year and month > now.month:
                continue
            for kind, sub, key, query in MONTHLY_TARGETS:
                task_id = f"{year:04d}-{month:02d}/{kind}/{sub}/{key}/{query}"
                out.append((task_id, year, month, kind, sub, key, query))
    return out


def request(typ, params):
    payload = json.loads(
        collector.get(collector.ARCHIVE + f"/api/{typ}/search?" + urlencode(params), attempts=1)
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Arctic Shift response did not contain a data list")
    return payload["data"]


def get_reddit(task, observed, checkpoint=None):
    """Return items, has_more_pages, and next checkpoint.

    A returned partial window will NOT be recorded as complete.
    """
    task_id, year, month, typ, sub, key, query = task
    checkpoint = checkpoint or {}
    mode = checkpoint.get("mode", "keyword")
    after = checkpoint.get("after", month_start(year, month))
    end = next_month(year, month)
    end_unix = datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp()
    params = {
        "subreddit": sub, "after": after, "before": end, "sort": "asc",
        "limit": LIMIT_KEYWORD,
        "fields": ("id,title,selftext,created_utc,subreddit" if typ == "posts" else
                   "id,body,link_id,created_utc,subreddit"),
    }
    if mode == "keyword":
        params[key] = query
        max_pages = 1
    else:
        params["limit"] = LIMIT_FALLBACK
        max_pages = MAX_FALLBACK_PAGES
    entries = []
    complete = False
    next_after = after

    for page in range(max_pages):
        try:
            batch = request(typ, params)
        except HTTPError as e:
            if e.code != 422 or typ != "posts" or mode != "keyword":
                raise
            # A keyword index timeout is common on old posts. Continue a
            # bounded, date-ordered scan and filter relevance in Python.
            mode = "unfiltered"
            params.pop(key, None)
            params["limit"] = LIMIT_FALLBACK
            max_pages = MAX_FALLBACK_PAGES
            batch = request(typ, params)
        entries.extend(batch)
        if len(batch) < params["limit"]:
            complete = True
            break
        last_timestamp = batch[-1].get("created_utc")
        if not isinstance(last_timestamp, (int, float)):
            raise ValueError("Cannot paginate: last result has no timestamp")
        next_after = int(last_timestamp) + 1
        if next_after >= end_unix:
            complete = True
            break
        params["after"] = next_after
        if mode == "keyword":
            # Each daily run has a fixed request budget per search window.
            break
        if page + 1 < max_pages:
            time.sleep(1.2)

    output = []
    for obj in entries:
        rid = str(obj.get("id") or "").removeprefix("t3_").removeprefix("t1_")
        community = str(obj.get("subreddit") or sub)
        if (not re.fullmatch(r"[A-Za-z0-9]{4,16}", rid) or
                not re.fullmatch(r"[A-Za-z0-9_]{1,28}", community)):
            continue
        title = (obj.get("title") or "") if typ == "posts" else ""
        body = (obj.get("selftext") or "") if typ == "posts" else (obj.get("body") or "")
        if not isinstance(title, str) or not isinstance(body, str):
            continue
        if body.strip().lower() in ("[removed]", "[deleted]"):
            continue
        if typ == "comments":
            parent = str(obj.get("link_id") or "").removeprefix("t3_")
            if not re.fullmatch(r"[A-Za-z0-9]{4,16}", parent):
                continue
            url = f"https://www.reddit.com/r/{community}/comments/{parent}/_/{rid}/"
        else:
            url = f"https://www.reddit.com/r/{community}/comments/{rid}/"
        item = collector.record(
            "reddit:" + ("c:" if typ == "comments" else "p:") + rid,
            "Reddit", body, title, url, collector.parse_date(obj.get("created_utc")),
            observed, historical=True, community="r/" + community, via="Arctic Shift",
        )
        if item:
            output.append(item)
    return output, (not complete), {"after": next_after, "mode": mode}


def main():
    if not collector.DATA.exists():
        raise RuntimeError("Daily data store missing; run collector first")
    store = json.loads(collector.DATA.read_text(encoding="utf-8"))
    observed = collector.now()
    jobs = tasks_for(observed)
    previous = store.get("backfill") or {}
    # Migration: previous version incorrectly marked capped windows complete.
    legacy_partial = set(previous.get("saturated", []))
    done = set(previous.get("completed", [])) - legacy_partial
    attempts = dict(previous.get("attempts", {}))
    checkpoints = dict(previous.get("checkpoints", {}))
    # Prioritize a few partially completed windows while exploring new years.
    partial = [t for t in jobs if t[0] not in done and
               (t[0] in checkpoints or t[0] in legacy_partial)]
    fresh = [t for t in jobs if t[0] not in done and t not in partial]
    partial.sort(key=lambda t: (attempts.get(t[0], 0), jobs.index(t)))
    fresh.sort(key=lambda t: (attempts.get(t[0], 0), jobs.index(t)))
    reserved = min(MAX_TASKS // 3, len(partial))
    selected = partial[:reserved] + fresh[:MAX_TASKS - reserved]
    if len(selected) < MAX_TASKS:
        selected += partial[reserved:reserved + MAX_TASKS - len(selected)]
    saved = {p["id"]: p for p in store.get("items", []) if p.get("id")}
    new = 0
    errors = []
    for task in selected:
        task_id = task[0]
        try:
            items, has_more, next_cursor = get_reddit(task, observed, checkpoints.get(task_id))
            for item in items:
                if item["id"] not in saved:
                    saved[item["id"]] = item
                    new += 1
            attempts.pop(task_id, None)
            if has_more:
                checkpoints[task_id] = next_cursor
                legacy_partial.add(task_id)
            else:
                done.add(task_id)
                checkpoints.pop(task_id, None)
                legacy_partial.discard(task_id)
            print(f"HISTORY {task_id}: {len(items)} relevant; more={has_more}", flush=True)
        except HTTPError as e:
            attempts[task_id] = attempts.get(task_id, 0) + 1
            errors.append(f"{task_id}: HTTP {e.code}")
            if e.code == 429:
                errors.append("Arctic Shift rate limited, stopped this run")
                break
        except (ValueError, URLError, TimeoutError, TypeError) as e:
            attempts[task_id] = attempts.get(task_id, 0) + 1
            errors.append(f"{task_id}: {str(e)[:80]}")
        time.sleep(2.2)

    state = {
        "start": f"{START_YEAR}-01",
        "last_attempt": collector.iso(observed),
        "total_windows": len(jobs),
        "completed_windows": len(done),
        "completed": sorted(done),
        "checkpoints": checkpoints,
        "attempts": attempts,
        "saturated": sorted(legacy_partial),
        "errors": errors[-20:],
        "note": ("Completed windows exhausted their available query pages. "
                 "The archive may be incomplete; date pagination may miss same-second posts."),
    }
    store["backfill"] = state
    store["items"] = sorted(
        saved.values(), key=lambda x: x.get("published_at", ""), reverse=True
    )[:30000]
    collector.DATA.write_text(
        json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Backfill: {len(done)}/{len(jobs)} completed, "
        f"{len(checkpoints)} paginated, {new} new, {len(errors)} errors",
        flush=True,
    )


if __name__ == "__main__":
    main()
