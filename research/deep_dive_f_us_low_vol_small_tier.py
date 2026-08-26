"""US-track deep-dive (MARATHON_PROTOCOL.md 1b) for `f_us_low_vol`, SMALL-TIER
sample -- follow-up to round 84's unstratified deep-dive (`deep_dive_f_us_low_vol.py`,
which FAILed) now that round 99's size-stratified re-test (`us_factor_ic_by_size.py`,
TIER="small") produced US_LEADS.md's strongest CHEAP_PASS of the three tier
variants (val IC +0.2181, train IC +0.0182, IR +1.057, hit_rate 0.88, percentile
100.0) -- the val-IC gradient across all four sample versions (unstratified +0.134,
large +0.038, mid +0.112, small +0.218) points the same direction as the
leverage-constraint literature's prediction (smaller/more-constrained names show
stronger low-vol anomalies), but per US_MARATHON_STATE.md round 99's explicit
instruction this must NOT be assumed to survive deep-dive just because the
gradient direction matches theory -- round 84's unstratified version had a
similarly clean-looking cheap-gate pass and then failed deep-dive on a weak
train-period IR, and that exact warning sign must be checked again here before
any upgrade past CHEAP_PASS.

**Why this is a new script, not a parameter tweak to `deep_dive_f_us_low_vol.py`
or `us_factor_ic_by_size.py`**: the former is hardcoded to the unstratified
40-name sample (`sample_us_universe_ids` from `us_factor_ic.py`); the latter only
runs the *cheap* IC gate (Spearman IC vs shuffle-null), not the full 1b backtest
(train/val long-short P&L, cost sensitivity, beta, Sortino). This script is the
minimal fork that swaps the SAMPLE source in the deep-dive backtest for the
small-tier one -- everything else (run_long_short_us, cost model wiring, SPY
benchmark fetch, random-control percentile) is copy-adapted unchanged from
`deep_dive_f_us_low_vol.py`, which already documents why it can't just call
`long_short_backtest.run_long_short` directly (TW cost-model signature mismatch).

**Sample**: reuses round 99's exact tier + seed (`TIER="small"`, `SAMPLE_SIZE=30`,
`SAMPLE_SEED=20260826_3` from `us_factor_ic_by_size.py`) so the deep-dive
backtest runs on precisely the same 30-name small-tier draw the cheap gate
already validated -- not a fresh draw, to keep this a true depth-check on the
same evidence rather than introducing new sampling variance.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import (
    COST_MULTIPLIERS,
    MAX_PLAUSIBLE_DAILY_RETURN,
    N_RANDOM_DRAWS,
    PERIODS,
    RANDOM_CONTROL_SEED,
    REBALANCE_DAYS,
    TARGET_FACTOR,
    _decile_legs,
    _load_market_df,
    run_long_short_us,
)
from finmind_client import load_dev
from us_factor_ic import load_us_sample_with_factors
from us_factor_ic_by_size import SAMPLE_SEED, SAMPLE_SIZE, TIER, sample_tier_ids
from validation import holdout
from validation import us_costs as us_costmod

assert TIER == "small", (
    "this script is specifically the small-tier deep-dive; if TIER in "
    "us_factor_ic_by_size.py has been changed since, re-check before reusing"
)


def run_one(data, calendar, market_df, start, end, slippage_bps):
    from functools import partial
    result = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slippage_bps, leg_fn=_decile_legs)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = (float("nan"), float("nan"))
    if not market_df.empty:
        beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        from deep_dive_f_us_low_vol import _random_legs
        rand_leg_fn = partial(_random_legs, rng=rng)
        rr = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slippage_bps, leg_fn=rand_leg_fn)
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100 if not pd.isna(alpha_ann) else float("nan"),
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
    }


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_tier_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== US deep-dive (1b): {TARGET_FACTOR}, tier={TIER} ===")
    print(f"Loading sample ({len(sample_ids)} requested, same tier+seed={SAMPLE_SEED} as round-99 "
          f"cheap gate, cache-first)...")
    data, quota_hit, quota_hit_ticker = load_us_sample_with_factors(sample_ids)
    print(f"  {len(data)}/{len(sample_ids)} usable names" +
          (f" (stopped early at {quota_hit_ticker} -- quota/rate-limit)" if quota_hit else ""))

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section "
              f"of 10 -- cannot run a meaningful deep-dive with this sample.")
        return None

    market_df, is_spy = _load_market_df()
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = us_costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, calendar, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print(f"tier: {TIER}  market benchmark used for beta: {'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"sample: {len(data)} names (cross-section decile size k={max(1, round(len(data)*0.10))}/leg -- "
          f"small-sample caveat, same disclosure pattern as the unstratified deep-dive)")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_low_vol_small_tier.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_small_tier.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
