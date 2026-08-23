"""US track, marathon round 2026-08-23 (5th): follow-up to us_survivorship_probe.py's
negative finding -- that round's "known last trading day" values were sanity-checked
from human memory of news coverage, not from an authoritative source. This round uses
the SEC EDGAR API (already live-verified working in sec_edgar_probe.py, round 3) to
check the actual filing record for the same 5 tickers, specifically looking for Form 25
/ 25-NSE (notification of removal from listing) filings, which is the authoritative
signal a company was formally delisted.

Question this answers: for TWTR/SIVB/SBNY/FRC/BBBY, does SEC EDGAR's own filing history
confirm delisting (and roughly when), or does the current company_tickers.json ticker
map not even resolve these anymore (which would itself explain part of round 4's EMPTY
results -- if company_tickers.json only lists currently-active tickers, a delisted
company's CIK can't be found this way at all, independent of whether SEC has records
for it under its CIK).

Two-step approach per ticker:
1. Try to resolve CIK via company_tickers.json (same map used in sec_edgar_probe.py).
   If not found, that's itself a finding: the *current* ticker->CIK map excludes it.
2. If a CIK is known (either from step 1, or hardcoded as a fallback for tickers that
   dropped off the current map), pull the full submissions JSON and scan filings.recent
   (and, if needed, the older filings.files[] archive pages) for form types starting
   with "25" (25, 25-NSE, 15-12B, 15-12G -- Section 12(g) deregistration is another
   delisting-adjacent signal worth capturing even though Form 25 is the primary one).

   CORRECTION (round 6, 2026-08-24): round 4's original docstring here claimed a
   hardcoded CIK fallback carries less "trust human memory" risk than a hardcoded date,
   reasoning that CIKs are permanent identifiers. Round 5 falsified this for SBNY --
   the hardcoded fallback (1288776) resolved to GOOGLE INC., not Signature Bank. A
   hand-typed, unverified identifier is a hand-typed, unverified identifier regardless
   of whether it happens to be a CIK or a date; neither is safe without checking the
   submissions API response's company name against what you expect. Round 6 tried to
   find the correct SBNY CIK via www.sec.gov/cgi-bin/browse-edgar company-name search
   and efts.sec.gov full-text-search entity aggregation (including an exhaustive scan
   of all Form 25-NSE filings in the 2023-03-01..2023-06-30 window, which correctly
   surfaced SVB FINANCIAL GROUP but never any entity containing "Signature") and did
   NOT find it -- the correct CIK for SBNY remains unknown. Do not add a new hardcoded
   guess without independently confirming the company name in the submissions response.

Hardcoded CIK fallback values below are copied from the same company_tickers.json
lookup style, but since round 4 already showed the *current* ticker map may not
resolve these anymore, this script tries the live lookup first and only falls back
to a hardcoded value if that fails -- and prints clearly which path was used, so the
provenance is honest in the output (not silently substituted).

This script only fetches SEC EDGAR data (no FinMind, no alpha.db) -- same
holdout-non-applicability note as sec_edgar_probe.py. Prints only; findings get
written into DATA.md / US_MARATHON_STATE.md / US_LOG.md by hand after reading output.
"""
from __future__ import annotations

import time

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}

# Fallback CIKs, used only if the live company_tickers.json lookup misses the ticker.
# Verified correct (submissions API company name matches, per round 5/6): TWTR, SIVB,
# FRC, BBBY. If a fallback is wrong, the submissions API will simply 404 or return an
# unrelated company (visible in the printed company name), not silently succeed -- this
# is exactly what happened for SBNY (see below), which is why "CIK fallback = safe"
# is NOT a blanket assumption; each value here still needs independent verification.
#
# SBNY: KNOWN WRONG, unresolved as of round 6 (2026-08-24). 1288776 resolves to
# GOOGLE INC., not Signature Bank (round 5 finding). Round 6 tried browse-edgar
# company-name search and efts.sec.gov full-text-search entity aggregation (including
# an exhaustive scan of every Form 25-NSE filer in 2023-03-01..2023-06-30) and could
# NOT find the correct CIK -- no entity containing "Signature" appears anywhere in
# that search. Do not replace this with a new guess without verifying the company
# name in the actual submissions API response first. See DATA.md "美股存活者偏差調查
# （再續）" (round 6) for the full negative-result writeup, including a new hypothesis
# that FDIC-receivership delistings (SBNY, and FRC from round 5) may not go through a
# standard Form 25 at all, unlike voluntary/acquisition delistings (TWTR, SIVB).
FALLBACK_CIK = {
    "TWTR": 1418091,
    "SIVB": 719739,
    "SBNY": None,  # unresolved, see comment above -- do not guess
    "FRC": 1132979,
    "BBBY": 886158,
}

DELISTING_FORM_PREFIXES = ("25", "15-12")


def load_ticker_map() -> dict[str, int]:
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"company_tickers.json: status={r.status_code}, entries={len(r.json()) if r.status_code == 200 else 'N/A'}")
    if r.status_code != 200:
        return {}
    data = r.json()
    return {v["ticker"]: v["cik_str"] for v in data.values()}


def probe_ticker(ticker: str, ticker_map: dict[str, int]) -> None:
    print(f"\n=== {ticker} ===")
    cik = ticker_map.get(ticker)
    source = "live company_tickers.json"
    if cik is None:
        cik = FALLBACK_CIK.get(ticker)
        source = "hardcoded fallback (ticker not in current company_tickers.json)"
        if cik is None:
            print("  no CIK available from either source -- cannot probe further")
            return
    print(f"  CIK={cik} (source: {source})")

    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  submissions status={r.status_code}")
    if r.status_code != 200:
        print(f"  FAILED, body snippet: {r.text[:200]}")
        return
    data = r.json()
    company_name = data.get("name")
    print(f"  company name on file: {company_name}")

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    delisting_filings = [
        (forms[i], dates[i])
        for i in range(len(forms))
        if forms[i].startswith(DELISTING_FORM_PREFIXES)
    ]
    if delisting_filings:
        print(f"  delisting-adjacent filings found in 'recent' window: {delisting_filings}")
    else:
        print(
            "  no Form 25/25-NSE/15-12B/15-12G in 'recent' window "
            f"(window covers {len(forms)} filings, earliest={min(dates) if dates else 'N/A'}, "
            f"latest={max(dates) if dates else 'N/A'}) -- if the real delisting predates "
            "this window, it would only be in the older filings.files[] archive pages, not checked here"
        )

    archive_files = data.get("filings", {}).get("files", [])
    if archive_files:
        print(f"  older-filings archive pointers exist: {[f['name'] for f in archive_files]} (not fetched this round)")


if __name__ == "__main__":
    ticker_map = load_ticker_map()
    for t in ["TWTR", "SIVB", "SBNY", "FRC", "BBBY"]:
        probe_ticker(t, ticker_map)
        time.sleep(0.3)  # stay well under SEC's ~10 req/sec guidance, no functional need for more
