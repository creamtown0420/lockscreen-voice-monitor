"""Incremental historical Reddit backfill, 2022 to present.

Searches bounded calendar-month windows and rotates years to surface long-term
examples early. No service guarantee; progress counts attempted-successfully
search windows, not an exhaustive index of Reddit.
"""
from __future__ import annotations
import calendar
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import json
import os
import re
import time

import collector

START_YEAR = 2022
HISTORY_SUBS = ("motorola", "xiaomi")
# Five targeted searches for each month, with no bulk-download pressure.
MONTHLY_TARGETS = (
    ("posts", "motorola", "title", "Glance"),
    ("comments", "motorola", "body", "Glance"),
    ("posts", "xiaomi", "title", "Glance"),
    ("comments", "xiaomi", "body", "Glance"),
    ("posts", "androidapps", "title", "Unity Aura"),
)
MAX_TASKS = max(1, min(28, int(os.getenv("HISTORY_TASKS_PER_RUN", "20"))))
LIMIT = 50

def month_start(year, month):
    return f"{year:04d}-{month:02d}-01"

def next_month(year, month):
    return month_start(year+1,1) if month == 12 else month_start(year,month+1)

def tasks_for(now):
    """Spread the first backfill runs across years before filling all months."""
    out = []
    for month in range(1,13):
        for year in range(START_YEAR, now.year+1):
            if year==now.year and month > now.month:
                continue
            for kind,sub,key,query in MONTHLY_TARGETS:
                task_id=f"{year:04d}-{month:02d}/{kind}/{sub}/{key}/{query}"
                out.append((task_id,year,month,kind,sub,key,query))
    return out

def get_reddit(task, observed):
    task_id,year,month,typ,sub,key,query=task
    params={"subreddit":sub,key:query,"after":month_start(year,month),
            "before":next_month(year,month),"sort":"asc","limit":LIMIT}
    payload=json.loads(collector.get(collector.ARCHIVE+f"/api/{typ}/search?"+urlencode(params),attempts=1))
    if not isinstance(payload,dict) or not isinstance(payload.get("data"),list):
        raise ValueError("no data list from archive")
    out=[]
    for obj in payload["data"]:
        rid=str(obj.get("id") or "").removeprefix("t3_").removeprefix("t1_")
        community=str(obj.get("subreddit") or sub)
        if not re.fullmatch(r"[A-Za-z0-9]{4,16}",rid) or not re.fullmatch(r"[A-Za-z0-9_]{1,28}",community):
            continue
        title=(obj.get("title") or "") if typ=="posts" else ""
        body=(obj.get("selftext") or "") if typ=="posts" else (obj.get("body") or "")
        if not isinstance(title,str) or not isinstance(body,str) or body.strip().lower() in ("[removed]","[deleted]"):
            continue
        if typ=="comments":
            parent=str(obj.get("link_id") or "").removeprefix("t3_")
            if not re.fullmatch(r"[A-Za-z0-9]{4,16}",parent):
                continue
            url=f"https://www.reddit.com/r/{community}/comments/{parent}/_/{rid}/"
        else:
            url=f"https://www.reddit.com/r/{community}/comments/{rid}/"
        item=collector.record("reddit:"+("c:" if typ=="comments" else "p:")+rid,
             "Reddit",body,title,url,collector.parse_date(obj.get("created_utc")),
             observed,historical=True,community="r/"+community,via="Arctic Shift")
        if item:
            out.append(item)
    return out, len(payload["data"]) >= LIMIT

def main():
    if not collector.DATA.exists():
        print("No daily data store; run collector first.",flush=True)
        return
    store=json.loads(collector.DATA.read_text(encoding="utf-8"))
    observed=collector.now()
    jobs=tasks_for(observed)
    state=store.get("backfill") or {}
    done=set(state.get("completed",[]))
    attempts=state.get("attempts",{})
    # Prioritize never-tried windows, then retry failures after new windows.
    pending=[t for t in jobs if t[0] not in done]
    pending.sort(key=lambda t:(attempts.get(t[0],0), jobs.index(t)))
    selected=pending[:MAX_TASKS]
    saved={p["id"]:p for p in store.get("items",[]) if p.get("id")}
    fresh=0
    errors=[]
    saturated=set(state.get("saturated",[]))
    for task in selected:
        task_id=task[0]
        try:
            items,limit_reached=get_reddit(task,observed)
            for item in items:
                if item["id"] not in saved:
                    saved[item["id"]]=item
                    fresh+=1
            done.add(task_id)
            attempts.pop(task_id,None)
            if limit_reached:
                saturated.add(task_id)
            print(f"HISTORY {task_id}: {len(items)} relevant posts/comments",flush=True)
        except HTTPError as e:
            attempts[task_id]=attempts.get(task_id,0)+1
            errors.append(f"{task_id}: HTTP {e.code}")
            if e.code==429:
                errors.append("Rate limit: stopped archive requests")
                break
        except (ValueError,URLError,TimeoutError,TypeError) as e:
            attempts[task_id]=attempts.get(task_id,0)+1
            errors.append(f"{task_id}: {str(e)[:70]}")
        time.sleep(2.0)
    state={"start":f"{START_YEAR}-01","last_attempt":collector.iso(observed),
           "total_windows":len(jobs),"completed_windows":len(done),
           "completed":sorted(done),"attempts":attempts,
           "saturated":sorted(saturated),"errors":errors[-15:],
           "note":"Historical Reddit archive, sampled queries; coverage is incomplete and may be delayed."}
    store["backfill"]=state
    store["items"]=sorted(saved.values(),key=lambda x:x.get("published_at",""),reverse=True)[:30000]
    collector.DATA.write_text(json.dumps(store,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Historical backfill: {len(done)}/{len(jobs)} search windows; {fresh} new; {len(errors)} errors",flush=True)

if __name__=="__main__":
    main()
