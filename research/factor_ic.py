"""Cross-sectional Information Coefficient (IC) testing for factors.py.

IC at a snapshot date T = Spearman rank correlation, across all stocks with
a valid factor value at T, between that factor's value and the stock's
forward N-trading-day return starting at T. A factor with real predictive
information should show a mean IC clearly distinguishable from zero and
consistent in sign between train and validation; CONSTITUTION.md's honesty
rule applies here exactly as it does to a full strategy -- a factor that
doesn't clear the bar gets excluded, not quietly kept "just in case".

Three checks per factor, all must be satisfied to "pass":
  1. Non-trivial validation-period IC magnitude (not ~0 / noise-level).
  2. Same sign in train and validation (CONSTITUTION.md's "多子期間方向一致").
  3. Validation IC is distinguishable from a random-shuffle null distribution
     (the factor-testing analog of CONSTITUTION.md's random control group --
     shuffle which stock got which factor value within each cross-section,
     keep the return pairing, recompute; a real factor's IC should sit well
     outside where shuffled IC ends up).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factors import prepare_factors, FACTOR_COLUMNS
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe
from validation import holdout

FORWARD_HORIZON = 20  # trading days
SAMPLE_SEED = 20260822
SAMPLE_SIZE = 100
START_DATE = "2010-01-01"
SNAPSHOT_START = "2015-01-01"
N_SHUFFLES = 1000  # raised from 200 (2026-08-22 Cowork review) so a Bonferroni-corrected
# threshold near the 98-99th percentile is actually measurable -- 200 draws only resolves
# to 0.5% steps, too coarse once the family-wise-corrected bar sits above ~98%.
SHUFFLE_SEED = 20260822
BASE_ALPHA = 0.10  # the single-test significance level implied by the original 90th-percentile
# bar (percentile >= 90 <=> roughly a one-sided p < 0.10). Multiple-comparison correction below
# divides this by how many factors are being tested together in one pass, per Cowork's review
# (2026-08-22): testing 6 factors at once with an uncorrected single-test bar inflates the
# chance that at least one passes by luck alone.


@dataclass
class FactorICResult:
    factor: str
    train_mean_ic: float
    train_ic_ir: float
    val_mean_ic: float
    val_ic_ir: float
    val_hit_rate: float
    n_dates_train: int
    n_dates_val: int
    null_percentile: float  # where |val_mean_ic| sits vs the shuffled null distribution, 0-100
    required_percentile: float  # the Bonferroni-corrected bar this run needed to clear
    same_sign: bool
    passes: bool
    reasons: list[str] = field(default_factory=list)


def load_sample_with_factors(sample_ids: list[str], market_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- same tolerance as run_weinstein_unbiased.py
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < 260:  # need at least ~1yr for the 60-day windows to ever populate
            continue
        try:
            d = prepare_factors(sid, px, market_df, START_DATE)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: factor ERROR ({e}), dropping")
            continue
        out[sid] = d
    return out


def build_snapshots(calendar: list[str], start: str, end: str, horizon: int = FORWARD_HORIZON) -> list[tuple[str, str]]:
    """Non-overlapping (as_of_date, forward_date) pairs every `horizon`
    trading days, both dates required to be <= `end` (forward_date is what
    actually gets clipped -- as_of dates near the tail with no valid
    forward date inside the window are simply not included).
    """
    in_range = [d for d in calendar if start <= d <= end]
    pairs = []
    i = 0
    while i + horizon < len(in_range):
        pairs.append((in_range[i], in_range[i + horizon]))
        i += horizon
    return pairs


def _cross_section(
    factor_col: str, snapshot: tuple[str, str], data: dict[str, pd.DataFrame]
) -> tuple[list[str], np.ndarray, np.ndarray]:
    as_of, fwd = snapshot
    ids, factor_vals, returns = [], [], []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        fidx = d.index[d["date"] == fwd]
        if len(idx) == 0 or len(fidx) == 0:
            continue
        fv = d.loc[idx[0], factor_col]
        p0 = d.loc[idx[0], "adj_close"]
        p1 = d.loc[fidx[0], "adj_close"]
        if pd.isna(fv) or pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        ids.append(sid)
        factor_vals.append(float(fv))
        returns.append(float(p1 / p0 - 1))
    return ids, np.array(factor_vals), np.array(returns)


def evaluate_factor(
    factor_col: str, data: dict[str, pd.DataFrame], snapshots: list[tuple[str, str]],
    bonferroni_n: int = 1,
) -> FactorICResult:
    """bonferroni_n: how many factors are being tested together in this pass
    (the "family" for multiple-comparison correction). required_percentile
    is set to 100*(1 - BASE_ALPHA/bonferroni_n) -- e.g. testing 6 factors at
    once with BASE_ALPHA=0.10 requires clearing the 98.3rd percentile, not
    just the 90th. Pass bonferroni_n=1 (the default) only for a genuinely
    standalone single-factor test; any batch run should pass the real count.
    """
    train_ics, val_ics = [], []
    cross_sections = []  # (snapshot_index, factor_vals, returns) for the shuffle test, val period only
    for as_of, fwd in snapshots:
        ids, fv, ret = _cross_section(factor_col, (as_of, fwd), data)
        if len(fv) < 10:  # too few names this date to trust a cross-sectional rank correlation
            continue
        ic, _ = spearmanr(fv, ret)
        if np.isnan(ic):
            continue
        if as_of <= holdout.TRAIN_END:
            train_ics.append(ic)
        elif as_of <= holdout.VAL_END:
            val_ics.append(ic)
            cross_sections.append((fv, ret))

    train_mean = float(np.mean(train_ics)) if train_ics else float("nan")
    train_ir = float(np.mean(train_ics) / np.std(train_ics)) if len(train_ics) > 1 and np.std(train_ics) > 0 else float("nan")
    val_mean = float(np.mean(val_ics)) if val_ics else float("nan")
    val_ir = float(np.mean(val_ics) / np.std(val_ics)) if len(val_ics) > 1 and np.std(val_ics) > 0 else float("nan")
    val_hit_rate = float(np.mean([np.sign(x) == np.sign(val_mean) for x in val_ics])) if val_ics and val_mean != 0 else float("nan")

    # random-shuffle null: within each validation cross-section, shuffle factor values
    # against returns, recompute mean IC across all val cross-sections, repeat N times
    rng = random.Random(SHUFFLE_SEED)
    null_means = []
    for _ in range(N_SHUFFLES):
        shuffled_ics = []
        for fv, ret in cross_sections:
            perm = fv.copy()
            idx = list(range(len(perm)))
            rng.shuffle(idx)
            perm = perm[idx]
            ic, _ = spearmanr(perm, ret)
            if not np.isnan(ic):
                shuffled_ics.append(ic)
        if shuffled_ics:
            null_means.append(np.mean(shuffled_ics))

    if null_means and not np.isnan(val_mean):
        null_percentile = 100.0 * np.mean([abs(val_mean) > abs(m) for m in null_means])
    else:
        null_percentile = float("nan")

    same_sign = (not np.isnan(train_mean) and not np.isnan(val_mean)
                 and np.sign(train_mean) == np.sign(val_mean) and train_mean != 0)

    required_percentile = 100.0 * (1 - BASE_ALPHA / max(bonferroni_n, 1))

    reasons = []
    passes = True
    if np.isnan(val_mean) or abs(val_mean) < 0.02:
        passes = False
        reasons.append(f"val_mean_ic too small or undefined ({val_mean:.4f})")
    if not same_sign:
        passes = False
        reasons.append(f"train/val sign mismatch (train={train_mean:.4f}, val={val_mean:.4f})")
    if np.isnan(null_percentile) or null_percentile < required_percentile:
        passes = False
        reasons.append(
            f"not distinguishable from random-shuffle null at the Bonferroni-corrected bar "
            f"(percentile={null_percentile:.1f}, required>={required_percentile:.1f} for n={bonferroni_n})"
        )

    return FactorICResult(
        factor=factor_col, train_mean_ic=train_mean, train_ic_ir=train_ir,
        val_mean_ic=val_mean, val_ic_ir=val_ir, val_hit_rate=val_hit_rate,
        n_dates_train=len(train_ics), n_dates_val=len(val_ics),
        null_percentile=null_percentile, required_percentile=required_percentile,
        same_sign=same_sign, passes=passes, reasons=reasons,
    )


def sample_universe_ids(sample_size: int, seed: int = SAMPLE_SEED) -> list[str]:
    u = build_universe()
    rng = random.Random(seed)
    return rng.sample(list(u["stock_id"]), sample_size)


def run_ic_test(
    factor_columns: list[str],
    sample_ids: list[str],
    label: str,
    snapshot_start: str = SNAPSHOT_START,
    bonferroni_n: int | None = None,
) -> list[FactorICResult]:
    """Reusable driver: fetch+prepare the given sample, build snapshots from
    `snapshot_start` to VAL_END, evaluate every column in `factor_columns`
    with Bonferroni correction sized to `bonferroni_n` (defaults to
    len(factor_columns) -- i.e. correct for exactly the family being tested
    in this call, which is the right default for a from-scratch batch test).
    """
    if bonferroni_n is None:
        bonferroni_n = len(factor_columns)
    print(f"\n=== {label} ===")
    print(f"Sample: {len(sample_ids)} names, snapshot_start={snapshot_start}, "
          f"bonferroni_n={bonferroni_n} (required percentile >= {100*(1-BASE_ALPHA/bonferroni_n):.1f})")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in factor_ic")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, snapshot_start, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping {FORWARD_HORIZON}-trading-day snapshots, "
          f"{snapshot_start}..{holdout.VAL_END}")

    results = []
    for col in factor_columns:
        print(f"\nEvaluating {col}...")
        r = evaluate_factor(col, data, snapshots, bonferroni_n=bonferroni_n)
        results.append(r)
        print(f"  train: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
        print(f"  val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
        print(f"  null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
        print(f"  PASSES: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))

    print(f"\n=== {label} SUMMARY ===")
    for r in results:
        print(f"  {r.factor}: {'PASS' if r.passes else 'FAIL'}  val_ic={r.val_mean_ic:+.4f}  "
              f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return results


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(FACTOR_COLUMNS, sample_ids, "original 6-factor batch (Bonferroni n=6)")
    return results


if __name__ == "__main__":
    main()
