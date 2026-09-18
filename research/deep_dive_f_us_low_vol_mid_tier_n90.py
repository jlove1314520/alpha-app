"""US-track deep-dive (MARATHON_PROTOCOL.md 1b) for `f_us_low_vol`, MID-TIER,
N=90 sample -- follow-up to round 446's CALIBRATION_PROBE.md-mandated re-test
of #52 (`us_factor_ic_by_size.py`, TIER="mid", SAMPLE_SIZE=90,
SAMPLE_SEED=20260826_3; TRIALS_LEDGER.md #206: 81/90 usable, VAL IC +0.0904,
null percentile=100.0, CHEAP_PASS). Round 446's own "下一步" flagged this as
undeep-dived: "評估是否值得為中型股tier單獨開一條策略構造深挖...但那條
[大型股tier]後續在策略層FAIL，中型股tier是否重蹈需要獨立驗證，不能直接
套用大型股結論". This script is that deep-dive, ~70 rounds later (candidate
pool otherwise exhausted per TW/US_MARATHON_STATE.md round 554/555).

**Why a new file, not editing `deep_dive_f_us_low_vol_mid_tier.py`**: that
script hardcodes `MID_TIER_SAMPLE_SIZE = 30` / `MID_TIER_SAMPLE_SEED =
20260826_2` in its own module-level constants (the *original*, pre-
CALIBRATION_PROBE.md N=30 mid-tier sample, already deep-dived and FAILed --
TRIALS_LEDGER.md #64, US_LEADS.md #14). Editing those constants in place
would silently invalidate the historical record of that already-concluded
N=30 result if anyone re-ran the file from source control history. This is
the minimal fork: only the two constants + docstring change, everything else
(`run_long_short_us`, cost model wiring, SPY benchmark fetch, random-control
percentile, decile/random leg functions) imported unchanged from
`deep_dive_f_us_low_vol.py`, same pattern the N=30 script itself used.

**Sample identity**: uses `us_factor_ic_by_size.py`'s *current* live
module-level TIER="mid"/SAMPLE_SIZE=90/SAMPLE_SEED=20260826_3 -- the exact
same draw that produced the #206 cheap-gate CHEAP_PASS, not a fresh
resample. No monkeypatch needed (unlike the N=30 script) because those are
already the file's live values as of round 446 (2026-09-08) and have not
changed since (confirmed by round 555 marathon state).
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
from us_factor_ic import load_us_sample_with_factors
from validation import holdout
from validation import us_costs as us_costmod

MID_TIER_N90_SAMPLE_SIZE = 90
MID_TIER_N90_SAMPLE_SEED = 20260826_3  # us_factor_ic_by_size.py's current live SAMPLE_SEED for
                                        # TIER="mid" as of round 446 -- same draw as TRIALS_LEDGER #206


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
    control_max = float(np.max(random_finals))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100 if not pd.isna(alpha_ann) else float("nan"),
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_max_equity": control_max,
        "random_control_percentile": percentile,
        "beats_control_max": real_final > control_max,
        "n_dates": len(result),
    }


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"
    assert size_mod.TIER == "mid", (
        f"us_factor_ic_by_size.py TIER is now {size_mod.TIER!r}, not 'mid' -- "
        "aborting rather than risk deep-diving the wrong tier under a stale assumption"
    )

    sample_ids = size_mod.sample_tier_ids(MID_TIER_N90_SAMPLE_SIZE, MID_TIER_N90_SAMPLE_SEED)
    print(f"=== US deep-dive (1b): {TARGET_FACTOR}, tier=mid, N=90 (follow-up to TRIALS_LEDGER #206) ===")
    print(f"Loading sample ({len(sample_ids)} requested, seed={MID_TIER_N90_SAMPLE_SEED}, cache-first)...")
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
                  f"max_equity={r['random_control_max_equity']:.4f}  real_percentile={r['random_control_percentile']:.1f}  "
                  f"beats_max={r['beats_control_max']}")

    print("\n=== SUMMARY ===")
    print(f"tier: mid (N=90)  market benchmark used for beta: {'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"sample: {len(data)} names (cross-section decile size k={max(1, round(len(data)*0.10))}/leg)")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}  "
              f"beats_max={r['beats_control_max']}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")
    all_beat_max = all(r["beats_control_max"] for r in all_results)
    print(f"beats control max in all {len(all_results)} period x cost combos: {all_beat_max} "
          f"(evaluate_vs_control()-style strict standard, not the old 90th-percentile threshold)")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_low_vol_mid_tier_n90.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_mid_tier_n90.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
