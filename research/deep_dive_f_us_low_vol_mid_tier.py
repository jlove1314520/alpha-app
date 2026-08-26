"""US-track deep-dive (MARATHON_PROTOCOL.md 1b) for `f_us_low_vol`, MID-TIER
sample -- follow-up to round 99's mid-tier cheap-gate CHEAP_PASS
(`us_factor_ic_by_size.py`, TIER="mid", US_LEADS.md #7: val IC +0.1123,
train IC +0.0300, null percentile=100.0) that has sat undeep-dived since
round 97/99 while round 103 deep-dived the small-tier sibling (#10) instead
and found it FAILed (sign flip on both return and beta between TRAIN/VAL --
`deep_dive_f_us_low_vol_small_tier.py`, TRIALS_LEDGER.md #64). Per
US_MARATHON_STATE.md round 103's explicit "下一步": deep-dive #7 (mid tier)
next, but do not assume a different outcome just because #1 (unstratified)
and #13 (small tier) both FAILed the same way -- run the full 1b gate anyway
and report honestly.

**Why this is a new script, not a parameter tweak to
`deep_dive_f_us_low_vol_small_tier.py`**: that script hardcodes
`TIER == "small"` via an assert (by design, to prevent silently deep-diving
the wrong tier if `us_factor_ic_by_size.py`'s module-level TIER constant
changes under it in a future round). This script is the minimal fork that
targets mid tier instead -- everything else (run_long_short_us, cost model
wiring, SPY benchmark fetch, random-control percentile, decile/random leg
functions) is imported unchanged from `deep_dive_f_us_low_vol.py`, same as
the small-tier script did.

**Tier + seed**: `us_factor_ic_by_size.py`'s module-level TIER is currently
"small" (set at round 99), not "mid" -- calling `sample_tier_ids()` as-is
would silently resample the wrong tier. Rather than editing that shared
module (which would affect any other script importing it), this script
monkeypatches the imported module's TIER attribute to "mid" *before* calling
`sample_tier_ids()`, using round 97's exact seed (20260826_2, per that
module's own docstring comment identifying which seed belongs to which
tier) and size (30) -- same tier + seed the round-97 cheap gate already
validated, not a fresh draw, to keep this a true depth-check on the same
evidence rather than introducing new sampling variance.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
import us_factor_ic_by_size as size_mod
from deep_dive_f_us_low_vol import (
    COST_MULTIPLIERS,
    N_RANDOM_DRAWS,
    PERIODS,
    RANDOM_CONTROL_SEED,
    REBALANCE_DAYS,
    TARGET_FACTOR,
    _decile_legs,
    _load_market_df,
    _random_legs,
    run_long_short_us,
)
from finmind_client import load_dev
from us_factor_ic import load_us_sample_with_factors
from validation import holdout
from validation import us_costs as us_costmod

MID_TIER_SAMPLE_SIZE = 30
MID_TIER_SAMPLE_SEED = 20260826_2  # round-97's seed for TIER="mid", per us_factor_ic_by_size.py's docstring comment

# monkeypatch the shared module's TIER for this process only -- does not touch the file on disk,
# does not affect any other script/round; see module docstring for why this approach vs. editing
# us_factor_ic_by_size.py directly.
size_mod.TIER = "mid"


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
    assert size_mod.TIER == "mid", "monkeypatch failed -- aborting rather than risk deep-diving the wrong tier"

    sample_ids = size_mod.sample_tier_ids(MID_TIER_SAMPLE_SIZE, MID_TIER_SAMPLE_SEED)
    print(f"=== US deep-dive (1b): {TARGET_FACTOR}, tier=mid ===")
    print(f"Loading sample ({len(sample_ids)} requested, same tier+seed={MID_TIER_SAMPLE_SEED} as round-97 "
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
    print(f"tier: mid  market benchmark used for beta: {'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"sample: {len(data)} names (cross-section decile size k={max(1, round(len(data)*0.10))}/leg -- "
          f"small-sample caveat, same disclosure pattern as the unstratified/small-tier deep-dives)")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_low_vol_mid_tier.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_mid_tier.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
