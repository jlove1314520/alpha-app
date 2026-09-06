"""US-track diagnostic: how much do `f_us_value_bm` (#20) and `f_us_low_vol`
(#21) decile long/short legs overlap during VAL, on the same clean stratified
universe? round400's US_MARATHON_STATE.md "下一輪接手" asked this directly --
both factors independently produced implausibly large VAL-period returns
(#20 +141%, #21 +90%~+230% across the val-year breakdown) on the same
248-name clean universe, while a fully-random leg draw on that same universe
lost money (#162). If the two factors' legs overlap heavily, that supports
"any non-random ranking rule harvests the same handful of extreme-dispersion
names in this universe" rather than each factor having an independent,
economically distinct edge.

**Single-variable, read-only diagnostic**: reuses `_decile_legs` and
`TARGET_FACTOR`/`DECILE_FRACTION`/`REBALANCE_DAYS` unchanged from
`deep_dive_f_us_low_vol.py` (low-vol) and `deep_dive_f_us_value_bm.py`
(value-bm, itself just a `partial(_decile_legs, factor_col="f_us_value_bm")`
of the same function). Zero new API calls -- both loaders hit existing
on-disk caches (`us_price_series` parquet / SEC EDGAR companyfacts json).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from deep_dive_f_us_low_vol import DECILE_FRACTION, REBALANCE_DAYS, _decile_legs
from deep_dive_f_us_low_vol import TARGET_FACTOR as LOWVOL_FACTOR
from deep_dive_f_us_value_bm import TARGET_FACTOR as VALUEBM_FACTOR
from us_factor_ic_lowvol_clean_universe import load_lowvol_sample
from us_factor_ic_value_clean_universe import load_value_sample
from validation import holdout

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END


def overlap_frac(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return float("nan")
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa)  # a is the smaller/reference leg in this script's calls


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    lowvol_data = load_lowvol_sample()
    value_data, _drop = load_value_sample()
    print(f"low_vol universe: {len(lowvol_data)} names; value_bm universe: {len(value_data)} names "
          f"(value_bm is a subset -- fewer names have usable SEC EDGAR book value)")

    shared_ids = sorted(set(lowvol_data) & set(value_data))
    print(f"shared names (in both factor samples): {len(shared_ids)}")

    calendar = sorted(set().union(*(set(d["date"].tolist()) for d in value_data.values())))
    val_days = [d for d in calendar if VAL_START < d <= VAL_END]
    if not val_days:
        print("ABORT: no VAL-period trading days found in the value_bm calendar")
        return None

    rebalance_days_in_val = val_days[::REBALANCE_DAYS]
    print(f"VAL period {VAL_START}..{VAL_END}: {len(val_days)} trading days, "
          f"{len(rebalance_days_in_val)} rebalance snapshots (every {REBALANCE_DAYS} days)\n")

    rows = []
    for as_of in rebalance_days_in_val:
        lv_long, lv_short = _decile_legs(as_of, lowvol_data, factor_col=LOWVOL_FACTOR)
        vb_long, vb_short = _decile_legs(as_of, value_data, factor_col=VALUEBM_FACTOR)
        if not (lv_long and vb_long):
            continue
        row = {
            "as_of": as_of,
            "lowvol_long_n": len(lv_long), "lowvol_short_n": len(lv_short),
            "valuebm_long_n": len(vb_long), "valuebm_short_n": len(vb_short),
            "long_long_overlap": overlap_frac(vb_long, lv_long),   # value_bm long is smaller universe -> reference
            "short_short_overlap": overlap_frac(vb_short, lv_short),
            "long_short_cross": overlap_frac(vb_long, lv_short),   # value's longs vs low_vol's shorts (should be ~independent-random if legs are unrelated)
            "short_long_cross": overlap_frac(vb_short, lv_long),
        }
        rows.append(row)
        print(f"  {as_of}: long-long={row['long_long_overlap']:.2f}  short-short={row['short_short_overlap']:.2f}  "
              f"long(vb)-short(lv) cross={row['long_short_cross']:.2f}  short(vb)-long(lv) cross={row['short_long_cross']:.2f}")

    if not rows:
        print("ABORT: no rebalance snapshot had both legs populated")
        return None

    import pandas as pd
    out = pd.DataFrame(rows)
    mean_ll = out["long_long_overlap"].mean()
    mean_ss = out["short_short_overlap"].mean()
    mean_cross = pd.concat([out["long_short_cross"], out["short_long_cross"]]).mean()

    # naive random-overlap baseline: if value_bm's long leg (size k_vb, drawn from
    # `value_data`'s universe, which is a subset of `shared_ids`) were drawn at random
    # from low_vol's shared universe, expected overlap fraction with a fixed low_vol
    # leg of size k_lv out of N shared names is k_lv/N.
    k_lv = out["lowvol_long_n"].iloc[0]
    n_shared = len(shared_ids)
    random_baseline = k_lv / n_shared if n_shared else float("nan")

    print("\n=== SUMMARY ===")
    print(f"mean long-long overlap (value_bm long vs low_vol long):   {mean_ll:.3f}")
    print(f"mean short-short overlap (value_bm short vs low_vol short): {mean_ss:.3f}")
    print(f"mean cross overlap (long vs opposite short, both directions): {mean_cross:.3f}")
    print(f"naive random-draw baseline overlap fraction: {random_baseline:.3f}  "
          f"(k_lowvol_leg={k_lv} / n_shared={n_shared})")
    same_side_ratio = (mean_ll + mean_ss) / 2 / random_baseline if random_baseline else float("nan")
    print(f"same-side overlap / random baseline ratio: {same_side_ratio:.2f}x")

    out.to_csv("data/us_leg_overlap_valuebm_lowvol.csv", index=False)
    print("\nsaved data/us_leg_overlap_valuebm_lowvol.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return out


if __name__ == "__main__":
    main()
