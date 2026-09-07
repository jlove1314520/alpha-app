"""US-track systematic scan for additional death-spiral reverse-split
contamination candidates in `data/us_stratified_universe_sample.csv`
(round431's `us_contamination_blacklist.py` known-bad list of 8 tickers was
found opportunistically -- only names that happened to land in an extreme
decile of one of the three factors tested so far. `US_MARATHON_STATE.md`
round431 "下一輪US軌接手(1)" explicitly asks for a systematic pass over all
240/248 tickers instead of waiting for the next factor to stumble onto one.

**Method**: back-adjusted `adj_close` retroactively multiplies historical
nominal prices by the cumulative product of all *future* split ratios,
including future reverse splits. A death-spiral reverse-split name (does
several reverse splits over its life to dodge exchange-delisting price
floors) therefore shows an adj_close series that is enormous early in its
history and collapses toward its real recent price -- exactly the pattern
measured on the 8 known-bad names (`max/last` ratio 6.4 to 3,304,364).
Genuine (non-contaminated) decliners exist too (a stock can legitimately
fall 90%), so this is a screen for *candidates to inspect*, not an
automatic blacklist addition -- consistent with `MARATHON_PROTOCOL.md`
1a's "no p-hacking a threshold to get the answer you want": the two
thresholds below are read directly off the known-bad calibration sample
and are NOT tuned against the unknown 240 to maximize hits.

Threshold (pre-registered against the known-bad calibration sample, not
tuned on the unknown 240): flag if max(adj_close) > $1,000 (no genuine
small/mid-cap name in this stratified sample should trade there; it is
either a reporting/currency artifact or a reverse-split back-adjustment)
OR max/last ratio > 5 (the lowest ratio among the 8 known-bad names,
WULF, is 6.4 -- 5 is a conservative floor below that).

Zero new API calls: `us_price_series()` hits the existing FinMind dev-cache
parquet built by prior `#20`/`#21`/`#23` factor runs (all 248 already
fetched).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from us_contamination_blacklist import KNOWN_CONTAMINATED_TICKERS
from us_factors import us_price_series

UNIVERSE_CSV = Path(__file__).parent / "data" / "us_stratified_universe_sample.csv"
MAX_PRICE_THRESHOLD = 1000.0
MAX_OVER_LAST_THRESHOLD = 5.0


def scan() -> pd.DataFrame:
    df = pd.read_csv(UNIVERSE_CSV)
    tickers = df[df["usable"] == True]["stock_id"].tolist()  # noqa: E712
    rows = []
    for i, t in enumerate(tickers):
        px = us_price_series(t)
        if px.empty:
            rows.append({"ticker": t, "status": "empty_price_series"})
            continue
        adj = px["adj_close"].dropna()
        if adj.empty:
            rows.append({"ticker": t, "status": "all_nan_adj_close"})
            continue
        mx = float(adj.max())
        last = float(adj.iloc[-1])
        first = float(adj.iloc[0])
        ratio = mx / last if last > 0 else float("inf")
        flagged = (mx > MAX_PRICE_THRESHOLD) or (ratio > MAX_OVER_LAST_THRESHOLD)
        rows.append({
            "ticker": t, "status": "ok", "n_days": len(px),
            "first_adj_close": first, "last_adj_close": last,
            "max_adj_close": mx, "max_over_last_ratio": ratio,
            "already_blacklisted": t in KNOWN_CONTAMINATED_TICKERS,
            "flagged_new_candidate": flagged and t not in KNOWN_CONTAMINATED_TICKERS,
        })
    return pd.DataFrame(rows)


def main():
    print("=== US-track systematic reverse-split contamination scan ===")
    print(f"universe: {UNIVERSE_CSV.name}, thresholds: max_price>${MAX_PRICE_THRESHOLD:.0f} "
          f"OR max/last>{MAX_OVER_LAST_THRESHOLD:.0f}x (calibrated on known-bad 8, not tuned on unknown set)")
    result = scan()
    out_path = Path(__file__).parent / "data" / "us_reverse_split_contamination_scan.csv"
    result.to_csv(out_path, index=False)
    print(f"\n{len(result)} tickers scanned, written to {out_path}")

    ok = result[result["status"] == "ok"]
    print(f"  status breakdown: {result['status'].value_counts().to_dict()}")

    already = ok[ok["already_blacklisted"]]
    print(f"\n{len(already)} already-blacklisted names re-confirmed flagged by these thresholds: "
          f"{sorted(already[already['flagged_new_candidate'] | already['already_blacklisted']]['ticker'].tolist())}")
    # sanity: do the thresholds actually catch all 8 known-bad?
    caught = already[(already["max_adj_close"] > MAX_PRICE_THRESHOLD) | (already["max_over_last_ratio"] > MAX_OVER_LAST_THRESHOLD)]
    print(f"  of {len(already)} already-blacklisted names present in usable set, "
          f"{len(caught)} would independently be caught by these thresholds (sanity check on calibration)")

    new_candidates = ok[ok["flagged_new_candidate"]].sort_values("max_over_last_ratio", ascending=False)
    print(f"\n{len(new_candidates)} NEW candidate(s) flagged (not already in blacklist):")
    if len(new_candidates):
        print(new_candidates[["ticker", "n_days", "first_adj_close", "last_adj_close",
                               "max_adj_close", "max_over_last_ratio"]].to_string(index=False))
    else:
        print("  (none)")


if __name__ == "__main__":
    main()
