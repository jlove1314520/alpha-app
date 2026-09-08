"""US-track corporate-action verification for the 59 flagged-but-unconfirmed
reverse-split contamination candidates left open by round433
(`us_reverse_split_contamination_scan.py` / `us_contamination_blacklist.py`
docstring: "confirming them needs per-ticker corporate-action lookup this
round did not do").

**Why price-magnitude alone (round433's method) isn't enough for this
group**: their max/last ratio (5x-160x) sits inside the range a genuine
company can plausibly show through ordinary long-run business decline (the
docstring's own example, AMN, appreciated to $127 during the COVID travel-
nursing boom then fell to $24 -- a real 5.3x round-trip, no death spiral).
Price shape alone cannot distinguish "real decline" from "reverse-split
back-adjustment" at this magnitude; it needs an actual corporate-action
record.

**Method** (SEC EDGAR full-text search, the market's *native* source per
`CLAUDE.md`'s 2026-09-08 decree -- no FinMind/Taiwan-vendor calls made here):
1. Resolve each ticker's current CIK via `sec_edgar_client.get_cik_map()`
   (already-cached, zero new calls beyond the one shared ticker-map fetch).
2. Query `efts.sec.gov` full-text search for the phrase "reverse stock
   split" restricted to `forms=8-K` and this ticker's CIK.
3. Keep only hits whose `file_date` falls inside the ticker's own price
   history window (`us_price_series()` first/last date, read from the
   existing FinMind dev-cache -- zero new price-vendor calls, same reuse
   pattern as round433's scan) -- a reverse split filed *before* the price
   series starts or *after* it ends cannot be the cause of an in-window
   back-adjustment artifact.
4. Classify:
   - 0 in-window hits -> `no_reverse_split_found` (contamination NOT
     confirmed; treat as a genuine decliner, do not blacklist).
   - >=2 in-window hits -> `serial_reverse_split_confirmed` (a company
     doing two or more reverse splits within the very window we're
     measuring is the death-spiral-financing pattern the blacklist exists
     to catch, independent of magnitude reconciliation -- legitimate
     companies essentially never do this) -> ADD to blacklist.
   - exactly 1 in-window hit -> `single_split_inconclusive`: fetch that
     filing's primary document and regex for a declared ratio
     ("N-for-1", "1-for-N", spelled-out small numbers "one"/"ten"/etc.)
     to sanity-check order of magnitude against the observed
     `max_over_last_ratio`. If the parsed ratio is within a factor of 3 of
     the observed ratio, treat as `single_split_confirmed` (one real split
     fully explains the observed magnitude) -> ADD to blacklist. Otherwise
     leave as `single_split_inconclusive` -> do NOT blacklist (a single
     split of unclear/mismatched magnitude is exactly the AMN-shaped case
     this round exists to avoid mislabeling).

Rate limiting: efts.sec.gov has no published hard ceiling (unlike
data.sec.gov's documented ~10 req/sec); this script sleeps 0.4s between
calls (well under 10/s) and only fetches a filing document for tickers that
clear the >=1-hit gate, so worst case is 59 search calls + <=59 document
fetches, ~1-2 minutes total. No retries/backoff added -- if SEC rate-limits
us the run fails loudly (`raise_for_status`) rather than silently degrading.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import requests

from sec_edgar_client import HEADERS, get_cik_map
from us_factors import us_price_series

SCAN_CSV = Path(__file__).parent / "data" / "us_reverse_split_contamination_scan.csv"
OUT_CSV = Path(__file__).parent / "data" / "us_reverse_split_corporate_action_verify.csv"
SLEEP_SEC = 0.4
RATIO_MATCH_TOLERANCE = 3.0  # single-split parsed ratio must be within 3x of observed to confirm

_SPELLED = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100,
}
_RATIO_RE = re.compile(
    r"(?:1|one)[\s-]*for[\s-]*(\d+|" + "|".join(_SPELLED) + r")\b",
    re.IGNORECASE,
)


def _search_reverse_split_8k(cik: int) -> list[dict]:
    url = (
        "https://efts.sec.gov/LATEST/search-index?"
        f"q=%22reverse+stock+split%22&forms=8-K&ciks={cik:010d}"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    out = []
    for h in hits:
        src = h["_source"]
        adsh = src["adsh"].replace("-", "")
        cik_str = src["ciks"][0].lstrip("0") or "0"
        doc_id = h["_id"].split(":")[-1]
        out.append({
            "file_date": src["file_date"],
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik_str}/{adsh}/{doc_id}",
        })
    return out


def _parse_ratio(text: str) -> float | None:
    ratios = []
    for m in _RATIO_RE.finditer(text):
        tok = m.group(1).lower()
        val = _SPELLED.get(tok)
        if val is None:
            try:
                val = int(tok)
            except ValueError:
                continue
        ratios.append(val)
    if not ratios:
        return None
    # a filing can mention the ratio multiple times (title + body) -- take
    # the largest as the declared ratio (smaller numbers are more likely to
    # be incidental digits caught by the regex, e.g. share counts).
    return float(max(ratios))


def verify() -> pd.DataFrame:
    scan = pd.read_csv(SCAN_CSV)
    candidates = scan[
        (scan["flagged_new_candidate"] == True) & (scan["already_blacklisted"] == False)  # noqa: E712
    ].sort_values("max_over_last_ratio", ascending=False)

    cik_map = get_cik_map()
    rows = []
    for _, row in candidates.iterrows():
        ticker = row["ticker"]
        cik = cik_map.get(ticker)
        if cik is None:
            rows.append({"ticker": ticker, "status": "no_cik_found",
                         "observed_ratio": row["max_over_last_ratio"]})
            continue

        px = us_price_series(ticker)
        if px.empty:
            rows.append({"ticker": ticker, "status": "no_price_series",
                         "observed_ratio": row["max_over_last_ratio"]})
            continue
        px_start, px_end = px["date"].min(), px["date"].max()

        try:
            hits = _search_reverse_split_8k(int(cik))
        except requests.HTTPError as e:
            rows.append({"ticker": ticker, "status": f"search_http_error:{e.response.status_code}",
                         "observed_ratio": row["max_over_last_ratio"]})
            time.sleep(SLEEP_SEC)
            continue
        except requests.RequestException as e:
            # transient network/timeout -- record and move on, don't let one
            # flaky call kill the other ~58 tickers' results.
            rows.append({"ticker": ticker, "status": f"search_network_error:{type(e).__name__}",
                         "observed_ratio": row["max_over_last_ratio"]})
            time.sleep(SLEEP_SEC)
            continue
        time.sleep(SLEEP_SEC)

        in_window = [h for h in hits if px_start <= h["file_date"] <= px_end]
        n_in_window = len(in_window)

        result = {
            "ticker": ticker, "cik": int(cik),
            "observed_ratio": row["max_over_last_ratio"],
            "px_start": px_start, "px_end": px_end,
            "n_8k_hits_total": len(hits), "n_8k_hits_in_window": n_in_window,
        }

        if n_in_window == 0:
            result["status"] = "no_reverse_split_found"
            result["confirmed"] = False
        elif n_in_window >= 2:
            result["status"] = "serial_reverse_split_confirmed"
            result["confirmed"] = True
        else:
            doc_url = in_window[0]["url"]
            try:
                doc_r = requests.get(doc_url, headers=HEADERS, timeout=20)
                doc_r.raise_for_status()
                parsed_ratio = _parse_ratio(doc_r.text)
            except requests.HTTPError as e:
                parsed_ratio = None
                result["doc_fetch_error"] = f"http_{e.response.status_code}"
            except requests.RequestException as e:
                parsed_ratio = None
                result["doc_fetch_error"] = type(e).__name__
            time.sleep(SLEEP_SEC)
            result["parsed_split_ratio"] = parsed_ratio
            if parsed_ratio is not None:
                observed = row["max_over_last_ratio"]
                match = (observed / RATIO_MATCH_TOLERANCE) <= parsed_ratio <= (observed * RATIO_MATCH_TOLERANCE)
                result["status"] = "single_split_confirmed" if match else "single_split_inconclusive"
                result["confirmed"] = bool(match)
            else:
                result["status"] = "single_split_inconclusive_unparsed"
                result["confirmed"] = False

        rows.append(result)
        print(f"  {ticker}: {result['status']} (in_window_hits={n_in_window})")

    return pd.DataFrame(rows)


def main():
    print("=== US-track corporate-action verification for 59 unconfirmed reverse-split candidates ===")
    result = verify()
    result.to_csv(OUT_CSV, index=False)
    print(f"\n{len(result)} tickers checked, written to {OUT_CSV}")
    if "status" in result.columns:
        print(result["status"].value_counts().to_string())
    if "confirmed" in result.columns:
        confirmed = result[result["confirmed"] == True]  # noqa: E712
        print(f"\n{len(confirmed)} CONFIRMED contaminated (to add to blacklist): {sorted(confirmed['ticker'].tolist())}")


if __name__ == "__main__":
    main()
