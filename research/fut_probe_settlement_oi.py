"""Futures track, marathon round 4 (2026-08-23 15:xx+08:00 slot): follow-up
probe to FUT_MARATHON_STATE.md priority item 1 -- is `settlement_price` /
`open_interest` in `TaiwanFuturesDaily` genuinely always 0, or was that just
an artifact of the narrow one-week window `fut_probe_milestone1.py` used?

Widens the window to a full month (2024-06) and groups by `trading_session`
so we can see whether some session value (not just `after_market`/`position`)
carries non-zero settlement/OI, and whether a longer window surfaces a
`regular`/`day`-style session label that the narrow week missed.

Also filters `contract_date` down to single-month contracts (excludes the
`/`-joined spread rows) per DATA.md's note that the two are mixed in one
table -- spread rows would muddy any "is this genuinely 0" conclusion since
settlement/OI semantics for a spread leg may differ from an outright.

Read-only probe, prints only. Data comes through finmind_client.load_dev()
(capped at VAL_END) -- same holdout discipline as fut_probe_milestone1.py.
"""
from __future__ import annotations

from finmind_client import load_dev


def main() -> None:
    contract = "TX"
    start, end = "2024-06-01", "2024-06-30"
    print(f"=== TaiwanFuturesDaily (data_id={contract}, {start}..{end}) ===")
    df = load_dev("TaiwanFuturesDaily", contract, start_date=start, end_date=end)
    if df.empty:
        print("  EMPTY")
        return
    print(f"  {len(df)} rows total (all contract_date values, incl. spreads)")

    outright = df[~df["contract_date"].astype(str).str.contains("/")]
    print(f"  {len(outright)} rows after filtering out spread rows (contract_date contains '/')")
    print(f"  distinct contract_date (outright only): {sorted(outright['contract_date'].unique())}")
    print(f"  distinct trading_session (outright only): {sorted(outright['trading_session'].unique())}")

    print("\n  -- settlement_price / open_interest: zero vs non-zero row counts, grouped by trading_session --")
    grouped = outright.groupby("trading_session").agg(
        n_rows=("date", "count"),
        n_settlement_nonzero=("settlement_price", lambda s: (s != 0).sum()),
        n_oi_nonzero=("open_interest", lambda s: (s != 0).sum()),
    )
    print(grouped.to_string())

    if outright["open_interest"].eq(0).all() and outright["settlement_price"].eq(0).all():
        print("\n  CONCLUSION: still all-zero across the full month and both observed sessions.")
    else:
        print("\n  CONCLUSION: non-zero values found -- narrow-window result was an artifact, not a real gap.")
        nonzero_oi = outright[outright["open_interest"] != 0]
        print(f"\n  sample non-zero open_interest rows ({len(nonzero_oi)} total):")
        print(nonzero_oi.head(10).to_string())


if __name__ == "__main__":
    main()
