"""Round 352 left FUT_LEADS.md's "next step" as: round348(c) "start designing
a cross-sectional factor for individual stock futures" -- prerequisite is
deciding which subset to use, OR investigating a "rolling universe" (let
membership vary over time by listing date, so the panel keeps both breadth
and length instead of trading one off against the other the way round349's
two fixed subsets did: 8 codes / 346 days, or 4 codes / 1623 days).

This round does the "investigate rolling universe feasibility" half of that
prerequisite, on the 19 F-suffix codes round344/347/348/349 have already
established as liquidity-screened and dispersion-tested. Purely descriptive:
for each of the 19 codes, find its actual on-disk full-history date range
(from the existing 2000-01-01..2024-12-31 cache -- build_continuous_series()
default args hit the exact cache key round347/349 already populated, so this
makes ZERO new API calls), then build a per-year headcount table showing how
many of the 19 codes have data in each calendar year. That table is what
lets us answer the actual design question: is there a multi-year window
where enough of the 19 codes are simultaneously listed to give a reasonable
per-period cross-sectional N (round349's 8-code clean subset is the current
floor), without shrinking the window back down to round349(a)'s 346 days?

Deliberately NOT re-running the dispersion_ratio/PCA test here -- that
requires picking one committed window/subset first, which is exactly the
decision this probe's output is meant to inform. Doing both in one round
would be the same "sample first, decide gate after" ordering mistake the
project's hash-lock discipline exists to prevent (decide the window, THEN
test dispersion on it, not the other way around).

Read-only, reuses continuous_contract.build_continuous_series() ->
finmind_client.load_dev() (dev-capped, holdout-safe). No factor or strategy
is tested here -- pure infrastructure/design probe, same TRIALS_LEDGER
non-entry precedent as round332/335/338/341/344/348/349.
"""
from __future__ import annotations

import sys

import pandas as pd

from continuous_contract import build_continuous_series

# Same 19 codes as round347/348/349 (round344's liquidity-screened set).
CODES = [
    "CCF", "CDF", "EHF", "FYF", "GMF", "HBF", "HQF", "ITF", "JWF", "KKF",
    "NWF", "OLF", "PAF", "QDF", "QRF", "RFF", "RUF", "SXF", "ZFF",
]

# round349's two clean-subset picks (0 skipped_rollover_events), for
# cross-reference in the output.
CLEAN_8 = {"CCF", "CDF", "OLF", "PAF", "QRF", "RFF", "RUF", "ZFF"}
LONG_4 = {"CCF", "CDF", "OLF", "PAF"}


def main() -> int:
    rows = []
    for code in CODES:
        series, skipped = build_continuous_series(code, session="position")
        if series.empty:
            print(f"{code}: EMPTY series (unexpected -- round347/348 already used this code)", file=sys.stderr)
            continue
        rows.append({
            "code": code,
            "first_date": series["date"].min(),
            "last_date": series["date"].max(),
            "n_days": len(series),
            "n_skipped_rollover_events": len(skipped),
            "clean_8": code in CLEAN_8,
            "long_4": code in LONG_4,
        })
    membership = pd.DataFrame(rows).sort_values("first_date").reset_index(drop=True)
    print("=== Per-code listing window (from on-disk cache, full 2000-2024 history) ===")
    print(membership.to_string(index=False))

    # Per-calendar-year headcount: how many of the 19 codes have >=1 trading
    # day of data in that year. This is the number that answers "how wide
    # could a rolling-universe cross-section be in year Y".
    years = range(2010, 2025)
    year_rows = []
    for y in years:
        y_start = pd.Timestamp(f"{y}-01-01")
        y_end = pd.Timestamp(f"{y}-12-31")
        active = membership[(membership["first_date"] <= y_end) & (membership["last_date"] >= y_start)]
        year_rows.append({
            "year": y,
            "n_active": len(active),
            "active_codes": ",".join(sorted(active["code"])),
        })
    year_table = pd.DataFrame(year_rows)
    print()
    print("=== Per-year headcount (>=1 trading day in that calendar year) ===")
    print(year_table[["year", "n_active"]].to_string(index=False))

    # Candidate rolling-universe windows: for each possible (start_year,
    # end_year) span with end_year fixed at 2024 (holdout boundary already
    # confirmed equal to FULL_HISTORY_END, per round328's finding -- cannot
    # extend past it), report the MINIMUM per-year headcount across that
    # span (the binding constraint for a rolling design: the thinnest year
    # sets the achievable cross-sectional N for the whole window).
    print()
    print("=== Candidate windows ending 2024, by span length (min headcount = binding N) ===")
    for start_year in range(2010, 2025):
        span = year_table[(year_table["year"] >= start_year) & (year_table["year"] <= 2024)]
        if span.empty:
            continue
        min_n = span["n_active"].min()
        span_years = 2024 - start_year + 1
        print(f"{start_year}-2024 ({span_years:>2}y): min per-year headcount = {min_n}")

    out_path = "data/fut_stock_futures_rolling_universe_probe_round355.csv"
    membership.to_csv(out_path, index=False)
    year_table.to_csv("data/fut_stock_futures_rolling_universe_yearcounts_round355.csv", index=False)
    print()
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
