"""US-track contamination check for `f_us_gross_profitability` (round412's
CHEAP_PASS, `TRIALS_LEDGER.md`#191, deep-dive job `20260907-054341-a450`
finished with an implausibly large VAL result: ann_return=+33.77%,
beta=-0.084, alpha=+44.65%, random_control_percentile=100.0 -- almost
identical shape (large positive VAL alpha, near-zero/negative beta, 100.0
percentile) to #20 (`f_us_value_bm`) and #21 (`f_us_low_vol`) before those
were traced to death-spiral reverse-split microcaps dominating one leg.
`deep_dive_f_us_gross_profitability.py`'s own docstring flagged this exact
risk up front but only checked ticker-set overlap (5/84 = `AMTX`/`CIIT`/
`DVLT`/`MNTS`/`WULF`), not which LEG they land in or how much they
contribute -- this script closes that gap, per
`US_MARATHON_STATE.md` round427's explicit next-step: "若5檔已知污染
ticker沒有主導空頭腿，這會是US軌第一個真正跳脫#20/#21資料陷阱的候選；
若重蹈覆轍，比照#20/#21的診斷方法論（leg分解/leave-extreme-out/持股
名單查核）逐步收斂成因".

**Method -- pre-registered before running (hash-lock discipline, same
trichotomy as `deep_dive_f_us_low_vol_leave_extreme_out.py`)**:
1. Walk every VAL-period rebalance date, call `_decile_legs` (imported
   unchanged, bound to `f_us_gross_profitability` via the same
   `functools.partial` composition `deep_dive_f_us_gross_profitability.py`
   already uses) and record which of the 5 known contaminated tickers
   appear in the long leg vs the short leg each time.
2. Re-run the exact VAL 1x-cost backtest with the 5 contaminated tickers
   removed from `data` entirely (not just from one leg -- removed from the
   whole cross-section, same as #21's `deep_dive_f_us_low_vol_leave_extreme_out.py`
   removed its top-N-by-return set from the whole cross-section).
3. **Pre-registered verdict criteria (decided now, before seeing the
   excluded-sample number, identical thresholds to #21's precedent)**:
   - **CONFIRMED** (contamination is a major contributor): excluded-sample
     VAL 1x ann_return drops below 30% of the full-sample ann_return, OR
     flips sign.
   - **REFUTED**: excluded-sample keeps the same sign AND retains >=60% of
     the full-sample magnitude.
   - **PARTIAL**: between 30%-60% retained, same sign.
   This does not itself upgrade/downgrade #191's CHEAP_PASS -- it answers
   "is this the same #20/#21 trap or not", informing whether portfolio-level
   consideration of this factor needs a universe fix first.

**API cost**: zero new calls -- reuses `load_quality_sample()` verbatim
(same on-disk parquet/companyfacts cache `deep_dive_f_us_gross_profitability.py`
already hit).
"""
from __future__ import annotations

import sys
from collections import Counter
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_gross_profitability import KNOWN_CONTAMINATED_TICKERS, TARGET_FACTOR
from deep_dive_f_us_low_vol import REBALANCE_DAYS, _decile_legs, _load_market_df
from deep_dive_f_us_low_vol import run_long_short_us
from us_factor_ic_quality_clean_universe import load_quality_sample
from validation import holdout
from validation import us_costs as us_costmod

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END
COST_MULT = 1


def _run_variant(data: dict, calendar: list, slip: float) -> dict:
    decile_fn = partial(_decile_legs, factor_col=TARGET_FACTOR)
    result = run_long_short_us(data, calendar, VAL_START, VAL_END, REBALANCE_DAYS, slip, leg_fn=decile_fn)
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

    print("=== US contamination check: f_us_gross_profitability known death-spiral tickers ===\n")

    data, drop_reasons = load_quality_sample()
    contaminated_in_sample = sorted(KNOWN_CONTAMINATED_TICKERS & set(data.keys()))
    print(f"{len(data)} usable names; known contaminated tickers present: {contaminated_in_sample} "
          f"({len(contaminated_in_sample)}/{len(data)})\n")

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    # --- (1) leg placement walk across VAL rebalances ---
    decile_fn = partial(_decile_legs, factor_col=TARGET_FACTOR)
    val_days = sorted(d for d in calendar if VAL_START <= d <= VAL_END)
    rebalance_days = [val_days[i] for i in range(0, len(val_days), REBALANCE_DAYS)]

    long_hits, short_hits, absent = Counter(), Counter(), Counter()
    n_rebalances = 0
    for day in rebalance_days:
        longs, shorts = decile_fn(day, data)
        if not longs or not shorts:
            continue
        n_rebalances += 1
        long_set, short_set = set(longs), set(shorts)
        for t in contaminated_in_sample:
            if t in long_set:
                long_hits[t] += 1
            elif t in short_set:
                short_hits[t] += 1
            else:
                absent[t] += 1

    print(f"VAL rebalances walked: {n_rebalances}")
    print("Per-ticker leg placement (count of rebalances landing in each leg):")
    for t in contaminated_in_sample:
        print(f"  {t:8s} long={long_hits[t]:3d}  short={short_hits[t]:3d}  neither={absent[t]:3d}")
    total_long = sum(long_hits.values())
    total_short = sum(short_hits.values())
    print(f"\nTotal contaminated-ticker leg-slots: long={total_long}  short={total_short}")

    # --- (2) leave-contaminated-out backtest, VAL 1x cost ---
    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    print(f"\n=== (a) baseline: full {len(data)}-name sample, VAL {VAL_START}..{VAL_END}, {COST_MULT}x cost ===")
    r_full = _run_variant(data, calendar, slip)
    print(f"  ann_return={r_full['annualized_return_pct']:+.2f}%  beta={r_full['beta']:+.3f}")
    print("  (deep_dive job 20260907-054341-a450 recorded VAL 1x ann_return=+33.77%, this run should reproduce that closely)")

    data_excl = {t: d for t, d in data.items() if t not in KNOWN_CONTAMINATED_TICKERS}
    print(f"\n=== (b) contaminated-excluded: {len(data_excl)}-name sample, VAL {VAL_START}..{VAL_END}, {COST_MULT}x cost ===")
    r_excl = _run_variant(data_excl, calendar, slip)
    print(f"  ann_return={r_excl['annualized_return_pct']:+.2f}%  beta={r_excl['beta']:+.3f}")

    print("\n=== VERDICT (pre-registered thresholds, see module docstring) ===")
    full_ann = r_full["annualized_return_pct"]
    excl_ann = r_excl["annualized_return_pct"]
    same_sign = (full_ann > 0) == (excl_ann > 0)
    retained_frac = abs(excl_ann) / abs(full_ann) if full_ann != 0 else float("nan")
    if not same_sign or retained_frac < 0.30:
        verdict = "CONFIRMED -- contamination is a major contributor"
    elif same_sign and retained_frac >= 0.60:
        verdict = "REFUTED as primary mechanism -- result not primarily driven by the 5 known contaminated tickers"
    else:
        verdict = "PARTIAL -- between thresholds, both mechanisms likely contribute"
    print(f"Excluding {len(contaminated_in_sample)} known contaminated tickers: ann_return {full_ann:+.2f}% -> {excl_ann:+.2f}%  "
          f"same_sign={same_sign}  retained_fraction={retained_frac:.2f}")
    print(f"Short-leg concentration: {total_short}/{total_long + total_short} contaminated leg-slots landed in the SHORT leg")
    print(f"Verdict: {verdict}")

    out = pd.DataFrame([
        {**r_full, "variant": f"full_{len(data)}"},
        {**r_excl, "variant": f"excl_contaminated_{len(data_excl)}"},
    ])
    out.to_csv("data/deep_dive_f_us_gross_profitability_contamination_check.csv", index=False)
    print("\nsaved data/deep_dive_f_us_gross_profitability_contamination_check.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return {"full": r_full, "excl": r_excl, "verdict": verdict, "total_long": total_long, "total_short": total_short}


if __name__ == "__main__":
    main()
