"""US-track 1b deep-dive rerun for `f_us_low_vol`, UNSTRATIFIED, on the full
cached-ticker universe (marathon round 336, US track) -- the deep-dive-level
analogue of round 335's cheap-gate-level rerun (`us_factor_ic_cached_universe.py`,
TRIALS_LEDGER.md #104), completing the loop `CALIBRATION_PROBE.md`'s "US軌
#47/#52同理各自重跑" instruction left open.

**Why this exists**: round 335 (#104) reran only the cheap gate (cross-sectional
IC) on 201/225 cached names and found it CHEAP_PASS at percentile 100.0 --
confirming that #47's (large-tier, 29 names) cheap-gate FAIL (percentile 83.4)
was very likely the calibration probe's diagnosed "small sample, insufficient
power" artifact, not a genuine absence of signal. But #104 explicitly did NOT
touch the deep-dive (1b) layer, which is what actually killed the
UNSTRATIFIED f_us_low_vol family in the first place (#41, 27 names: TRAIN
period lost to its own random control at percentile 41-48, VAL period beta
collapsed to -0.891 -- a strategy-construction failure, not a cheap-gate
power failure). #104's own docstring flagged this open question for a future
round: "#52...如需重查，正確工作單位是用更大樣本重跑
deep_dive_f_us_low_vol_mid_tier.py的1b回測，非cheap gate" (TRIALS_LEDGER.md,
"待重跑清單" note). This script answers the more fundamental version of that
question first: does the ORIGINAL unstratified #41 failure (not just the
mid-tier #52 one) also look different at ~9x the name count?

**Why unstratified (not mid-tier specifically)**: tiering these 225 cached
names by market cap would need a fresh `USStockInfo` fetch for exactly this
list (not yet done -- see `us_factor_ic_cached_universe.py`'s docstring,
which deferred the same tiering question for the same reason). Running the
unstratified deep-dive first is strictly cheaper (zero new API calls, same
`cached_ticker_ids()` list #104 already validated works end-to-end for this
purpose) and directly answers the question CALIBRATION_PROBE.md actually
posed for #47's family: was the *cheap-gate* verdict too small a sample, and
does that flow through to the *deep-dive* verdict too? The mid-tier-specific
#52 deep-dive rerun (which needs the market-cap fetch this script deliberately
skips) is left as a distinct, still-open future work unit if this result
makes it seem worthwhile.

**Zero new API calls**: identical `cached_ticker_ids()` list and
`us_price_series()`/`prepare_us_factors()` loaders as #104 -- everything is
an on-disk parquet cache hit. The one exception, `_load_market_df()`'s SPY
series, is also expected to be a cache hit (SPY has been fetched repeatedly
by rounds 329/333/335's US-track scripts already).

Reuses `run_long_short_us()`, `_decile_legs()`, `_random_legs()`,
`_load_market_df()`, `PERIODS`, `COST_MULTIPLIERS`, `REBALANCE_DAYS`,
`N_RANDOM_DRAWS`, `RANDOM_CONTROL_SEED`, `TARGET_FACTOR` unchanged from
`deep_dive_f_us_low_vol.py` -- no forked backtest math, only the data-loading
step changes (cached-universe scan instead of a fresh 40-name random draw).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from deep_dive_f_us_low_vol import (
    COST_MULTIPLIERS,
    PERIODS,
    REBALANCE_DAYS,
    TARGET_FACTOR,
    _load_market_df,
    run_one,
)
from us_factors import prepare_us_factors, us_price_series
from us_portfolio_pilot_real_data import cached_ticker_ids
from validation import holdout
from validation import us_costs as us_costmod


def load_cached_sample_with_factors() -> dict:
    ids = cached_ticker_ids()
    out = {}
    dropped = []
    for sid in ids:
        px = us_price_series(sid)
        if px.empty or len(px) < 260:
            dropped.append(sid)
            continue
        out[sid] = prepare_us_factors(px)
    print(f"cached tickers: {len(ids)} total, {len(out)} usable (>=260 rows), "
          f"{len(dropped)} dropped: {dropped}")
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print(f"=== US deep-dive (1b) rerun: {TARGET_FACTOR}, cached full universe, unstratified ===")
    print("Serves CALIBRATION_PROBE.md's larger-sample instruction at the deep-dive layer "
          "(round 335/#104 already answered it at the cheap-gate layer).\n")

    data = load_cached_sample_with_factors()
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
            print(f"  random control ({r['n_dates']} dates, 100 draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print(f"sample: {len(data)} names (cached full universe, unstratified) -- market benchmark for beta: "
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
    out.to_csv("data/deep_dive_f_us_low_vol_cached_universe.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_cached_universe.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
