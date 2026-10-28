# -*- coding: utf-8 -*-
"""先.一四一-2 自測：合成 git log 時間（OK／LATE／MISSING／休市日不算／週一 09:00 閘門／本週已跑過）。零外部請求、不讀 git。"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_tw_close_landing_check as W  # noqa: E402

TW = timezone(timedelta(hours=8))
FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=TW)


def main() -> int:
    closed = {"2026-10-23"}
    days = W.week_trading_days(date(2026, 10, 19), closed)
    check("休市日 10/23 不算交易日", days == ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"], str(days))
    a = [(t("2026-10-19T17:40"), "2026-10-19"), (t("2026-10-21T01:10"), "2026-10-20"), (t("2026-10-21T17:40"), "2026-10-21")]
    b = [(t("2026-10-19T17:41"), "2026-10-19"), (t("2026-10-20T17:41"), "2026-10-20"), (t("2026-10-21T23:59"), "2026-10-21")]
    rows = {r["date"]: r for r in W.evaluate(days, {"a": a, "b": b})}
    check("10/19 兩檔當晚落地 → OK", rows["2026-10-19"]["status"] == "OK")
    check("10/20 一檔隔天 01:10 才落地 → LATE（取較差）", rows["2026-10-20"]["status"] == "LATE" and rows["2026-10-20"]["files"]["b"]["status"] == "OK")
    check("10/21 23:59 落地 → OK", rows["2026-10-21"]["status"] == "OK")
    check("10/22 至今沒落地 → MISSING", rows["2026-10-22"]["status"] == "MISSING")
    jump = [(t("2026-10-21T17:40"), "2026-10-21")]
    check("日期欄一次跳過 10/20 → 10/20 以跳過那版的時間算（LATE）",
          W.classify("2026-10-20", W.first_landing("2026-10-20", jump)) == "LATE")
    check("UTC 時間換算台北：10-19T15:59Z＝台北 23:59 → OK",
          W.classify("2026-10-19", datetime(2026, 10, 19, 15, 59, tzinfo=timezone.utc)) == "OK")
    check("UTC 16:01Z＝台北隔天 00:01 → LATE",
          W.classify("2026-10-19", datetime(2026, 10, 19, 16, 1, tzinfo=timezone.utc)) == "LATE")
    check("last_monday：週四 10/29 → 10/19", W.last_monday(t("2026-10-29T04:50")) == date(2026, 10, 19))
    check("last_monday：週一 11/02 → 10/26", W.last_monday(t("2026-11-02T09:05")) == date(2026, 10, 26))
    # 閘門（不碰檔案：只走到 return 之前的分支）
    orig_state = W.STATE
    W.STATE = Path(__file__).resolve().parent / "__no_such_state__.json"
    try:
        check("週四不跑", W.run(t("2026-10-29T10:00"))["decision"] == "not_monday_morning")
        check("週一 08:59 不跑", W.run(t("2026-11-02T08:59"))["decision"] == "not_monday_morning")
        tmp = Path(__file__).resolve().parent / "__selftest_weekly_state__.json"
        tmp.write_text('{"last_week": "2026-W45"}', encoding="utf-8")
        W.STATE = tmp
        check("週一 09:05 本週已跑過 → already_ran", W.run(t("2026-11-02T09:05"))["decision"] == "already_ran")
        tmp.unlink()
    finally:
        W.STATE = orig_state
    print(f"\n合計 {'全部通過' if not FAIL else f'{len(FAIL)} 項失敗：' + '、'.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
