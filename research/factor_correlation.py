"""Cross-sectional correlation between the 4 factors that passed
factor_ic.py's Bonferroni-corrected bar (see FACTORS.md 2026-08-23):
f_eps_growth, f_eps_surprise, f_revenue_surprise, f_low_vol.

Why this matters before score.py: IC testing only asks "does this factor
predict returns", not "is this factor a repackaging of another one already
in the set". If two passing factors are highly correlated, summing both
into a composite score double-counts one underlying signal instead of
combining two independent ones -- CONSTITUTION.md's honesty rule applies
here too (a score.py that silently overweights one signal by counting it
twice is a subtler version of the same "hidden lookahead" dishonesty this
project keeps checking for).

Method: reuses factor_ic.py's exact sample (same seed, same cached
factor data -- zero new API calls) and snapshot grid. Unlike IC (factor
value vs FORWARD return), this measures factor value vs factor value
within each cross-section, so there is no train/val split concern and no
leakage risk -- correlating two already-known-today values leaks nothing
about the future. Per-snapshot Spearman correlation (rank-based, consistent
with how IC itself is measured), averaged across all snapshots where both
factors have >=10 valid names (same minimum-breadth rule as evaluate_factor).
Full snapshot range (train+val pooled) is used since this is a structural
question about the factors themselves, not a predictive-power claim.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START, build_snapshots,
    load_sample_with_factors, sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

PASSING_FACTORS = ["f_eps_growth", "f_eps_surprise", "f_revenue_surprise", "f_low_vol"]
CORR_REDUNDANCY_THRESHOLD = 0.6  # |corr| >= this treated as "same family", per user's 2026-08-23 instruction


def _factor_cross_section(as_of: str, data: dict[str, pd.DataFrame], cols: list[str]) -> pd.DataFrame:
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        row = {"stock_id": sid}
        for c in cols:
            row[c] = d.loc[idx[0], c]
        rows.append(row)
    return pd.DataFrame(rows)


def compute_correlation_matrix(cols: list[str] = PASSING_FACTORS) -> pd.DataFrame:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2010-01-01")
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in factor_correlation")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached, no new API calls expected)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    n = len(cols)
    sums = np.zeros((n, n))
    counts = np.zeros((n, n))
    for as_of, _fwd in snapshots:
        cs = _factor_cross_section(as_of, data, cols)
        cs = cs.dropna(subset=cols, how="any")
        if len(cs) < 10:
            continue
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                rho, _ = spearmanr(cs[cols[i]], cs[cols[j]])
                if not np.isnan(rho):
                    sums[i, j] += rho
                    counts[i, j] += 1

    avg = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    np.fill_diagonal(avg, 1.0)
    return pd.DataFrame(avg, index=cols, columns=cols), int(counts[0, 1]) if n > 1 else 0


def main():
    corr, n_snapshots_used = compute_correlation_matrix()
    print(f"\n=== Average per-snapshot Spearman correlation ({n_snapshots_used} snapshots with >=10 names) ===")
    print(corr.round(3).to_string())

    print(f"\n=== Redundancy check (|corr| >= {CORR_REDUNDANCY_THRESHOLD}) ===")
    pairs_flagged = []
    for i, a in enumerate(PASSING_FACTORS):
        for b in PASSING_FACTORS[i + 1:]:
            r = corr.loc[a, b]
            flag = abs(r) >= CORR_REDUNDANCY_THRESHOLD
            print(f"  {a} vs {b}: {r:+.3f}  {'FLAGGED (same family)' if flag else 'independent'}")
            if flag:
                pairs_flagged.append((a, b, r))
    return corr, pairs_flagged


if __name__ == "__main__":
    main()
