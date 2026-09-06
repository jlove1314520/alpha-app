"""US-track follow-up to round408's leg decomposition (`TRIALS_LEDGER.md`#172,
`deep_dive_us_value_bm_lowvol_leg_decomposition.py`): VAL-period magnitude for
both `f_us_value_bm` (#20) and `f_us_low_vol` (#21) is driven almost entirely
by the SHORT leg (11.5x/19.0x the long leg's magnitude). `US_MARATHON_STATE.md`
round408's "下一輪接手" names two untested candidate mechanisms:
  (a) the short decile keeps re-selecting the same batch of structurally
      collapsing names (stratified-universe composition artifact), or
  (b) the flat $50 REPRESENTATIVE_PRICE cost-model simplification misprices
      shorting stocks that have fallen to single-digit dollar prices (borrow
      fee / margin-call / liquidity-exhaustion costs not reflected).

**What this tests**: for every VAL-period rebalance date, record the actual
short-decile ticker list and their `adj_close` price at that date, for both
factors, using the SAME `_value_legs`/`_lowvol_legs` selection functions and
159-name combo universe as round408 (no re-derivation). From that:
  - price distribution of short-leg holdings (median, % below $50/$10/$5) ->
    directly answers (b): is REPRESENTATIVE_PRICE=$50 a reasonable stand-in?
  - per-ticker frequency count across all VAL rebalances -> directly answers
    (a): is the short leg dominated by a small repeatedly-shorted set, or
    does it rotate through many different names?

**Zero new API calls**: reuses `build_combo_universe()` (round383/391/400/
404/406/407/408's on-disk SEC EDGAR + price caches). Not a backtest -- pure
holdings/price bookkeeping, single pass, no cost mechanics, no random control.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from deep_dive_f_us_low_vol import REPRESENTATIVE_PRICE, REBALANCE_DAYS
from deep_dive_us_value_bm_lowvol_combo import build_combo_universe, _value_legs, _lowvol_legs
from validation import holdout

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END


def collect_short_leg_holdings(data, calendar, leg_fn, start, end, rebalance_days):
    """Returns list of (rebalance_date, ticker, price) for every short-leg
    holding at every rebalance date in [start, end]."""
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    days = sorted(d for d in calendar if start < d <= end)
    rows = []
    for i, day in enumerate(days):
        if i % rebalance_days != 0:
            continue
        _longs, shorts = leg_fn(day, data)
        for sid in shorts:
            if sid not in idx or day not in idx[sid].index:
                continue
            price = idx[sid].loc[day, "adj_close"]
            if pd.isna(price):
                continue
            rows.append({"rebalance_date": day, "ticker": sid, "price": float(price)})
    return rows


def report(name, rows):
    if not rows:
        print(f"\n{name}: no short-leg holdings recorded (empty).")
        return None
    df = pd.DataFrame(rows)
    n_rebalances = df["rebalance_date"].nunique()
    n_unique_tickers = df["ticker"].nunique()
    n_total_holdings = len(df)
    prices = df["price"]

    pct_below_50 = (prices < 50).mean() * 100
    pct_below_10 = (prices < 10).mean() * 100
    pct_below_5 = (prices < 5).mean() * 100
    pct_below_1 = (prices < 1).mean() * 100

    freq = Counter(df["ticker"])
    top10 = freq.most_common(10)
    # concentration: what share of all short-leg holding-instances are the top-10 most frequent tickers
    top10_share = sum(c for _, c in top10) / n_total_holdings * 100

    print(f"\n=== {name}: short-leg holdings, VAL period ({VAL_START} exclusive .. {VAL_END}) ===")
    print(f"  rebalances={n_rebalances}  unique tickers ever shorted={n_unique_tickers}  "
          f"total holding-instances={n_total_holdings}")
    print(f"  price distribution: median=${prices.median():.2f}  mean=${prices.mean():.2f}  "
          f"min=${prices.min():.2f}  max=${prices.max():.2f}")
    print(f"  REPRESENTATIVE_PRICE=${REPRESENTATIVE_PRICE:.0f} vs actual: "
          f"{pct_below_50:.1f}% of holding-instances priced <$50, "
          f"{pct_below_10:.1f}% <$10, {pct_below_5:.1f}% <$5, {pct_below_1:.1f}% <$1")
    print(f"  concentration: top-10 most-frequently-shorted tickers account for "
          f"{top10_share:.1f}% of all holding-instances (out of {n_unique_tickers} unique)")
    print(f"  top 10 by frequency: " + ", ".join(f"{t}({c}/{n_rebalances})" for t, c in top10))

    return {
        "factor": name, "n_rebalances": n_rebalances, "n_unique_tickers": n_unique_tickers,
        "n_total_holdings": n_total_holdings, "price_median": float(prices.median()),
        "price_mean": float(prices.mean()), "price_min": float(prices.min()),
        "price_max": float(prices.max()), "pct_below_50": pct_below_50,
        "pct_below_10": pct_below_10, "pct_below_5": pct_below_5, "pct_below_1": pct_below_1,
        "top10_share_pct": top10_share,
        "top10_tickers": ";".join(f"{t}:{c}" for t, c in top10),
    }


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US short-leg holdings/price check: VAL-period #20/#21 short-decile composition ===")
    data = build_combo_universe()
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section of 10.")
        return None

    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    summary_rows = []
    detail_rows = []
    for name, leg_fn in [("value_bm", _value_legs), ("low_vol", _lowvol_legs)]:
        rows = collect_short_leg_holdings(data, calendar, leg_fn, VAL_START, VAL_END, REBALANCE_DAYS)
        for r in rows:
            r2 = dict(r)
            r2["factor"] = name
            detail_rows.append(r2)
        s = report(name, rows)
        if s:
            summary_rows.append(s)

    if summary_rows:
        out = pd.DataFrame(summary_rows)
        out.to_csv("data/us_short_leg_holdings_summary.csv", index=False)
        print("\nsaved data/us_short_leg_holdings_summary.csv")
    if detail_rows:
        det = pd.DataFrame(detail_rows)
        det.to_csv("data/us_short_leg_holdings_detail.csv", index=False)
        print("saved data/us_short_leg_holdings_detail.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return summary_rows


if __name__ == "__main__":
    main()
