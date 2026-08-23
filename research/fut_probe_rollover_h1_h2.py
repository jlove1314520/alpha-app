"""Futures track, marathon round (2026-08-24 slot): validates FUT_MARATHON_STATE.md
priority item 1 -- rollover timing rule H1 (settlement-date rollover) vs H2
(volume-crossover rollover), per FUT_CONTINUOUS_CONTRACT_DESIGN.md "尚待驗證" #1.

Approach: for every monthly TX settlement date (3rd Wednesday) in the cached
history, compare daily volume of the nominal near-month contract vs the
next-month contract in the trading days leading up to that settlement. H2
(volume-crossover, common in commodity CTA literature) predicts the
next-month contract should overtake near-month volume *before* settlement
day for at least some meaningful fraction of cycles. H1 (simple
settlement-date rollover) predicts the near-month contract stays
volume-dominant essentially all the way through settlement.

Data source note: a first attempt this round to fetch a narrow window
(2024-05-15..2024-07-15) fresh from FinMind got HTTP 402 (quota exhausted,
see FUT_LOG.md this round's entry). Rather than retry against a known-
exhausted quota, this script instead reuses the full-history cache already
on disk from an earlier round (data/raw/TaiwanFuturesDaily__TX__2000-01-01__
2024-12-31.parquet, 64,936 rows) by requesting the *exact* same
(dataset, data_id, start_date, end_date) key -- load_dev()/_fetch() then
serves it straight from parquet with zero network calls. This also means we
get to test across the *entire* cached history (2000-2024, ~25 years / ~300
monthly settlement cycles) at zero marginal API cost, which is a much
stronger cheap-gate test than a single 2-month window would have been.

Read-only probe. Prints only, no side effects other than stdout.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev


def third_wednesday(year: int, month: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    first_wed = first + pd.Timedelta(days=(2 - first.weekday()) % 7)
    return first_wed + pd.Timedelta(weeks=2)


def all_settlement_dates(start_year: int, end_year: int) -> list[pd.Timestamp]:
    dates = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            dates.append(third_wednesday(y, m))
    return dates


def analyze_session(df_session: pd.DataFrame, settlement_dates: list[pd.Timestamp], lookback_days: int, session_name: str) -> None:
    """For each settlement date, look at the `lookback_days` trading days
    strictly before it and check whether next-month volume ever exceeded
    near-month volume on any of those days."""
    df_session = df_session.copy()
    df_session["contract_date"] = df_session["contract_date"].astype(str)
    pivot = df_session.pivot_table(index="date", columns="contract_date", values="volume", aggfunc="sum").fillna(0)
    pivot = pivot.sort_index()
    all_trading_dates = pivot.index

    cycles_tested = 0
    cycles_with_crossover = 0
    cycles_skipped_no_data = 0
    crossover_examples = []

    for settle in settlement_dates:
        window_dates = all_trading_dates[(all_trading_dates < settle) & (all_trading_dates >= settle - pd.Timedelta(days=lookback_days * 2))]
        window_dates = window_dates[-lookback_days:] if len(window_dates) > lookback_days else window_dates
        if len(window_dates) == 0:
            continue

        found_any_contracts = False
        had_crossover = False
        for dt in window_dates:
            row = pivot.loc[dt]
            active = sorted(c for c in row.index if row[c] > 0)
            if len(active) < 2:
                continue
            found_any_contracts = True
            near, nxt = active[0], active[1]
            if row[nxt] > row[near]:
                had_crossover = True
                days_before = (settle - dt).days
                crossover_examples.append((session_name, str(settle.date()), str(dt.date()), days_before, near, row[near], nxt, row[nxt]))

        if not found_any_contracts:
            cycles_skipped_no_data += 1
            continue
        cycles_tested += 1
        if had_crossover:
            cycles_with_crossover += 1

    print(f"  [session={session_name}] settlement cycles tested: {cycles_tested} (skipped, no data in window: {cycles_skipped_no_data})")
    print(f"  [session={session_name}] cycles where next-month volume exceeded near-month volume at least once in the {lookback_days} trading days before settlement: {cycles_with_crossover} ({100 * cycles_with_crossover / cycles_tested:.1f}%)" if cycles_tested else "  [no cycles tested]")
    if crossover_examples:
        offsets = [ex[3] for ex in crossover_examples]
        offset_counts = pd.Series(offsets).value_counts().sort_index()
        print(f"  [session={session_name}] crossover day-offset distribution (calendar days before settlement, {len(crossover_examples)} instances total):")
        print("    " + offset_counts.to_string().replace("\n", "\n    "))
        print(f"  [session={session_name}] first 10 crossover instances:")
        for ex in crossover_examples[:10]:
            print(f"    settle={ex[1]} date={ex[2]} ({ex[3]}d before) near={ex[4]}(vol={ex[5]:.0f}) next={ex[6]}(vol={ex[7]:.0f})")


def main() -> None:
    contract = "TX"
    full_start, full_end = "2000-01-01", "2024-12-31"
    print(f"=== TaiwanFuturesDaily (data_id={contract}, cached full-history {full_start}..{full_end}) ===")
    df_full = load_dev("TaiwanFuturesDaily", contract, start_date=full_start, end_date=full_end)
    if df_full.empty:
        print("  EMPTY -- cache miss or genuinely no data. Aborting probe.")
        return
    df_full["date"] = pd.to_datetime(df_full["date"])
    print(f"  {len(df_full)} rows total (raw, full cached history)")

    outright = df_full[~df_full["contract_date"].astype(str).str.contains("/")].copy()
    print(f"  {len(outright)} rows after excluding spread contract_date rows")

    start_year = int(outright["date"].min().year)
    end_year = int(outright["date"].max().year)
    settlement_dates = all_settlement_dates(start_year, end_year)
    print(f"\n  testing {len(settlement_dates)} monthly settlement dates spanning {start_year}-{end_year}")
    print(f"  (front-two-calendar-month volume comparison, lookback = 10 trading days before each settlement)\n")

    for session in sorted(outright["trading_session"].unique()):
        sub = outright[outright["trading_session"] == session]
        analyze_session(sub, settlement_dates, lookback_days=10, session_name=session)
        print()


if __name__ == "__main__":
    main()
