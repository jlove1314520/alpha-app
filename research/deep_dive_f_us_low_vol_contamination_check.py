"""US-track contamination check for `f_us_low_vol` (#21) -- same named-blacklist
method as `deep_dive_f_us_value_bm_contamination_check.py` (#20) and
`deep_dive_f_us_gross_profitability_contamination_check.py` (#23, CONFIRMED).
See that value_bm sibling script's docstring for why this is a real gap
(round363/394's leave-extreme-out used a magnitude-based, not named, exclusion
set) rather than a reskin of an already-answered question -- identical
reasoning applies here, with round410's `us_short_leg_holdings_check.py`
having found `WATT`/`CRWD`/`LEE`/`AMTX` at 51/51 rebalances (100% of the VAL
period) for this exact factor's short leg.

Does not reopen `#21`'s FAIL verdict either way (already closed, round425,
resource-limited). Answers whether the named-blacklist method implicates the
same root cause here as it did for `#23`.

**API cost**: zero new calls -- pure-price factor, all 248 tickers already
`us_price_series()` parquet-cache hits (same cache
`deep_dive_f_us_low_vol_clean_universe.py` already hit).
"""
from __future__ import annotations

from collections import Counter
from functools import partial
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import REBALANCE_DAYS, TARGET_FACTOR, _decile_legs, _load_market_df, run_long_short_us
from deep_dive_f_us_low_vol_clean_universe import load_clean_sample_with_factors
from us_contamination_blacklist import KNOWN_CONTAMINATED_TICKERS
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

    print("=== US contamination check: f_us_low_vol (#21) known death-spiral tickers ===\n")

    data = load_clean_sample_with_factors()
    contaminated_in_sample = sorted(KNOWN_CONTAMINATED_TICKERS & set(data.keys()))
    print(f"{len(data)} usable names; known contaminated tickers present: {contaminated_in_sample} "
          f"({len(contaminated_in_sample)}/{len(data)})\n")

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

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

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    print(f"\n=== (a) baseline: full {len(data)}-name sample, VAL {VAL_START}..{VAL_END}, {COST_MULT}x cost ===")
    r_full = _run_variant(data, calendar, slip)
    print(f"  ann_return={r_full['annualized_return_pct']:+.2f}%  beta={r_full['beta']:+.3f}")

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
        verdict = "REFUTED as primary mechanism -- result not primarily driven by the known contaminated tickers"
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
    out.to_csv("data/deep_dive_f_us_low_vol_contamination_check.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_contamination_check.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return {"full": r_full, "excl": r_excl, "verdict": verdict, "total_long": total_long, "total_short": total_short}


if __name__ == "__main__":
    main()
