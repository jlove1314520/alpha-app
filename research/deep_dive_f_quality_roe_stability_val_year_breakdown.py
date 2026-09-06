"""TW-track diagnosis for `TRIALS_LEDGER.md`#156 (round396 PASS verdict, 1b deep-dive,
300-clean-sample rerun of `f_quality_roe_stability`): the round396 verdict flagged an
unresolved concern -- VAL(2021-2024) annualized return shrank from the 100-name sample's
+13.2%~13.4% to the 300-name sample's +0.98%~1.25% (~1/13), raising the question of
whether this much-smaller VAL edge is broad-based across the four VAL years or actually
concentrated in (i.e. an artifact of) a single calendar year. Same failure family as
`margin_debt_level_train_val_heterogeneity.py`#142 and
`deep_dive_f_us_low_vol_val_year_breakdown.py`#152, generalized here to a leave-EACH-year-out
sweep (no single year was pre-flagged as suspicious for this factor, unlike #152's 2022
rate-hike prior) rather than a single leave-2022-out test.

**Single real backtest, no random-control redraw**: `deep_dive_f_quality_roe_stability.py`'s
`run_one()` N_RANDOM_DRAWS=100 loop (the actual heavy cost) is NOT needed here. This script
calls `long_short_backtest.run_long_short()` exactly ONCE per period (VAL only, cost 1x --
matches the flagged row, and #156's own note that all 3 cost multipliers were "stable
direction" so 1x suffices for this diagnosis, same shortcut #152 took) to get the real daily
spread_return series, then does year-by-year decomposition + leave-one-year-out for each of
the 4 VAL calendar years (2021/2022/2023/2024) on that single series. Expected runtime:
a few minutes (cached raw data + factor computation, one backtest pass over ~1000 VAL days;
no new FinMind calls).

**Pre-registered judgment (hash-locked before running, same trichotomy as #142/#152)**:
- Compute annualized return for the full VAL period, and for VAL-leave-<year>-out (concatenate
  all VAL daily spread returns excluding that one calendar year, compound, annualize over
  actual day count) for each of 2021/2022/2023/2024 in turn.
- **CONFIRMED (single-year-driven / not broad-based)**: ANY leave-<year>-out annualized return
  flips sign vs full-VAL, OR drops to <30% of full-VAL's annualized return magnitude, for at
  least one year.
- **REFUTED (broad-based across VAL)**: ALL FOUR leave-<year>-out annualized returns keep the
  same sign AND retain >=60% of full-VAL's magnitude.
- **PARTIAL**: anything in between (some years retain 30%-60%, none flip sign or drop below 30%).
- Per-year breakdown itself is reported for descriptive context (same spirit as #142's "VAL期
  四年獨立看"), not part of the binding judgment -- the leave-one-year-out sweep is binding.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_quality_roe_stability import (
    TARGET_FACTOR, START_DATE, REBALANCE_DAYS, _decile_legs_factor,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from functools import partial
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

VAL_START, VAL_END = "2021-01-01", holdout.VAL_END
COST_MULT = 1  # matches the flagged EXPERIMENTAL->PASS row; #156 notes all 3x were "stable direction"


def _annualize(total_return: float, n_days: int) -> float:
    if n_days <= 0:
        return float("nan")
    return ((1 + total_return) ** (252 / n_days) - 1) * 100


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== f_quality_roe_stability 300-sample VAL-period year decomposition (TRIALS_LEDGER.md#156 follow-up) ===")
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_f_quality_roe_stability_val_year_breakdown")
    market_df = prepare_market_data(market_raw)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, same seed as round396)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    leg_fn = partial(_decile_legs_factor, factor_col=TARGET_FACTOR)
    result = lsb.run_long_short(data, market_df, None, VAL_START, VAL_END, REBALANCE_DAYS, leg_fn=leg_fn)
    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS  # restore module default before exit

    result["date"] = pd.to_datetime(result["date"])
    result["year"] = result["date"].dt.year

    full_total_ret = result["equity"].iloc[-1] / result["equity"].iloc[0] - 1
    full_ann_ret = _annualize(full_total_ret, len(result))
    print(f"\nfull VAL ({VAL_START}..{VAL_END}, {COST_MULT}x cost): n_days={len(result)}  "
          f"total_return={full_total_ret*100:+.2f}%  annualized={full_ann_ret:+.2f}%")

    print("\n--- per-year breakdown (descriptive, not the binding judgment) ---")
    year_rows = []
    for yr, g in result.groupby("year"):
        if len(g) < 5:
            print(f"  {yr}: n_days={len(g)} (too few, skipped from table)")
            continue
        yr_total = float(np.prod(1 + g["spread_return"])) - 1
        yr_ann = _annualize(yr_total, len(g))
        year_rows.append({"year": yr, "n_days": len(g), "total_return_pct": yr_total * 100, "annualized_return_pct": yr_ann})
        print(f"  {yr}: n_days={len(g)}  total_return={yr_total*100:+.2f}%  annualized={yr_ann:+.2f}%")

    print("\n--- leave-each-year-out sweep (binding judgment) ---")
    loyo_rows = []
    any_confirmed = False
    for yr in (2021, 2022, 2023, 2024):
        subset = result[result["year"] != yr]
        if len(subset) < 5:
            print(f"  leave-{yr}-out: n_days={len(subset)} (too few, skipped)")
            continue
        loo_total = float(np.prod(1 + subset["spread_return"])) - 1
        loo_ann = _annualize(loo_total, len(subset))
        same_sign = (full_ann_ret > 0) == (loo_ann > 0)
        retained_frac = abs(loo_ann) / abs(full_ann_ret) if full_ann_ret != 0 else float("nan")
        flagged = (not same_sign) or (retained_frac < 0.30)
        any_confirmed = any_confirmed or flagged
        loyo_rows.append({
            "leave_out_year": yr, "n_days": len(subset), "annualized_return_pct": loo_ann,
            "same_sign": same_sign, "retained_fraction": retained_frac, "flagged": flagged,
        })
        print(f"  leave-{yr}-out: n_days={len(subset)}  annualized={loo_ann:+.2f}%  "
              f"same_sign={same_sign}  retained_fraction={retained_frac:.2f}  flagged={flagged}")

    all_retain_60 = all(r["same_sign"] and r["retained_fraction"] >= 0.60 for r in loyo_rows)
    if any_confirmed:
        verdict = "CONFIRMED (single-year-driven / not broad-based)"
    elif all_retain_60:
        verdict = "REFUTED (broad-based across VAL)"
    else:
        verdict = "PARTIAL"
    print(f"\n=== VERDICT: {verdict} ===")

    out = pd.DataFrame(year_rows)
    out.to_csv("data/deep_dive_f_quality_roe_stability_val_year_breakdown.csv", index=False)
    print("\nsaved data/deep_dive_f_quality_roe_stability_val_year_breakdown.csv")

    loyo_out = pd.DataFrame(loyo_rows)
    loyo_out["full_ann_return_pct"] = full_ann_ret
    loyo_out["verdict"] = verdict
    loyo_out.to_csv("data/deep_dive_f_quality_roe_stability_val_leave_year_out.csv", index=False)
    print("saved data/deep_dive_f_quality_roe_stability_val_leave_year_out.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return verdict


if __name__ == "__main__":
    main()
