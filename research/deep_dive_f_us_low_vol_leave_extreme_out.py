"""US-track leave-top-N-out concentration check for `f_us_low_vol` clean-universe
1b deep-dive (`TRIALS_LEDGER.md`#151, round386/392/393's EXPERIMENTAL verdict).

**Why this is this round's work unit (marathon round 394/395-window, US track)**:
round392 found the clean stratified universe's VAL-period (2020-12-31..2024-12-31)
decile long-short ann_return for `f_us_low_vol` implausibly large (+90%~+92%,
beta -0.82) vs the BAB/low-vol literature's typical single-digit-to-teens
annual alpha. round393's year-breakdown REFUTED the "single crisis year (2022)"
explanation -- all four VAL years independently exceed plausible magnitude, which
round393 explicitly flagged as *more* consistent with a concentration artifact
(a handful of extreme-return names dominating the low-vol decile legs every
rebalance) than a regime-specific one, and named this leave-top-N-out check
as the next step, reusing the exact methodology `deep_dive_f_us_value_bm_leave_extreme_out.py`
(round363, `US_LEADS.md`#17/#18) used for the unrelated `f_us_value_bm` factor on
the old `cached_ticker_ids()` pool -- same diagnostic question (is an extreme
result driven by a few outlier names or broadly distributed?), different pool
(this one is the clean 248-name stratified universe, not the old contaminated
one) and different factor.

**Method -- pre-registered before running (hash-lock discipline)**:
1. Compute each usable name's own VAL-period buy-and-hold total return from
   `adj_close` (first available price after TRAIN_END vs last by VAL_END) --
   same `own_val_return()` logic as round363's script, copied verbatim (not
   re-derived) to avoid subtle definitional drift between the two checks.
2. **Exclusion group = top N by that own-return ranking, N = round(7% of
   usable count)** -- round363 used a fixed count of 10 on 135 names (~7.4%);
   this generalizes to a fixed *percentage* instead of a fixed *count* so the
   two checks are comparable in relative terms across differently-sized pools,
   decided before inspecting this pool's actual return values (same anti
   p-hacking rationale as round363's docstring).
3. **Single real backtest per variant, no random-control redraw** (same
   speed shortcut as round393's `deep_dive_f_us_low_vol_val_year_breakdown.py`
   -- `run_one()`'s 100-draw random control is the expensive part of the full
   1b deep-dive (~22min/combo per round387's log), not needed to answer "is
   this driven by a few names", so this script calls `run_long_short_us()`
   directly, ONCE per variant, VAL period, 1x cost only). Expected runtime:
   well under 5 minutes for both variants combined.
4. **Pre-registered verdict criteria** (decided now, before seeing (b)'s
   number, same trichotomy shape as round363's #18 and round393's #152):
   - **CONFIRMED** (concentration is a major contributor): excluded-sample
     ann_return drops below 30% of the full-sample ann_return, OR flips sign.
   - **REFUTED** (not primarily concentration-driven): excluded-sample
     ann_return keeps the same sign AND retains >=60% of the full-sample
     magnitude -- points to a broadly-distributed pool bias instead (e.g.
     survivorship/stratification artifact in `us_stratified_universe_sample.csv`
     itself), which would need a different fix than name exclusion.
   - **PARTIAL**: between 30%-60% retained, same sign -- both mechanisms
     likely contribute, report as-is.
   This check does not reopen #151's EXPERIMENTAL verdict either way by
   itself; it exists to inform *which* follow-up (name-level exclusion vs.
   universe reconstruction) is worth pursuing next, same non-committal framing
   round363's script used for `f_us_value_bm`.

**API cost**: zero new calls -- reuses `load_clean_sample_with_factors()`
verbatim (all 248 tickers already `us_price_series()` parquet-cache hits per
round386/#145's own confirmation).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import REBALANCE_DAYS, _decile_legs, _load_market_df, run_long_short_us
from deep_dive_f_us_low_vol_clean_universe import load_clean_sample_with_factors
from validation import holdout
from validation import us_costs as us_costmod

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END
EXCLUDE_FRAC = 0.07  # pre-registered, matches round363's ~7% ratio on 135 names, see module docstring
COST_MULT = 1


def own_val_return(df: pd.DataFrame) -> float | None:
    """單檔股票自己在VAL期的買進持有總報酬（不是long-short回測），跟round363
    `deep_dive_f_us_value_bm_leave_extreme_out.py::own_val_return()`定義完全一致，
    僅換了資料來源，避免兩次檢查之間出現定義漂移。"""
    sub = df[(df["date"] > VAL_START) & (df["date"] <= VAL_END)].sort_values("date")
    if len(sub) < 2:
        return None
    p0 = sub["adj_close"].iloc[0]
    p1 = sub["adj_close"].iloc[-1]
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return None
    return float(p1 / p0 - 1)


def _run_variant(data: dict, calendar: list, slip: float) -> dict:
    result = run_long_short_us(data, calendar, VAL_START, VAL_END, REBALANCE_DAYS, slip, leg_fn=_decile_legs)
    ann_ret = lsb.annualized_return(result) * 100
    beta = float("nan")
    market_df, is_spy = _load_market_df()
    if not market_df.empty:
        beta, _alpha = lsb.capm_beta(result, market_df)
    total_ret = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100
    return {"n_names": len(data), "n_dates": len(result), "total_return_pct": total_ret,
            "annualized_return_pct": ann_ret, "beta": beta}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US leave-top-N-out concentration check: f_us_low_vol clean universe (TRIALS_LEDGER.md#151 follow-up) ===\n")

    data = load_clean_sample_with_factors()
    n_exclude = round(len(data) * EXCLUDE_FRAC)
    print(f"{len(data)} usable names, EXCLUDE_FRAC={EXCLUDE_FRAC} -> excluding top {n_exclude}\n")

    own_returns = {}
    for ticker, df in data.items():
        r = own_val_return(df)
        if r is not None:
            own_returns[ticker] = r

    ranked = sorted(own_returns.items(), key=lambda t: t[1], reverse=True)
    print(f"Own VAL-period (2020-2024) return ranking, top {n_exclude + 5} of {len(ranked)}:")
    for i, (ticker, r) in enumerate(ranked[:n_exclude + 5]):
        marker = " [EXCLUDED]" if i < n_exclude else ""
        print(f"  {i+1:2d}. {ticker:8s} {r*100:+10.1f}%{marker}")

    exclude_set = {t for t, _ in ranked[:n_exclude]}

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT

    print(f"\n=== (a) baseline: full {len(data)}-name sample, VAL {VAL_START}..{VAL_END}, {COST_MULT}x cost ===")
    r_full = _run_variant(data, calendar, slip)
    print(f"  ann_return={r_full['annualized_return_pct']:+.2f}%  beta={r_full['beta']:+.3f}")
    print(f"  (round392/#151 recorded VAL 1x ann_return in the +90%~+92% range, this run should reproduce that closely)")

    data_excl = {t: d for t, d in data.items() if t not in exclude_set}
    print(f"\n=== (b) top-{n_exclude}-excluded: {len(data_excl)}-name sample, VAL {VAL_START}..{VAL_END}, {COST_MULT}x cost ===")
    r_excl = _run_variant(data_excl, calendar, slip)
    print(f"  ann_return={r_excl['annualized_return_pct']:+.2f}%  beta={r_excl['beta']:+.3f}")

    print("\n=== VERDICT (pre-registered thresholds, see module docstring) ===")
    full_ann = r_full["annualized_return_pct"]
    excl_ann = r_excl["annualized_return_pct"]
    same_sign = (full_ann > 0) == (excl_ann > 0)
    retained_frac = abs(excl_ann) / abs(full_ann) if full_ann != 0 else float("nan")
    if not same_sign or retained_frac < 0.30:
        verdict = "CONFIRMED -- concentration in top winners is a major contributor"
    elif same_sign and retained_frac >= 0.60:
        verdict = "REFUTED as primary mechanism -- bias more broadly distributed across pool"
    else:
        verdict = "PARTIAL -- between thresholds, both mechanisms likely contribute"
    print(f"Excluding top-{n_exclude} own-return winners: ann_return {full_ann:+.2f}% -> {excl_ann:+.2f}%  "
          f"same_sign={same_sign}  retained_fraction={retained_frac:.2f}")
    print(f"Verdict: {verdict}")

    out = pd.DataFrame([
        {**r_full, "variant": f"full_{len(data)}"},
        {**r_excl, "variant": f"excl_top{n_exclude}"},
    ])
    out.to_csv("data/deep_dive_f_us_low_vol_leave_extreme_out.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_leave_extreme_out.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return {"full": r_full, "excl": r_excl, "verdict": verdict}


if __name__ == "__main__":
    main()
