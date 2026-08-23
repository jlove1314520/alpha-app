"""TW marathon round: deep-dive validation for `f_quality_roe_stability`
(the ROE quarter-to-quarter stability factor), per MARATHON_PROTOCOL.md
section 1b. This candidate cleared the cheap IC gate
(factor_ic_value_quality.py, TRIALS_LEDGER.md #15) with a verified PIT
mechanism (same `quarterly_pit`+`balance_sheet_pit` machinery as the
already-PASSed f_eps_growth), so it is the next in line for full
validation, not f_value_pb (still PIT-unverified per TW_LEADS.md).

**What "full validation" means here, concretely**: the cheap gate only
checked cross-sectional Spearman IC vs a random-shuffle null. That answers
"does this factor rank stocks in a direction correlated with future
returns", not "is this a usable strategy net of real costs, and is any
apparent edge just market beta in disguise". This script answers the
second question by building an actual decile long-short portfolio (same
methodology as long_short_backtest.py's score.py-composite evaluation,
reused here for a single factor instead of the 4-factor composite):

  1. Train/validation split (holdout.py's TRAIN_END/VAL_END) -- reuses the
     SAME cached 100-name sample as the cheap gate (factor_ic.py's
     SAMPLE_SEED), no new FinMind calls.
  2. Matched random long-short control (same rebalance cadence, same
     decile sizes, random picks) -- NOT a static/buy&hold benchmark, per
     MARATHON_PROTOCOL.md 1b's explicit "配對式隨機控制組（不是靜態版）".
  3. Cost sensitivity at 1x/2x/3x the default slippage assumption
     (validation/costs.py's DEFAULT_SLIPPAGE_BPS=5bps -> 5/10/15bps),
     commission held at the conservative full published rate throughout.
  4. CAPM beta vs TAIEX (long_short_backtest.py's capm_beta()) -- audits
     whether the long-short spread is actually market-neutral, not
     assumed to be just because it's long-short by construction.

**What this script deliberately does NOT do** (disclosed, not hidden):
walk-forward re-estimation across multiple rolling windows. The factor
here has no fitted parameters (roe_stability is -rolling_std(roe, fixed
window), not something tuned on TRAIN data), so there is nothing to
"re-fit" fold-by-fold the way a parameterized strategy would need --
the TRAIN/VAL split already serves the out-of-sample purpose. If a
future deep-dive involves a factor/strategy with tunable parameters,
proper rolling-window WFA becomes necessary and should not be skipped.

Same 80-name sample as the cheap gate (out of 100 requested; ~20 dropped
for missing history, same as `factor_ic_value_quality.py`'s run) --
decile size at 10% is therefore small (k=8), disclosed as a real
small-sample limitation, not hidden behind a misleadingly precise number.
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

TARGET_FACTOR = "f_quality_roe_stability"
START_DATE = "2010-01-01"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # matches factor_ic.py's FORWARD_HORIZON snapshot cadence, for comparability
N_RANDOM_DRAWS = 20  # smaller than long_short_backtest.py's 40 -- this sample (80 names) is much
# smaller than a full-universe run, disclosed reduction not a hidden shortcut
RANDOM_CONTROL_SEED = 20260823
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
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)  # higher f_quality_roe_stability = more attractive -> long
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
    lsb.SLIPPAGE_BPS = slippage_bps  # module-global read at call time inside run_long_short/costmod calls
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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_f_quality_roe_stability")
    market_df = prepare_market_data(market_raw)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, same seed as cheap gate)...")
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

    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS  # restore module default before exit, in case anything
    # else in-process imports lsb after this script runs (defensive; this script normally runs standalone)

    print("\n=== SUMMARY ===")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_quality_roe_stability.csv", index=False)
    print("\nsaved data/deep_dive_f_quality_roe_stability.csv")
    return all_results


if __name__ == "__main__":
    main()
