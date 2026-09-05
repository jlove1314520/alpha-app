# -*- coding: utf-8 -*-
"""`live_factors.py` 的單元測試（2026-09-05）。不連網路、不讀 repo 資料檔，純邏輯。

跑法：`python research/live_factors_test.py`
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_factors as lf  # noqa: E402


def _q(y, q, eps=None, rev=None, gm=None, om=None):
    return {"year": y, "quarter": q, "eps": eps, "revenue": rev, "gross_margin_pct": gm, "op_margin_pct": om}


def test_earnings_growth_uses_all_available_signals():
    quarters = [_q(2025, 2, eps=10.0, rev=1000.0, gm=50.0, om=40.0), _q(2026, 2, eps=12.0, rev=1200.0, gm=55.0, om=44.0)]
    val, comp = lf.earnings_growth(quarters)
    assert abs(comp["eps_yoy"] - 0.2) < 1e-9, comp
    assert abs(comp["revenue_yoy"] - 0.2) < 1e-9, comp
    assert abs(comp["gross_margin_yoy_pp"] - 5.0) < 1e-9, comp
    assert comp["n_signals"] == 4
    assert abs(val - (0.2 + 0.2 + 0.05 + 0.04) / 4) < 1e-9, val
    print("test_earnings_growth_uses_all_available_signals PASS")


def test_earnings_growth_partial_signals_still_scores():
    """只有營收（沒有 EPS）也要給值——這是覆蓋率從 589 檔拉到約 1900 檔的關鍵。"""
    quarters = [_q(2025, 1, rev=100.0), _q(2026, 1, rev=150.0)]
    val, comp = lf.earnings_growth(quarters)
    assert comp["eps_yoy"] is None and comp["n_signals"] == 1
    assert abs(val - 0.5) < 1e-9, val
    print("test_earnings_growth_partial_signals_still_scores PASS")


def test_earnings_growth_needs_year_over_year_pair():
    assert lf.earnings_growth([_q(2026, 2, eps=5.0)])[0] is None
    assert lf.earnings_growth(None)[0] is None
    assert lf.earnings_growth([])[0] is None
    print("test_earnings_growth_needs_year_over_year_pair PASS")


def test_yoy_hard_cap():
    quarters = [_q(2025, 1, rev=1.0), _q(2026, 1, rev=1000.0)]
    val, comp = lf.earnings_growth(quarters)
    assert comp["revenue_yoy"] == lf.YOY_HARD_CAP, comp
    print("test_yoy_hard_cap PASS")


def test_rsi_known_values():
    assert lf.rsi([1, 2, 3]) is None
    assert lf.rsi([100 + i for i in range(20)]) == 100.0
    assert lf.rsi([100 - i for i in range(20)]) == 0.0
    flat = lf.rsi([100] * 20)
    assert flat == 50.0, flat
    print("test_rsi_known_values PASS")


def test_technical_composite():
    rows = [{"close": 100 + i, "turnover": 1000} for i in range(70)]
    val, comp = lf.technical(rows)
    assert comp["ma_alignment"] == 1.0, comp          # 多頭排列
    assert comp["range_position_60d"] == 1.0, comp    # 站在區間最高
    assert comp["rsi14"] == 1.0, comp                 # RSI=100
    assert comp["volume_change"] == 0.0, comp         # 量能持平
    assert comp["n_signals"] == 4 and val is not None
    print("test_technical_composite PASS")


def test_technical_partial_history():
    """只有 20 天資料：MA60 那項算不出來，其他仍要算。"""
    rows = [{"close": 50 + i} for i in range(20)]
    val, comp = lf.technical(rows)
    assert comp["ma_alignment"] is not None and comp["rsi14"] is not None
    assert comp["volume_change"] is None
    assert val is not None
    assert lf.technical([{"close": 1}])[0] is None
    print("test_technical_partial_history PASS")


def test_gain_60d():
    rows = [{"close": 100} for _ in range(59)] + [{"close": 200}]
    assert abs(lf.gain_60d(rows) - 1.0) < 1e-9
    assert lf.gain_60d([{"close": 1}] * 10) is None
    print("test_gain_60d PASS")


def test_inst_behavior_streaks():
    hist = [{"date": f"2026090{i}", "foreign_lots": 100, "trust_lots": -50, "dealer_lots": 0} for i in range(1, 6)]
    val, comp = lf.inst_behavior({"history": hist})
    assert comp["foreign_streak_days"] == 5, comp
    assert comp["trust_streak_days"] == -5, comp
    assert comp["history_days"] == 5 and val is not None
    assert lf.inst_behavior(None)[0] is None
    assert lf.inst_behavior({"history": []})[0] is None
    print("test_inst_behavior_streaks PASS")


def test_inst_behavior_single_day():
    """history 只有 1 天也要給值（18763 檔有 institutional，不能因為天數少就全 NaN）。"""
    val, comp = lf.inst_behavior({"history": [{"date": "20260905", "foreign_lots": 500, "trust_lots": 10, "dealer_lots": 0}]})
    assert val is not None and comp["foreign_streak_days"] == 1
    print("test_inst_behavior_single_day PASS")


def test_event_score_freshness_decay():
    today = date(2026, 9, 5)
    fresh = lf.event_score([{"type": "mops_material", "date": "2026-09-05"}], as_of=today)[0]
    week_old = lf.event_score([{"type": "mops_material", "date": "2026-08-29"}], as_of=today)[0]
    assert abs(fresh - 1.0) < 1e-9, fresh
    assert abs(week_old - 0.5) < 1e-6, week_old          # 半衰期 7 天
    assert lf.event_score([{"type": "mops_material", "date": "2026-07-01"}], as_of=today)[0] is None  # >30天忽略
    assert lf.event_score(None)[0] is None and lf.event_score([])[0] is None
    val, comp = lf.event_score([{"type": "monthly_revenue", "date": "2026-09-05"},
                                {"type": "news", "date": "2026-09-05"}], as_of=today)
    assert abs(val - (0.6 + 0.3)) < 1e-9 and comp["n_events"] == 2, (val, comp)
    print("test_event_score_freshness_decay PASS")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"{t.__name__} FAIL: {e}")
        except Exception as e:  # noqa: BLE001
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"{t.__name__} ERROR: {type(e).__name__}: {e}")
    print()
    if failed:
        print(f"=== {len(failed)}/{len(tests)} 項測試FAIL ===")
        for n, m in failed:
            print(f"  - {n}: {m}")
        return 1
    print(f"=== 全部{len(tests)}項測試PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
