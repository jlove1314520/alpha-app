"""US-track follow-up to round412 (`US_MARATHON_STATE.md`, `TRIALS_LEDGER.md`#177,
`US_LEADS.md`#20/#21). Round412's price-floor filter (`us_short_leg_price_floor_check.py`)
REFUTED the "exclude penny-priced candidates" fix (short_ann went UP, not down --
because `adj_close` for these reverse-split death-spiral names is back-adjusted and
gets retroactively inflated to absurd historical levels, so a price floor applied to
`adj_close` doesn't actually screen out the names it's meant to). Round412 named the
next step explicitly: "(b)成本模型機制未被推翻，下一步改做round410選項(ii)：成本模型
隨股價/流動性反向縮放（而非固定$50代表性價格）".

**What this tests**: `run_decomposed()` (used by round408/410/412's leg-decomposition
work) prices the SHORT leg's stock-loan cost using a single flat
`REPRESENTATIVE_PRICE=$50` and `BORROW_FEE_ANNUAL_PCT=2.0`/yr for every short position,
regardless of what's actually in the basket. Round410 already showed the VAL-period
short leg for both factors is dominated by sub-$50 (often sub-$5, sub-$1 in a handful
of cases) micro-cap names that went through repeated reverse splits -- textbook
hard-to-borrow (HTB) profile, not the flat "easy borrow" 2%/yr the old model assumed.
This script replaces that flat borrow assumption with `validation.us_costs.
borrow_fee_annual_pct_tiered()` (new function, this round, grounded in published
HTB fee ranges -- see that function's docstring for sources/caveats), applied PER
STOCK using its actual `adj_close` price at the day the short is opened, not a single
representative $50. If the >100%/+75% VAL-period short-leg annualized returns
(round410 baseline) collapse toward a plausible range once a realistic HTB borrow
cost is charged, that supports round410's mechanism (ii) as the (or a major)
explanation for the implausible magnitude -- i.e. the "edge" is largely an artifact
of under-pricing the true cost of holding this specific short basket, not a real
factor return.

**Important asymmetry, stated up front so the result isn't over-read**: this does
NOT touch the `adj_close`-inflation problem round412 already found (back-adjusted
prices for reverse-split names are unreliable for a *price floor* screen, but they
are still usable here as an input to a *continuous* borrow-fee tier, since we are not
trying to exclude anything -- we're pricing the cost of borrowing whatever the
current-period nominal price implies, which is a materially different use of the
same imperfect column. This is disclosed, not silently assumed clean.

**Design**: reuses `deep_dive_us_value_bm_lowvol_combo.py`'s `build_combo_universe()`
(159-name intersection) and `deep_dive_us_value_bm_lowvol_leg_decomposition.py`'s
long/short decile selection (`_value_legs`/`_lowvol_legs`, unmodified -- this is a
cost-model change, not a selection-rule change). Adds `run_decomposed_tiered()`, a
copy of `run_decomposed()` with ONE change: the short leg's per-rebalance turnover
cost uses `mean(borrow_fee_annual_pct_tiered(price_i) for i in short_basket)` instead
of the flat `BORROW_FEE_ANNUAL_PCT` constant (long leg and all other cost components
unchanged). VAL period only (that's where the anomaly is), 1x slippage/commission,
single real pass per factor -- cost-model refinement, not a new cheap-gate hypothesis
test, does not consume bonferroni_n.

**Zero new API calls**: same on-disk SEC EDGAR + price caches already populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from deep_dive_f_us_low_vol import REBALANCE_DAYS, REPRESENTATIVE_PRICE, REPRESENTATIVE_SHARES
from deep_dive_us_value_bm_lowvol_combo import build_combo_universe, VALUE_COL, LOWVOL_COL
from deep_dive_us_value_bm_lowvol_leg_decomposition import _annualize_equity, _max_drawdown
from validation import holdout
from validation import us_costs as us_costmod

COST_MULT = 1  # single-pass cost-model comparison, not a sensitivity sweep
VAL_PERIOD = (holdout.TRAIN_END, holdout.VAL_END)

# Re-derive the same top/bottom decile selection used throughout #20/#21's leg work.
# Not imported directly because `_value_legs`/`_lowvol_legs` in the combo module
# return only the combined-score legs; the underlying single-factor zscore helper
# is what round408/410/412 actually used for the per-factor leg decomposition.
from deep_dive_us_value_bm_lowvol_combo import DECILE_FRACTION, _zscore_cross_section


def _legs(as_of, data, col):
    scores = _zscore_cross_section(as_of, data, col)
    n = len(scores)
    if n < 10:
        return [], []
    order = sorted(scores.items(), key=lambda t: t[1], reverse=True)
    k = max(1, round(n * DECILE_FRACTION))
    longs = [sid for sid, _ in order[:k]]
    shorts = [sid for sid, _ in order[-k:]]
    return longs, shorts


def _price_at(data, sid, as_of):
    df = data[sid]
    idx = df.index[df["date"] == as_of]
    if len(idx) == 0:
        return None
    p = df.loc[idx[0], "adj_close"]
    return None if pd.isna(p) else float(p)


def run_decomposed_tiered(data, calendar, start, end, rebalance_days, slippage_bps, leg_fn):
    """Same as `deep_dive_us_value_bm_lowvol_leg_decomposition.run_decomposed()`,
    except the SHORT leg's per-rebalance borrow cost is priced per-stock via
    `us_costs.borrow_fee_annual_pct_tiered()` using each name's actual price,
    instead of a flat `BORROW_FEE_ANNUAL_PCT` at a single `REPRESENTATIVE_PRICE`.
    Long leg cost unchanged (round408 already showed the long leg's magnitude is
    unremarkable -- this round only touches the short-cost assumption)."""
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    days = sorted(d for d in calendar if start <= d <= end)
    if not days:
        raise ValueError("empty calendar for the given date range")

    round_trip = us_costmod.round_trip_cost_pct(
        price=REPRESENTATIVE_PRICE, shares=REPRESENTATIVE_SHARES, slippage_bps=slippage_bps)

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

                # Per-stock tiered borrow fee, priced at THIS stock's actual price,
                # not the flat $50 representative price.
                short_prices = [_price_at(data, sid, day) for sid in new_shorts]
                short_borrow_pcts = [us_costmod.borrow_fee_annual_pct_tiered(p) for p in short_prices]
                mean_borrow_pct = float(np.mean(short_borrow_pcts)) if short_borrow_pcts else us_costmod.BORROW_FEE_ANNUAL_PCT
                short_round_trip_tiered = us_costmod.short_round_trip_cost_pct(
                    price=REPRESENTATIVE_PRICE, holding_days=rebalance_days, shares=REPRESENTATIVE_SHARES,
                    slippage_bps=slippage_bps, borrow_fee_annual_pct=mean_borrow_pct)
                short_equity *= (1 - turnover_short * short_round_trip_tiered)
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
                    if abs(r) > 0.50:  # same data-artifact guard as run_long_short_us
                        continue
                    rets.append(r)
            return float(np.mean(rets)) if rets else 0.0

        r_long = leg_return(longs)
        r_short = leg_return(shorts)
        long_equity *= (1 + r_long)
        short_equity *= (1 - r_short)
        rows.append({"date": day, "long_equity": long_equity, "short_equity": short_equity})

    return pd.DataFrame(rows)


def run_factor(name, leg_fn, data, calendar, start, end, slip) -> dict:
    result = run_decomposed_tiered(data, calendar, start, end, REBALANCE_DAYS, slip, leg_fn)
    long_ann = _annualize_equity(result["long_equity"])
    short_ann = _annualize_equity(result["short_equity"])
    long_mdd = _max_drawdown(result["long_equity"])
    short_mdd = _max_drawdown(result["short_equity"])
    print(f"  {name:10s}: LONG  ann={long_ann:+9.2f}%  MDD={long_mdd:+7.2f}%")
    print(f"  {name:10s}: SHORT ann={short_ann:+9.2f}%  MDD={short_mdd:+7.2f}%  (tiered HTB borrow cost)")
    return {"factor": name, "long_annualized_pct": long_ann, "long_mdd_pct": long_mdd,
            "short_annualized_pct": short_ann, "short_mdd_pct": short_mdd}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US short-leg cost-model check: round412 option (ii) -- does a price-tiered "
          "hard-to-borrow fee (vs flat 2%/yr @ $50) bring VAL-period short-leg magnitude "
          "back to a plausible range? ===")
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
        # round408/#172 baseline (flat 2%/yr @ $50 representative price), for comparison
        "value_bm": {"short_annualized_pct": 112.80},
        "low_vol": {"short_annualized_pct": 75.91},
    }
    for name, col in [("value_bm", VALUE_COL), ("low_vol", LOWVOL_COL)]:
        leg_fn = lambda as_of, data, col=col: _legs(as_of, data, col)
        r = run_factor(name, leg_fn, data, calendar, start, end, slip)
        rows.append(r)

    out = pd.DataFrame(rows)
    print("\n=== SUMMARY: short-leg annualized return, flat 2%/yr baseline vs price-tiered HTB borrow ===")
    for name in ["value_bm", "low_vol"]:
        base = baselines[name]["short_annualized_pct"]
        r = out[out["factor"] == name].iloc[0]
        drop_pct = (1 - r["short_annualized_pct"] / base) * 100 if base != 0 else float("nan")
        print(f"  {name:10s}: flat baseline short_ann={base:+9.2f}%  tiered short_ann={r['short_annualized_pct']:+9.2f}%  "
              f"relative drop={drop_pct:+.1f}%")

    out.to_csv("data/us_short_leg_tiered_borrow_check.csv", index=False)
    print("\nsaved data/us_short_leg_tiered_borrow_check.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    main()
