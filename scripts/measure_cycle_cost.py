# -*- coding: utf-8 -*-
"""先.二十八-三：量測 marathon／hypothesis_queue 在指定時間窗內實際呼叫 Claude 的次數與 cost_usd。
用法：python scripts/measure_cycle_cost.py [--start ISO] [--end ISO]（預設最近 24 小時，台北時間）
資料源：research/quota_usage_daily.log 的 `<launcher>: run（...）` 行＝實際啟動 claude -p；
cost_usd 取自 research/marathon_cycle.log 的 cycle end 行。hypothesis_queue 的 launcher 沒有
stream-json，本來就不記 cost_usd，如實輸出 None，不估算。唯讀，失敗只印警告。"""
import re, sys, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
R = Path(__file__).resolve().parent.parent / "research"
TZ = timezone(timedelta(hours=8))

def parse(a):
    d = datetime.fromisoformat(a)
    return d if d.tzinfo else d.replace(tzinfo=TZ)

def measure(start, end):
    runs = {"marathon": 0, "hypothesis_queue": 0}
    skips = {"marathon": 0, "hypothesis_queue": 0}
    for ln in (R / "quota_usage_daily.log").read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"(\S+) (marathon|hypothesis_queue): (run|skip\w*)", ln)
        if not m:
            continue
        try:
            t = parse(m.group(1))
        except ValueError:
            continue
        if start <= t < end:
            (runs if m.group(3) == "run" else skips)[m.group(2)] += 1
    cost, n = 0.0, 0
    for ln in (R / "marathon_cycle.log").read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"cycle end: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*cost_usd=([\d.]+)", ln)
        if m:
            t = parse(m.group(1).replace(" ", "T"))
            if start <= t < end:
                cost += float(m.group(2)); n += 1
    return {"window": [start.isoformat(), end.isoformat()], "claude_runs": runs, "skipped_by_throttle": skips,
            "marathon_cost_usd": round(cost, 4), "marathon_cycles_with_cost": n, "hypothesis_cost_usd": None}

if __name__ == "__main__":
    a = sys.argv
    end = parse(a[a.index("--end") + 1]) if "--end" in a else datetime.now(TZ)
    start = parse(a[a.index("--start") + 1]) if "--start" in a else end - timedelta(hours=24)
    try:
        print(json.dumps(measure(start, end), ensure_ascii=False, indent=1))
    except Exception as e:
        print(f"::warning::量測失敗 {type(e).__name__}: {e}")
