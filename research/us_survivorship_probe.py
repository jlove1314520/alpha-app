"""US track, marathon round 2026-08-23 (4th): probe whether FinMind's US price
data preserves history for stocks that have since been delisted/gone private/
collapsed -- the biggest unresolved foundation gap per US_MARATHON_STATE.md's
"下一輪建議工作單位" item 1.

Question this answers: if a company was delisted, does USStockPrice still
return its historical rows up to the last trading day (like TW's price-row-
presence-as-ground-truth approach in universe.py), or does FinMind's free
tier silently drop delisted names entirely (which would mean survivorship
bias is baked into USStockPrice and we'd need a different data source)?

Candidates chosen to span different delisting *reasons* (acquisition-and-
taken-private, bank-collapse/FDIC seizure, bankruptcy) and different years,
all safely before VAL_END (2024-12-31) so this is an ordinary load_dev() call,
not a holdout question:
  - TWTR (Twitter): taken private by Musk, last trading day 2022-10-27.
  - SIVB (Silicon Valley Bank): FDIC seizure, last trading day 2023-03-10.
  - SBNY (Signature Bank): FDIC seizure, last trading day 2023-03-10.
  - FRC (First Republic Bank): FDIC seizure/JPM acquisition, last trading day
    2023-05-01.
  - BBBY (Bed Bath & Beyond): Chapter 11, delisted from Nasdaq 2023-05-03.

All known last-trading-day dates above are from public news coverage at the
time of each event (approximate, used only to sanity-check what FinMind
returns -- not treated as ground truth themselves).

Also checks whether USStockInfo snapshots (the 289-snapshot membership list
DATA.md's milestone 1 already characterized) drop these tickers from later
snapshots after their real-world delisting date -- this is the "snapshot
diff" approach US_MARATHON_STATE.md flagged as an unverified assumption.

Everything here goes through load_dev() (price, time-series, capped at
VAL_END) or _fetch() directly (USStockInfo, membership snapshot -- same
precedent as universe.py/us_probe_milestone1.py use for *StockInfo
datasets). This script only prints; findings get written back into DATA.md
and US_MARATHON_STATE.md by hand after reading the output.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev, _fetch

CANDIDATES = {
    "TWTR": "2022-10-27",  # Twitter, taken private
    "SIVB": "2023-03-10",  # Silicon Valley Bank, FDIC seizure
    "SBNY": "2023-03-10",  # Signature Bank, FDIC seizure
    "FRC": "2023-05-01",   # First Republic Bank, FDIC seizure/JPM
    "BBBY": "2023-05-03",  # Bed Bath & Beyond, Chapter 11 delisting
}


def probe_price_history() -> dict[str, dict]:
    print("=== 1. USStockPrice history for known-delisted tickers (load_dev, start=2000-01-01) ===")
    results = {}
    for ticker, known_last_day in CANDIDATES.items():
        df = load_dev("USStockPrice", ticker, start_date="2000-01-01")
        if df.empty:
            print(f"  {ticker}: EMPTY -- no price data at all (bad sign for survivorship coverage)")
            results[ticker] = {"rows": 0}
            continue
        dates = pd.to_datetime(df["date"])
        first, last = dates.min().date(), dates.max().date()
        # does data continue meaningfully past the known real-world last trading day?
        # (a ticker symbol getting reused for an unrelated company would show up as this)
        past_known = df[dates.dt.date.astype(str) > known_last_day]
        print(
            f"  {ticker}: {len(df)} rows, first={first}, last={last}, "
            f"known_last_trading_day~={known_last_day}, "
            f"rows_after_known_last_day={len(past_known)}"
        )
        results[ticker] = {
            "rows": len(df),
            "first": str(first),
            "last": str(last),
            "known_last_day": known_last_day,
            "rows_after_known_last_day": len(past_known),
        }
    return results


def probe_info_snapshot_diff() -> None:
    print("\n=== 2. USStockInfo snapshot presence for the same tickers ===")
    info = _fetch("USStockInfo", "", "2000-01-01")
    if info.empty:
        print("  USStockInfo EMPTY -- cannot check snapshot diff")
        return
    for ticker, known_last_day in CANDIDATES.items():
        rows = info[info["stock_id"] == ticker]
        if rows.empty:
            print(f"  {ticker}: never appears in any USStockInfo snapshot (289 snapshots total)")
            continue
        snap_dates = sorted(pd.to_datetime(rows["date"]).dt.date.unique())
        last_seen = snap_dates[-1]
        print(
            f"  {ticker}: appears in {len(snap_dates)} snapshot(s), "
            f"first_seen={snap_dates[0]}, last_seen={last_seen}, "
            f"known_real_world_delist~={known_last_day} -- "
            f"{'still appearing AFTER real delisting (snapshot diff would NOT catch this)' if str(last_seen) > known_last_day else 'stops appearing at/before known delisting (snapshot diff plausible)'}"
        )


if __name__ == "__main__":
    probe_price_history()
    probe_info_snapshot_diff()
