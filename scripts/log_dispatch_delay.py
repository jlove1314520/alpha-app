"""記錄 market.yml 排程派發延遲（cron排定時間 -> run createdAt），總司令裁示【先.九】三。

用法：python scripts/log_dispatch_delay.py --since 2026-10-02
  - 用 `gh run list --workflow market.yml --event schedule` 取得 run 的 createdAt
  - 依 market.yml 現行三個 cron 時段，用「最早的、尚未配對且 <= createdAt 的排定時間」逐一配對
  - 結果去重後 append 到 research/dispatch_delay_log.jsonl（一行一個 run，可重複執行）
  - 排定時間沒有任何 run 對應者，印出為「missing」，不寫檔
限制：GitHub 若直接丟棄某個排程時段（不派發），後面的 run 可能被配到前一個空缺，
      所以連續出現 missing 時要回頭人工核對。
不是排程腳本，只在人工／互動視窗呼叫，不寫任何 workflow 的 git add allowlist 範圍。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SLOTS_UTC = [(9, 13), (10, 41), (21, 43)]  # market.yml 現行 cron，週一至週五（UTC）
OUT = os.path.join("research", "dispatch_delay_log.jsonl")


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def slots_between(start, end):
    d = start.date()
    while d <= end.date():
        if d.weekday() < 5:
            for h, m in SLOTS_UTC:
                t = datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)
                if start <= t <= end:
                    yield t
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="YYYY-MM-DD（UTC）起算排定時間")
    ap.add_argument("--workflow", default="market.yml")
    a = ap.parse_args()
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    raw = subprocess.run(
        ["gh", "run", "list", "--workflow", a.workflow, "--event", "schedule", "--limit", "200",
         "--json", "databaseId,createdAt,startedAt,updatedAt,conclusion"],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    runs = sorted((r for r in json.loads(raw) if parse_ts(r["createdAt"]) >= since),
                  key=lambda r: r["createdAt"])
    if not runs:
        print("沒有符合的 schedule run")
        return
    slots = list(slots_between(since, parse_ts(runs[-1]["createdAt"])))
    seen = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            line = line.strip()
            if line:
                seen.add(json.loads(line)["run_id"])

    pending = list(slots)
    rows = []
    for r in runs:
        created = parse_ts(r["createdAt"])
        slot = next((s for s in pending if s <= created), None)
        if slot is None:
            print("無法配對排定時間:", r["databaseId"], r["createdAt"])
            continue
        pending.remove(slot)
        rows.append({
            "run_id": r["databaseId"], "workflow": a.workflow,
            "scheduled_utc": slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "created_utc": r["createdAt"],
            "delay_min": round((created - slot).total_seconds() / 60, 1),
            "conclusion": r.get("conclusion"),
        })
    for s in pending:
        print("missing（排定後無對應 run）:", s.strftime("%Y-%m-%dT%H:%M:%SZ"))
    new = [x for x in rows if x["run_id"] not in seen]
    if new:
        with open(OUT, "ab") as f:
            for x in new:
                f.write((json.dumps(x, ensure_ascii=False) + "\n").encode("utf-8"))
    for x in rows:
        print(x["scheduled_utc"], "->", x["created_utc"], "延遲", x["delay_min"], "分", x["conclusion"])
    print("新增", len(new), "筆 ->", OUT)


if __name__ == "__main__":
    main()
