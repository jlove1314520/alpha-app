"""One-off PIT verification for f_value_pb/f_value_pe (marathon TW track,
2026-08-23). Answers the question factors.py's docstring left open: does
FinMind's daily PBR/PER on TaiwanStockPER update the moment a fiscal quarter
ENDS (hidden lookahead bias baked into FinMind's own data), or only once the
quarter is actually plausibly DISCLOSED (near pit.py's assumed period_end+45
day lag)?

Method (same spirit as the f_eps_growth/f_rev_accel day-by-day check
described in STRATEGY_LOG.md): PBR = close_price / book_value_per_share, so
book_value_per_share = close_price / PBR is implied and should be a step
function that only changes on the day FinMind updates its trailing book
value input -- never gradually. Detect the step dates (day-over-day jump in
implied BVPS beyond a noise threshold) and compare them against each
quarter's fiscal_period_end (from pit.quarterly_pit()) and this project's
assumed pit_date (period_end + 45 days).

Single stock (2330, the most liquid/best-covered name already used in prior
PIT checks per STRATEGY_LOG.md), single API call each to TaiwanStockPrice/
TaiwanStockPER -- cheap, bounded, no new API strain.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev
from pit import quarterly_pit

STOCK_ID = "2330"
START_DATE = "2015-01-01"
JUMP_THRESHOLD_PCT = 0.8  # day-over-day %% change in implied BVPS beyond this = a real update, not rounding noise


def main() -> None:
    price = load_dev("TaiwanStockPrice", STOCK_ID, START_DATE)[["date", "close"]]
    per = load_dev("TaiwanStockPER", STOCK_ID, START_DATE)[["date", "PBR"]]
    df = pd.merge(price, per, on="date", how="inner").sort_values("date").reset_index(drop=True)
    df = df[df["PBR"] > 0].copy()
    df["implied_bvps"] = df["close"] / df["PBR"]
    df["pct_change"] = df["implied_bvps"].pct_change().abs() * 100

    jumps = df[df["pct_change"] > JUMP_THRESHOLD_PCT].copy()
    print(f"Rows total: {len(df)}, PBR range {df['date'].min()}..{df['date'].max()}")
    print(f"Jump threshold: {JUMP_THRESHOLD_PCT}% day-over-day implied BVPS change")
    print(f"Jump dates found: {len(jumps)}")
    print(jumps[["date", "implied_bvps", "pct_change"]].to_string(index=False))

    q = quarterly_pit(STOCK_ID, "2010-01-01")
    q = q[["fiscal_period_end", "pit_date"]].dropna().sort_values("fiscal_period_end")
    q["fiscal_period_end"] = pd.to_datetime(q["fiscal_period_end"])
    q["pit_date"] = pd.to_datetime(q["pit_date"])
    # Only keep quarters whose disclosure window is fully covered by the price/PER
    # series we actually loaded (START_DATE) -- earlier quarters would spuriously
    # show "no jump found" just because we never fetched that price history, not
    # because FinMind didn't update. That's a script scoping artifact, not a finding.
    q = q[q["fiscal_period_end"] >= pd.Timestamp(START_DATE) - pd.Timedelta(days=100)].reset_index(drop=True)

    print("\n--- per-quarter nearest jump date vs fiscal_period_end / assumed pit_date ---")
    rows = []
    for _, r in q.iterrows():
        pe = r["fiscal_period_end"]
        pit = r["pit_date"]
        window_start = pe
        window_end = pe + pd.Timedelta(days=120)
        cand = jumps[(pd.to_datetime(jumps["date"]) >= window_start) & (pd.to_datetime(jumps["date"]) <= window_end)]
        if cand.empty:
            rows.append((pe.date(), pit.date(), None, None, "NO_JUMP_FOUND_IN_WINDOW"))
            continue
        first_jump = pd.to_datetime(cand["date"]).min()
        lag_from_period_end = (first_jump - pe).days
        lag_from_assumed_pit = (first_jump - pit).days
        rows.append((pe.date(), pit.date(), first_jump.date(), lag_from_period_end, lag_from_assumed_pit))

    result = pd.DataFrame(rows, columns=["fiscal_period_end", "assumed_pit_date", "first_jump_date",
                                          "lag_days_from_period_end", "lag_days_from_assumed_pit"])
    print(result.to_string(index=False))

    found = result.dropna(subset=["lag_days_from_period_end"])
    print(f"\nQuarters with a detected jump: {len(found)}/{len(result)}")
    if not found.empty:
        print(f"lag_days_from_period_end: min={found['lag_days_from_period_end'].min()}, "
              f"median={found['lag_days_from_period_end'].median()}, max={found['lag_days_from_period_end'].max()}")
        print(f"lag_days_from_assumed_pit: min={found['lag_days_from_assumed_pit'].min()}, "
              f"median={found['lag_days_from_assumed_pit'].median()}, max={found['lag_days_from_assumed_pit'].max()}")

    result.to_csv("data/verify_pit_value_pb_2330.csv", index=False)
    print("\nWrote data/verify_pit_value_pb_2330.csv")


if __name__ == "__main__":
    main()
