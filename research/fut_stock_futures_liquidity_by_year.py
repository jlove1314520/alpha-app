"""Round 358 (FUT) -- extend round344's liquidity screen from a single year
(2024 only) to every calendar year, for the 19 F-suffix codes round344/347/
348/349/352/355 have already established as the liquidity-screened /
rolling-universe candidate pool.

Why this round exists: round355's rolling-universe feasibility probe found
candidate windows (e.g. 2015-2024, min per-year headcount=11; 2011-2024,
min=10) that look much better than round349's two fixed subsets, but flagged
three honest limitations -- the first being "in-universe (has a quote that
year) is not the same as liquid; round344's liquidity screen only ever
checked 2024". This round closes that specific gap: it does NOT change the
subset/window decision itself (that is still open, per round355's "next
step"), it only checks whether the liquidity bar round344 pre-registered for
2024 also holds in earlier years for the same 19 codes -- the answer feeds
directly into whether the round355 "min headcount by year" table can be
trusted as a *liquid* headcount table, or whether it is currently just a
*listed* headcount table that could shrink once liquidity is applied.

Data source: continuous_contract.build_continuous_series(), called with its
default FULL_HISTORY_START/END args (2000-01-01..2024-12-31) -- this is the
EXACT cache key round347/348/349/352/355 already populated for all 19 codes,
so this makes ZERO new API calls (confirmed by inspecting continuous_contract.py
before writing this script, not assumed).

Threshold (pre-registered before looking at any per-year number, same
discipline as round344's docstring, and reusing round344's exact numbers
rather than inventing a new bar for this round -- changing the bar after
seeing results would defeat the purpose of a hash-lock):
  - >=200 trading days with a front-month quote in that calendar year, AND
  - mean front-month day-session volume over those days >= 50 contracts/day.
Applied per (code, year) independently. This is still a permissive,
first-pass bar (per round344's own framing), not a claim that 50
contracts/day is enough for a real strategy.

Read-only, infra/design probe (not a factor or strategy test) -- same
TRIALS_LEDGER non-entry precedent as round332/335/338/341/344/348/349/355.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import build_continuous_series

CODES = [
    "CCF", "CDF", "EHF", "FYF", "GMF", "HBF", "HQF", "ITF", "JWF", "KKF",
    "NWF", "OLF", "PAF", "QDF", "QRF", "RFF", "RUF", "SXF", "ZFF",
]

MIN_ACTIVE_DAYS = 200
MIN_MEAN_VOLUME = 50.0
YEARS = range(2010, 2025)


def main() -> int:
    rows = []
    for code in CODES:
        series, _skipped = build_continuous_series(code, session="position")
        if series.empty:
            print(f"{code}: EMPTY series (unexpected -- prior rounds already used this code)")
            continue
        series = series.copy()
        series["year"] = series["date"].dt.year
        for y in YEARS:
            yr = series[series["year"] == y]
            if yr.empty:
                continue
            active_days = len(yr)
            mean_volume = float(yr["volume"].mean())
            liquid = active_days >= MIN_ACTIVE_DAYS and mean_volume >= MIN_MEAN_VOLUME
            rows.append({
                "code": code, "year": y,
                "active_days": active_days,
                "mean_volume": round(mean_volume, 1),
                "liquid": liquid,
            })

    out = pd.DataFrame(rows)
    out_path = "data/fut_stock_futures_liquidity_by_year_round358.csv"
    out.to_csv(out_path, index=False)

    print("=== Per (code, year) liquidity, full 2010-2024 (reusing existing cache, zero new API calls) ===")
    print(out.to_string(index=False))

    # The number that actually matters for round355's window decision: for
    # each candidate window ending 2024, how many of the 19 codes are BOTH
    # listed AND liquid in EVERY year of that window (the binding constraint
    # is "liquid in the worst year", same logic as round355's "min headcount").
    print()
    print("=== Per-year LIQUID headcount (code passes both thresholds that year) ===")
    year_liquid_counts = out[out["liquid"]].groupby("year")["code"].count()
    for y in YEARS:
        n = int(year_liquid_counts.get(y, 0))
        print(f"{y}: {n} liquid / 19 total candidates")

    print()
    print("=== Candidate windows ending 2024: min per-year LIQUID headcount across the span ===")
    year_liquid_counts = year_liquid_counts.reindex(YEARS, fill_value=0)
    for start_year in range(2010, 2025):
        span = year_liquid_counts[(year_liquid_counts.index >= start_year) & (year_liquid_counts.index <= 2024)]
        if span.empty:
            continue
        min_n = int(span.min())
        span_years = 2024 - start_year + 1
        print(f"{start_year}-2024 ({span_years:>2}y): min per-year LIQUID headcount = {min_n}")

    # Also report: for each code, in how many of its listed years (per
    # round355's on-disk date range) does it actually clear the liquidity
    # bar -- flags codes that are "listed but thin" for a large fraction of
    # their history, which round355's listing-only table could not show.
    print()
    print("=== Per-code: years listed vs years liquid (within 2010-2024 window checked) ===")
    per_code = out.groupby("code").agg(
        years_checked=("year", "count"),
        years_liquid=("liquid", "sum"),
    ).reset_index()
    per_code["pct_liquid"] = (100.0 * per_code["years_liquid"] / per_code["years_checked"]).round(1)
    print(per_code.sort_values("pct_liquid").to_string(index=False))

    print()
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
