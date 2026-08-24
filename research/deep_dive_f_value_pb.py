"""TW marathon round: deep-dive validation for `f_value_pb` (negative-PBR
value factor), per MARATHON_PROTOCOL.md section 1b.

Why this candidate, why now: `f_value_pb` cleared the cheap IC gate
(factor_ic_value_quality.py, TRIALS_LEDGER.md #13) and its PIT precondition
was spot-checked in marathon round 4 (`verify_pit_value_pb.py`, single-stock
2330 jump-detection, see `factors.py` lines ~39-55 and `TW_LEADS.md` #1) --
"no severe lookahead bias found on a spot check", NOT "fully verified". Any
result below inherits that same single-stock-limited PIT caveat; it is
repeated in the SUMMARY output on purpose so it can't be silently dropped
by a future reader who only skims the numbers.

This round hit the FinMind rate-limit wall immediately on `backfill_universe.py`
(15/15 consecutive rate limits, see TW_LOG.md this round's entry) so this
script deliberately makes ZERO new FinMind calls: it reuses the exact same
100-name cached sample (factor_ic.py's SAMPLE_SEED=20260822/SAMPLE_SIZE=100)
that the f_value_pb cheap gate already pulled and cached to data/raw/, via
the same `load_sample_with_factors` used by the f_quality_roe_stability
deep-dive. Any name not already cached is silently dropped by that loader
(same behavior as the round-2 f_quality_roe_stability deep dive), not
re-fetched.

Method mirrors `deep_dive_f_quality_roe_stability.py` (copied methodology,
not copied file, per TW_LEADS.md's next-step note): decile long-short
(k = round(n*10%)), TRAIN/VAL split, matched random long-short control
(N_RANDOM_DRAWS draws, not a static benchmark), cost sensitivity at
1x/2x/3x DEFAULT_SLIPPAGE_BPS, CAPM beta vs TAIEX. No walk-forward here for
the same reason as the ROE deep-dive: f_value_pb has no fitted parameters
(it's -PBR, not something tuned on TRAIN data), so TRAIN/VAL split already
serves the out-of-sample purpose.
"""
from __future__ import annotations

import random
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TARGET_FACTOR = "f_value_pb"
START_DATE = "2010-01-01"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # same cadence as factor_ic.py's forward-return horizon and the ROE deep-dive, for comparability
N_RANDOM_DRAWS = 100  # matches the ROE deep-dive's round-3 resolution (not the original round-2 20), since we
# already know from that round's experience that 20 draws gives only 5% percentile steps -- start at the resolution
# that was needed there rather than re-discovering the same limitation from scratch.
RANDOM_CONTROL_SEED = 20260823  # same seed as the ROE deep-dive; different factor/leg-selection means the
# actual random legs picked will differ even with the same seed (rng.sample() draws depend on which ids/dates
# have non-NaN f_value_pb, not just the seed), so this is not a leakage concern -- it's just seed reuse for
# auditability (same seed value = same "this round's canonical random-control seed", not shared randomness).
COST_MULTIPLIERS = [1, 2, 3]  # x DEFAULT_SLIPPAGE_BPS, per CONSTITUTION.md's cost-sensitivity requirement

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": ("2021-01-01", holdout.VAL_END),
}


def _factor_cross_section(as_of: str, data: dict[str, pd.DataFrame], factor_col: str) -> tuple[list[str], list[float]]:
    ids, vals = [], []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        fv = d.loc[idx[0], factor_col]
        if pd.isna(fv):
            continue
        ids.append(sid)
        vals.append(float(fv))
    return ids, vals


def _decile_legs_factor(as_of: str, data: dict, industry_map, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, vals = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    # f_value_pb = -PBR, so HIGHER f_value_pb = cheaper (lower PBR) = long leg, same convention as the ROE factor.
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)
    k = max(1, round(n * DECILE_FRACTION))
    longs = [sid for sid, _ in order[:k]]
    shorts = [sid for sid, _ in order[-k:]]
    return longs, shorts


def _random_legs_factor(as_of: str, data: dict, industry_map, rng: random.Random, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, _ = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    k = max(1, round(n * DECILE_FRACTION))
    if n < 2 * k:
        return [], []
    picks = rng.sample(ids, 2 * k)
    return picks[:k], picks[k:]


def run_one(data, market_df, start, end, slippage_bps):
    lsb.SLIPPAGE_BPS = slippage_bps
    leg_fn = partial(_decile_legs_factor, factor_col=TARGET_FACTOR)
    result = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=leg_fn)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = partial(_random_legs_factor, rng=rng, factor_col=TARGET_FACTOR)
        rr = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=rand_leg_fn)
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100,
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_f_value_pb")
    market_df = prepare_market_data(market_raw)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, same seed as cheap gate, ZERO new FinMind calls expected)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    n_with_factor = sum(1 for d in data.values() if d[TARGET_FACTOR].notna().any())
    print(f"  {n_with_factor}/{len(data)} names have at least one non-NaN {TARGET_FACTOR} value")

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = lsb.costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS

    print("\n=== SUMMARY ===")
    print("CAVEAT (repeat on purpose, do not drop): PIT status for f_value_pb is 'single-stock (2330) spot check, "
          "no severe lookahead bias found', NOT 'fully verified'. Below numbers inherit that limitation.")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_value_pb.csv", index=False)
    print("\nsaved data/deep_dive_f_value_pb.csv")
    return all_results


if __name__ == "__main__":
    main()
