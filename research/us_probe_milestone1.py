"""US track, marathon round 2026-08-23: milestone-1-style probe of FinMind US
datasets, mirroring how DATA.md's milestone 1 validated the TW datasets
before any factor work started on that track.

Answers the three questions US_MARATHON_STATE.md's "第一輪建議工作單位" item 1
asks for: USStockPrice historical depth, ticker coverage, update frequency.
Findings get written back into DATA.md by hand after reading this script's
output -- this script itself only prints, it does not edit other files.

All price fetches go through finmind_client.load_dev() (capped at VAL_END,
2024-12-31) per MARATHON_PROTOCOL.md section 4 -- depth/frequency questions
don't need anything past that boundary. USStockInfo is fetched directly via
_fetch(), same precedent as universe.py uses for TaiwanStockInfo/
TaiwanStockDelisting: it's a membership/reference list, not a capped time
series, and load_dev() would misbehave on it (see universe.py's docstring).
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev, _fetch


def probe_historical_depth(tickers: list[str]) -> None:
    print("=== 1. Historical depth (USStockPrice, load_dev, start=1990-01-01) ===")
    for t in tickers:
        df = load_dev("USStockPrice", t, start_date="1990-01-01")
        if df.empty:
            print(f"  {t}: EMPTY (no data at all)")
            continue
        dates = pd.to_datetime(df["date"])
        print(
            f"  {t}: {len(df)} rows, first={dates.min().date()}, last={dates.max().date()}"
        )


def probe_update_frequency(ticker: str, window_start: str, window_end: str) -> None:
    print(f"\n=== 2. Update frequency (USStockPrice, {ticker}, {window_start}..{window_end}) ===")
    df = load_dev("USStockPrice", ticker, start_date=window_start, end_date=window_end)
    if df.empty:
        print("  EMPTY")
        return
    dates = sorted(pd.to_datetime(df["date"]).dt.date.unique())
    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    from collections import Counter

    gap_counts = Counter(gaps)
    print(f"  {len(dates)} distinct trading days, gap-in-days histogram: {dict(sorted(gap_counts.items()))}")
    print(f"  columns present: {list(df.columns)}")


def probe_coverage() -> None:
    print("\n=== 3. Ticker coverage (USStockInfo, _fetch direct -- metadata precedent) ===")
    info = _fetch("USStockInfo", "", "2000-01-01")
    if info.empty:
        print("  USStockInfo returned EMPTY or dataset name is wrong -- needs manual check")
        return
    print(f"  {len(info)} rows, columns: {list(info.columns)}")
    print(info.head(10).to_string())
    if "type" in info.columns:
        print("\n  value_counts on 'type':")
        print(info["type"].value_counts().to_string())
    if "industry_category" in info.columns:
        print(f"\n  distinct industry_category count: {info['industry_category'].nunique()}")


if __name__ == "__main__":
    # AAPL/MSFT: long-listed mega-caps, should show maximal depth if FinMind has any.
    # A mid-cap with a known-recent IPO would also be useful but was skipped this
    # round -- one bounded work unit, per MARATHON_PROTOCOL.md section 1.
    probe_historical_depth(["AAPL", "MSFT"])
    probe_update_frequency("AAPL", "2024-06-01", "2024-06-30")
    probe_coverage()
