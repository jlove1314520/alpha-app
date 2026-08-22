"""AI 選股引擎 Phase A 步驟 3 (part 2) -- 對 score.py 的綜合分「前N名」跑一次
真實的扣成本+換手組合回測。IC 高不代表扣成本後還賺錢；這支腳本就是誠實檢驗這件事的地方。

Reuses backtest/engine.py's run_backtest() wholesale (not a new engine) --
that function already implements exactly the mechanism a top-N portfolio
needs: weekly re-evaluation, T+1 execution, cost-aware fills, only trading
names that actually enter/exit the top N (not full weekly rebalancing of
unchanged holdings). This script only supplies a signal_fn that scores each
rebalance day via score.py and returns the top N.

Random control group: same mechanism (score.compute_scores_at_date's
eligible pool, same rebalance cadence, same position count, same cost
model), but the signal_fn picks N random eligible names instead of ranking
by composite score -- the composite-score-specific analog of Cowork's
"same actions, only randomize which stock fills each slot" methodology
already used for weinstein_stage2_unbiased (validation/control_group.py).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import compute_scores_at_date, eligible_for_ranking, load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 10  # matches BacktestConfig's existing max_positions default/precedent used elsewhere in this repo
N_RANDOM_DRAWS = 60  # reduced from the Weinstein precedent's 200 for tractability -- each draw here re-runs a
# full multi-year weekly-rebalance backtest (not a single cheap percentile-of-final-value draw like
# control_group.py's static version), so 200 draws was computationally impractical. 60 still gives a usable
# percentile estimate; disclosed honestly as a smaller random-control budget than the Weinstein precedent.
RANDOM_CONTROL_SEED = 20260823

_eligible_pool_cache: dict[str, list[str]] = {}  # as_of -> eligible stock_ids, shared across all random draws
# for a given date (the eligible pool doesn't depend on the random seed) -- avoids recomputing the full
# cross-sectional composite-score table (industry z-scores etc.) from scratch on every one of the 60 draws
# at every rebalance date, which was the actual bottleneck (an earlier 200-draw attempt was killed for being
# too slow: recomputing scores 200x per rebalance date, not once).


def _eligible_pool(as_of: str, price_data: dict[str, pd.DataFrame], industry_map: dict[str, str]) -> list[str]:
    if as_of not in _eligible_pool_cache:
        cs = eligible_for_ranking(compute_scores_at_date(as_of, price_data, industry_map))
        _eligible_pool_cache[as_of] = cs["stock_id"].tolist()
    return _eligible_pool_cache[as_of]


def make_score_signal_fn(industry_map: dict[str, str], top_n: int = TOP_N):
    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        cs = eligible_for_ranking(compute_scores_at_date(as_of, price_data, industry_map))
        top = cs.head(top_n)
        return dict(zip(top["stock_id"], top["composite"]))
    return signal_fn


def make_random_signal_fn(industry_map: dict[str, str], top_n: int, seed: int):
    rng = random.Random(seed)

    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        pool = _eligible_pool(as_of, price_data, industry_map)
        picks = pool if len(pool) <= top_n else rng.sample(pool, top_n)
        return {sid: 1.0 for sid in picks}  # score value unused for random draws, just needs to exist
    return signal_fn


def _buy_and_hold_pct(data: dict[str, pd.DataFrame], start_date: str, end_date: str) -> float:
    """Equal-weight buy-once-and-hold of every sample name, no rebalancing,
    no costs (the conventional passive benchmark already used for the
    other LEADS.md entries in this repo)."""
    rets = []
    for sid, d in data.items():
        row_s = d[d["date"] >= start_date]
        row_e = d[d["date"] <= end_date]
        if row_s.empty or row_e.empty:
            continue
        p0, p1 = row_s.iloc[0]["adj_close"], row_e.iloc[-1]["adj_close"]
        if p0 and p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
            rets.append(p1 / p0 - 1)
    return float(np.mean(rets) * 100) if rets else float("nan")


def run_period(label: str, data: dict, market_df: pd.DataFrame, industry_map: dict, start: str, end: str):
    print(f"\n=== {label}: {start}..{end} ===")

    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N, book_name="score_topn_v1")
    result = run_backtest(make_score_signal_fn(industry_map, TOP_N), data, market_df, cfg)
    print(f"  Score top-{TOP_N}: return={result.total_return_pct:+.2f}%  MDD={result.max_drawdown_pct:.2f}%  "
          f"Sortino={result.sortino_ratio:.3f}  trades={result.n_trades}")

    bh = _buy_and_hold_pct(data, start, end)
    print(f"  Buy&hold (equal-weight, no rebal, no cost): {bh:+.2f}%")

    cost_results = {}
    for mult in (1, 2, 3):
        c = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                            book_name="score_topn_v1", cost_multiplier=mult)
        r = run_backtest(make_score_signal_fn(industry_map, TOP_N), data, market_df, c)
        cost_results[mult] = r.total_return_pct
        print(f"  Cost {mult}x: {r.total_return_pct:+.2f}%")

    print(f"  Random control ({N_RANDOM_DRAWS} draws, same rebalance cadence/position count/cost)...")
    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N, book_name="score_topn_random_control")
        rfn = make_random_signal_fn(industry_map, TOP_N, seed=RANDOM_CONTROL_SEED + i)
        rr = run_backtest(rfn, data, market_df, rcfg)
        random_finals.append(rr.final_equity)
    real_final = result.final_equity
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    print(f"  Real final equity {real_final:,.0f} vs random control median {np.median(random_finals):,.0f} "
          f"-- percentile {percentile:.1f}")

    return {
        "label": label, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "n_trades": result.n_trades,
        "buy_and_hold_pct": bh, "cost_1x": cost_results[1], "cost_2x": cost_results[2], "cost_3x": cost_results[3],
        "random_control_percentile": percentile,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_score_backtest")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    industry_map = load_industry_map()
    print(f"  industry_map: {len(industry_map)} entries")

    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in run_score_backtest")

    train_result = run_period("TRAIN", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END)
    val_result = run_period("VALIDATION", data, market_df, industry_map, "2021-01-01", holdout.VAL_END)

    print("\n=== SUMMARY ===")
    for r in (train_result, val_result):
        print(f"  {r['label']}: score={r['return_pct']:+.2f}% vs buy&hold={r['buy_and_hold_pct']:+.2f}%  "
              f"MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  trades={r['n_trades']}  "
              f"cost1x/2x/3x={r['cost_1x']:+.2f}%/{r['cost_2x']:+.2f}%/{r['cost_3x']:+.2f}%  "
              f"random_control_pct={r['random_control_percentile']:.1f}")

    pd.DataFrame([train_result, val_result]).to_csv("data/score_backtest_results.csv", index=False)
    print("saved data/score_backtest_results.csv")
    return train_result, val_result


if __name__ == "__main__":
    main()
