"""US-track follow-up to round407's `us_universe_dispersion_check.py` (raw
per-ticker return dispersion REFUTED as the driver of #20/#21's implausible
VAL-period magnitude, `TRIALS_LEDGER.md`#171). `US_MARATHON_STATE.md`
round407's "下一輪接手" names the next step explicitly: "拆解decile long/short
腿分別看VAL期年化報酬，確認異常量級主要來自哪一腿".

**What this tests**: `_decile_legs`/`run_long_short_us` only ever report the
LONG-MINUS-SHORT spread. If the >100% annualized VAL spread for `f_us_value_bm`
(#20, TRIALS_LEDGER.md#163) and `f_us_low_vol` (#21, #165/#167) is driven almost
entirely by one leg (e.g. the short-decile stocks collapsing, or the long-decile
stocks rocketing), that points at a specific mechanism (e.g. short leg = the
2020-2024 period's worst-performing small/distressed names, an artifact of
`us_stratified_universe_sample.csv`'s stratification, not a genuine factor
edge). If both legs contribute comparably, that's weaker evidence either way.

**Design**: reuses `deep_dive_us_value_bm_lowvol_combo.py`'s `build_combo_universe()`
(159-name value_bm/low_vol intersection, same clean-universe cache) and
`_value_legs`/`_lowvol_legs` (identical decile selection, no re-derivation).
Adds a NEW backtest runner `run_decomposed()` that tracks LONG-only and
SHORT-only equity curves separately (long-only = holding just the top-decile
basket with its own turnover cost; short-only = holding just the short
position in the bottom-decile basket, P&L = -leg_return, with its own
borrow/short cost) instead of `run_long_short_us()`'s single combined spread
equity. Single real backtest pass per period (no 100-draw random control),
1x cost only -- this is leg attribution, not a new cheap-gate hypothesis test.

**Zero new API calls**: same on-disk SEC EDGAR + price caches round383/391/
400/404/406/407 already populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import (
    REBALANCE_DAYS, REPRESENTATIVE_PRICE, REPRESENTATIVE_SHARES, _load_market_df,
)
from deep_dive_us_value_bm_lowvol_combo import build_combo_universe, _value_legs, _lowvol_legs
from validation import holdout
from validation import us_costs as us_costmod

COST_MULT = 1  # single-pass leg attribution, not a cost-sensitivity sweep

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def run_decomposed(data, calendar, start, end, rebalance_days, slippage_bps, leg_fn) -> pd.DataFrame:
    """Same rebalance/cost/return mechanics as `run_long_short_us()`, but
    tracks LONG-only and SHORT-only equity curves separately instead of a
    single combined spread. long_equity = P&L of holding the long decile
    outright; short_equity = P&L of the short position alone (profits when
    the short-decile basket falls)."""
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    days = sorted(d for d in calendar if start <= d <= end)
    if not days:
        raise ValueError("empty calendar for the given date range")

    round_trip = us_costmod.round_trip_cost_pct(
        price=REPRESENTATIVE_PRICE, shares=REPRESENTATIVE_SHARES, slippage_bps=slippage_bps)
    short_round_trip = us_costmod.short_round_trip_cost_pct(
        price=REPRESENTATIVE_PRICE, holding_days=rebalance_days, shares=REPRESENTATIVE_SHARES, slippage_bps=slippage_bps)

    longs, shorts = [], []
    rows = []
    long_equity, short_equity = 1.0, 1.0
    for i, day in enumerate(days):
        if i % rebalance_days == 0:
            new_longs, new_shorts = leg_fn(day, data)
            if new_longs and new_shorts:
                turnover_long = 1.0 if not longs else len(set(new_longs) ^ set(longs)) / (2 * len(new_longs))
                turnover_short = 1.0 if not shorts else len(set(new_shorts) ^ set(shorts)) / (2 * len(new_shorts))
                long_equity *= (1 - turnover_long * round_trip)
                short_equity *= (1 - turnover_short * short_round_trip)
                longs, shorts = new_longs, new_shorts
        if i == 0:
            rows.append({"date": day, "long_equity": long_equity, "short_equity": short_equity})
            continue
        prev_day = days[i - 1]

        def leg_return(ids):
            rets = []
            for sid in ids:
                if sid not in idx:
                    continue
                df = idx[sid]
                if day not in df.index or prev_day not in df.index:
                    continue
                p0, p1 = df.loc[prev_day, "adj_close"], df.loc[day, "adj_close"]
                if p0 and p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
                    r = p1 / p0 - 1
                    if abs(r) > 0.50:  # same data-artifact guard as run_long_short_us's MAX_PLAUSIBLE_DAILY_RETURN
                        continue
                    rets.append(r)
            return float(np.mean(rets)) if rets else 0.0

        r_long = leg_return(longs)
        r_short = leg_return(shorts)
        long_equity *= (1 + r_long)
        short_equity *= (1 - r_short)  # short position profits when the basket falls
        rows.append({"date": day, "long_equity": long_equity, "short_equity": short_equity})

    return pd.DataFrame(rows)


def _annualize_equity(equity: pd.Series) -> float:
    n = len(equity)
    if n < 2:
        return float("nan")
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    return ((1 + total_ret) ** (252 / n) - 1) * 100


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min()) * 100


def run_factor(name, leg_fn, data, calendar, start, end, slip) -> dict:
    result = run_decomposed(data, calendar, start, end, REBALANCE_DAYS, slip, leg_fn)
    long_ann = _annualize_equity(result["long_equity"])
    short_ann = _annualize_equity(result["short_equity"])
    long_total = (result["long_equity"].iloc[-1] / result["long_equity"].iloc[0] - 1) * 100
    short_total = (result["short_equity"].iloc[-1] / result["short_equity"].iloc[0] - 1) * 100
    long_mdd = _max_drawdown(result["long_equity"])
    short_mdd = _max_drawdown(result["short_equity"])
    spread_ann = ((result["long_equity"].iloc[-1] * result["short_equity"].iloc[-1]) /
                  (result["long_equity"].iloc[0] * result["short_equity"].iloc[0])) ** (252 / len(result)) - 1
    spread_ann *= 100
    print(f"  {name:10s}: LONG  total={long_total:+9.2f}%  ann={long_ann:+9.2f}%  MDD={long_mdd:+7.2f}%")
    print(f"  {name:10s}: SHORT total={short_total:+9.2f}%  ann={short_ann:+9.2f}%  MDD={short_mdd:+7.2f}%")
    print(f"  {name:10s}: implied combined ann (long*short compounding) = {spread_ann:+9.2f}%")
    return {"factor": name, "long_total_return_pct": long_total, "long_annualized_pct": long_ann,
            "long_mdd_pct": long_mdd, "short_total_return_pct": short_total,
            "short_annualized_pct": short_ann, "short_mdd_pct": short_mdd,
            "combined_annualized_pct": spread_ann}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US leg decomposition: which side (long decile vs short decile) drives #20/#21's VAL-period magnitude ===")
    data = build_combo_universe()
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section of 10.")
        return None

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * COST_MULT
    rows = []
    for period_label, (start, end) in PERIODS.items():
        print(f"\n=== {period_label} {start}..{end}, cost {COST_MULT}x, universe n={len(data)} ===")
        for name, leg_fn in [("value_bm", _value_legs), ("low_vol", _lowvol_legs)]:
            r = run_factor(name, leg_fn, data, calendar, start, end, slip)
            r["period"] = period_label
            rows.append(r)

    print("\n=== SUMMARY (which leg dominates the VAL-period anomaly?) ===")
    for r in rows:
        if r["period"] != "VAL":
            continue
        long_mag, short_mag = abs(r["long_annualized_pct"]), abs(r["short_annualized_pct"])
        dominant = "LONG" if long_mag > short_mag else "SHORT"
        ratio = max(long_mag, short_mag) / min(long_mag, short_mag) if min(long_mag, short_mag) > 0 else float("inf")
        print(f"  {r['factor']:10s}: |long|={long_mag:.2f}%  |short|={short_mag:.2f}%  "
              f"dominant={dominant}  ratio={ratio:.2f}x")

    out = pd.DataFrame(rows)
    out.to_csv("data/deep_dive_us_value_bm_lowvol_leg_decomposition.csv", index=False)
    print("\nsaved data/deep_dive_us_value_bm_lowvol_leg_decomposition.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    main()
