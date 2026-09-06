"""US-track portfolio-level combo test for `f_us_value_bm` (#20) x `f_us_low_vol`
(#21) -- both CHEAP_PASS-then-EXPERIMENTAL (never PASS) on the clean stratified
universe, per `MARATHON_PROTOCOL.md` 2026-09-03's mandate that the marathon's
main axis is now portfolio-level work (weighting-method iteration / downside
proof), not another single-factor test. `US_MARATHON_STATE.md` round404's
"下一輪接手" option (1) suggested a different-seed universe re-run instead, but
that needs a fresh stratified sample -- a multi-minute new-ticker fetch that
would require `run_detached.py submit`, and TW's heavy job
(`20260906-173133-fce9`) already holds the one-heavy-job-at-a-time slot this
round. This script needs **zero new API calls** (both factors' price/SEC data
are already on-disk cached from round383/391/400/404) and is designed as a
single real backtest pass per period (no 100-draw random control), so it stays
well under the 25-minute cycle budget while still advancing the portfolio axis.

**What this tests**: does a naive equal-weight cross-sectional z-score
combination of the two factors (pre-registered method: rank each factor
cross-sectionally at each rebalance date, z-score, sum with 1/N=0.5 weights --
no fitted weights, no train-time tuning) tame the implausible VAL-period
return magnitude either factor shows alone (#163: value_bm VAL 1x +141%~+142%
annualized; #165/#167 lineage: low_vol shows a comparable pattern), and/or
improve beta market-neutrality / max drawdown relative to either standalone
factor -- this is the downside-protection question `CLAUDE.md`'s "最高投資
原則" requires before any candidate can be taken seriously, not just "does
combining reduce variance of returns".

**Universe**: intersection of the two factors' already-loaded clean-universe
samples (`load_value_sample()`'s 159 names -- value_bm's cache is the binding
constraint since only 159/248 clean-universe tickers have usable SEC EDGAR
book-value history; low_vol itself covers all 248). All three legs below
(value_bm alone, low_vol alone, combo) are re-run on this SAME 159-name
intersection for a controlled comparison -- the low_vol standalone numbers
here will therefore NOT match #165/#167's 248-name figures, by design.

**Pre-registered read (not a PASS/FAIL cheap-gate verdict -- this is portfolio
construction, not a new hypothesis test)**: report ann_return, beta, alpha,
and max drawdown for TRAIN and VAL (1x cost only, single pass) for all three
legs. If combo's VAL magnitude is not diluted (stays similar to the average or
max of the two standalones) alongside beta staying non-neutral, that is
further evidence the >100% annualized VAL numbers are a pool/universe-dispersion
artifact (per round404's working hypothesis) rather than genuine additive edge
-- diversifying across two supposedly-independent signals should shrink an
artifact's magnitude, not preserve it, if the two factors' apparent edges were
really independent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import _load_market_df, run_long_short_us, REBALANCE_DAYS
from us_factor_ic_value_clean_universe import load_value_sample
from us_factors import prepare_us_factors, us_price_series
from validation import holdout
from validation import us_costs as us_costmod

VALUE_COL = "f_us_value_bm"
LOWVOL_COL = "f_us_low_vol"
DECILE_FRACTION = 0.10
COST_MULT = 1  # single-pass diagnostic, not a cost-sensitivity sweep

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def build_combo_universe() -> dict[str, pd.DataFrame]:
    value_data, drop_reasons = load_value_sample()
    print(f"value_bm clean-universe sample: {len(value_data)} usable (out of {len(value_data) + len(drop_reasons)})")

    combo: dict[str, pd.DataFrame] = {}
    n_lowvol_fail = 0
    for sid, vdf in value_data.items():
        px = us_price_series(sid)  # zero new API calls -- same cache us_factor_ic_value_clean_universe.py already hit
        if px.empty or len(px) < 260:
            n_lowvol_fail += 1
            continue
        lvdf = prepare_us_factors(px)[["date", LOWVOL_COL]]
        merged = vdf.merge(lvdf, on="date", how="inner")
        if merged[LOWVOL_COL].notna().sum() == 0:
            n_lowvol_fail += 1
            continue
        combo[sid] = merged
    print(f"combo universe (both factors non-empty): {len(combo)} names "
          f"({n_lowvol_fail} dropped for missing/short low_vol price history)")
    return combo


def _zscore_cross_section(as_of, data: dict[str, pd.DataFrame], col: str) -> dict[str, float]:
    ids, vals = [], []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        fv = d.loc[idx[0], col]
        if pd.isna(fv):
            continue
        ids.append(sid)
        vals.append(float(fv))
    if len(ids) < 10:
        return {}
    arr = np.array(vals)
    mu, sd = arr.mean(), arr.std()
    if sd == 0:
        return {}
    return {sid: (v - mu) / sd for sid, v in zip(ids, vals)}


def _legs_from_scores(scores: dict[str, float]) -> tuple[list[str], list[str]]:
    n = len(scores)
    if n < 10:
        return [], []
    order = sorted(scores.items(), key=lambda t: t[1], reverse=True)
    k = max(1, round(n * DECILE_FRACTION))
    return [sid for sid, _ in order[:k]], [sid for sid, _ in order[-k:]]


def _value_legs(as_of, data):
    return _legs_from_scores(_zscore_cross_section(as_of, data, VALUE_COL))


def _lowvol_legs(as_of, data):
    return _legs_from_scores(_zscore_cross_section(as_of, data, LOWVOL_COL))


def _combo_legs(as_of, data):
    """Pre-registered 1/N weighting: 0.5*z(value_bm) + 0.5*z(low_vol), no fitted weights."""
    z_value = _zscore_cross_section(as_of, data, VALUE_COL)
    z_lowvol = _zscore_cross_section(as_of, data, LOWVOL_COL)
    shared = set(z_value) & set(z_lowvol)
    if len(shared) < 10:
        return [], []
    combo_scores = {sid: 0.5 * z_value[sid] + 0.5 * z_lowvol[sid] for sid in shared}
    return _legs_from_scores(combo_scores)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min()) * 100  # negative %, e.g. -34.5


def run_leg(name, leg_fn, data, calendar, market_df, start, end, slip):
    result = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slip, leg_fn=leg_fn)
    ann_ret = lsb.annualized_return(result) * 100
    total_ret = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100
    mdd = _max_drawdown(result["equity"])
    beta, alpha_ann = (float("nan"), float("nan"))
    if not market_df.empty:
        beta, alpha_ann = lsb.capm_beta(result, market_df)
        alpha_ann *= 100
    print(f"  {name:10s}: total_return={total_ret:+8.2f}%  ann_return={ann_ret:+8.2f}%  "
          f"MDD={mdd:+7.2f}%  beta={beta:+.3f}  alpha={alpha_ann:+.2f}%")
    return {"leg": name, "total_return_pct": total_ret, "annualized_return_pct": ann_ret,
            "mdd_pct": mdd, "beta": beta, "annualized_alpha_pct": alpha_ann}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US portfolio-axis combo test: f_us_value_bm x f_us_low_vol (1/N z-score combination) ===")
    data = build_combo_universe()
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section of 10.")
        return None

    market_df, is_spy = _load_market_df()
    print(f"market benchmark: {'SPY' if is_spy else 'NONE (fetch failed)'}")

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    rows = []
    for period_label, (start, end) in PERIODS.items():
        print(f"\n=== {period_label} {start}..{end}, cost {COST_MULT}x, universe n={len(data)} ===")
        for name, leg_fn in [("value_bm", _value_legs), ("low_vol", _lowvol_legs), ("combo", _combo_legs)]:
            r = run_leg(name, leg_fn, data, calendar, market_df, start, end, slip)
            r["period"] = period_label
            rows.append(r)

    print("\n=== SUMMARY (does 1/N combination dilute the standalone magnitude, or preserve it?) ===")
    val_rows = {r["leg"]: r for r in rows if r["period"] == "VAL"}
    if len(val_rows) == 3:
        max_standalone = max(abs(val_rows["value_bm"]["annualized_return_pct"]),
                              abs(val_rows["low_vol"]["annualized_return_pct"]))
        combo_ann = abs(val_rows["combo"]["annualized_return_pct"])
        diluted = combo_ann < 0.5 * max_standalone
        print(f"  VAL |combo ann_return|={combo_ann:.2f}%  vs max(|value_bm|,|low_vol|)={max_standalone:.2f}%  "
              f"-> {'DILUTED (<50%)' if diluted else 'PRESERVED (>=50%, consistent with shared-artifact hypothesis)'}")
        print(f"  VAL beta: value_bm={val_rows['value_bm']['beta']:+.3f}  low_vol={val_rows['low_vol']['beta']:+.3f}  "
              f"combo={val_rows['combo']['beta']:+.3f}")
        print(f"  VAL MDD:  value_bm={val_rows['value_bm']['mdd_pct']:+.2f}%  low_vol={val_rows['low_vol']['mdd_pct']:+.2f}%  "
              f"combo={val_rows['combo']['mdd_pct']:+.2f}%")

    out = pd.DataFrame(rows)
    out.to_csv("data/deep_dive_us_value_bm_lowvol_combo.csv", index=False)
    print("\nsaved data/deep_dive_us_value_bm_lowvol_combo.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    main()
