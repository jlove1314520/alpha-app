"""Runner: Weinstein Stage 2 v2（`HYPOTHESIS_QUEUE.md`#1），無偏宇宙 +
配對式控制組——跟`run_weinstein_unbiased.py`（v1）完全同一套方法論/
基礎設施（同樣的隨機無偏宇宙抽樣、同樣的matched control group），**唯一
差異是訊號函式換成`stage2_signal_v2`**（多一個`f_rel_strength>0`gate，
排名依據改用相對強度而非絕對動能，見`strategies/weinstein_stage2_v2.py`
docstring完整說明）。

刻意複製這支腳本而不是直接改v1（`run_weinstein_unbiased.py`）或加參數
切換——v1被`TRIALS_LEDGER.md`#10/#11引用，改了會讓舊結果的可重現性
出問題。

Run with: `python -m strategies.run_weinstein_unbiased_v2` from research/.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from finmind_client import load_dev
from universe import universe as build_universe
from validation import holdout
from validation.control_group import extract_trade_schedule, run_matched_control_group
from backtest.engine import BacktestConfig, run_backtest, buy_leg_rate, sell_leg_rate
from strategies.weinstein_stage2 import prepare_price_data, prepare_market_data
from strategies.weinstein_stage2_v2 import stage2_signal_v2

SAMPLE_SEED = 20260822  # 跟v1同一個seed，方便v1/v2用同一批股票池直接比較差異
SAMPLE_SIZE = 100
START_DATE = "2010-01-01"


def load_sample_price_data(stock_ids: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for i, sid in enumerate(stock_ids):
        try:
            df = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(stock_ids)}] {sid}: ERROR ({e}), dropping")
            continue
        if df.empty or len(df) < 200:
            print(f"  [{i+1}/{len(stock_ids)}] {sid}: only {len(df)} rows, dropping")
            continue
        out[sid] = df
    return out


def summarize(label: str, result) -> dict:
    n = result.n_trades
    print(f"\n--- {label} ---")
    print(f"  period: {result.config.start_date} .. {result.config.end_date}")
    print(f"  trades: {n}{'  ** <100, UNRELIABLE per CONSTITUTION.md **' if n < 100 else ''}")
    print(f"  final equity: {result.final_equity:,.0f} ({result.total_return_pct:+.2f}%)")
    print(f"  max drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"  Sortino: {result.sortino_ratio:.3f}")
    return {
        "label": label, "n_trades": n, "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct, "sortino": result.sortino_ratio,
    }


def buy_and_hold_return(market_df: pd.DataFrame, start: str, end: str) -> float:
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    if window.empty:
        return float("nan")
    return (window["close"].iloc[-1] / window["close"].iloc[0] - 1) * 100


def main():
    print(f"Sampling {SAMPLE_SIZE} names (seed={SAMPLE_SEED}) from universe.py's full post-2003 universe...")
    u = build_universe()
    rng = random.Random(SAMPLE_SEED)
    sample_ids = rng.sample(list(u["stock_id"]), SAMPLE_SIZE)
    print(f"  universe.py total: {len(u)} ({(u.status=='delisted').sum()} delisted since 2003)")

    print("Loading sampled price data (cached after first run, shared with v1 -- same SAMPLE_SEED/SIZE)...")
    raw_price_data = load_sample_price_data(sample_ids)
    print(f"  {len(raw_price_data)}/{SAMPLE_SIZE} usable names loaded")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_weinstein_unbiased_v2")

    price_data = prepare_price_data(raw_price_data)
    market_df = prepare_market_data(market_raw)

    results = {}

    val_start = "2021-01-01"
    val_cfg = BacktestConfig(start_date=val_start, end_date=holdout.VAL_END)
    val_result = run_backtest(stage2_signal_v2, price_data, market_df, val_cfg)
    results["validation"] = summarize("VALIDATION (%s..%s)" % (val_start, holdout.VAL_END), val_result)
    bh_val = buy_and_hold_return(market_df, val_start, holdout.VAL_END)
    print(f"  TAIEX buy&hold: {bh_val:+.2f}%  beats it: {val_result.total_return_pct > bh_val}")
    results["validation"]["bh_return_pct"] = bh_val
    results["validation"]["beats_bh"] = val_result.total_return_pct > bh_val

    train_cfg = BacktestConfig(start_date="2015-01-01", end_date=holdout.TRAIN_END)
    train_result = run_backtest(stage2_signal_v2, price_data, market_df, train_cfg)
    results["train"] = summarize("TRAIN (2015-01-01..%s)" % holdout.TRAIN_END, train_result)
    bh_train = buy_and_hold_return(market_df, train_cfg.start_date, train_cfg.end_date)
    print(f"  TAIEX buy&hold: {bh_train:+.2f}%  beats it: {train_result.total_return_pct > bh_train}")
    results["train"]["bh_return_pct"] = bh_train
    results["train"]["beats_bh"] = train_result.total_return_pct > bh_train

    print("\n--- Cost sensitivity (validation period) ---")
    for mult in (1, 2, 3):
        cfg = BacktestConfig(start_date=val_start, end_date=holdout.VAL_END, cost_multiplier=mult)
        r = run_backtest(stage2_signal_v2, price_data, market_df, cfg)
        print(f"  {mult}x costs: return={r.total_return_pct:+.2f}%  trades={r.n_trades}  maxDD={r.max_drawdown_pct:.2f}%")
        results[f"cost_{mult}x"] = {"return_pct": r.total_return_pct, "n_trades": r.n_trades}

    print("\n--- Matched random control group (validation period) ---")
    schedule = extract_trade_schedule(val_result.trades)
    print(f"  trade schedule extracted: {len(schedule)} round trips (same entry/exit dates reused in every random draw)")
    cost_rates = {"buy": buy_leg_rate(val_cfg), "sell": sell_leg_rate(val_cfg)}
    cg = run_matched_control_group(
        trade_schedule=schedule,
        price_data=price_data,
        strategy_final_equity=val_result.final_equity,
        initial_capital=val_cfg.initial_capital,
        slot_allocation=val_cfg.initial_capital / val_cfg.max_positions,
        cost_rates=cost_rates,
        n_random=200,
    )
    print(f"  strategy final equity: {cg.candidate_metric:,.0f}")
    print(f"  matched random control (n=200, same {len(schedule)} entry/exit dates, random stock per slot):")
    print(f"    median: {np.median(cg.random_metrics):,.0f}  percentile of strategy: {cg.percentile:.1f}")
    print(f"    beats_random_at: {cg.beats_random_at}")
    results["control_group_percentile"] = cg.percentile

    val_result.trades.to_csv("data/backtests/weinstein_stage2_v2_unbiased_validation_trades.csv", index=False)
    val_result.equity_curve.to_csv("data/backtests/weinstein_stage2_v2_unbiased_validation_equity.csv", index=False)
    train_result.trades.to_csv("data/backtests/weinstein_stage2_v2_unbiased_train_trades.csv", index=False)
    train_result.equity_curve.to_csv("data/backtests/weinstein_stage2_v2_unbiased_train_equity.csv", index=False)

    return results, train_result, val_result, cg


if __name__ == "__main__":
    main()
