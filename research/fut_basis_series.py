"""Near-month futures vs. spot index basis series (期現價差).

Foundation module for the basis-hypothesis family per MARATHON_PROTOCOL.md 3
("期貨（技術面出發）... 期現價差（basis，近月期貨 vs 現貨指數）"). This is
the second infra step for that family -- fut_probe_spot_index.py (round 66)
established the spot-index data source (`TaiwanStockPrice`/`TAIEX`, plain
OHLC, NOT the total-return index `TaiwanStockTotalReturnIndex`). This module
joins that spot series against the near-month (front-month) futures close
from continuous_contract.py and computes basis = fut_close - spot_close.

Design notes:
- "Near-month" reuses continuous_contract.py's front_month_series() verbatim
  (smallest contract_date with a non-null close that day) -- per
  MARATHON_PROTOCOL.md 5b instruction to reuse the existing definition, not
  redesign it.
- Uses RAW (unadjusted) futures close, not adj_close. Basis is a real-world
  same-day tradeable-price snapshot (actual close vs actual spot on that
  date); the ratio back-adjustment in continuous_contract.py exists to make
  a *return series* splice cleanly across rollovers, which is a different
  purpose and would distort a same-day basis snapshot for no reason (the
  adjustment factor is 1.0 for the most-recent segment anyway, but earlier
  segments get scaled, which is wrong for a spot-vs-future same-day diff).
- Inner join on date: any date where either side is missing a quote (holiday
  calendar mismatch, data gap) is dropped, not filled/guessed. Coverage is
  reported explicitly by the __main__ probe below, not assumed from the
  round-66 "row count coincidence" (6185 vs 6185) -- that coincidence in row
  *counts* does not by itself prove the trading-day *calendars* line up
  date-for-date, which is what actually matters for an inner join.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import FULL_HISTORY_END, FULL_HISTORY_START, build_continuous_series
from finmind_client import load_dev
from validation import holdout


def build_basis_series(
    contract: str = "TX",
    start_date: str = FULL_HISTORY_START,
    end_date: str = FULL_HISTORY_END,
) -> pd.DataFrame:
    """One row per date (inner join): near-month futures raw close, TAIEX
    spot close, basis = fut_close - spot_close (positive = futures trading
    above spot / premium; negative = discount), and basis_pct = basis /
    spot_close for cross-period comparability (TAIEX level itself has grown
    ~5x over the full history range, so raw basis points are not comparable
    across the full sample without normalizing).
    """
    fut, _skipped = build_continuous_series(contract, start_date, end_date)
    holdout.assert_no_holdout_leakage(fut, context="fut_basis_series: front-month futures")
    fut = fut[["date", "contract_date", "close"]].rename(columns={"close": "fut_close"})

    spot = load_dev("TaiwanStockPrice", "TAIEX", start_date=start_date, end_date=end_date)
    spot["date"] = pd.to_datetime(spot["date"])
    holdout.assert_no_holdout_leakage(spot, context="fut_basis_series: TAIEX spot")
    spot = spot[["date", "close"]].rename(columns={"close": "spot_close"})

    merged = fut.merge(spot, on="date", how="inner")
    merged["basis"] = merged["fut_close"] - merged["spot_close"]
    merged["basis_pct"] = merged["basis"] / merged["spot_close"]
    return merged.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    # Manual spot-check + coverage/sanity probe, same discipline as
    # continuous_contract.py's __main__ block (MARATHON_PROTOCOL.md 1c).
    fut, _ = build_continuous_series()
    basis = build_basis_series()

    n_fut = len(fut)
    n_basis = len(basis)
    print(f"front-month futures raw rows: {n_fut}")
    print(f"basis series rows (inner join w/ TAIEX spot): {n_basis}")
    print(f"join coverage: {n_basis / n_fut:.4%}")

    unmatched = sorted(set(fut["date"]) - set(basis["date"]))
    print(f"futures dates with no matching spot row: {len(unmatched)}")
    if unmatched:
        print(f"  first 10 unmatched dates: {unmatched[:10]}")
        print(f"  last 10 unmatched dates: {unmatched[-10:]}")

    print("\nbasis (absolute, index points) distribution:")
    print(basis["basis"].describe())
    print("\nbasis_pct distribution:")
    print(basis["basis_pct"].describe())

    n_premium = (basis["basis"] > 0).sum()
    n_discount = (basis["basis"] < 0).sum()
    n_flat = (basis["basis"] == 0).sum()
    print(f"\npremium (fut>spot) days: {n_premium} ({n_premium/n_basis:.2%})")
    print(f"discount (fut<spot) days: {n_discount} ({n_discount/n_basis:.2%})")
    print(f"exactly flat days: {n_flat}")

    # Exploratory outlier flag, not a hard-coded pass/fail threshold -- just
    # surfaces anything that warrants an eyeball look before trusting the
    # series as clean.
    extreme = basis[basis["basis_pct"].abs() > 0.05]
    print(f"\nrows with |basis_pct| > 5%: {len(extreme)}")
    if not extreme.empty:
        print(extreme[["date", "contract_date", "fut_close", "spot_close", "basis", "basis_pct"]]
              .head(15).to_string(index=False))

    n_null_basis = basis["basis"].isna().sum()
    n_zero_spot = (basis["spot_close"] <= 0).sum()
    n_zero_fut = (basis["fut_close"] <= 0).sum()
    print(f"\nnull basis: {n_null_basis}, spot_close<=0: {n_zero_spot}, fut_close<=0: {n_zero_fut}")

    print("\nfirst 5 rows:")
    print(basis.head(5).to_string(index=False))
    print("\nlast 5 rows:")
    print(basis.tail(5).to_string(index=False))
