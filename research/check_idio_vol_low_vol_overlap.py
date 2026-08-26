"""TW marathon round 99: pre-deep-dive overlap check for `f_idio_vol` vs
`f_low_vol` (both from the "低風險" family, MARATHON_PROTOCOL.md section 3).

Round 96 found f_idio_vol CHEAP_PASS (percentile=100.0) and explicitly
flagged the next step (TW_LEADS.md #7 / TW_MARATHON_STATE.md): before
spending a deep-dive on it, check whether it is a genuinely distinct signal
from f_low_vol (already PASS) or just a high-overlap rediscovery of the same
underlying mechanism. f_low_vol is total 60-day return volatility;
f_idio_vol is the market-model residual component after removing
beta*market volatility (factors.py's `prepare_factors`, ~line 418-430) --
conceptually distinct in the literature (Ang, Hodrick, Xing & Zhang 2006)
but likely correlated in practice since idiosyncratic variance is a
component of total variance.

Method: reuse the exact same cached 100-name sample (SAMPLE_SEED=20260822)
and non-overlapping 20-trading-day snapshots that factor_ic.py's cheap gate
already uses -- zero new FinMind/yfinance calls needed, all prices should
already be on disk from prior rounds' runs of this same sample. At each
snapshot's as-of date, compute (a) cross-sectional Spearman correlation
between the two factor values, and (b) Jaccard overlap of each factor's top
decile (best score = candidates for "buy" leg) and bottom decile ("short"
leg) stock sets. Report the average across all snapshots.

This is a diagnostic, not a new hypothesis test -- no IC-vs-return
evaluation here, no Bonferroni/FDR bar, not a TRIALS_LEDGER.md row. Output
feeds the go/no-go decision for whether f_idio_vol's upcoming deep-dive
should proceed as an independent candidate or be reframed as "same
mechanism as f_low_vol, marginal value only."
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START,
    build_snapshots, load_sample_with_factors, sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

FACTOR_A = "f_low_vol"
FACTOR_B = "f_idio_vol"
DECILE_FRAC = 0.10


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return float("nan")
    union = a | b
    if not union:
        return float("nan")
    return len(a & b) / len(union)


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2010-01-01")
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in overlap check")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (should be fully cached from prior rounds)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    corrs = []
    top_overlaps = []
    bottom_overlaps = []
    n_names_used = []

    for as_of, _fwd in snapshots:
        ids, va, vb = [], [], []
        for sid, d in data.items():
            idx = d.index[d["date"] == as_of]
            if len(idx) == 0:
                continue
            fa = d.loc[idx[0], FACTOR_A]
            fb = d.loc[idx[0], FACTOR_B]
            if pd.isna(fa) or pd.isna(fb):
                continue
            ids.append(sid)
            va.append(float(fa))
            vb.append(float(fb))
        if len(ids) < 10:
            continue
        va_arr = np.array(va)
        vb_arr = np.array(vb)
        rho, _ = spearmanr(va_arr, vb_arr)
        if not np.isnan(rho):
            corrs.append(rho)

        n_decile = max(1, int(len(ids) * DECILE_FRAC))
        order_a = np.argsort(-va_arr)  # descending: highest score = best "long" candidate
        order_b = np.argsort(-vb_arr)
        top_a = {ids[i] for i in order_a[:n_decile]}
        top_b = {ids[i] for i in order_b[:n_decile]}
        bot_a = {ids[i] for i in order_a[-n_decile:]}
        bot_b = {ids[i] for i in order_b[-n_decile:]}
        top_overlaps.append(_jaccard(top_a, top_b))
        bottom_overlaps.append(_jaccard(bot_a, bot_b))
        n_names_used.append(len(ids))

    mean_corr = float(np.mean(corrs)) if corrs else float("nan")
    mean_top = float(np.nanmean(top_overlaps)) if top_overlaps else float("nan")
    mean_bottom = float(np.nanmean(bottom_overlaps)) if bottom_overlaps else float("nan")

    print(f"\n=== f_low_vol vs f_idio_vol overlap ({len(corrs)} usable snapshots, "
          f"avg {np.mean(n_names_used):.0f} names/snapshot) ===")
    print(f"  mean cross-sectional Spearman correlation: {mean_corr:+.3f}")
    print(f"  mean top-decile Jaccard overlap (long leg):   {mean_top:.3f}")
    print(f"  mean bottom-decile Jaccard overlap (short leg): {mean_bottom:.3f}")

    if mean_corr > 0.7 or (mean_top > 0.5 and mean_bottom > 0.5):
        verdict = ("HIGH OVERLAP -- likely the same underlying mechanism as f_low_vol; "
                   "deep-diving f_idio_vol as an independently combinable candidate is "
                   "probably not worth the effort, treat as a marginal/redundant variant.")
    elif mean_corr > 0.4:
        verdict = ("MODERATE OVERLAP -- correlated but decile membership diverges enough "
                   "that f_idio_vol may add information beyond f_low_vol; deep-dive is "
                   "justified but should include a f_low_vol-orthogonalized robustness check.")
    else:
        verdict = ("LOW OVERLAP -- the two factors behave as largely distinct signals "
                   "despite being related in theory; proceed to full deep-dive as an "
                   "independent candidate.")
    print(f"\nVERDICT: {verdict}")
    return mean_corr, mean_top, mean_bottom, verdict


if __name__ == "__main__":
    main()
