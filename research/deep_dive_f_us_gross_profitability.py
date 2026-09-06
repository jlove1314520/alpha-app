"""US-track 1b deep-dive for `f_us_gross_profitability` (Novy-Marx gross
profitability), the CHEAP_PASS result from this round's
`us_factor_ic_quality_clean_universe.py` (84/248 clean-universe names
usable, train_ic=+0.0503, val_ic=+0.0499, null percentile 100.0, same_sign
True -- see `us_factors_quality.py` module docstring for why this is a
genuinely new economic mechanism, not a #20/#21 reskin).

**Why this cheap-gate result is structurally different from #20's
(`f_us_value_bm`) in one respect worth flagging up front, not discovered
after the fact**: train_ic (+0.0503) and val_ic (+0.0499) are almost
IDENTICAL here, unlike #16/#20's pattern of a much weaker train IC than
val IC (e.g. #20: train +0.0432 vs val +0.0853, nearly 2x) that turned out
to be an early symptom of the eventual universe-artifact problem. A stable
train≈val IC is a mildly encouraging sign but is NOT a substitute for this
1b deep-dive -- `f_us_low_vol`'s #7 (mid-tier CHEAP_PASS) also looked
reasonable at the cheap-gate stage and still failed 1b on beta grounds
(`US_LEADS.md` #14), so this script still runs the full battery before any
conclusion.

**Known contamination risk carried over from #20/#21, not yet resolved,
being surfaced rather than ignored**: `US_LEADS.md` #20 round410 found
`MNTS`/`DVLT`/`TRNR` (among others) are recurring death-spiral
reverse-split microcaps in this same 248-ticker stratified universe with
back-adjusted `adj_close` inflating their historical prices -- and this
round's cheap-gate loader print confirms `MNTS` and `TRNR` are both in the
84-name usable sample for THIS factor too (they have GrossProfit/Assets
10-K tags). If gross profitability's decile short leg picks up the same
names, this deep-dive could hit the identical data-integrity trap for a
completely different economic reason (regardless of whether the raw
profitability signal itself is real) -- this script does not pre-filter
them out (that would be after-the-fact cherry-picking of the universe
based on knowing the answer), but the SUMMARY section explicitly checks
for and reports this overlap so the result can be interpreted correctly,
not just applied a blanket "known good methodology" label from #20's
run because it uses the same harness.

**Data pipeline, zero forked math**: reuses `load_quality_sample()`
verbatim from `us_factor_ic_quality_clean_universe.py` and
`_decile_legs()`/`_random_legs()`/`run_long_short_us()`/`_load_market_df()`/
`PERIODS`/`COST_MULTIPLIERS`/`REBALANCE_DAYS`/`N_RANDOM_DRAWS`/
`RANDOM_CONTROL_SEED` unchanged from `deep_dive_f_us_low_vol.py` -- same
composition-over-monkeypatching precedent `deep_dive_f_us_value_bm.py`
already established for a differently-named target factor column.

**API cost**: zero new SEC EDGAR fetches expected (same companyfacts cache
already populated). Zero FinMind calls (all price series on-disk-cache
hits via `cached_ticker_ids()`-independent `us_price_series()`, same as
`deep_dive_f_us_value_bm.py`).

**Runtime**: 2 periods x 3 cost multipliers x (1 real + 100 random draws)
= 606 `run_long_short_us()` calls on an 84-name cross-section (decile
k=8/leg) -- submitted via `run_detached.py` per `MARATHON_PROTOCOL.md`
0b rather than run inline, since #20's same-shaped run (159 names) took
93.5 minutes end to end.
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
from deep_dive_f_us_low_vol import (
    COST_MULTIPLIERS,
    N_RANDOM_DRAWS,
    PERIODS,
    RANDOM_CONTROL_SEED,
    REBALANCE_DAYS,
    _decile_legs,
    _load_market_df,
    _random_legs,
    run_long_short_us,
)
from us_factor_ic_quality_clean_universe import load_quality_sample
from validation import holdout
from validation import us_costs as us_costmod

TARGET_FACTOR = "f_us_gross_profitability"

# US_LEADS.md #20 round410's confirmed recurring death-spiral reverse-split
# microcaps in this same stratified universe -- checked for overlap in the
# SUMMARY below, not filtered out (see module docstring on why).
KNOWN_CONTAMINATED_TICKERS = {"WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI", "LEE"}


def run_one_quality(data, calendar, market_df, start, end, slippage_bps):
    """Factor-column-bound copy of `deep_dive_f_us_low_vol.run_one()` -- see
    `deep_dive_f_us_value_bm.py`'s `run_one_value()` for why this pattern
    (composition via `functools.partial`, not monkeypatching) is used."""
    decile_fn = partial(_decile_legs, factor_col=TARGET_FACTOR)
    result = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slippage_bps, leg_fn=decile_fn)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = (float("nan"), float("nan"))
    if not market_df.empty:
        beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = partial(_random_legs, rng=rng, factor_col=TARGET_FACTOR)
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

    print(f"=== US deep-dive (1b): {TARGET_FACTOR} (Novy-Marx gross profitability) ===")
    print("Serves as component-candidate pre-check for a future US portfolio-level "
          "multi-factor iteration (MARATHON_PROTOCOL.md 2026-09-03 directive) -- "
          "this run does NOT itself constitute a portfolio backtest.\n")

    data, drop_reasons = load_quality_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
    if drop_reasons:
        from collections import Counter
        reason_kinds = Counter(r.split(" (")[0].split(" --")[0] for r in drop_reasons.values())
        print("Drop reasons:")
        for kind, count in reason_kinds.most_common():
            print(f"  {count}x {kind}")

    contaminated_in_sample = sorted(KNOWN_CONTAMINATED_TICKERS & set(data.keys()))
    print(f"\nKnown death-spiral reverse-split tickers present in this sample: "
          f"{contaminated_in_sample if contaminated_in_sample else 'NONE'} "
          f"({len(contaminated_in_sample)}/{len(data)})")

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
            r = run_one_quality(data, calendar, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print(f"market benchmark used for beta: {'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"sample: {len(data)} names (cross-section decile size k={max(1, round(len(data) * 0.10))}/leg)")
    print(f"known contaminated tickers in sample: {contaminated_in_sample if contaminated_in_sample else 'NONE'}")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")

    train_1x_pct = all_results[0]["random_control_percentile"]
    val_1x_pct = all_results[3]["random_control_percentile"]
    print(f"TRAIN 1x random_control_percentile={train_1x_pct:.1f}  VAL 1x random_control_percentile={val_1x_pct:.1f}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_gross_profitability.csv", index=False)
    print("\nsaved data/deep_dive_f_us_gross_profitability.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
