"""US-track 1b deep-dive rerun for `f_us_value_bm` on the STRATIFIED clean
universe (`data/us_stratified_universe_sample.csv`), marathon round 391.

**Why this exists**: round 383 (#144) found `f_us_value_bm`'s cheap-gate
(cross-sectional IC) CHEAP_PASS at percentile 100.0 on the clean stratified
universe (159/248 usable) -- reversing #128's FAIL verdict on the old
`cached_ticker_ids()` pool. But #144 explicitly did NOT touch the deep-dive
(1b) layer, which is where the old pool's version actually died (#128: VAL
period return magnitude implausible). `US_MARATHON_STATE.md` round387's
"下一輪接手" explicitly names this as the follow-up after `f_us_low_vol`'s
own clean-universe 1b rerun (`deep_dive_f_us_low_vol_clean_universe.py`,
round386) finishes collecting.

**Single-variable control**: reuses `run_one_value()`, `PERIODS`,
`COST_MULTIPLIERS`, `REBALANCE_DAYS`, `_load_market_df()` from
`deep_dive_f_us_value_bm.py` UNCHANGED -- no forked backtest math. The only
difference from `deep_dive_f_us_value_bm.py` is the data loader:
`us_factor_ic_value_clean_universe.load_value_sample()` (clean stratified
universe, round 382's cheap-gate loader) instead of
`us_factor_ic_value.load_value_sample()` (old `cached_ticker_ids()` pool).
Same shape contract (`{ticker: DataFrame(date, adj_close, f_us_value_bm)}`),
so `run_one_value()` needs no changes.

**Zero *new* API calls expected**: round 382's background job
(`20260906-010314-7940`) already populated the on-disk SEC EDGAR
`companyfacts` cache for the resolvable CIKs in this 248-name list (159
came back usable). This rerun is expected to be a full cache hit; any
ticker that couldn't resolve a CIK or had empty companyfacts in round 382
will fail identically here (not a new problem this round introduces).

**Not run in this round's session** (2026-09-06, round 391): per protocol
section 0b, only one heavy job may run at a time, and
`us_deep_dive_lowvol_clean_universe_retry` (job `20260906-060311-6a01`) was
still `running` when this file was written. This script is infrastructure
only this round -- next round should submit it via `run_detached.py` once
the low-vol job is collected (expect a similarly long runtime: 159 names is
smaller than low-vol's 248, but still 2 periods x 3 cost multipliers x
(1 real + 100 random draws) = 606 full decile long-short backtests; budget
a `--timeout-min` on the order of 100+ minutes, not the 20-minute default
that round386 discovered was too conservative for this same backtest
engine at a similar name count).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from deep_dive_f_us_value_bm import (
    COST_MULTIPLIERS,
    PERIODS,
    TARGET_FACTOR,
    _load_market_df,
    run_one_value,
)
from us_factor_ic_value_clean_universe import load_value_sample
from validation import holdout
from validation import us_costs as us_costmod


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print(f"=== US deep-dive (1b) rerun: {TARGET_FACTOR}, clean stratified universe ===")
    print("Answers round387's US_MARATHON_STATE.md next-step: does the CHEAP_PASS "
          "cheap-gate verdict on the clean universe (#144, percentile 100.0) survive "
          "the decile long-short deep-dive layer that killed #128 on the old "
          "cached_ticker_ids() pool?\n")

    data, drop_reasons = load_value_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
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
            print(f"  random control ({r['n_dates']} dates, 100 draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print(f"sample: {len(data)} names (clean stratified universe) -- market benchmark for beta: "
          f"{'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"cross-section decile size k={max(1, round(len(data) * 0.10))}/leg")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_value_bm_clean_universe.csv", index=False)
    print("\nsaved data/deep_dive_f_us_value_bm_clean_universe.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
