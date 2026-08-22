"""AI 選股引擎 Phase A 步驟 3 -- composite scoring engine.

Only combines factors that passed factor_ic.py's Bonferroni-corrected bar
(FACTORS.md 2026-08-23): f_eps_growth, f_eps_surprise, f_revenue_surprise,
f_low_vol. A factor that failed IC testing gets weight 0, permanently --
this module has no code path that could accidentally include one.

**De-duplication (factor_correlation.py, 2026-08-22 user instruction):**
f_eps_growth and f_eps_surprise measure the same underlying "EPS
momentum/surprise" family (average cross-sectional Spearman correlation
+0.831 across 121 snapshots -- see FACTORS.md). Summing both into a
composite would double-count one signal, not combine two independent
ones. They are collapsed into a single combined EPS-family z-score
(average of their two peer z-scores) before scoring. f_revenue_surprise
(+0.249/+0.266 vs the EPS pair) and f_low_vol (-0.09 to -0.12 vs all
three) are genuinely close to orthogonal and each keep their own
independent weight.

**Result: 3 independent scoring components, not 4 raw factors:**
  1. eps_family  (avg z of f_eps_growth, f_eps_surprise)
  2. revenue_surprise  (z of f_revenue_surprise)
  3. low_vol  (z of f_low_vol)
Composite = equal-weighted mean of whichever of the 3 are available for a
given stock on a given date (missing components are skipped, not treated
as 0 -- a stock with 2 of 3 components available is scored on those 2, not
penalized for the third being NaN). Equal weighting, not IC-magnitude
weighting: differential weights would be a free parameter never validated
out-of-sample, and CONSTITUTION.md's anti-overfitting stance argues against
introducing one without evidence it helps.

**Peer normalization: z-scored WITHIN industry_category, not market-wide.**
Comparing a semiconductor stock's EPS growth against a shipping stock's
compares different economic regimes, not stock quality -- industry-relative
z-scoring is the standard cross-sectional practice for exactly this reason.
`industry_category` comes from TaiwanStockInfo, fetched via `_fetch()`
(membership/classification data, same precedent as universe.py -- not a
price/volume time series, so load_dev()'s VAL_END cap doesn't apply and
isn't needed; a stock's industry classification isn't a look-ahead risk).
**Known simplification, disclosed:** industry_category is treated as static
per stock (first non-null value seen), not point-in-time -- FinMind's
TaiwanStockInfo gives one row per stock, not a history of reclassifications.
If a stock changed industry group over the backtest period this is wrong
for the older dates; not expected to be common or long-run material, but
not verified either.

Peer groups with fewer than MIN_PEER_GROUP_SIZE names on a given date fall
back to whole-sample z-scoring for that date (too few peers to normalize
against, disclosed rather than silently producing a noisy z-score off 2-3
names).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import warnings

import numpy as np
import pandas as pd

from finmind_client import _fetch

# std() on a 1-name or all-NaN group is mathematically NaN by construction (ddof=1 on n<=1) -- the code
# below already checks for that (`std and not np.isnan(std) and std > 0`) and falls back correctly, but
# numpy/pandas still emits a RuntimeWarning on the way there. Silencing this specific, already-handled
# case -- not warnings in general -- so it doesn't flood stdout across thousands of per-date/per-group calls.
warnings.filterwarnings("ignore", message="invalid value encountered in subtract", category=RuntimeWarning)

EPS_FAMILY_COLS = ["f_eps_growth", "f_eps_surprise"]
INDEPENDENT_RAW_COLS = ["f_revenue_surprise", "f_low_vol"]
ALL_RAW_COLS_NEEDED = EPS_FAMILY_COLS + INDEPENDENT_RAW_COLS
SCORE_COMPONENTS = ["eps_family", "revenue_surprise", "low_vol"]
MIN_PEER_GROUP_SIZE = 5
MIN_COMPONENTS_FOR_RANKING = 2  # a composite built from just 1 of 3 components is too thin to rank/pick on;
# observed concretely with ETF tickers (e.g. 00844B, 00923) which have no real EPS/revenue data and end up
# scored on f_low_vol alone -- ETFs are structurally smoother than single stocks, so a low-vol-only score
# would systematically over-rank them for a reason that has nothing to do with stock-picking quality. Rows
# below this threshold are still returned by compute_scores_at_date() (with their real n_components visible)
# but excluded from anything that acts on the ranking (top-N export, backtest selection) via eligible_for_ranking().


def load_industry_map() -> dict[str, str]:
    """stock_id -> industry_category, static snapshot (see module docstring
    for the point-in-time caveat). Uses _fetch() directly, not load_dev(),
    same justification as universe.py: this is membership/classification
    metadata, not a price/volume time series -- there is nothing here that
    could leak future price information.
    """
    raw = _fetch("TaiwanStockInfo", "", "2000-01-01")
    if raw.empty:
        return {}
    dedup = raw.drop_duplicates(subset=["stock_id"], keep="first")
    return dict(zip(dedup["stock_id"], dedup["industry_category"]))


def _zscore_within_group(values: pd.Series, groups: pd.Series) -> pd.Series:
    """Cross-sectional z-score within each group value; groups smaller than
    MIN_PEER_GROUP_SIZE fall back to a whole-sample z-score for those rows.
    """
    out = pd.Series(index=values.index, dtype=float)
    counts = groups.value_counts()
    small_groups = set(counts[counts < MIN_PEER_GROUP_SIZE].index)
    small_mask = groups.isin(small_groups) | groups.isna()

    if small_mask.any():
        sub = values[small_mask]
        std = sub.std()
        out[small_mask] = (sub - sub.mean()) / std if std and not np.isnan(std) and std > 0 else np.nan

    for g, idx in groups[~small_mask].groupby(groups[~small_mask]).groups.items():
        sub = values.loc[idx]
        std = sub.std()
        out.loc[idx] = (sub - sub.mean()) / std if std and not np.isnan(std) and std > 0 else np.nan
    return out


def compute_scores_at_date(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str],
) -> pd.DataFrame:
    """One row per stock with a valid date==as_of row in `data`. Returns
    stock_id, industry, the 3 raw factor inputs, the 3 peer-z score
    components, composite (mean of available components), and rank.
    `data` is the same {stock_id: DataFrame with date/factor columns}
    structure factor_ic.py's load_sample_with_factors() produces -- this
    function does not fetch anything itself, keeping it testable/reusable
    against any already-prepared factor panel (live pipeline or backtest).
    """
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        row = {"stock_id": sid, "industry": industry_map.get(sid, "UNKNOWN")}
        for c in ALL_RAW_COLS_NEEDED:
            row[c] = d.loc[idx[0], c] if c in d.columns else np.nan
        rows.append(row)
    cs = pd.DataFrame(rows)
    if cs.empty:
        return cs

    groups = cs["industry"]
    eps_g_z = _zscore_within_group(cs["f_eps_growth"], groups)
    eps_s_z = _zscore_within_group(cs["f_eps_surprise"], groups)
    cs["eps_family"] = pd.concat([eps_g_z, eps_s_z], axis=1).mean(axis=1, skipna=True)
    cs["revenue_surprise"] = _zscore_within_group(cs["f_revenue_surprise"], groups)
    cs["low_vol"] = _zscore_within_group(cs["f_low_vol"], groups)

    cs["composite"] = cs[SCORE_COMPONENTS].mean(axis=1, skipna=True)
    cs["n_components"] = cs[SCORE_COMPONENTS].notna().sum(axis=1)
    cs = cs[cs["n_components"] > 0].copy()  # a stock with all 3 components missing can't be scored at all
    cs["rank"] = cs["composite"].rank(ascending=False, method="min").astype(int)
    return cs.sort_values("rank").reset_index(drop=True)


def eligible_for_ranking(cs: pd.DataFrame) -> pd.DataFrame:
    """Rows with enough real components to trust the composite for
    ranking/selection purposes (see MIN_COMPONENTS_FOR_RANKING docstring).
    Re-ranks within the eligible subset so rank 1 is always a real #1, not
    an artifact of thin-coverage rows that got filtered out after ranking.
    """
    out = cs[cs["n_components"] >= MIN_COMPONENTS_FOR_RANKING].copy()
    out["rank"] = out["composite"].rank(ascending=False, method="min").astype(int)
    return out.sort_values("rank").reset_index(drop=True)


def export_scores_json(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str],
    out_path: str, top_n: int | None = None,
) -> pd.DataFrame:
    """Writes the viewer-facing scores.json the App's 選股 tab reads.
    Schema documented inline in the written file's own "_meta" block so the
    App side and this side can never silently drift out of sync. Only
    eligible_for_ranking() rows are exported -- the viewer is a ranked pick
    list, not a raw data dump, so thin-coverage rows that can't be trusted
    for ranking don't belong in it.
    """
    cs = eligible_for_ranking(compute_scores_at_date(as_of, data, industry_map))
    if top_n:
        cs = cs.head(top_n)

    # json.dump() happily emits the bare (non-standard) token NaN for float('nan') -- Python's json module
    # accepts it on read but it is NOT valid JSON per spec, and JS's JSON.parse() correctly rejects it.
    # Found live in browser testing (2026-08-23): the App's fetch('scores.json') failed with "Unexpected
    # token 'N' ... is not valid JSON" the first time this was tried against real (NaN-containing) output.
    # Fix: replace NaN with None AFTER converting to plain Python dicts, not before -- a pandas float64
    # column cannot hold Python None (DataFrame.where(..., None) silently reverts it back to NaN), so the
    # replacement has to happen on the already-converted records, where a plain dict has no such constraint.
    records = cs.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None

    payload = {
        "_meta": {
            "as_of": as_of,
            "generated_by": "research/score.py",
            "score_components": SCORE_COMPONENTS,
            "eps_family_note": "avg peer-z of f_eps_growth + f_eps_surprise (correlated +0.831, "
                                "collapsed to avoid double-counting -- see FACTORS.md 2026-08-23)",
            "peer_group": "industry_category (TaiwanStockInfo), static classification, "
                           f"min group size {MIN_PEER_GROUP_SIZE} else whole-sample fallback",
            "min_components_for_ranking": MIN_COMPONENTS_FOR_RANKING,
            "disclaimer": "研究/教育用途，非投資建議。歷史回測不代表未來績效。樣本非全市場逐檔掃描"
                           "（見 FACTORS.md/STRATEGY_LOG.md 已知限制）。",
        },
        "scores": records,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False, default=float)
    return cs
