# -*- coding: utf-8 -*-
"""假設池空時只記一行心跳（2026-10-13 總司令【先.八十二】8 裁示⑦）。
用法：python research/pool_empty_heartbeat.py <marathon|hypothesis_queue>
由 run-marathon-cycle.ps1／run-hypothesis-queue-cycle.ps1 在 quota_throttle.py pool_empty 判定池空時呼叫，
寫一行到 research/PROGRESS_HEARTBEAT.jsonl 後，外層腳本直接結束（不叫 claude）。"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

track = sys.argv[1] if len(sys.argv) > 1 else "unknown"
p = Path(__file__).resolve().parent / "PROGRESS_HEARTBEAT.jsonl"
row = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
       "source": track, "item": "pool_empty", "summary": "假設池空：上一輪沒有新增試驗、池子內容未變，本週只記心跳不啟動"}
with open(p, "a", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("POOL_EMPTY_HEARTBEAT", track)
