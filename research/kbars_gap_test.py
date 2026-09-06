# -*- coding: utf-8 -*-
"""實測.二.補 的單元測試：缺口偵測、合併規則、kbars 呼叫預算。

這些是純函式，不需要 Shioaji 連線也不需要開盤，所以可以隨時跑：
    python research/kbars_gap_test.py

盤中那段（09:15 才啟動、09:20 加冷門股，首根仍須是 09:00～09:01）沒辦法在這裡測，
要等交易時段用 Playwright 跑 `research/kbars_open_check.py`，見該檔說明。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alpha_live_server as srv  # noqa: E402
import shioaji_quotes as sq      # noqa: E402


def _bars(*hhmm: str, day: str = "2026-09-07") -> list[dict]:
    return [{"t": f"{day}T{t}", "c": 100.0 + i} for i, t in enumerate(hhmm)]


def test_needs_backfill_late_start():
    """09:15 才開始聚合 → 要補。"""
    assert srv._needs_kbars_backfill(_bars("09:15", "09:16", "09:17")) is not None
    reason = srv._needs_kbars_backfill(_bars("09:15", "09:16"))
    assert "09:15" in reason and "09:01" in reason, reason
    print("test_needs_backfill_late_start PASS")


def test_no_backfill_when_from_open():
    """09:00 或 09:01 開始且連續 → 不用補。"""
    assert srv._needs_kbars_backfill(_bars("09:00", "09:01", "09:02")) is None
    assert srv._needs_kbars_backfill(_bars("09:01", "09:02", "09:03")) is None
    print("test_no_backfill_when_from_open PASS")


def test_gap_detection_threshold():
    """缺口 3 分鐘以內算正常（冷門股沒成交就是沒有 K），超過 3 分鐘才補。"""
    assert srv._needs_kbars_backfill(_bars("09:01", "09:04")) is None       # 差 3 分，不補
    r = srv._needs_kbars_backfill(_bars("09:01", "09:05"))                  # 差 4 分，要補
    assert r is not None and "缺口" in r, r
    print("test_gap_detection_threshold PASS")


def test_merge_prefers_tick():
    """同一分鐘 tick 聚合優先；查詢只填沒有的分鐘。"""
    agg = [{"t": "2026-09-07T09:20", "c": 55.5, "v": 10}]
    queried = [{"ts": "2026-09-07T09:00:00+08:00", "close": 50.0, "volume": 1},
               {"ts": "2026-09-07T09:20:00+08:00", "close": 99.9, "volume": 2}]
    out = srv._merge_bars(agg, queried)
    assert [b["t"] for b in out] == ["2026-09-07T09:00", "2026-09-07T09:20"], out
    got = {b["t"]: b for b in out}
    assert got["2026-09-07T09:00"]["c"] == 50.0 and got["2026-09-07T09:00"]["src"] == "api.kbars"
    # 這一條是重點：同一分鐘不可以被查詢結果覆蓋掉
    assert got["2026-09-07T09:20"]["c"] == 55.5 and got["2026-09-07T09:20"]["src"] == "tick"
    print("test_merge_prefers_tick PASS")


def test_merge_result_is_sorted():
    out = srv._merge_bars(
        [{"t": "2026-09-07T10:00", "c": 1}],
        [{"ts": "2026-09-07T09:30:00+08:00", "close": 2},
         {"ts": "2026-09-07T09:05:00+08:00", "close": 3}])
    assert [b["t"][11:] for b in out] == ["09:05", "09:30", "10:00"], out
    print("test_merge_result_is_sorted PASS")


def test_kbars_daily_budget():
    """每日額度用完就拒絕。官方盤中上限 270，我們自訂 240 留餘裕。"""
    sq._kbars_budget["day"] = None
    sq._kbars_budget["count"] = 0
    sq._kbars_budget["window"] = []
    assert sq.KBARS_DAILY_BUDGET <= 270, "自訂額度不可以超過官方盤中上限 270"
    assert sq.KBARS_RATE_MAX <= 50, "10 秒額度不可以超過官方上限 50"
    # 直接把計數推到上限，驗證會被擋
    ok, _ = sq._kbars_budget_take()
    assert ok
    sq._kbars_budget["count"] = sq.KBARS_DAILY_BUDGET
    ok, why = sq._kbars_budget_take()
    assert not ok and "上限" in why, why
    print("test_kbars_daily_budget PASS")


def test_kbars_rate_limit():
    """10 秒視窗額度用完也要擋（官方超過會暫停服務一分鐘、反覆違規停權）。"""
    import time
    sq._kbars_budget["day"] = None
    sq._kbars_budget["count"] = 0
    sq._kbars_budget["window"] = []
    now = time.time()
    sq._kbars_budget_take()  # 初始化當日
    sq._kbars_budget["window"] = [now] * sq.KBARS_RATE_MAX
    ok, why = sq._kbars_budget_take()
    assert not ok and "10 秒" in why, why
    # 視窗過期後要放行
    sq._kbars_budget["window"] = [now - sq.KBARS_RATE_WINDOW_SEC - 1] * sq.KBARS_RATE_MAX
    ok, _ = sq._kbars_budget_take()
    assert ok
    print("test_kbars_rate_limit PASS")


if __name__ == "__main__":
    fails = 0
    for fn in (test_needs_backfill_late_start, test_no_backfill_when_from_open,
               test_gap_detection_threshold, test_merge_prefers_tick,
               test_merge_result_is_sorted, test_kbars_daily_budget,
               test_kbars_rate_limit):
        try:
            fn()
        except AssertionError as e:
            fails += 1
            print(f"{fn.__name__} FAIL: {e}")
    print(f"\n{'全部通過' if not fails else str(fails) + ' 項 FAIL'}")
    sys.exit(1 if fails else 0)
