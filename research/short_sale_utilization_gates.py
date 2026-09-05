"""`HYPOTHESIS_QUEUE.md`#36（個股融券使用率）GATE_SEQUENCE第3關補完腳本。

**存在的理由（誠實記錄，不是重造輪子）**：`short_sale_utilization_portfolio_
v1.py`（上一輪排程寫的，逐字比照`margin_utilization_regime_portfolio_v1.py`
架構）只做了第2關（隨機控制組，已PASS）+第4關成本1x/2x/3x（已算好，見該
檔案），還沒做第3關（參數密集高原）——依`HYPOTHESIS_QUEUE_PROTOCOL.md`
「GATE_SEQUENCE不得跳關」，這裡新增本腳本補上第3關，不修改
`short_sale_utilization_portfolio_v1.py`本體。

**方法論參考**：逐字比照`f52w_high_gates.py`（#17第3關）同一套精神——
TOP_N網格+REBALANCE_DAYS網格，兩個維度合併看「網格內報酬為正的點佔比是否
>=60%」，避免登錄門檻點是單點孤峰而非一整片高原。**只測TRAIN期**（開發期
探索，不動VAL），跟`f52w_high_gates.py`/`pair_trading_gates.py`同一個原則。

2026-09-05 hypothesis_queue排程接續，#36第3關以後。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2

from short_sale_utilization_portfolio_v1 import (
    REBALANCE_DAYS as ANCHOR_REBALANCE_DAYS,
    TOP_N as ANCHOR_TOP_N,
    make_signal_fn,
)

TRAIN_START = "2015-01-01"
TRAIN_END = holdout.TRAIN_END  # "2020-12-31"


def _run(signal_fn, data, market_df, start, end, top_n, rebalance_days):
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=top_n,
                          rebalance_every_n_days=rebalance_days, book_name="short_sale_utilization_gates")
    return run_backtest(signal_fn, data, market_df, cfg)


def gate3_parameter_plateau(data, market_df, liquidity) -> dict:
    print("\n" + "=" * 70)
    print("第3關：參數密集高原（TRAIN期，1x成本）")
    print("=" * 70)
    signal_fn = make_signal_fn(liquidity)

    rows = []
    top_n_grid = [10, 15, ANCHOR_TOP_N, 25, 30]
    print(f"  掃描一：TOP_N in {top_n_grid}（固定REBALANCE_DAYS={ANCHOR_REBALANCE_DAYS}）")
    for tn in top_n_grid:
        r = _run(signal_fn, data, market_df, TRAIN_START, TRAIN_END, tn, ANCHOR_REBALANCE_DAYS)
        rows.append({"dim": "top_n", "top_n": tn, "rebalance_days": ANCHOR_REBALANCE_DAYS,
                     "return_pct": r.total_return_pct, "n_trades": r.n_trades, "mdd_pct": r.max_drawdown_pct})
        print(f"    TOP_N={tn:>3d}  報酬={r.total_return_pct:+8.2f}%  n_trades={r.n_trades}  MDD={r.max_drawdown_pct:.2f}%")

    rebal_grid = [10, 21, 42, 63]
    print(f"  掃描二：REBALANCE_DAYS in {rebal_grid}（固定TOP_N={ANCHOR_TOP_N}）")
    for rd in rebal_grid:
        if rd == ANCHOR_REBALANCE_DAYS:
            continue  # 已在掃描一算過(TOP_N=20,REBALANCE_DAYS=21)這個錨點，不重算
        r = _run(signal_fn, data, market_df, TRAIN_START, TRAIN_END, ANCHOR_TOP_N, rd)
        rows.append({"dim": "rebalance_days", "top_n": ANCHOR_TOP_N, "rebalance_days": rd,
                     "return_pct": r.total_return_pct, "n_trades": r.n_trades, "mdd_pct": r.max_drawdown_pct})
        print(f"    REBALANCE_DAYS={rd:>3d}  報酬={r.total_return_pct:+8.2f}%  n_trades={r.n_trades}  MDD={r.max_drawdown_pct:.2f}%")

    grid_df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    grid_df.to_csv(out_dir / "short_sale_utilization_gate3_grid.csv", index=False)

    n_positive = int((grid_df["return_pct"] > 0).sum())
    frac_positive = n_positive / len(grid_df)
    anchor_row = grid_df[(grid_df["top_n"] == ANCHOR_TOP_N) & (grid_df["rebalance_days"] == ANCHOR_REBALANCE_DAYS)]
    anchor_return = float(anchor_row["return_pct"].iloc[0]) if len(anchor_row) else float("nan")
    print(f"\n  登錄門檻點(TOP_N={ANCHOR_TOP_N},REBALANCE_DAYS={ANCHOR_REBALANCE_DAYS})報酬={anchor_return:+.2f}%；"
          f"網格{len(grid_df)}點中報酬為正的有{n_positive}點({frac_positive*100:.0f}%)")
    gate3_pass = frac_positive >= 0.60
    print(f"  第3關判定（門檻：網格內>=60%的點報酬為正，不是只有登錄點單點孤峰）："
          f"{'PASS' if gate3_pass else 'FAIL'}")
    return {"pass": gate3_pass, "frac_positive": frac_positive, "anchor_return": anchor_return,
            "grid": grid_df.to_dict("records")}


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in short_sale_utilization_gates")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in short_sale_utilization_gates")

    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    gate3 = gate3_parameter_plateau(data, market_df, liquidity)

    if not gate3["pass"]:
        print("\n**第3關參數高原未過，快殺判定FAIL，不進第5/6關。**")
    else:
        print("\n第3關PASS，下一步：第5關leave-one-out、第6關逐年一致性、第7關樣本外"
              "（已在`short_sale_utilization_portfolio_v1.py`完成，VAL期percentile=100.0/"
              "alpha p=0.0354顯著但TRAIN期alpha不顯著）、第9關下檔保護。")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
