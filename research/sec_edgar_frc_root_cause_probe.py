"""US track, marathon round 2026-08-24 (~41st): follow-up to round 7's open question -- the
correct CIK for the 2010-2023-era NYSE:FRC (First Republic Bank) entity was never found in SEC
EDGAR, despite exhausting browse-edgar name search and efts.sec.gov full-text search. This round
does NOT find a CIK -- instead it finds why no CIK will ever be found, which is a bigger and more
useful result.

Step 1 -- broaden the browse-edgar company-name search beyond what round 7 tried. Round 7 only
tried the prefix "first republic" (returned 6 entities, all irrelevant) and a browse-edgar HTML
search for the exact name "first republic bank" (returned CIK 1132979, the 13G-only filer already
ruled out). This round adds:
  (a) prefix "first republic" + type=10-K filter, HTML output (not atom -- atom's <company-info
      name=...> attribute renders as a broken "ARRAY(0x...)" string on this SEC endpoint, a minor
      quirk worth recording so future rounds don't waste time on atom output for this query shape).
      Result: same 6 entities as round 7's plain prefix search (770975 BANCORP INC /CA, 834285
      REPUBLIC FIRST BANCORP INC /PA -- note reversed word order, a DIFFERENT bank, not a typo --,
      1137111/1137138 mortgage trusts, 36856 unrelated textile company, 1143834 PREFERRED CAPITAL
      CORP, a REIT subsidiary). None is a plausible 10-K filer for the real FRC.
  (b) exact name "first republic bank" (no type filter): surfaces a SECOND candidate round 7
      missed, CIK 1097256 "FIRST REPUBLIC BANK /MSD". Checked: single filing, form type "MSDW"
      (Morgan Stanley Dean Witter), dated 2008-08-28 -- almost certainly an MSDW-administered
      trust/note referencing First Republic Bank as a reference entity, not the bank's own filer
      CIK. Ruled out.
  Conclusion: exhausted browse-edgar name search across both prefix and exact-name modes, plus
  type=10-K restriction. No entity whose name plausibly matches "First Republic Bank" has EVER
  filed a 10-K in SEC EDGAR. This is the key clue for step 2.

Step 2 -- efts.sec.gov full-text search, broadened beyond round 7's narrow entityName-filtered
query. Searched unrestricted (no entityName, no form filter) for the exact phrase "First Republic
Bank" in filings from 2019 (a normal pre-crisis year, chosen so hits would mostly be the company's
own self-references plus third-party mentions, not crisis-era news 8-Ks from unrelated filers).
7,802 total hits, but the top-20 entity buckets are ALL mutual funds/ETFs holding FRC stock in
their portfolios (Fannie Mae, ProFunds, SPDR, DFA, etc.) -- not FRC itself. Narrowed further to
forms=10-K only, same 2019 window: 74 total hits, entity buckets are all Sequoia Mortgage Trusts
(unrelated RMBS issuers that happen to reference "First Republic Bank" as a loan originator/
servicer in boilerplate) plus a handful of unrelated banks. FRC's own FY2018 10-K (which should
exist and should self-reference "First Republic Bank" on its cover page alone) is simply ABSENT
from this index. This is the decisive anomaly: a company's own 10-K missing entirely from a
full-text-search corpus that captures 7,802 incidental third-party mentions in the same year
cannot be an indexing gap -- it means the 10-K was never filed with SEC EDGAR in the first place.

Step 3 -- resolve WHY: general web research (public, no-login SEC/FDIC/eCFR government sources
only, per MARATHON_PROTOCOL.md section 3's public-source rules) confirms Section 12(i) of the
Securities Exchange Act of 1934: FDIC-insured STATE NONMEMBER banks (state-chartered banks that
are not members of the Federal Reserve System) with securities registered under Exchange Act
section 12(b)/12(g) file their periodic disclosure reports (10-K/10-Q/8-K equivalents, beneficial
ownership, tender offers, proxy materials, etc.) directly with the FDIC under 12 CFR Part 335 --
NOT with the SEC -- because the FDIC (not the SEC) is that bank's primary securities regulator.
National banks file with the OCC; state MEMBER banks and bank holding companies file with the
Federal Reserve or SEC as applicable. Sources (both public, no-login, .gov):
  - https://www.fdic.gov/accounting/bank-securities
  - https://www.ecfr.gov/current/title-12/chapter-III/subchapter-B/part-335
First Republic Bank was a California STATE-CHARTERED bank and (per general public knowledge, not
independently re-verified this round -- flag as an assumption) was NOT a Federal Reserve member,
and critically had NO separate SEC-registered bank holding company above it (unlike most large
NYSE-listed banks, which use a holding-company structure specifically so the HOLDING COMPANY,
not the bank, is the SEC registrant). That combination -- non-Fed-member state bank, no separate
SEC-registered holding company -- means FRC's own periodic reports were filed with the FDIC, not
SEC EDGAR. This explains EVERY anomaly found across rounds 4-7 in one stroke:
  - no 10-K/10-Q/8-K under any "First Republic Bank"-named CIK in SEC EDGAR (steps 1-2 above)
  - no Form 25 for FRC's 2023 delisting (round 5/6/7 finding) -- Form 25 is an SEC form; an entity
    that was never an SEC EDGAR filer for its own reports would not use it
  - SBNY (Signature Bank, round 6) fits the same pattern -- also a NY STATE-chartered bank; if it
    was also a non-Fed-member, the same explanation applies (not independently confirmed this
    round which state banking regulator SBNY reported to -- flag as an assumption needing its own
    check before being treated as fully verified)
The round-6/7 "FDIC receivership doesn't file Form 25" hypothesis should be RETIRED, not merely
weakened further -- it was based on a false premise (assuming these were normal SEC-EDGAR-filing
entities that mysteriously stopped filing Form 25 upon receivership). The real explanation is
structural and predates the 2023 receivership entirely: these banks were never SEC EDGAR filers
for their own periodic reports to begin with, receivership or not.

Step 4 -- the FDIC's own public filing portal is reachable (200 OK): efr.fdic.gov/fcxweb/efr/ --
"Securities Exchange Act Filings System", per fdic.gov/accounting/bank-securities. It is a
JavaScript-driven single-page app (index.html loads index.jsp + jquery/bootstrap bundles); this
round only confirmed HTTP reachability and did not reverse-engineer its search API -- that is
explicitly left as the next round's work unit if this line of inquiry is judged worth continuing
(see US_MARATHON_STATE.md "下一輪建議工作單位" for the updated item 1/2 framing).

Net effect: item 1 (find FRC's SEC CIK) and item 2 (verify the FDIC-receivership-no-Form-25
hypothesis / find SBNY's delisting date) from the "下一輪建議工作單位" list are now understood to
be THE SAME QUESTION with the same root-cause answer, and neither can be resolved further within
SEC EDGAR -- any further progress requires the FDIC's own filing system (efr.fdic.gov) or a
banking-regulator-specific source, not more SEC EDGAR queries.

This script only fetches public SEC EDGAR + FDIC.gov pages (no FinMind, no alpha.db) -- same
holdout-non-applicability note as sec_edgar_probe.py / sec_edgar_frc_cik_probe.py. Prints only;
findings get written into DATA.md / US_MARATHON_STATE.md / US_LOG.md by hand after reading output.
"""
from __future__ import annotations

from collections import Counter

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}


def browse_edgar_name_search(company: str, type_filter: str | None = None) -> None:
    print(f"\n=== browse-edgar company name search: company={company!r} type={type_filter!r} ===")
    params = {
        "action": "getcompany", "company": company, "dateb": "", "owner": "include", "count": 100,
    }
    if type_filter:
        params["type"] = type_filter
    r = requests.get("https://www.sec.gov/cgi-bin/browse-edgar", params=params, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        return
    import re
    rows = re.findall(
        r'CIK=(\d{10})[^>]*>\1</a></td>\s*<td scope="row">([^<]+)', r.text
    )
    print(f"  {len(rows)} matches:")
    for cik, name in rows:
        print(f"    CIK {cik}: {name.strip()}")


def dump_cik_filing_profile(cik: int, label: str) -> None:
    print(f"\n=== CIK {cik} ({label}) ===")
    url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    print(f"  name: {data.get('name')}")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    print(f"  total filings: {len(forms)}, range: {min(dates) if dates else None}..{max(dates) if dates else None}")
    print(f"  form types: {Counter(forms).most_common(10)}")


def efts_search(q: str, forms: str | None = None, extra: dict | None = None, top_n: int = 20) -> None:
    params = {"q": q}
    if forms:
        params["forms"] = forms
    if extra:
        params.update(extra)
    r = requests.get("https://efts.sec.gov/LATEST/search-index", params=params, headers=HEADERS, timeout=20)
    print(f"\n=== efts full-text search: q={q!r} forms={forms} extra={extra} ===")
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        return
    d = r.json()
    print(f"  total hits: {d['hits']['total']}")
    buckets = d.get("aggregations", {}).get("entity_filter", {}).get("buckets", [])
    for b in buckets[:top_n]:
        print(f"    {b}")


def check_fdic_portal_reachable() -> None:
    print("\n=== FDIC Securities Exchange Act Filings System reachability ===")
    r = requests.get("https://efr.fdic.gov/fcxweb/efr/index.html", headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}, content-length={len(r.text)}")
    print("  (JS-driven SPA -- reverse-engineering its search API is a separate future work unit)")


if __name__ == "__main__":
    # Step 1: broaden browse-edgar name search beyond round 7's attempts.
    browse_edgar_name_search("first republic", type_filter="10-K")
    browse_edgar_name_search("first republic bank")  # no type filter -> surfaces CIK 1097256
    dump_cik_filing_profile(1097256, "new candidate: FIRST REPUBLIC BANK /MSD")
    dump_cik_filing_profile(1132979, "re-check: round-5/7 fallback CIK, already ruled out")

    # Step 2: unrestricted full-text search for FRC's own name in a normal pre-crisis year.
    efts_search('"First Republic Bank"', extra={"dateRange": "custom", "startdt": "2019-01-01", "enddt": "2019-12-31"})
    efts_search('"First Republic Bank"', forms="10-K", extra={"dateRange": "custom", "startdt": "2019-01-01", "enddt": "2019-12-31"})

    # Step 4: confirm the FDIC's own filing portal is publicly reachable.
    check_fdic_portal_reachable()
