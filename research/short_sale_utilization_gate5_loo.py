"""`HYPOTHESIS_QUEUE.md`#36（個股融券使用率）GATE_SEQUENCE第5關
leave-one-out——接續第3關（`short_sale_utilization_gates.py`，已PASS）。

**只測TRAIN期（開發期探索），不動VAL**——跟`f52w_high_gates.py`第5關/
`equal_weight_rebalance_leave_one_out_v1.py`（#29）/
`copper_gold_ratio_overlay_v1.py::gate5_leave_one_out()`（#34）同一個原則：
第2~6關屬於開發期探索，只有第7關才是正式樣本外判定，VAL期資料不可被這幾
關的探索過程碰到。

**判準逐字比照`copper_gold_ratio_overlay_v1.py::gate5_leave_one_out()`**：
把TRAIN期equity curve依日曆年切開，各自年度內複利連乘得到年度total_return，
再看拿掉貢獻最大的那一年後，剩餘複利連乘總報酬是否仍為正——原本為正、拿掉
最大貢獻年後翻負才判FAIL，避免像`copper_gold_ratio_overlay_v1`（#34）那樣
表面高原漂亮實則靠單一年份撐起全部效果。

**用1x成本單一真實訊號回測**——不是100次隨機控制組（那是第2關已經做過的
事），這關只需要一條真實訊號的equity curve做逐年拆解，直接複用
`short_sale_utilization_portfolio_v1.py::make_signal_fn()`跑一次TRAIN期。

**誠實提醒（沿用#36既有已知限制，不要在這裡藏起來）**：這仍是訊號多頭
鏡像半邊（融券使用率最低分位做多），不是完整放空高使用率那一腿的
leave-one-out——`backtest/engine.py`不支援放空，見
`short_sale_utilization_portfolio_v1.py`模組docstring已知限制段落。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續#36第3關以後。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import portfolio_backtest_v2 as pbv2
from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

from short_sale_utilization_portfolio_v1 import (
    REBALANCE_DAYS,
    TOP_N,
    make_signal_fn,
)

TRAIN_START = "2015-01-01"
TRAIN_END = holdout.TRAIN_END  # "2020-12-31"


def gate5_leave_one_out(equity_curve: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("第5關：leave-one-out（TRAIN期逐年拿掉最大貢獻年份）")
    print("=" * 70)
    ret = equity_curve.set_index("date")["equity"].pct_change().dropna()
    ret.index = pd.to_datetime(ret.index)
    years = sorted(ret.index.year.unique().tolist())
    yearly: dict[int, float] = {}
    for y in years:
        sub = ret[ret.index.year == y]
        if sub.empty:
            continue
        yearly[y] = float((1 + sub).prod() - 1)
    print(f"  逐年報酬：{ {y: f'{v*100:+.2f}%' for y, v in yearly.items()} }")

    if not yearly:
        return {"pass": False, "yearly": yearly, "compounded_total_pct": float("nan")}

    compounded_total = 1.0
    for v in yearly.values():
        compounded_total *= (1 + v)
    compounded_total_pct = (compounded_total - 1) * 100
    print(f"  逐年複利連乘總報酬={compounded_total_pct:+.2f}%")

    max_year = max(yearly, key=lambda y: yearly[y])
    loo_compounded = 1.0
    for y, v in yearly.items():
        if y == max_year:
            continue
        loo_compounded *= (1 + v)
    loo_total_pct = (loo_compounded - 1) * 100
    print(f"  貢獻最大年份={max_year}（{yearly[max_year]*100:+.2f}%）；"
          f"拿掉後剩餘複利總報酬={loo_total_pct:+.2f}%")

    gate5_pass = not (compounded_total_pct > 0 and loo_total_pct <= 0)
    print(f"  第5關判定（門檻：原本為正的話，拿掉最大貢獻年份後不能翻負）："
          f"{'PASS' if gate5_pass else 'FAIL'}")
    return {"pass": gate5_pass, "yearly": yearly, "compounded_total_pct": compounded_total_pct,
            "max_year": max_year, "loo_total_pct": loo_total_pct}


def gate6_yearly_consistency(yearly: dict[int, float]) -> dict:
    """逐字比照`copper_gold_ratio_overlay_v1.py::gate6_yearly_consistency()`
    判準：直接複用gate5已經算好的逐年報酬dict，不重新回測（免費延伸判斷，
    不是新的工作單位）——>=6個年度時要求>=5/6正，不足6年時退化為寬鬆檢查。"""
    print("\n" + "=" * 70)
    print("第6關：逐年一致性（TRAIN期各年度獨立判方向，門檻>=5/6正）")
    print("=" * 70)
    n_years = len(yearly)
    n_positive = sum(1 for v in yearly.values() if v > 0)
    gate6_pass = (n_positive >= 5) if n_years >= 6 else (n_positive >= max(1, n_years - 1))
    print(f"  {n_years}個年度中報酬為正的有{n_positive}個")
    print(f"  第6關判定（門檻：>=6個年度時要求>=5/6正；不足6年時退化為寬鬆檢查）："
          f"{'PASS' if gate6_pass else 'FAIL'}")
    return {"pass": gate6_pass, "n_positive": n_positive, "n_years": n_years, "yearly": yearly}


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in short_sale_utilization_gate5_loo")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date",
                                           context=f"data[{sid}] in short_sale_utilization_gate5_loo")

    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    signal_fn = make_signal_fn(liquidity)

    cfg = BacktestConfig(start_date=TRAIN_START, end_date=TRAIN_END, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="short_sale_utilization_gate5_loo")
    print(f"\n跑TRAIN期({TRAIN_START}..{TRAIN_END})單一真實訊號回測，1x成本...")
    result = run_backtest(signal_fn, data, market_df, cfg)
    holdout.assert_no_holdout_leakage(result.trades, date_col="date",
                                       context="short_sale_utilization_gate5_loo TRAIN")
    print(f"  TRAIN總報酬={result.total_return_pct:+.2f}%（應與`short_sale_utilization_"
          f"portfolio_v1.py`TRAIN的real.return_pct=+59.53%一致，交叉確認同一套"
          f"signal_fn/資料）")

    gate5 = gate5_leave_one_out(result.equity_curve)

    if not gate5["pass"]:
        print("\n**第5關leave-one-out未過，快殺判定FAIL，不進第6關以後。**")
        holdout_ok = holdout.is_holdout_consumed() is False
        print(f"\nholdout check (after): is_holdout_consumed() -> "
              f"{not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
        assert holdout_ok, "holdout must remain untouched (after)"
        return

    gate6 = gate6_yearly_consistency(gate5["yearly"])
    if not gate6["pass"]:
        print("\n**第6關逐年一致性未過，快殺判定FAIL，不進第7關以後。**")
    else:
        print("\n**第5/6關皆PASS**，下一步：第7關樣本外（已在`short_sale_"
              "utilization_portfolio_v1.py`完成，VAL期percentile=100.0/"
              "alpha p=0.0354顯著，但TRAIN期alpha本身不顯著p=0.3717仍待留意）、"
              "第9關下檔保護。")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> "
          f"{not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
