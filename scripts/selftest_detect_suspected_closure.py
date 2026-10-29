"""自測：盤中疑似臨時休市判斷 `.github/scripts/detect_suspected_closure.py` 的 `judge()`（先.一三五-1bi）。

純函式、零檔案寫入、零外部請求。
"""
from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import detect_suspected_closure as D  # noqa: E402

TW = timezone(timedelta(hours=8))
ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


NOW = datetime(2026, 10, 29, 10, 0, tzinfo=TW)  # 週四
CAL = {"tw": {"2026": {"closed": ["2026-10-10"], "unscheduled_closed": []}}}


def quotes(dates, fetched=NOW - timedelta(minutes=5)):
    return {"fetched_at": fetched.isoformat() if isinstance(fetched, datetime) else fetched,
            "quotes": {f"{2330 + i}": {"date": d} for i, d in enumerate(dates)}}


def j(cal, q, now=NOW):
    c = copy.deepcopy(cal)
    return D.judge(c, q, now), c


stale = quotes(["20261028", "20261028"])

print("\n[skip 情境]")
check("週六 → skip", j(CAL, stale, datetime(2026, 10, 31, 10, 0, tzinfo=TW))[0] == "skip")
check("09:29 → skip", j(CAL, stale, NOW.replace(hour=9, minute=29))[0] == "skip")
check("09:30 整 → 不再 skip（suspected）", j(CAL, stale, NOW.replace(hour=9, minute=30))[0] == "suspected")
cal_known = copy.deepcopy(CAL)
cal_known["tw"]["2026"]["unscheduled_closed"] = ["2026-10-29"]
check("已記在 unscheduled_closed → skip", j(cal_known, stale)[0] == "skip")
cal_closed = copy.deepcopy(CAL)
cal_closed["tw"]["2026"]["closed"].append("2026-10-29")
check("已記在 closed → skip", j(cal_closed, stale)[0] == "skip")
check("報價檔逾 30 分鐘 → skip", j(CAL, quotes(["20261028"], NOW - timedelta(minutes=31)))[0] == "skip")
check("fetched_at 壞值 → skip", j(CAL, quotes(["20261028"], "not-a-date"))[0] == "skip")
check("fetched_at 缺 → skip", j(CAL, {"quotes": {"2330": {"date": "20261028"}}})[0] == "skip")
check("空報價 → skip", j(CAL, quotes([]))[0] == "skip")
check("當年度不在日曆 → skip", j({"tw": {"2025": {}}}, stale)[0] == "skip")
check("日曆沒有 tw → skip", j({}, stale)[0] == "skip")
naive = quotes(["20261028"], (NOW - timedelta(minutes=5)).replace(tzinfo=None).isoformat())
check("fetched_at 無時區當台北時間 → suspected", j(CAL, naive)[0] == "suspected")

print("\n[suspected／open]")
v, c = j(CAL, stale)
mark = c["tw"]["2026"].get("suspected_closed_today") or {}
check("全部日期早於今天 → suspected", v == "suspected")
check("寫入當天標記、附 source", mark.get("date") == "2026-10-29" and "quotes_tw.json" in mark.get("source", ""), mark)
check("不寫 unscheduled_closed", c["tw"]["2026"]["unscheduled_closed"] == [])

cal_marked = c
v, c2 = j(cal_marked, quotes(["20261028", "20261029"]))
check("有一檔是今天 → open", v == "open")
check("open 時清掉當天舊標記", "suspected_closed_today" not in c2["tw"]["2026"])

cal_other = copy.deepcopy(CAL)
cal_other["tw"]["2026"]["suspected_closed_today"] = {"date": "2026-10-28"}
v, c3 = j(cal_other, quotes(["20261029"]))
check("open 時不清別天的標記", v == "open" and c3["tw"]["2026"].get("suspected_closed_today") == {"date": "2026-10-28"})
check("非 dict 的報價列忽略", j(CAL, {"fetched_at": (NOW - timedelta(minutes=1)).isoformat(),
                                    "quotes": {"x": "bad", "2330": {"date": "20261029"}}})[0] == "open")

print(f"\n結果：{ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
