"""US-track 1b deep-dive rerun for `f_us_low_vol` on the STRATIFIED clean
universe (`data/us_stratified_universe_sample.csv`), marathon round 386.

**Why this exists**: round 383 (#145) found `f_us_low_vol`'s cheap-gate
(cross-sectional IC) CHEAP_PASS at percentile 100.0 on the 248-name clean
stratified universe -- reversing #15/#41/#104/#115's FAIL verdicts on the old
`cached_ticker_ids()` pool. But #145 explicitly did NOT touch the deep-dive
(1b) layer, which is where the old pool's family actually died: #15/#41/#115
all failed at decile long-short backtest (TRAIN losing to its own random
control, or beta collapsing far from market-neutral). #145's docstring left
this as the explicit next step ("下一輪接手：對#20或#21擇一做1b深挖").
This script answers it for #21 (`f_us_low_vol`).

**Single-variable control**: reuses `run_one()`, `PERIODS`,
`COST_MULTIPLIERS`, `REBALANCE_DAYS`, `TARGET_FACTOR`, `_load_market_df()`
from `deep_dive_f_us_low_vol.py` UNCHANGED -- no forked backtest math. The
only difference from `deep_dive_f_us_low_vol_cached_universe.py` (round 336)
is the ticker source: `data/us_stratified_universe_sample.csv` (usable==True)
instead of `cached_ticker_ids()`.

**Zero new API calls**: all 248 tickers are already `us_price_series()`
parquet-cache hits (round 381/382 already fetched full price history for
this list; #145 confirmed 248/248 usable for the price-only low-vol factor).
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
from validation import holdout
from validation import us_costs as us_costmod

UNIVERSE_CSV = Path(__file__).parent / "data" / "us_stratified_universe_sample.csv"


def load_clean_universe_tickers() -> list[str]:
    df = pd.read_csv(UNIVERSE_CSV)
    return df[df["usable"] == True]["stock_id"].tolist()  # noqa: E712


def load_clean_sample_with_factors() -> dict:
    ids = load_clean_universe_tickers()
    out = {}
    dropped = []
    for sid in ids:
        px = us_price_series(sid)
        if px.empty or len(px) < 260:
            dropped.append(sid)
            continue
        out[sid] = prepare_us_factors(px)
    print(f"clean stratified universe: {len(ids)} total, {len(out)} usable (>=260 rows), "
          f"{len(dropped)} dropped: {dropped}")
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print(f"=== US deep-dive (1b) rerun: {TARGET_FACTOR}, clean stratified universe ===")
    print("Answers round383/#145's explicit next step: does the CHEAP_PASS cheap-gate "
          "verdict on the clean universe survive the decile long-short deep-dive layer "
          "that killed #15/#41/#115 on the old cached_ticker_ids() pool?\n")

    data = load_clean_sample_with_factors()
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
    out.to_csv("data/deep_dive_f_us_low_vol_clean_universe.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_clean_universe.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
