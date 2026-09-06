"""US-track diagnosis for `TRIALS_LEDGER.md`#163 (round400 EXPERIMENTAL verdict on
`f_us_value_bm` clean-universe 1b deep-dive): is the VAL-period (2020-12-31..2024-12-31)
+141%~+142% annualized return / beta -0.171 driven by a single regime year, same
question already asked and answered for `f_us_low_vol` (#152, `deep_dive_f_us_low_vol_
val_year_breakdown.py`) but never asked for `f_us_value_bm` -- `US_MARATHON_STATE.md`
round402's "下一輪接手" names this exact gap: "#20/#21兩者之一做VAL期逐年分解...
value_bm尚未做過".

**Single real backtest, no random-control redraw**: same design as #152's script --
`run_long_short_us()` is called exactly ONCE (VAL period, cost 1x only) via a
`functools.partial(_decile_legs, factor_col=TARGET_FACTOR)` leg_fn (same binding
technique `run_one_value()` in `deep_dive_f_us_value_bm.py` already uses for its real-vs-
random comparison), not the 100-draw `run_one_value()` loop. Expected runtime: well
under 5 minutes (159-name clean universe, cached SEC EDGAR + price data, one backtest
pass over ~1000 VAL days).

**Pre-registered judgment (hash-locked before running, identical trichotomy to #152's
script for direct comparability)**:
- Compute annualized return for each calendar year inside VAL, and for VAL-leave-2022-out
  (concatenate all non-2022 VAL daily spread returns, compound them, annualize over their
  actual day count).
- **CONFIRMED (2022-driven / regime-specific)**: leave-2022-out annualized return flips
  sign vs full-VAL, OR drops to <30% of full-VAL's annualized return magnitude.
- **REFUTED (not solely 2022-driven)**: leave-2022-out annualized return keeps the same
  sign AND retains >=60% of full-VAL's magnitude.
- **PARTIAL**: anything in between (30%-60% retained, same sign).
- Also report per-year breakdown for 2021/2022/2023/2024 for descriptive context, not
  part of the binding judgment (same spirit as #152/#157's per-year tables).

**Zero new API calls**: `load_value_sample()` (clean-universe loader, round382/391's
already-populated on-disk SEC EDGAR cache) -- same cache-hit guarantee #391's clean-
universe 1b deep-dive already relied on.
"""
from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from deep_dive_f_us_low_vol import REBALANCE_DAYS, _decile_legs, run_long_short_us
from deep_dive_f_us_value_bm import TARGET_FACTOR
from us_factor_ic_value_clean_universe import load_value_sample
from validation import holdout
from validation import us_costs as us_costmod

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END
COST_MULT = 1  # matches #152's script -- #163's 1x-3x table already showed stable direction, 1x suffices for this diagnosis


def _annualize(total_return: float, n_days: int) -> float:
    if n_days <= 0:
        return float("nan")
    return ((1 + total_return) ** (252 / n_days) - 1) * 100


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== f_us_value_bm clean-universe VAL-period year decomposition (TRIALS_LEDGER.md#163 follow-up) ===")
    data, drop_reasons = load_value_sample()
    print(f"{len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    decile_fn = partial(_decile_legs, factor_col=TARGET_FACTOR)
    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    result = run_long_short_us(data, calendar, VAL_START, VAL_END, REBALANCE_DAYS, slip, leg_fn=decile_fn)
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
    out.to_csv("data/deep_dive_f_us_value_bm_val_year_breakdown.csv", index=False)
    print("\nsaved data/deep_dive_f_us_value_bm_val_year_breakdown.csv")

    pd.DataFrame([{
        "full_ann_return_pct": full_ann_ret, "loo_2022_ann_return_pct": loo_ann,
        "same_sign": same_sign, "retained_fraction": retained_frac, "verdict": verdict,
    }]).to_csv("data/deep_dive_f_us_value_bm_val_leave_2022_out.csv", index=False)
    print("saved data/deep_dive_f_us_value_bm_val_leave_2022_out.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return verdict


if __name__ == "__main__":
    main()
