"""Probe: is night-session (`after_market`) front-month rollover synchronized
with day-session (`position`) rollover, using the same `date` label?

This is 1c infra work per FUT_MARATHON_STATE.md round 86's "下一輪建議" item
(a): before writing a night-session-aware continuous series or any session-
effect hypothesis, confirm whether the night session's front-month contract
switches on the SAME calendar `date` label as the day session, or is offset
by one trading day -- rather than assuming it lines up.

Background (round 63, fut_verify_night_session_timing.py): night session row
labeled `date`=T represents "evening of T-1 through early morning of T", i.e.
it PRECEDES day session T, not follows it. Given that, and given
continuous_contract.py's day-session rollover rule (front-month switches to
the new contract on the first date it has a valid quote, which for TX is the
trading day immediately after the old contract's settlement date), the
synchronization question this script answers empirically (not by assumption):
does the night session's `date` label first show the NEW front contract on
the exact same calendar date the day session does, or is there a lag/lead?

Deliberately reuses continuous_contract.load_position_session's exact
(dataset, contract, start_date, end_date) cache key so the day-session half
of this comparison hits the existing on-disk full-history parquet with zero
new API calls -- same precedent as fut_probe_night_session.py.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import (
    FULL_HISTORY_END,
    FULL_HISTORY_START,
    front_month_series,
    load_position_session,
)
from finmind_client import load_dev


def _night_front_month_series(df: pd.DataFrame) -> pd.DataFrame:
    """Same rule as continuous_contract.front_month_series (smallest
    contract_date with a valid close on that date), applied to night-session
    rows. Not reusing front_month_series directly because it expects the
    caller to have already filtered to single-month contracts and to a
    single session -- night session needs its own spread-row filter check
    first (per fut_probe_night_session.py, night session may or may not have
    spread rows; this script re-derives it rather than assuming)."""
    if df.empty:
        return pd.DataFrame(columns=["date", "contract_date", "close"])
    valid = df.dropna(subset=["close"])
    idx = valid.groupby("date")["contract_date"].idxmin()
    return valid.loc[idx, ["date", "contract_date", "close"]].sort_values("date").reset_index(drop=True)


def _switch_dates(front: pd.DataFrame) -> pd.DataFrame:
    """One row per rollover: the date the front contract_date first differs
    from the previous row's, plus old/new contract_date."""
    if front.empty:
        return pd.DataFrame(columns=["date", "old_contract", "new_contract"])
    front = front.sort_values("date").reset_index(drop=True)
    switches = []
    for i in range(1, len(front)):
        old_id, new_id = front.loc[i - 1, "contract_date"], front.loc[i, "contract_date"]
        if old_id != new_id:
            switches.append({"date": front.loc[i, "date"], "old_contract": old_id, "new_contract": new_id})
    return pd.DataFrame(switches)


def main() -> None:
    # Day session: reuse continuous_contract.py's existing, already-validated helpers.
    day_df = load_position_session("TX", FULL_HISTORY_START, FULL_HISTORY_END)
    day_front = front_month_series(day_df)
    day_switches = _switch_dates(day_front)
    print(f"day session: {len(day_front)} front-month rows, {len(day_switches)} rollover events")

    # Night session: same cache key (dataset/contract/date range) as
    # fut_probe_night_session.py, filtered to after_market instead of position.
    raw = load_dev("TaiwanFuturesDaily", "TX", start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    night = raw[raw["trading_session"] == "after_market"].copy()
    night = night[~night["contract_date"].astype(str).str.contains("/")].copy()
    night["date"] = pd.to_datetime(night["date"])
    night["contract_date"] = night["contract_date"].astype(int)
    night_front = _night_front_month_series(night)
    night_switches = _switch_dates(night_front)
    print(f"night session: {len(night_front)} front-month rows, {len(night_switches)} rollover events")

    # Restrict day-session switches to the window where night session data exists at all
    # (night session only starts 2017-05-16 per round 60), otherwise the comparison below
    # would be dominated by pre-2017 events that have no night-session counterpart by
    # construction, not because of any desync.
    night_start = night["date"].min()
    day_switches_in_window = day_switches[day_switches["date"] >= night_start].reset_index(drop=True)
    print(f"\nday-session rollover events on/after night session start ({night_start.date()}): "
          f"{len(day_switches_in_window)}")

    day_dates = set(day_switches_in_window["date"])
    night_dates = set(night_switches["date"])

    exact_match = day_dates & night_dates
    day_only = day_dates - night_dates
    night_only = night_dates - day_dates
    print(f"\nexact same-date rollover matches: {len(exact_match)} / {len(day_switches_in_window)} day-side events")
    print(f"day-side rollover dates with NO exact night-side match: {len(day_only)}")
    print(f"night-side rollover dates with NO exact day-side match: {len(night_only)}")

    # For every day-side rollover with no exact night match, find the nearest night-side
    # rollover date (by calendar days) to characterize any systematic lag/lead, rather than
    # just reporting "no match" with no further diagnosis.
    if day_only:
        night_dates_sorted = sorted(night_dates)
        print("\nnearest night-side rollover date for each unmatched day-side event "
              "(offset in calendar days, +ve = night lags day):")
        offsets = []
        for d in sorted(day_only)[:15]:  # cap printout, full stats computed below regardless
            nearest = min(night_dates_sorted, key=lambda n: abs((n - d).days))
            offset = (nearest - d).days
            offsets.append(offset)
            print(f"  day={d.date()}  nearest_night={nearest.date()}  offset_days={offset}")
        if len(day_only) > 15:
            all_offsets = [min((n - d).days for n in night_dates_sorted) if False else
                           (min(night_dates_sorted, key=lambda n: abs((n - d).days)) - d).days
                           for d in sorted(day_only)]
            print(f"\n  (full set, n={len(all_offsets)}) offset_days value_counts:")
            print(pd.Series(all_offsets).value_counts().sort_index())

    print("\nfirst 5 day-side rollover events in comparison window (for eyeball reference):")
    print(day_switches_in_window.head(5).to_string(index=False))
    print("\nfirst 5 night-side rollover events:")
    print(night_switches.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
