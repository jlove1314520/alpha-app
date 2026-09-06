"""US-track portfolio-axis diagnostic: is the TRAIN->VAL blow-up in cross-
sectional return dispersion specific to `us_stratified_universe_sample.csv`
(the "clean" universe #20/#21 were re-tested on), or does the same pattern
also show up in the older `cached_ticker_ids()` superset (the "hot-stock
biased" pool #17/#128 already flagged as having its own artifact)? If BOTH
pools show a similarly extreme VAL/TRAIN dispersion ratio, that points to a
broad 2020-2024 market-regime effect (COVID crash/recovery, 2021 meme-stock
mania, 2022 rate-hike bear market, 2023-2024 AI rally all raise cross-
sectional dispersion for ANY US equity sample) rather than something
specific to the stratified sampling procedure itself -- this is the exact
open question `US_MARATHON_STATE.md` round404/406 left for "heavy-job-slot
空出後" but does NOT actually need a new fetch: it only needs the
already-cached price parquet files both pools already hit (#20/#21's clean
universe from round383/391/400/404/406; the old pool from round336-357).

Zero new API calls. Single pass (no random control needed -- this measures
a raw descriptive statistic, not a strategy's edge, so there is no
PASS/FAIL cheap-gate verdict here, only a pre-registered read of the ratio).

Pre-registered read: compute per-ticker annualized (CAGR) buy-and-hold
return over TRAIN and VAL for both pools (annualized, not raw total return,
because TRAIN spans ~6y and VAL ~4y -- raw total-return std would conflate
period length with genuine dispersion), take the cross-sectional std of
those annualized returns ("dispersion"), and report VAL_dispersion /
TRAIN_dispersion for each pool plus each pool's dispersion relative to
SPY's own realized volatility in the same window (a market-wide dispersion
should show up in SPY's vol too, not just single-name spread). If the two
pools' VAL/TRAIN dispersion ratios are within ~2x of each other (same order
of magnitude), that supports the market-regime explanation over a
sampling-method artifact.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from deep_dive_f_us_low_vol import _load_market_df
from us_factor_ic_value_clean_universe import load_value_sample
from us_factors import us_price_series
from us_portfolio_pilot_real_data import cached_ticker_ids
from validation import holdout

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def _bh_return(px: pd.DataFrame, start: str, end: str, min_coverage: float = 0.8) -> float | None:
    """Annualized (CAGR) buy-and-hold return, not raw total return -- TRAIN
    (~6y) and VAL (~4y) have different lengths, so raw total-return std
    would overstate TRAIN's dispersion purely from the longer compounding
    window, not genuine cross-sectional spread. Annualizing makes the two
    periods' dispersion figures comparable.

    `min_coverage` requires the ticker to have data for at least 80% of the
    period's expected trading days (~252/yr) -- a loose `len(win) >= 30`
    floor lets short-lived IPO/relisting windows get annualized via
    `total_return ** (252/n_days)`, which explodes any modest short-window
    move into an implausible three-digit "annualized" number and would
    dominate the cross-sectional std with pure annualization-window noise,
    not genuine dispersion.
    """
    win = px[(px["date"] >= start) & (px["date"] <= end)]
    expected_days = (pd.Timestamp(end) - pd.Timestamp(start)).days * (252.0 / 365.0)
    if len(win) < max(30, min_coverage * expected_days):
        return None
    p0 = win["adj_close"].iloc[0]
    p1 = win["adj_close"].iloc[-1]
    if p0 <= 0 or pd.isna(p0) or pd.isna(p1):
        return None
    n_days = len(win)
    total_ret = p1 / p0
    if total_ret <= 0:
        return None
    return float(total_ret ** (252.0 / n_days) - 1.0)


def _pool_dispersion(ids: list[str], label: str) -> dict:
    rows = {"TRAIN": [], "VAL": []}
    n_ok = 0
    for sid in ids:
        px = us_price_series(sid)
        if px.empty:
            continue
        got_any = False
        for period, (start, end) in PERIODS.items():
            r = _bh_return(px, start, end)
            if r is not None:
                rows[period].append(r)
                got_any = True
        if got_any:
            n_ok += 1
    out = {"pool": label, "n_requested": len(ids), "n_with_data": n_ok}
    for period in PERIODS:
        arr = np.array(rows[period])
        out[f"{period.lower()}_n"] = len(arr)
        out[f"{period.lower()}_std"] = float(arr.std()) if len(arr) else float("nan")
        out[f"{period.lower()}_iqr"] = (
            float(np.percentile(arr, 75) - np.percentile(arr, 25)) if len(arr) else float("nan")
        )
        out[f"{period.lower()}_median"] = float(np.median(arr)) if len(arr) else float("nan")
    if out["train_std"] and out["train_std"] == out["train_std"] and out["train_std"] != 0:
        out["val_over_train_std_ratio"] = out["val_std"] / out["train_std"]
    else:
        out["val_over_train_std_ratio"] = float("nan")
    return out


def _spy_vol(market_df: pd.DataFrame) -> dict:
    out = {}
    df = market_df.sort_values("date").copy()
    df["ret"] = df["close"].pct_change()
    for period, (start, end) in PERIODS.items():
        win = df[(df["date"] >= start) & (df["date"] <= end)]
        if len(win) < 30:
            out[f"spy_{period.lower()}_ann_vol"] = float("nan")
            continue
        out[f"spy_{period.lower()}_ann_vol"] = float(win["ret"].std() * (252 ** 0.5) * 100)
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US portfolio-axis diagnostic: cross-sectional return dispersion, clean vs old pool ===")

    value_data, drop_reasons = load_value_sample()
    clean_ids = sorted(value_data.keys())
    print(f"clean (stratified) universe: {len(clean_ids)} tickers (value_bm-usable subset, same 159 as round406 combo)")

    old_ids = cached_ticker_ids()
    print(f"old (hot-stock-biased) pool: {len(old_ids)} tickers")

    overlap = set(clean_ids) & set(old_ids)
    print(f"overlap between the two pools: {len(overlap)} tickers ({len(overlap)/len(clean_ids)*100:.1f}% of clean)")

    clean_stats = _pool_dispersion(clean_ids, "clean_stratified")
    old_stats = _pool_dispersion(old_ids, "old_cached")

    market_df, is_spy = _load_market_df()
    spy_stats = _spy_vol(market_df) if is_spy else {}
    print(f"market benchmark: {'SPY' if is_spy else 'NONE (fetch failed)'}")

    for s in (clean_stats, old_stats):
        print(f"\n--- {s['pool']} (n_with_data={s['n_with_data']}/{s['n_requested']}) ---")
        for period in PERIODS:
            p = period.lower()
            print(f"  {period}: n={s[f'{p}_n']:4d}  median_ann_return={s[f'{p}_median']*100:+7.2f}%  "
                  f"std={s[f'{p}_std']*100:7.2f}%  IQR={s[f'{p}_iqr']*100:7.2f}%")
        print(f"  VAL/TRAIN std ratio: {s['val_over_train_std_ratio']:.2f}x")

    if spy_stats:
        print(f"\n--- SPY realized annualized vol ---")
        print(f"  TRAIN: {spy_stats.get('spy_train_ann_vol', float('nan')):.2f}%   "
              f"VAL: {spy_stats.get('spy_val_ann_vol', float('nan')):.2f}%   "
              f"ratio: {spy_stats.get('spy_val_ann_vol', float('nan')) / spy_stats.get('spy_train_ann_vol', float('nan')):.2f}x")

    print("\n=== SUMMARY (are the two pools' VAL/TRAIN dispersion blow-ups the same order of magnitude?) ===")
    r_clean = clean_stats["val_over_train_std_ratio"]
    r_old = old_stats["val_over_train_std_ratio"]
    same_order = (r_clean / r_old <= 2.0 and r_old / r_clean <= 2.0) if (r_clean == r_clean and r_old == r_old and r_old != 0) else False
    print(f"  clean_stratified ratio={r_clean:.2f}x   old_cached ratio={r_old:.2f}x   "
          f"-> {'SAME ORDER OF MAGNITUDE (supports market-regime hypothesis)' if same_order else 'DIFFERENT (supports sampling-method-specific artifact)'}")

    out = pd.DataFrame([clean_stats, old_stats])
    for k, v in spy_stats.items():
        out[k] = v
    out.to_csv("data/us_universe_dispersion_check.csv", index=False)
    print("\nsaved data/us_universe_dispersion_check.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return out


if __name__ == "__main__":
    main()
