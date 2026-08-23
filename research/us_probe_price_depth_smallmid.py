"""US track, marathon round 2026-08-24: USStockPrice historical depth probe
for mid/small-cap and recently-IPO'd tickers.

US_MARATHON_STATE.md's "下一輪建議工作單位" item 4 explicitly flags that the
first depth probe (us_probe_milestone1.py, 2026-08-23) only tested AAPL/MSFT
-- two long-listed mega-caps -- and warned "不能假設全市場都一樣深". This
script closes that gap with two groups of tickers, both selected from the
cached USStockInfo latest snapshot (data/raw/USStockInfo__ALL__2000-01-01__
latest.parquet, date=2026-08-22) using MarketCap/IPOYear columns, restricted
to plain alpha tickers (regex [A-Z]{1,5}) to avoid warrants/units/rights
suffixes (W/WS/U/R) which are a different, noisier instrument class:

  - small/mid cap group: MarketCap in [3e8, 2e9] on the latest snapshot.
    Picked XPER, SWIM, IMOS, ABR, OCSL (random sample, seed=3, from the 1523
    qualifying rows -- see marathon round log for the exact selection code).
  - recent-IPO group: IPOYear in [2021, 2023], MarketCap > 1e8. Picked
    FINW, LAW, NRGV, GPCR, CAVA (same sampling method).

All price fetches go through finmind_client.load_dev() (capped at VAL_END,
2024-12-31) per MARATHON_PROTOCOL.md section 4. This script only prints --
findings get written back into DATA.md/US_MARATHON_STATE.md by hand after
reading the output, same precedent as us_probe_milestone1.py.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from finmind_client import load_dev

SMALL_MID_CAP = ["XPER", "SWIM", "IMOS", "ABR", "OCSL"]
RECENT_IPO = ["FINW", "LAW", "NRGV", "GPCR", "CAVA"]


def probe_depth(label: str, tickers: list[str]) -> None:
    print(f"=== {label} (USStockPrice, load_dev, start=1990-01-01) ===")
    for t in tickers:
        df = load_dev("USStockPrice", t, start_date="1990-01-01")
        if df.empty:
            print(f"  {t}: EMPTY (no data at all)")
            continue
        dates = sorted(pd.to_datetime(df["date"]).dt.date.unique())
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        gap_counts = Counter(gaps)
        # flag any gap > 7 calendar days as a potential hole (long weekend/holiday
        # clusters normally cap out around 3-4 days; anything bigger is worth a look)
        big_gaps = [(dates[i], dates[i + 1]) for i in range(len(dates) - 1) if gaps[i] > 7]
        print(
            f"  {t}: {len(df)} rows, first={dates[0]}, last={dates[-1]}, "
            f"gap-histogram(days>1)={ {k: v for k, v in sorted(gap_counts.items()) if k > 1} }"
        )
        if big_gaps:
            print(f"    >7-day gaps ({len(big_gaps)}): {big_gaps[:5]}{' ...' if len(big_gaps) > 5 else ''}")


if __name__ == "__main__":
    probe_depth("small/mid cap group", SMALL_MID_CAP)
    print()
    probe_depth("recent-IPO group (2021-2023)", RECENT_IPO)
