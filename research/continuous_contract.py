"""Ratio back-adjusted continuous front-month TX futures series.

Design decisions (ratio method, H1 settlement-date rollover, raw prices kept
as audit trail) were made in an earlier marathon round and are written up in
FUT_CONTINUOUS_CONTRACT_DESIGN.md -- read that file for the "why", this
module is just the "how". Same discipline as adjust.py for stocks: never
overwrite the raw series, only ever add a derived adjusted column next to it.

Rollover mechanism: this module does NOT need a separate "is it settlement
day yet" check. TX single-month contracts simply stop appearing in
TaiwanFuturesDaily the trading day after they expire (confirmed by eyeball
inspection: contract_date=202406 is present on 2024-06-19, the June 2024
settlement date, and gone entirely from 2024-06-20 onward -- see this
module's __main__ block). So "front month" is trivially "the contract with
the smallest contract_date that has data today", and that definition
naturally rolls on settlement day with zero extra logic -- which is exactly
H1 by construction, no H1/H2 branch needed here.

Session choice: only `trading_session == "position"` rows are used. Per
DATA.md section 6, `settlement_price`/`open_interest` are only populated
under "position" (high-confidence but not officially-confirmed inference:
`position` = day session / day-session settlement snapshot, `after_market` =
night session, based on after_market's data start date lining up with
TAIFEX's night-session launch date). Night-session bars are NOT included in
this continuous series yet -- that would be a separate, deliberate decision
if a strategy ever needs it, not a default.

Known gap (honesty, not silently ignored): if the incoming front contract is
missing a quote on the exact day the outgoing contract makes its last
appearance (a data gap), the rollover ratio for that transition cannot be
computed. Such events are collected in `skipped_events` rather than silently
dropped or guessed at -- see `rollover_events()`.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev

FULL_HISTORY_START = "2000-01-01"
FULL_HISTORY_END = "2024-12-31"  # matches the on-disk full-history cache key; see FUT_LOG.md


def load_position_session(
    contract: str = "TX",
    start_date: str = FULL_HISTORY_START,
    end_date: str = FULL_HISTORY_END,
) -> pd.DataFrame:
    """Raw TaiwanFuturesDaily rows for `contract`, filtered to single-month
    contracts (excludes spread contract_date rows like "202406/202407") and
    to the `position` session (see module docstring for why).

    Passing the exact (start_date, end_date) that matches an existing
    data/raw/ parquet cache key lets this hit the cache with zero network
    calls -- deliberately defaulted to the known full-history cache key
    rather than a narrower window, for the same reason fut_probe_rollover_h1_h2.py
    did this: it costs nothing extra and gives every caller the full
    available history by default.
    """
    df = load_dev("TaiwanFuturesDaily", contract, start_date=start_date, end_date=end_date)
    if df.empty:
        return df
    df = df[~df["contract_date"].astype(str).str.contains("/")].copy()
    df = df[df["trading_session"] == "position"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["contract_date"] = df["contract_date"].astype(int)
    return df.sort_values(["date", "contract_date"]).reset_index(drop=True)


def front_month_series(df: pd.DataFrame) -> pd.DataFrame:
    """One row per date: the contract with the smallest contract_date that
    has a non-null close that day (see module docstring: this is the whole
    rollover mechanism, nothing else is needed)."""
    if df.empty:
        return pd.DataFrame(columns=["date", "contract_date", "open", "max", "min", "close", "volume", "open_interest"])
    valid = df.dropna(subset=["close"])
    idx = valid.groupby("date")["contract_date"].idxmin()
    front = valid.loc[idx, ["date", "contract_date", "open", "max", "min", "close", "volume", "open_interest"]]
    return front.sort_values("date").reset_index(drop=True)


def rollover_events(df: pd.DataFrame, front: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Detect every day-over-day change in the front-month contract and
    compute the ratio back-adjustment factor for it.

    Ratio = new_contract_close / old_contract_close, both priced on the last
    day the OLD contract was still front (i.e. the day before the switch,
    normally the settlement day itself) -- that's the last day both
    contracts have a real quote in the raw data. Mirrors adjust.py's
    "prev_trading_date" anchor for stock ex-dividend events.

    Returns (events_df, skipped) where `skipped` lists transitions where the
    incoming contract had no quote on the anchor day (data gap) -- these are
    NOT silently dropped from the continuous series (the front series itself
    still switches), they just contribute no adjustment factor, which is
    flagged rather than assumed harmless.
    """
    if front.empty:
        return pd.DataFrame(columns=["roll_date", "prev_date", "old_contract", "new_contract", "old_close", "new_close", "ratio"]), []

    close_by_date_contract = {(row.date, row.contract_date): row.close for row in df.itertuples(index=False)}
    front = front.sort_values("date").reset_index(drop=True)

    events = []
    skipped = []
    for i in range(1, len(front)):
        prev_row, cur_row = front.iloc[i - 1], front.iloc[i]
        old_id, new_id = prev_row["contract_date"], cur_row["contract_date"]
        if old_id == new_id:
            continue
        prev_date = prev_row["date"]
        old_close = close_by_date_contract.get((prev_date, old_id))
        new_close = close_by_date_contract.get((prev_date, new_id))
        if old_close in (None, 0) or new_close in (None, 0) or pd.isna(old_close) or pd.isna(new_close):
            skipped.append({
                "roll_date": cur_row["date"], "prev_date": prev_date,
                "old_contract": old_id, "new_contract": new_id,
                "reason": "new contract has no quote on the old contract's last day",
            })
            continue
        events.append({
            "roll_date": cur_row["date"], "prev_date": prev_date,
            "old_contract": old_id, "new_contract": new_id,
            "old_close": old_close, "new_close": new_close,
            "ratio": new_close / old_close,
        })

    events_df = pd.DataFrame(events)
    if not events_df.empty:
        events_df = events_df.sort_values("roll_date").reset_index(drop=True)
    return events_df, skipped


def build_continuous_series(
    contract: str = "TX",
    start_date: str = FULL_HISTORY_START,
    end_date: str = FULL_HISTORY_END,
) -> tuple[pd.DataFrame, list[dict]]:
    """The public entry point. Returns (series, skipped_events).

    `series` has one row per trading day with: the raw (unadjusted)
    front-month contract_date/open/max/min/close/volume/open_interest, plus
    adj_open/adj_max/adj_min/adj_close (ratio back-adjusted, cumulative
    across every rollover after this date -- most-recent price is never
    adjusted, same convention as adjust.py). `skipped_events` mirrors
    rollover_events()'s second return value -- always check it, an empty
    list means every transition had a clean adjustment ratio, a non-empty
    list means some transitions have NO adjustment applied (raw price used
    as-is for those, which will show up as a visible jump in adj_close).
    """
    df = load_position_session(contract, start_date, end_date)
    front = front_month_series(df)
    events, skipped = rollover_events(df, front)

    out = front.copy()
    for col in ("open", "max", "min", "close"):
        out[f"adj_{col}"] = out[col].astype(float)

    if not events.empty:
        for _, ev in events.sort_values("roll_date", ascending=False).iterrows():
            mask = out["date"] < ev["roll_date"]
            for col in ("open", "max", "min", "close"):
                out.loc[mask, f"adj_{col}"] *= ev["ratio"]

    out.attrs["n_rollover_events"] = len(events)
    out.attrs["n_skipped_events"] = len(skipped)
    return out, skipped


if __name__ == "__main__":
    # Manual spot-check, per MARATHON_PROTOCOL.md 1c: "第一輪先把單一合約序列
    # 銜接寫出來、用少數幾次轉倉手動驗證正確性即可，不用一次做完全部功能".
    # This prints a handful of rollovers for eyeball verification against the
    # raw data queried independently below -- not an automated test.
    series, skipped = build_continuous_series()
    print(f"continuous series: {len(series)} trading days, "
          f"{series.attrs['n_rollover_events']} rollover events, "
          f"{series.attrs['n_skipped_events']} skipped (no clean ratio)")

    print("\nfirst 5 rollover-adjacent windows (raw front contract switch + close/adj_close either side):")
    switches = series[series["contract_date"] != series["contract_date"].shift(1)].index[1:6]
    for idx in switches:
        window = series.loc[max(idx - 1, 0):idx]
        print(window[["date", "contract_date", "close", "adj_close"]].to_string(index=False))
        print()

    if skipped:
        print(f"SKIPPED EVENTS (no ratio applied, {len(skipped)} total) -- first 5:")
        for s in skipped[:5]:
            print(f"  {s}")

    # Independent manual check for the 2024-06 rollover found by eyeball
    # inspection earlier this round: 202406 -> 202407, anchor day 2024-06-19
    # (June 2024 settlement date), raw closes 23225.0 (202406) / 23129.0
    # (202407) -> expected ratio 23129/23225 = 0.995866...
    check = series[(series["date"] >= "2024-06-17") & (series["date"] <= "2024-06-21")]
    print("\nmanual spot-check window 2024-06-17..21 (expect switch 202406->202407 after 2024-06-19):")
    print(check[["date", "contract_date", "close", "adj_close"]].to_string(index=False))
