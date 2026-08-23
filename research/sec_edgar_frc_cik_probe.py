"""US track, marathon round 2026-08-24 (7th): follow-up to round 5/6's open question about
FRC (First Republic Bank, NYSE ticker, collapsed/seized by FDIC 2023-05-01) -- round 5 found
no Form 25/25-NSE for FRC's fallback CIK (1132979) within the `filings.recent` window and left
open whether this was (a) a genuine "FDIC receivership doesn't file Form 25" finding, (b) a
window-truncation artifact needing `filings.files[]` archive pages, or (c) something else.

This round answers (b) directly, and in doing so discovers a bigger, unrelated problem: the
FALLBACK_CIK["FRC"] value used since round 5 (1132979) is very likely the WRONG ENTITY.

Step 1 -- resolve (b): fetch submissions API for CIK 1132979, check `filings.files[]` (the
older-archive pointer list). Result: EMPTY. `filings.recent` for this CIK spans 2004-01-05 to
2024-02-09 -- i.e. `recent` IS the complete filing history for this CIK, not a truncated
window; there is no older archive to be missing filings from. This confirms round 5's
"no Form 25 found" was NOT a window-truncation artifact.

Step 2 -- but is CIK 1132979 even the right entity? Its full filing history (43 filings) is
entirely `SC 13G` / `SC 13G/A` (beneficial-ownership disclosures, normally filed by an
institutional investor about ITS holdings in some OTHER company) plus one `40-6B/A` -- zero
10-K, zero 10-Q, zero 8-K. That is not a plausible filing profile for a NYSE-listed bank
holding company the size of the real First Republic Bank (FRC), which should have ~13 years
of annual 10-Ks, quarterly 10-Qs, and routine 8-Ks. This is a strong signal that CIK 1132979,
while its `name` field says "FIRST REPUBLIC BANK", is NOT the corporate SEC filer CIK for the
company that traded as NYSE:FRC -- most likely it is a different CIK role for the bank (e.g.
its trust/wealth-management arm filing 13Gs as a beneficial owner of OTHER companies' stock),
never independently checked beyond "company name matches" in round 5.

Step 3 -- attempt to find the correct CIK for the real NYSE:FRC filer:
  (a) browse-edgar company-name search ("first republic") surfaces CIK 0000770975,
      "FIRST REPUBLIC BANCORP INC" (San Francisco, CA) -- plausible-sounding, but its full
      filing history (90 filings) ends in 2008-02-14 and includes a genuine Form 25 dated
      2005-04-22. This is evidently a DIFFERENT, older "First Republic" entity (delisted/
      went private in 2005) that predates the 2010 IPO of the bank that later collapsed in
      2023. Same name-collision trap as SBNY (round 6) and BBBY (round 5), now confirmed for
      "First Republic" too -- three out of five original tickers in this investigation have
      now hit an entity-name-collision problem.
  (b) efts.sec.gov full-text search restricted to Form 25-NSE in the 2023-04-01..2023-08-31
      window (around FRC's 2023-05-01 FDIC seizure), searching for "republic" in doc text:
      only 1 unrelated hit (Global Cord Blood Corp, matched incidentally). No FRC-related
      entity appears in the Form-25-NSE entity aggregation for this window at all.
  (c) efts.sec.gov full-text search for entityName="First Republic Bank" + forms=10-K: only
      2 hits, both unrelated mortgage-backed-securities trusts (FIRST REPUBLIC BANK MORT PAS
      THR CER ... TRUST), not the bank itself.
  (d) www.sec.gov/files/company_tickers.json: ticker "FRC" does not resolve at all (already
      known from round 4/5 -- delisted tickers drop off the live map).
  Conclusion: the correct CIK for the 2010-2023-era NYSE:FRC entity was NOT found this round.
  This is an open, unresolved question -- do not guess a new CIK without independently
  verifying the company name AND a plausible filing-type profile (10-K/10-Q/8-K presence,
  not just 13G) in the submissions API response.

Net effect on the FDIC-receivership hypothesis (round 6, from SBNY+FRC both lacking Form 25):
that hypothesis is now WEAKER than round 6's writeup implied, not stronger. Round 6's FRC
data point was based on the wrong CIK the whole time (per this round's Step 2 finding), so
"FRC has no Form 25" was never actually confirmed for the real entity -- it was confirmed
only for an unrelated 13G-filer CIK that happens to share a name. The hypothesis still has
SBNY as a data point (search exhausted, no candidate CIK found at all, so it can't be
re-checked either way), but SBNY alone is not two independent confirmations anymore.

This script only fetches SEC EDGAR data (no FinMind, no alpha.db) -- same holdout-non-
applicability note as sec_edgar_probe.py / sec_edgar_delisting_probe.py. Prints only;
findings get written into DATA.md / US_MARATHON_STATE.md / US_LOG.md by hand after reading
output.
"""
from __future__ import annotations

from collections import Counter

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}


def dump_cik_filing_profile(cik: int, label: str) -> None:
    print(f"\n=== CIK {cik} ({label}) ===")
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        print(f"  FAILED, body snippet: {r.text[:200]}")
        return
    data = r.json()
    print(f"  name on file: {data.get('name')}")
    print(f"  tickers: {data.get('tickers')}, exchanges: {data.get('exchanges')}")
    archive_files = data.get("filings", {}).get("files", [])
    print(f"  archive pointer list (filings.files[]): {archive_files}")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    print(f"  total filings in 'recent': {len(forms)}, date range: "
          f"{min(dates) if dates else 'N/A'} .. {max(dates) if dates else 'N/A'}")
    print(f"  form type distribution: {Counter(forms).most_common(15)}")
    delisting = [(forms[i], dates[i]) for i in range(len(forms)) if forms[i].startswith(("25", "15-12"))]
    print(f"  delisting-adjacent filings (25*/15-12*): {delisting}")


def search_efts_form_window(query: str, forms: str, startdt: str, enddt: str) -> None:
    print(f"\n=== efts full-text search: q={query!r} forms={forms} {startdt}..{enddt} ===")
    url = (
        f'https://efts.sec.gov/LATEST/search-index?q={requests.utils.quote(chr(34) + query + chr(34))}'
        f"&forms={forms}&dateRange=custom&startdt={startdt}&enddt={enddt}"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    print(f"  total hits: {data['hits']['total']}")
    buckets = data.get("aggregations", {}).get("entity_filter", {}).get("buckets", [])
    for b in buckets[:15]:
        print(f"    {b}")


if __name__ == "__main__":
    # Step 1+2: is the round-5 fallback CIK's "empty archive" real, and is it even FRC?
    dump_cik_filing_profile(1132979, "round-5 FALLBACK_CIK['FRC'], name says 'FIRST REPUBLIC BANK'")

    # Step 3a: browse-edgar company-name search candidate
    dump_cik_filing_profile(770975, "browse-edgar company-name search hit, 'FIRST REPUBLIC BANCORP INC'")

    # Step 3b: full-text search for Form 25-NSE near the 2023-05-01 FDIC seizure date
    search_efts_form_window("republic", "25-NSE", "2023-04-01", "2023-08-31")

    # Step 3c: full-text search for 10-K filings literally named "First Republic Bank"
    print("\n=== efts full-text search: entityName filter, forms=10-K ===")
    url = (
        "https://efts.sec.gov/LATEST/search-index?q=%22Item+1.+Business%22"
        "&forms=10-K&entityName=First+Republic+Bank"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  total hits: {data['hits']['total']}")
        for h in data["hits"]["hits"][:5]:
            print(f"    {h['_source']['display_names']} {h['_source']['file_date']}")

    # Step 3d: does the current live ticker map resolve FRC at all? (expected: no, per round 4/5)
    print("\n=== company_tickers.json: does 'FRC' resolve? ===")
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=20)
    tmap = r.json() if r.status_code == 200 else {}
    hit = next((v for v in tmap.values() if v.get("ticker") == "FRC"), None)
    print(f"  {hit if hit else 'not found (consistent with round 4/5: delisted tickers drop off the live map)'}")
