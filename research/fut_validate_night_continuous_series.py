"""Validate continuous_contract.py's new `session="after_market"` support
(round 91) against round 90's independently-computed night-session rollover
dates (fut_probe_night_session_rollover.py), plus basic sanity checks on the
resulting adjusted series.

This is 1c infra work, not a hypothesis test -- no TRIALS_LEDGER.md row, same
precedent as rounds 39/60/63/90. The point of this script is specifically to
NOT trust the new build_continuous_series(session="after_market") code path
just because it imports cleanly -- it re-derives the night rollover dates a
second, independent way (via fut_probe_night_session_rollover.py's own
_night_front_month_series/_switch_dates helpers, which do not call the new
load_session()/build_continuous_series() code at all) and diffs the two.

Zero new API calls: everything here hits the existing on-disk full-history
parquet cache (same cache key precedent as every other fut_probe_*.py script
this marathon).
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import FULL_HISTORY_END, FULL_HISTORY_START, build_continuous_series
from fut_probe_night_session_rollover import _night_front_month_series, _switch_dates
from finmind_client import load_dev


def main() -> None:
    # --- 1. Build the night series via the new code path under test. ---
    night_series, night_skipped = build_continuous_series(
        "TX", FULL_HISTORY_START, FULL_HISTORY_END, session="after_market"
    )
    print(f"build_continuous_series(session='after_market'): {len(night_series)} rows, "
          f"{night_series.attrs['n_rollover_events']} rollover events, "
          f"{night_series.attrs['n_skipped_events']} skipped")

    # --- 2. Independently re-derive night rollover dates (round 90's method,
    #        no shared code with load_session()/build_continuous_series()). ---
    raw = load_dev("TaiwanFuturesDaily", "TX", start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    night_raw = raw[raw["trading_session"] == "after_market"].copy()
    night_raw = night_raw[~night_raw["contract_date"].astype(str).str.contains("/")].copy()
    night_raw["date"] = pd.to_datetime(night_raw["date"])
    night_raw["contract_date"] = night_raw["contract_date"].astype(int)
    independent_front = _night_front_month_series(night_raw)
    independent_switches = _switch_dates(independent_front)
    print(f"\nindependent re-derivation (round 90 method): {len(independent_front)} front-month rows, "
          f"{len(independent_switches)} rollover events")

    # --- 3. Diff: does the new code's rollover dates match the independent ones exactly? ---
    new_switch_dates = set(
        night_series.loc[night_series["contract_date"] != night_series["contract_date"].shift(1), "date"]
        .iloc[1:]
    )
    independent_switch_dates = set(independent_switches["date"])
    only_new = new_switch_dates - independent_switch_dates
    only_independent = independent_switch_dates - new_switch_dates
    print(f"\nnew code rollover dates: {len(new_switch_dates)}, independent rollover dates: {len(independent_switch_dates)}")
    print(f"exact match: {new_switch_dates == independent_switch_dates}")
    if only_new:
        print(f"  dates only in new code (first 10): {sorted(only_new)[:10]}")
    if only_independent:
        print(f"  dates only in independent derivation (first 10): {sorted(only_independent)[:10]}")

    # --- 4. Basic sanity checks on the adjusted series itself. ---
    print(f"\ndate range: {night_series['date'].min()} .. {night_series['date'].max()}")
    print(f"NaN counts:\n{night_series[['open', 'max', 'min', 'close', 'adj_open', 'adj_max', 'adj_min', 'adj_close']].isna().sum()}")
    non_positive = (night_series[["open", "max", "min", "close"]] <= 0).sum().sum()
    print(f"non-positive raw price cells: {non_positive}")
    print(f"open_interest all-zero (expected per round 60 finding): {(night_series['open_interest'] == 0).all()}")
    if night_skipped:
        print(f"\nskipped rollover events (no clean ratio, {len(night_skipped)} total) -- first 5:")
        for s in night_skipped[:5]:
            print(f"  {s}")

    print("\nfirst 3 rows:")
    print(night_series.head(3)[["date", "contract_date", "close", "adj_close"]].to_string(index=False))
    print("\nlast 3 rows:")
    print(night_series.tail(3)[["date", "contract_date", "close", "adj_close"]].to_string(index=False))


if __name__ == "__main__":
    main()
