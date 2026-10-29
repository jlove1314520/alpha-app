"""自測：交易日曆每日臨時休市確認 `.github/scripts/fetch_trading_calendar.py` 的 `confirm_recent_closure()`（先.一三五-1bm）。

FMTQIK 與官方報價檔都換成假函式：零外部請求、零檔案寫入（只改記憶體裡的 dict）。
前向模擬與看守員靠 `data/trading_calendar.json` 的 `unscheduled_closed` 跳過休市日，這裡確認：
已過去日寫入、今天要雙重佐證、確認進度不會推過沒確認完的日子、FMTQIK 失敗保留既有、盤中誤判告警。
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
import fetch_trading_calendar as C  # noqa: E402

TW = timezone(timedelta(hours=8))
ok = fail = 0
calls: list = []


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def weekdays(y, m, upto, skip=()):
    """y-m 月 1 日到 upto 日的平日，扣掉 skip。"""
    from datetime import date
    out, d = set(), date(y, m, 1)
    while d.month == m and d.day <= upto:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.add(d.isoformat())
        d += timedelta(days=1)
    return out


def setup(traded=None, quotes_before=None, raise_exc=None):
    calls.clear()

    def fake_fmtqik(y, m):
        calls.append((y, m))
        if raise_exc:
            raise raise_exc
        return traded

    C._fmtqik_traded = fake_fmtqik
    C._official_quotes_all_before = lambda day: quotes_before


BASE = {"2026": {"published": True, "closed": ["2026-10-06", "2026-10-09"], "unscheduled_closed": ["2026-07-10"]}}

print("情境一：已過去日（目標日＝昨天）")
tw = copy.deepcopy(BASE)
setup(traded=weekdays(2026, 10, 28, skip={"2026-10-06", "2026-10-09", "2026-10-21"}))
C.confirm_recent_closure(tw, datetime(2026, 10, 29, 10, 0, tzinfo=TW))  # 17:00 前 → 目標日 10/28
y = tw["2026"]
check("只問一次 FMTQIK、問目標月", calls == [(2026, 10)], calls)
check("10/21 平日沒成交 → 寫入", "2026-10-21" in y["unscheduled_closed"], y["unscheduled_closed"])
check("既有 07-10 保留", "2026-07-10" in y["unscheduled_closed"])
check("休市表日期（10/06、10/09）不重複寫", not {"2026-10-06", "2026-10-09"} & set(y["unscheduled_closed"]))
check("週末不寫", not any(d in y["unscheduled_closed"] for d in ("2026-10-24", "2026-10-25")))
check("確認進度＝10/28", y.get("daily_confirm_through") == "2026-10-28", y.get("daily_confirm_through"))
check("今天 10/29 不在處理範圍", "2026-10-29" not in y["unscheduled_closed"])

print("情境二：同一目標日第二次呼叫不再送請求")
setup(traded=set())
C.confirm_recent_closure(tw, datetime(2026, 10, 29, 12, 0, tzinfo=TW))
check("零請求", calls == [], calls)

print("情境三：目標日＝今天（17:00 後），FMTQIK 沒有今天")
full = weekdays(2026, 10, 28, skip={"2026-10-06", "2026-10-09"})
for qb, label in ((True, "報價檔全部早於今天 → 寫入"), (False, "報價檔有今天 → 不寫、進度停在昨天"),
                  (None, "報價檔讀不到 → 不寫、進度停在昨天")):
    tw = copy.deepcopy(BASE)
    tw["2026"]["daily_confirm_through"] = "2026-10-28"
    setup(traded=full, quotes_before=qb)
    C.confirm_recent_closure(tw, datetime(2026, 10, 29, 18, 0, tzinfo=TW))
    y = tw["2026"]
    if qb:
        check(label, "2026-10-29" in y["unscheduled_closed"] and y["daily_confirm_through"] == "2026-10-29",
              (y["unscheduled_closed"], y["daily_confirm_through"]))
    else:
        check(label, "2026-10-29" not in y["unscheduled_closed"] and y["daily_confirm_through"] == "2026-10-28",
              (y["unscheduled_closed"], y["daily_confirm_through"]))

print("情境四：今天沒確認完，下一班仍會再問")
tw = copy.deepcopy(BASE)
setup(traded=full, quotes_before=False)
C.confirm_recent_closure(tw, datetime(2026, 10, 29, 18, 0, tzinfo=TW))
setup(traded=full | {"2026-10-29"}, quotes_before=False)
C.confirm_recent_closure(tw, datetime(2026, 10, 29, 21, 0, tzinfo=TW))
check("21:00 班仍送 1 次請求", calls == [(2026, 10)], calls)
check("FMTQIK 補上今天後進度推到 10/29、不寫入", tw["2026"]["daily_confirm_through"] == "2026-10-29"
      and "2026-10-29" not in tw["2026"]["unscheduled_closed"], tw["2026"])

print("情境五：FMTQIK 失敗／非 OK → 保留既有")
for kind in ("raise", "none"):
    tw = copy.deepcopy(BASE)
    before = copy.deepcopy(tw)
    setup(traded=None, raise_exc=RuntimeError("FMTQIK HTTP 429（不重試）") if kind == "raise" else None)
    C.confirm_recent_closure(tw, datetime(2026, 10, 29, 10, 0, tzinfo=TW))
    check(f"{kind}：日曆內容完全不變", tw == before, tw)

print("情境六：年度未公布／不存在 → 零請求")
for cal, label in (({"2026": {"published": False}}, "published=False"), ({}, "沒有該年度")):
    setup(traded=set())
    C.confirm_recent_closure(copy.deepcopy(cal), datetime(2026, 10, 29, 10, 0, tzinfo=TW))
    check(label, calls == [], calls)

print("情境七：盤中推測休市、官方卻有成交 → 記 mismatch")
tw = copy.deepcopy(BASE)
tw["2026"]["suspected_closed_today"] = {"date": "2026-10-28", "source": "quotes_tw"}
setup(traded=full)
C.confirm_recent_closure(tw, datetime(2026, 10, 29, 10, 0, tzinfo=TW))
check("suspected_closed_mismatch 寫入", (tw["2026"].get("suspected_closed_mismatch") or {}).get("date") == "2026-10-28",
      tw["2026"].get("suspected_closed_mismatch"))
check("有成交的日子不寫進 unscheduled_closed", "2026-10-28" not in tw["2026"]["unscheduled_closed"])

print("情境八：跨月——11/02（週一）上午，目標日＝10/30 之後的 11/01（週日）")
tw = copy.deepcopy(BASE)
setup(traded=set())
C.confirm_recent_closure(tw, datetime(2026, 11, 2, 9, 0, tzinfo=TW))
check("問 11 月", calls == [(2026, 11)], calls)
check("11/01 週日不寫入", "2026-11-01" not in tw["2026"]["unscheduled_closed"], tw["2026"]["unscheduled_closed"])

print("情境九：跨年——2027-01-01 上午，目標日落在 2026 年")
tw = copy.deepcopy(BASE)
tw["2027"] = {"published": True, "closed": ["2027-01-01"]}
setup(traded=weekdays(2026, 12, 31, skip={"2026-12-25"}))
C.confirm_recent_closure(tw, datetime(2027, 1, 1, 9, 0, tzinfo=TW))
check("寫進 2026 年度、不動 2027", tw["2026"]["daily_confirm_through"] == "2026-12-31"
      and "daily_confirm_through" not in tw["2027"], (tw["2026"].get("daily_confirm_through"), tw["2027"]))
check("12/25（不在 2026 休市表）沒成交 → 寫入", "2026-12-25" in tw["2026"]["unscheduled_closed"])

print(f"\n結果：{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
