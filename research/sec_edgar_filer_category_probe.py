"""Probe: does SEC EDGAR expose *historical* (per-fiscal-year) filer category
data, or only a single current snapshot?

Context (see US_MARATHON_STATE.md 下一輪建議工作單位 item 12, round 65's
`era_reliability()` open question): `era_reliability()` in `us_pit.py` applies
one SEC-wide accelerated-filer deadline schedule to every filer, regardless of
that filer's own historical filer-category status. Round 65 found this
unreliable for a recent IPO (PLTR, 14/24 mismatch rate) because a newly
public company's own filer-category history isn't accounted for. This probe
asks: does SEC's public API expose the per-company, per-year data needed to
fix that, or only today's snapshot?

Two candidate fields probed, both against AAPL/MSFT/PLTR (same three CIKs
prior rounds already verified, see sec_edgar_client.py):

1. `submissions/CIK{cik}.json` top-level `category` field.
2. `api/xbrl/companyfacts/CIK{cik}.json` -> facts.dei.EntityPublicFloat.

Deliberately NOT implementing era_reliability integration in this script --
that is a separate, larger work unit. This is investigation-only, matching
the "地基" precedent of sec_edgar_xbrl_facts_probe.py etc: probe, print,
document findings by hand in DATA.md/US_MARATHON_STATE.md, decide next step
in a later round.
"""
from __future__ import annotations

import requests

from sec_edgar_client import HEADERS, get_cik, get_cik_map, get_submissions

_TICKERS = ["AAPL", "MSFT", "PLTR"]


def probe_category_field() -> None:
    print("=== 1. submissions API top-level `category` field ===")
    cik_map = get_cik_map()
    for ticker in _TICKERS:
        cik = get_cik(ticker, cik_map)
        data = get_submissions(cik)
        print(f"{ticker}: category={data.get('category')!r}")
    print(
        "(this is ONE value per company -- today's snapshot, not a per-year "
        "history; no filing/date context, unlike filings.recent)"
    )


def probe_entity_public_float() -> None:
    print("\n=== 2. XBRL company facts: facts.dei.EntityPublicFloat ===")
    cik_map = get_cik_map()
    for ticker in _TICKERS:
        cik = get_cik(ticker, cik_map)
        cik_padded = str(cik).zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        dei = data.get("facts", {}).get("dei", {})
        print(f"{ticker}: dei concepts available = {sorted(dei.keys())}")
        entries = dei.get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
        print(f"  EntityPublicFloat: n={len(entries)} entries")
        for e in entries:
            print(
                f"    end={e.get('end')} val=${e.get('val'):,} fy={e.get('fy')} "
                f"form={e.get('form')} filed={e.get('filed')}"
            )
    print(
        "\n(EntityPublicFloat IS per-fiscal-year, tagged with `end`/`filed` -- "
        "this is the actual input SEC rules use to determine accelerated-filer "
        "status, not the category label itself. A per-year category proxy "
        "could in principle be *derived* from this + a historical threshold "
        "table, but that derivation is NOT done here -- open question below.)"
    )


if __name__ == "__main__":
    probe_category_field()
    probe_entity_public_float()
    print(
        "\n=== Conclusion ===\n"
        "`category` (submissions API): exists but is a single current-day "
        "snapshot (confirmed: AAPL/MSFT/PLTR all show 'Large accelerated "
        "filer' today, which is uninformative for PLTR's early years when it "
        "almost certainly was NOT large-accelerated). Same failure mode as "
        "USStockInfo / company_tickers.json snapshot fields documented "
        "elsewhere in US_MARATHON_STATE.md -- current-state fields cannot "
        "answer historical questions.\n"
        "`EntityPublicFloat` (XBRL dei concept): DOES have per-fiscal-year "
        "granularity with `end`/`filed`/`fy` -- this is a real candidate for "
        "deriving a per-company per-year filer-category proxy, since SEC's "
        "own accelerated-filer rule is defined directly in terms of public "
        "float thresholds. NOT YET DONE (left for a future round if this "
        "path is picked up): (a) confirming the historical threshold "
        "schedule itself (thresholds changed over time, same class of "
        "problem era_reliability()'s _ERA_SEGMENTS already solved for "
        "deadline days -- would need equally careful WebSearch verification, "
        "not guessing); (b) writing the derivation logic; (c) testing it "
        "against PLTR's known-unreliable years to see if it actually "
        "improves on the current single-schedule era_reliability()."
    )
