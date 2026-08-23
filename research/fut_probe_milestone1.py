"""Futures track, marathon round 2026-08-23 (second round on this track):
milestone-1-style probe of FinMind futures datasets, mirroring the same
pattern us_probe_milestone1.py used for the US track and DATA.md's original
milestone 1 used for TW -- confirm dataset names / field structure / history
depth BEFORE building any continuous-contract or factor code on top of them.

The previous round on this track hit a FinMind rate-limit ban (403,
retry_after=1782s, ~11:47:30+08:00) before a single successful call was made,
so `TaiwanFuturesDaily` and `TaiwanFuturesInstitutionalInvestors` are still
UNCONFIRMED dataset names at the start of this round -- see FUT_MARATHON_STATE.md.

Deliberately narrow: one contract code, one short date window (per
MARATHON_PROTOCOL.md 1a "小樣本快篩" / 5 "只確認資料源可用性"). This script
only prints -- findings get written back into DATA.md and FUT_MARATHON_STATE.md
by hand after reading the output, same division of labor as
us_probe_milestone1.py.

Price/volume history goes through finmind_client.load_dev() (capped at
VAL_END) since it's a plain time series with a `date` column. If either
dataset turns out not to have a `date` column, load_dev() will raise rather
than silently skip the holdout cap -- that's the intended behavior per its
own docstring, not a bug to work around here.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev


def probe_futures_daily(contract: str, start_date: str, end_date: str) -> None:
    print(f"=== 1. TaiwanFuturesDaily (data_id={contract}, {start_date}..{end_date}) ===")
    df = load_dev("TaiwanFuturesDaily", contract, start_date=start_date, end_date=end_date)
    if df.empty:
        print("  EMPTY -- dataset name or data_id may be wrong, or genuinely no data in this window")
        return
    print(f"  {len(df)} rows, columns: {list(df.columns)}")
    print(df.head(15).to_string())
    for col in ("contract_date", "trading_session"):
        if col in df.columns:
            print(f"\n  distinct {col} values in this window: {sorted(df[col].unique())}")


def probe_futures_institutional(contract: str, start_date: str, end_date: str) -> None:
    print(f"\n=== 2. TaiwanFuturesInstitutionalInvestors (data_id={contract}, {start_date}..{end_date}) ===")
    df = load_dev("TaiwanFuturesInstitutionalInvestors", contract, start_date=start_date, end_date=end_date)
    if df.empty:
        print("  EMPTY -- dataset name or data_id may be wrong, or genuinely no data in this window")
        return
    print(f"  {len(df)} rows, columns: {list(df.columns)}")
    print(df.head(15).to_string())


def probe_historical_depth(contract: str) -> None:
    print(f"\n=== 3. Historical depth check (TaiwanFuturesDaily, data_id={contract}, start=2000-01-01) ===")
    df = load_dev("TaiwanFuturesDaily", contract, start_date="2000-01-01")
    if df.empty:
        print("  EMPTY")
        return
    dates = pd.to_datetime(df["date"])
    print(f"  {len(df)} rows, first={dates.min().date()}, last={dates.max().date()}")


if __name__ == "__main__":
    # TX = Taiwan Stock Exchange Capitalization Weighted Stock Index Futures
    # (台指期), the contract code CLAUDE.md/FUT_LEADS.md assume FinMind uses --
    # unconfirmed until this actually runs. One narrow week-long window first,
    # per protocol -- widen only after confirming the dataset responds at all.
    contract = "TX"
    start, end = "2024-06-03", "2024-06-07"
    probe_futures_daily(contract, start, end)
    probe_futures_institutional(contract, start, end)
    probe_historical_depth(contract)
