"""US-track 1b deep-dive for `f_us_value_bm` (book-to-market) -- the US
track's first CHEAP_PASS fundamentals-based factor (round 347,
`US_LEADS.md` #16, `TRIALS_LEDGER.md` #119), and the first genuinely new
factor family (not another price-only variant) to reach this stage.

**Why this is this round's work unit (marathon round 350, US track)**:
per `MARATHON_PROTOCOL.md` 2026-09-03 top-of-file directive, the primary
axis is now portfolio-level work; a standalone single-factor test is only
allowed as a "component-candidate pre-check for a specific portfolio
iteration". This deep-dive IS that pre-check: `us_portfolio_backtest.py`
(round 329) + `us_portfolio_pilot_real_data.py` (round 333) already built
the US-track portfolio-level backtest engine, but round 333's own
"下一步" (c) explicitly deferred picking real component factors because at
that time zero US-track factors had a surviving CHEAP_PASS. `f_us_value_bm`
is now the only candidate that could plausibly become the first real
component of a `US_PORTFOLIO_STRATEGY_SPEC.md`-style multi-factor
portfolio -- but per protocol section 1b and this track's own repeated
lesson (`f_us_low_vol`'s #1/#13/#14/#15, all CHEAP_PASS but FAIL at 1b),
a cheap-gate CHEAP_PASS must never be assumed to survive strategy
construction. This script runs the full 1b gate before any such
component decision is made.

**Why NOT `#47/#52` (the calibration probe's stratified low-vol rerun)
instead**: `CALIBRATION_PROBE.md`'s "US/FUT軌的#47/#52...同理各自重跑"
instruction predates this track's own subsequent, more thorough work
(round 335's #104 cheap-gate rerun on 201 cached names, percentile 100.0;
round 336's #15 full 1b deep-dive rerun on the same 201-name cached
universe, still FAIL on strategy-construction grounds -- TRAIN losing to
its own random control, beta not market-neutral). #47/#52's FAIL mode is a
cheap-gate small-sample-power question the family has since answered more
rigorously via #104/#15 already, and `f_us_low_vol`'s underlying failure
(#13/#14, both explicit 1b deep-dives) is a strategy-construction problem
a bigger cheap-gate sample cannot fix -- re-running #47/#52 with more
names would re-litigate an already-closed family without addressing why
it closed. `f_us_value_bm` is the higher-value, not-yet-answered question.

**Data pipeline, zero forked math**: reuses `load_value_sample()` verbatim
from `us_factor_ic_value.py` (round 347's cheap-gate loader -- already
produces the exact `{ticker: DataFrame(date, adj_close, f_us_value_bm)}`
shape `_decile_legs()`/`run_long_short_us()` need) and
`_decile_legs()`/`_random_legs()`/`run_long_short_us()`/`_load_market_df()`/
`PERIODS`/`COST_MULTIPLIERS`/`REBALANCE_DAYS`/`N_RANDOM_DRAWS`/
`RANDOM_CONTROL_SEED` unchanged from `deep_dive_f_us_low_vol.py`. The only
new code below is `run_one_value()`, a thin factor-column-bound copy of
that module's `run_one()` (which hardcodes `_decile_legs`/`_random_legs`
to their own `TARGET_FACTOR` default via closures over the imported
names, so it cannot be reused as-is for a different factor column without
either monkeypatching or this kind of `functools.partial` rebind -- the
latter is the less surprising option, consistent with
`deep_dive_f_us_low_vol_cached_universe.py`'s own precedent of preferring
composition over monkeypatching wherever the imported functions already
expose the needed parameter).

**API cost**: `load_value_sample()` hits `get_cik_map()` (cached, 24h TTL)
and `book_value_per_share_pit()` per ticker -- round 347 already populated
the on-disk `SEC_companyfacts_*.json` cache for every resolvable CIK in
this sample (224 files on disk before this round runs), so this rerun is
expected to be ~zero new SEC EDGAR fetches (any ticker whose CIK wasn't
resolvable or whose companyfacts came back genuinely empty in round 347
will fail identically here, same cache-miss/absent-data behavior, not a
new problem this round introduces). Zero FinMind calls (all price series
are on-disk-cache hits via `cached_ticker_ids()`'s own guarantee, same as
every prior deep-dive in this family).
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
from us_factor_ic_value import load_value_sample
from validation import holdout
from validation import us_costs as us_costmod

TARGET_FACTOR = "f_us_value_bm"


def run_one_value(data, calendar, market_df, start, end, slippage_bps):
    """Factor-column-bound copy of `deep_dive_f_us_low_vol.run_one()` --
    see module docstring for why this can't just call that function
    directly (its leg_fn choices are closed over `f_us_low_vol` by way of
    the imported functions' own default `factor_col` argument)."""
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

    print(f"=== US deep-dive (1b): {TARGET_FACTOR} (book-to-market) ===")
    print("Serves as component-candidate pre-check for a future US portfolio-level "
          "multi-factor iteration (MARATHON_PROTOCOL.md 2026-09-03 directive) -- "
          "this run does NOT itself constitute a portfolio backtest.\n")

    data, drop_reasons = load_value_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} cached-price candidates)")
    if drop_reasons:
        from collections import Counter
        reason_kinds = Counter(r.split(" (")[0].split(" --")[0] for r in drop_reasons.values())
        print("Drop reasons:")
        for kind, count in reason_kinds.most_common():
            print(f"  {count}x {kind}")

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
            r = run_one_value(data, calendar, market_df, start, end, slip)
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
    out.to_csv("data/deep_dive_f_us_value_bm.csv", index=False)
    print("\nsaved data/deep_dive_f_us_value_bm.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
