"""US-track follow-up to round410 (`US_MARATHON_STATE.md`, `TRIALS_LEDGER.md`#174,
`US_LEADS.md`#20/#21). Round410 found the VAL-period short leg is dominated by a
small set of micro-cap tickers that have collapsed via repeated reverse splits
(median short-leg price $10-33, up to 49% of low_vol short-leg holdings <$5),
and named two concrete next steps: "(i)對短腿加價格/流動性下限篩選（例如排除股價
<$5或<$1的候選）重跑VAL期回測，看報酬量級是否顯著回落到合理範圍". This script
implements exactly that -- option (i).

**What this tests**: at each VAL-period rebalance, screen OUT any candidate whose
`adj_close` on that day is below a price floor from short-leg eligibility only
(long-leg selection is untouched -- round408's leg decomposition already showed
the long leg's VAL magnitude was unremarkable). If the short leg's annualized
return collapses toward a plausible range once penny/micro-cap names are
excluded, that supports round410's mechanism (2) and (with round410's borrow-
cost point) suggests the >100% VAL short-leg number is a data/tradability
artifact, not a genuine edge. Two floors tested (both named in the state file,
pre-registered, not tuned): $5 and $1.

**Design**: reuses `deep_dive_us_value_bm_lowvol_combo.py`'s `build_combo_universe()`
(same 159-name intersection) and `deep_dive_us_value_bm_lowvol_leg_decomposition.py`'s
`run_decomposed()` (long/short tracked separately) unchanged. Only the leg-selection
function is new: candidates below the floor are skipped when filling the short
decile (next-lowest-score eligible name takes their place), long decile selection
is the existing `_value_legs`/`_lowvol_legs` top-decile logic, unmodified. VAL
period only (that's where the anomaly is; TRAIN already looked reasonable per
round410), 1x cost, single real pass per (factor, floor) combo -- leg-composition
attribution, not a new cheap-gate hypothesis test.

**Zero new API calls**: same on-disk SEC EDGAR + price caches already populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from deep_dive_f_us_low_vol import REBALANCE_DAYS
from deep_dive_us_value_bm_lowvol_combo import (
    DECILE_FRACTION, LOWVOL_COL, VALUE_COL, build_combo_universe,
    _zscore_cross_section,
)
from deep_dive_us_value_bm_lowvol_leg_decomposition import run_decomposed, run_factor
from validation import holdout
from validation import us_costs as us_costmod

COST_MULT = 1
PRICE_FLOORS = [5.0, 1.0]
VAL_PERIOD = (holdout.TRAIN_END, holdout.VAL_END)


def _price_at(data, sid, as_of):
    df = data[sid]
    idx = df.index[df["date"] == as_of]
    if len(idx) == 0:
        return None
    p = df.loc[idx[0], "adj_close"]
    return None if pd.isna(p) else float(p)


def _legs_price_filtered(as_of, data, col, price_floor):
    scores = _zscore_cross_section(as_of, data, col)
    n = len(scores)
    if n < 10:
        return [], []
    order = sorted(scores.items(), key=lambda t: t[1], reverse=True)  # high->low
    k = max(1, round(n * DECILE_FRACTION))
    longs = [sid for sid, _ in order[:k]]  # long leg: unchanged, no floor
    ascending = [sid for sid, _ in reversed(order)]  # low score first (short candidates)
    shorts = []
    n_skipped = 0
    for sid in ascending:
        p = _price_at(data, sid, as_of)
        if p is None or p < price_floor:
            n_skipped += 1
            continue
        shorts.append(sid)
        if len(shorts) >= k:
            break
    return longs, shorts


def make_leg_fn(col, price_floor):
    def _fn(as_of, data):
        return _legs_price_filtered(as_of, data, col, price_floor)
    return _fn


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US short-leg price-floor check: round410 option (i) -- does filtering out sub-$floor "
          "candidates from short-leg eligibility bring VAL-period short-leg magnitude back to a plausible range? ===")
    data = build_combo_universe()
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section of 10.")
        return None

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    start, end = VAL_PERIOD
    print(f"\n=== VAL {start}..{end}, cost {COST_MULT}x, universe n={len(data)} ===")

    rows = []
    baselines = {
        # round410/#174 baseline (unfiltered short leg), for comparison -- not recomputed here
        "value_bm": {"floor": 0.0, "short_annualized_pct": 112.80},
        "low_vol": {"floor": 0.0, "short_annualized_pct": 75.91},
    }
    for name, col in [("value_bm", VALUE_COL), ("low_vol", LOWVOL_COL)]:
        for floor in PRICE_FLOORS:
            leg_fn = make_leg_fn(col, floor)
            print(f"\n-- {name}, price floor=${floor:.0f} --")
            r = run_factor(f"{name}_floor{floor:.0f}", leg_fn, data, calendar, start, end, slip)
            r["factor"] = name
            r["price_floor"] = floor
            rows.append(r)

    out = pd.DataFrame(rows)
    print("\n=== SUMMARY: short-leg annualized return, baseline (no floor, round410) vs filtered ===")
    for name in ["value_bm", "low_vol"]:
        base = baselines[name]["short_annualized_pct"]
        print(f"  {name:10s}: floor=$0 (baseline, round410) short_ann={base:+9.2f}%")
        for _, r in out[out["factor"] == name].iterrows():
            drop_pct = (1 - r["short_annualized_pct"] / base) * 100 if base != 0 else float("nan")
            print(f"  {name:10s}: floor=${r['price_floor']:.0f}  short_ann={r['short_annualized_pct']:+9.2f}%  "
                  f"long_ann={r['long_annualized_pct']:+9.2f}%  vs baseline: {drop_pct:+.1f}% relative drop")

    out.to_csv("data/us_short_leg_price_floor_check.csv", index=False)
    print("\nsaved data/us_short_leg_price_floor_check.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    main()
