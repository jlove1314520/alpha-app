"""Probe: is the `after_market` (assumed night session) TaiwanFuturesDaily
data usable as an infra building block for a day-vs-night session-effect
hypothesis?

This is 1c infra work per MARATHON_PROTOCOL.md 5, item 1(b) in
FUT_MARATHON_STATE.md's "下一輪建議工作單位": before writing a
night-session-aware continuous contract, confirm the raw shape of
`after_market` rows -- date range, contract_date structure, per-day
cardinality, and how each night-session row's `date` label relates to the
adjacent `position` (day session) rows -- rather than assuming it mirrors
the day session 1:1.

Deliberately reuses continuous_contract.load_position_session's exact
(dataset, contract, start_date, end_date) cache key so this hits the
existing on-disk full-history parquet with zero new API calls -- same
precedent as fut_probe_institutional_positions.py and
fut_recheck_*_highres.py.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import FULL_HISTORY_END, FULL_HISTORY_START
from finmind_client import load_dev


def main() -> None:
    df = load_dev("TaiwanFuturesDaily", "TX", start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    print(f"raw TX rows: {len(df)}")
    print(f"trading_session value counts:\n{df['trading_session'].value_counts(dropna=False)}")

    night = df[df["trading_session"] == "after_market"].copy()
    day = df[df["trading_session"] == "position"].copy()
    print(f"\nnight (after_market) rows: {len(night)}, day (position) rows: {len(day)}")

    if night.empty:
        print("NO after_market rows at all -- night session infra cannot be built with this dataset. Stop here.")
        return

    night["date"] = pd.to_datetime(night["date"])
    day["date"] = pd.to_datetime(day["date"])

    print(f"\nnight date range: {night['date'].min()} .. {night['date'].max()}")
    print(f"day date range:   {day['date'].min()} .. {day['date'].max()}")

    # spread rows (e.g. "202406/202407") exist in day session per continuous_contract.py's
    # filter -- check whether night session also has them, so a future continuous-series
    # builder knows whether it needs the same filter.
    night_spread = night["contract_date"].astype(str).str.contains("/").sum()
    print(f"\nnight rows with spread contract_date (contains '/'): {night_spread} / {len(night)}")

    # per-day cardinality of single-month contracts in night session -- does night session
    # also list every listed contract_date (near + far months), same as day session?
    night_single = night[~night["contract_date"].astype(str).str.contains("/")].copy()
    night_single["contract_date"] = night_single["contract_date"].astype(int)
    per_day_counts = night_single.groupby("date")["contract_date"].nunique()
    print(f"\nnight single-month contract_date count per day -- describe:\n{per_day_counts.describe()}")

    # settlement_price / open_interest population under after_market, per DATA.md section 6
    # this round is re-verifying that claim directly rather than trusting the old note.
    for col in ("settlement_price", "open_interest"):
        if col in night.columns:
            non_null = night[col].notna().sum()
            print(f"\nnight '{col}' non-null: {non_null} / {len(night)} ({non_null / len(night):.1%})")

    # Key question for a future night-session continuous series: for a given calendar
    # `date` label, does the after_market row represent the night session that STARTS that
    # evening (i.e. before the next day's position session), or the one that ENDED that
    # morning (i.e. after the previous day's position session)? Inspect a handful of
    # contract-date first/last appearances in night vs day to see which lines up.
    front_day = day[~day["contract_date"].astype(str).str.contains("/")].copy()
    front_day["contract_date"] = front_day["contract_date"].astype(int)
    sample_contract = int(front_day["contract_date"].mode().iloc[0])
    day_dates = sorted(front_day[front_day["contract_date"] == sample_contract]["date"].unique())
    night_dates = sorted(night_single[night_single["contract_date"] == sample_contract]["date"].unique())
    print(f"\nsample contract_date={sample_contract}: day session first/last = {day_dates[0]} / {day_dates[-1]}, "
          f"night session first/last = {night_dates[0] if night_dates else 'N/A'} / {night_dates[-1] if night_dates else 'N/A'}")

    # First night session date overall, for cross-check against TAIFEX's known night-session
    # launch date (2017-05-15) -- DATA.md's "after_market == night session" inference was
    # based on this date lining up; re-confirm the exact first date here.
    print(f"\nfirst-ever after_market date in this dataset: {night['date'].min()} "
          f"(TAIFEX night session officially launched 2017-05-15 -- compare)")


if __name__ == "__main__":
    main()
