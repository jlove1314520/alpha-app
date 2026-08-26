"""TW marathon round: decompose why `f_quality_roe_stability`'s decile
long-short TRAIN period (2015-2020) has a *negative* net-of-cost absolute
return while VAL (2021-2024) is positive, even though the factor's
cross-sectional IC is same-sign and positive in both periods (per
`factor_ic_value_quality.py`, TRIALS_LEDGER.md #15) and the deep-dive
(`deep_dive_f_quality_roe_stability.py`, TRIALS_LEDGER.md #16/#17) beats
the matched random control in all 6 TRAIN/VAL x 1x/2x/3x-cost configs.

TW_LEADS.md #3's open question, restated: is the TRAIN-period negative
absolute return caused by (a) turnover-cost drag from the 20-day rebalance
cadence on a small (k=8, 80-name sample) decile construction, or (b) the
factor itself pointing the wrong direction during 2015-2020 specifically?
The deep-dive already noted a supporting clue: the TRAIN-period *matched
random control* itself loses heavily too (median final equity far below
1.0), which is consistent with (a) -- if turnover cost alone is enough to
sink even a random long-short book in this period, that's not something a
better factor could fix.

This script tests hypothesis (a) directly and minimally: rerun the exact
same decile long-short construction as the deep-dive (same 80-name cached
sample, same seed, same cost model, same random-control methodology) but
with REBALANCE_DAYS raised from 20 to 60 (matches TW_LEADS.md #3's "拉長
換倉週期（例如60日）" suggestion). Lower rebalance frequency directly cuts
turnover-driven cost drag without touching the factor definition itself.
If the TRAIN-period sign flips positive under 60-day rebalance while VAL
stays positive, that supports (a) (drag was the dominant driver, not a
factor-direction problem). If TRAIN stays negative even at 60-day, that
weakens (a) and leaves (b) (or some other unexplained mechanism) as the
more likely explanation -- this script does NOT assume the answer in
advance; it reports whichever result comes out.

Deliberately NOT tested here (disclosed, not hidden): decile fraction
narrowing (TW_LEADS.md #3's other suggestion, "縮小十分位比例"). Doing
both changes in one script would confound which change (if either) drove
any observed effect. If 60-day rebalance alone does not resolve the sign
flip, decile-fraction narrowing is the natural next bounded work unit,
not folded in here.

Zero new FinMind API calls: reuses the exact same on-disk cache as
`deep_dive_f_quality_roe_stability.py` (same SAMPLE_SEED, same
load_sample_with_factors()).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

# Reuse the deep-dive's leg-selection + run_one machinery verbatim (import,
# not copy-paste) so this script cannot silently drift from the already-
# reviewed methodology (same decile construction, same matched random
# control, same cost multipliers, same CAPM beta calc).
import deep_dive_f_quality_roe_stability as dd

TARGET_FACTOR = dd.TARGET_FACTOR
START_DATE = dd.START_DATE
COST_MULTIPLIERS = dd.COST_MULTIPLIERS
PERIODS = dd.PERIODS

REBALANCE_DAYS_VARIANTS = {
    "20d (deep-dive baseline, for side-by-side comparison)": 20,
    "60d (turnover-drag test)": 60,
}


def run_variant(rebalance_days: int, data, market_df):
    """Same as dd.run_one() but with a caller-supplied REBALANCE_DAYS,
    monkey-patched onto dd's leg functions via a fresh partial each call
    so the two variants in this script don't interfere with each other."""
    import random
    from functools import partial

    results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = lsb.costmod.DEFAULT_SLIPPAGE_BPS * mult
            lsb.SLIPPAGE_BPS = slip
            leg_fn = partial(dd._decile_legs_factor, factor_col=TARGET_FACTOR)
            result = lsb.run_long_short(data, market_df, None, start, end, rebalance_days, leg_fn=leg_fn)
            ann_ret = lsb.annualized_return(result)
            sortino = lsb.sortino_ratio(result)
            beta, alpha_ann = lsb.capm_beta(result, market_df)
            total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

            random_finals = []
            for i in range(dd.N_RANDOM_DRAWS):
                rng = random.Random(dd.RANDOM_CONTROL_SEED + i)
                rand_leg_fn = partial(dd._random_legs_factor, rng=rng, factor_col=TARGET_FACTOR)
                rr = lsb.run_long_short(data, market_df, None, start, end, rebalance_days, leg_fn=rand_leg_fn)
                random_finals.append(rr["equity"].iloc[-1])
            real_final = result["equity"].iloc[-1]
            percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

            results.append({
                "rebalance_days": rebalance_days,
                "period": period_label,
                "cost_multiplier": mult,
                "total_return_pct": total_ret_pct,
                "annualized_return_pct": ann_ret * 100,
                "sortino": sortino,
                "beta": beta,
                "annualized_alpha_pct": alpha_ann * 100,
                "random_control_median_final_equity": float(np.median(random_finals)),
                "random_control_percentile": percentile,
                "n_dates": len(result),
            })
            print(f"  [{rebalance_days}d] {period_label} {mult}x: ann_return={ann_ret*100:+.2f}%  "
                  f"beta={beta:+.3f}  alpha={alpha_ann*100:+.2f}%  Sortino={sortino:.3f}  "
                  f"random_control_median_final_equity={np.median(random_finals):.4f}  "
                  f"real_percentile={percentile:.1f}")
    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS
    return results


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in decompose_f_quality_roe_stability_rebalance")
    market_df = prepare_market_data(market_raw)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, same seed as cheap gate)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names\n")

    all_results = []
    for label, rebalance_days in REBALANCE_DAYS_VARIANTS.items():
        print(f"=== rebalance={rebalance_days}d ({label}) ===")
        all_results.extend(run_variant(rebalance_days, data, market_df))
        print()

    out = pd.DataFrame(all_results)
    out.to_csv("data/decompose_f_quality_roe_stability_rebalance.csv", index=False)
    print("saved data/decompose_f_quality_roe_stability_rebalance.csv")

    print("\n=== TRAIN-period sign comparison (the question this script answers) ===")
    for rebalance_days in REBALANCE_DAYS_VARIANTS.values():
        train_rows = [r for r in all_results if r["rebalance_days"] == rebalance_days and r["period"] == "TRAIN"]
        signs = [r["annualized_return_pct"] > 0 for r in train_rows]
        print(f"  rebalance={rebalance_days}d: TRAIN ann_return positive in {sum(signs)}/{len(signs)} cost configs "
              f"(values: {[round(r['annualized_return_pct'], 2) for r in train_rows]})")

    return all_results


if __name__ == "__main__":
    main()
