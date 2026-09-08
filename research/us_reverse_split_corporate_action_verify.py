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
4. **Require item 5.03** ("Amendments to Articles of Incorporation or
   Bylaws" -- the SEC-mandated disclosure item for an executed change to
   share structure) on at least one in-window hit before confirming.
   A first version of this script used a cruder ">=2 raw phrase hits"
   heuristic and it produced a confirmed false positive on the very first
   run: `FCNCA` (First Citizens BancShares, a real, never-split, high
   nominal-price bank stock -- round433's own manual false-positive
   example) had 3 in-window "reverse stock split" hits, but all were items
   1.01/7.01/8.01/9.01 -- boilerplate mentions of the phrase inside a
   merger/securities agreement, not FCNCA's own stock being split. None
   had item 5.03. Requiring 5.03 rules that class of false positive out at
   the search-result level, with zero extra HTTP calls (item codes are
   already in the search response), and needs no document fetch or
   ratio-parsing to sanity-check magnitude.
   - 0 in-window hits -> `no_reverse_split_found` (not confirmed).
   - in-window hits but none carry item 5.03 -> `phrase_mentioned_no_item503_likely_boilerplate`
     (not confirmed -- the FCNCA-shaped case).
   - >=1 in-window hit carries item 5.03 -> `item503_reverse_split_confirmed`
     (an actual executed change to share structure was filed inside the
     price window) -> ADD to blacklist.

Rate limiting: efts.sec.gov has no published hard ceiling (unlike
data.sec.gov's documented ~10 req/sec); this script sleeps 0.4s between
calls (well under 10/s), one search call per ticker, ~59 calls total,
under a minute. No retries/backoff added -- if SEC rate-limits us a given
ticker's row records `search_network_error`/`search_http_error` rather
than crashing the whole run (a real timeout was hit and recovered from
during development).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import requests

from sec_edgar_client import HEADERS, get_cik_map
from us_contamination_blacklist import KNOWN_CONTAMINATED_TICKERS
from us_factors import us_price_series

SCAN_CSV = Path(__file__).parent / "data" / "us_reverse_split_contamination_scan.csv"
OUT_CSV = Path(__file__).parent / "data" / "us_reverse_split_corporate_action_verify.csv"
SLEEP_SEC = 0.4


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
            "items": src.get("items", []),
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik_str}/{adsh}/{doc_id}",
        })
    return out


def verify() -> pd.DataFrame:
    scan = pd.read_csv(SCAN_CSV)
    # NOTE (fixed after a first pass got this wrong): `flagged_new_candidate`
    # and `already_blacklisted` in the scan CSV are frozen at round433 scan
    # time -- `already_blacklisted` only reflects the ORIGINAL 8-name list,
    # not the 25-name list round433 itself grew to by its own end. Filtering
    # on those stale columns re-includes the 17 round433 already added.
    # Filter against the current `KNOWN_CONTAMINATED_TICKERS` instead.
    candidates = scan[
        (scan["flagged_new_candidate"] == True)  # noqa: E712
        & (~scan["ticker"].isin(KNOWN_CONTAMINATED_TICKERS))
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
        # Item 5.03 ("Amendments to Articles of Incorporation or Bylaws") is
        # the SEC-mandated disclosure item for an *executed* change to share
        # structure (a reverse split changes authorized/outstanding shares
        # and often par value). A bare phrase-count heuristic was tried
        # first and produced a confirmed false positive: FCNCA (First
        # Citizens BancShares, a real, never-split bank stock) had 3
        # in-window hits, all items 1.01/7.01/8.01/9.01 -- boilerplate
        # mentions of "reverse stock split" as a generic mechanism in a
        # merger/securities agreement, not FCNCA's own stock being split.
        # Requiring item 5.03 rules that class of false positive out.
        item503_hits = [h for h in in_window if "5.03" in h.get("items", [])]
        n_in_window, n_503 = len(in_window), len(item503_hits)

        result = {
            "ticker": ticker, "cik": int(cik),
            "observed_ratio": row["max_over_last_ratio"],
            "px_start": px_start, "px_end": px_end,
            "n_8k_hits_total": len(hits), "n_8k_hits_in_window": n_in_window,
            "n_item503_hits_in_window": n_503,
        }

        if n_503 >= 1:
            result["status"] = "item503_reverse_split_confirmed"
            result["confirmed"] = True
        elif n_in_window >= 1:
            result["status"] = "phrase_mentioned_no_item503_likely_boilerplate"
            result["confirmed"] = False
        else:
            result["status"] = "no_reverse_split_found"
            result["confirmed"] = False

        rows.append(result)
        print(f"  {ticker}: {result['status']} (in_window={n_in_window}, item5.03={n_503})")

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
