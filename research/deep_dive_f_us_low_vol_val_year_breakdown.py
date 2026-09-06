"""US-track diagnosis for `TRIALS_LEDGER.md`#151 (round392 EXPERIMENTAL verdict on
`f_us_low_vol` clean-universe 1b deep-dive): is the VAL-period (2020-12-31..2024-12-31)
+90%~+92% annualized return / beta -0.82 driven by a single regime year (2022 rate-hike
bear market), same failure family as `margin_debt_level_v1`#141-143?

**Single real backtest, no random-control redraw**: `run_one()`'s N_RANDOM_DRAWS=100 loop
(the actual heavy cost -- ~22min/combo, 136min for the full 6-combo job) is NOT needed
here. This script calls `run_long_short_us()` exactly ONCE (VAL period, cost 1x only,
same call `run_one()` makes internally) to get the real daily spread_return series, then
does year-by-year decomposition + leave-one-year-out on that single series. Expected
runtime: well under 5 minutes (cached prices, one backtest pass over ~1000 VAL days).

**Pre-registered judgment (hash-locked before running, same trichotomy as
`margin_debt_level_train_val_heterogeneity.py`#142 / round377's window-robustness style)**:
- Compute annualized return for each calendar year inside VAL, and for VAL-leave-2022-out
  (concatenate all non-2022 VAL daily spread returns, compound them, annualize over their
  actual day count).
- **CONFIRMED (2022-driven / regime-specific)**: leave-2022-out annualized return flips
  sign vs full-VAL, OR drops to <30% of full-VAL's annualized return magnitude.
- **REFUTED (not solely 2022-driven)**: leave-2022-out annualized return keeps the same
  sign AND retains >=60% of full-VAL's magnitude.
- **PARTIAL**: anything in between (30%-60% retained, same sign).
- Also report per-year breakdown for 2021/2022/2023/2024 (2020 has only 1 calendar day in
  VAL, excluded from per-year stats) for descriptive context, not part of the binding
  judgment (same spirit as #142's "VAL期四年獨立看" being informative, LOYO being binding).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import REBALANCE_DAYS, _decile_legs, run_long_short_us
from deep_dive_f_us_low_vol_clean_universe import load_clean_sample_with_factors
from validation import holdout
from validation import us_costs as us_costmod

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END
COST_MULT = 1  # only the base cost multiplier -- matches the flagged EXPERIMENTAL row (1x-3x all "stable direction" per #151, so 1x suffices for this diagnosis)


def _annualize(total_return: float, n_days: int) -> float:
    if n_days <= 0:
        return float("nan")
    return ((1 + total_return) ** (252 / n_days) - 1) * 100


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== f_us_low_vol clean-universe VAL-period year decomposition (TRIALS_LEDGER.md#151 follow-up) ===")
    data = load_clean_sample_with_factors()
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    result = run_long_short_us(data, calendar, VAL_START, VAL_END, REBALANCE_DAYS, slip, leg_fn=_decile_legs)
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

    print("\n--- leave-2022-out (binding judgment) ---")
    non_2022 = result[result["year"] != 2022]
    loo_total = float(np.prod(1 + non_2022["spread_return"])) - 1
    loo_ann = _annualize(loo_total, len(non_2022))
    print(f"  leave-2022-out: n_days={len(non_2022)}  total_return={loo_total*100:+.2f}%  annualized={loo_ann:+.2f}%")

    same_sign = (full_ann_ret > 0) == (loo_ann > 0)
    retained_frac = abs(loo_ann) / abs(full_ann_ret) if full_ann_ret != 0 else float("nan")
    print(f"  full VAL annualized={full_ann_ret:+.2f}%  vs leave-2022-out annualized={loo_ann:+.2f}%  "
          f"same_sign={same_sign}  retained_fraction={retained_frac:.2f}")

    if not same_sign or retained_frac < 0.30:
        verdict = "CONFIRMED (2022-driven / regime-specific)"
    elif same_sign and retained_frac >= 0.60:
        verdict = "REFUTED (not solely 2022-driven)"
    else:
        verdict = "PARTIAL"
    print(f"\n=== VERDICT: {verdict} ===")

    out = pd.DataFrame(year_rows)
    out.to_csv("data/deep_dive_f_us_low_vol_val_year_breakdown.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_val_year_breakdown.csv")

    pd.DataFrame([{
        "full_ann_return_pct": full_ann_ret, "loo_2022_ann_return_pct": loo_ann,
        "same_sign": same_sign, "retained_fraction": retained_frac, "verdict": verdict,
    }]).to_csv("data/deep_dive_f_us_low_vol_val_leave_2022_out.csv", index=False)
    print("saved data/deep_dive_f_us_low_vol_val_leave_2022_out.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return verdict


if __name__ == "__main__":
    main()
