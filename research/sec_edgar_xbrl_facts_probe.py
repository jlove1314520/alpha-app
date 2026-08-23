"""US track, marathon round 2026-08-24 (round: pick up US_MARATHON_STATE.md
suggestion #3): first live probe of the SEC EDGAR XBRL "company facts" API,
following up on sec_edgar_probe.py (round 3) which only tested the
submissions API.

Round 3 confirmed data.sec.gov/submissions/CIK{cik}.json exposes
filingDate/reportDate per filing. This script checks whether the XBRL
company-facts endpoint offers something more precise or complementary for
PIT alignment purposes -- specifically whether its `filed` field (per
XBRL fact, not per filing) lines up with the submissions API's filingDate,
and whether it gives finer-grained per-metric disclosure timestamps that
could matter for a future US-track pit.py analog.

Endpoint tested (public, no-auth, per SEC's own developer docs):
- https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json

This is independent of the open FRC/SBNY CIK problem (US_MARATHON_STATE.md
work items #1/#2) -- it only needs CIKs already validated in round 3
(AAPL/MSFT/PLTR), so it can be done as a standalone bounded work unit
without touching the still-unresolved survivorship-bias CIK lookups.

Rate/identification: same User-Agent convention as sec_edgar_probe.py (a
project-identifying placeholder, not the user's real email -- CLAUDE.md
says not to send it to unrelated third-party services). Fetches at most 3
CIKs' company-facts payloads (one request each), well under SEC's
documented ~10 req/sec guidance.

Only fetches SEC EDGAR data (not FinMind, not alpha.db) -- the holdout
boundary in MARATHON_PROTOCOL.md section 4 doesn't apply here. This script
prints; it does not write to other research/*.md files itself (those get
updated by hand after reading its output, same convention as
sec_edgar_probe.py).
"""
from __future__ import annotations

from datetime import date

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}

# CIKs already validated live in round 3 (sec_edgar_probe.py) -- reused here
# to avoid re-fetching the ticker->CIK map for the same three names.
KNOWN_CIK = {"AAPL": 320193, "MSFT": 789019, "PLTR": 1321655}

# EPS-related XBRL concept tags to sample from us-gaap taxonomy. Not every
# filer uses every tag (e.g. some report diluted EPS only under a different
# tag name) -- this is intentionally a short probe list, not a full mapping.
SAMPLE_CONCEPTS = ["EarningsPerShareDiluted", "Revenues"]


def probe_company_facts(ticker: str, cik: int) -> None:
    print(f"\n=== Company facts API ({ticker}, CIK={cik}) ===")
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    print(f"  status={r.status_code}, content-type={r.headers.get('Content-Type')}")
    if r.status_code != 200:
        print(f"  FAILED, body snippet: {r.text[:300]}")
        return
    data = r.json()
    print(f"  top-level keys: {list(data.keys())}")
    facts = data.get("facts", {})
    print(f"  facts taxonomies present: {list(facts.keys())}")
    usgaap = facts.get("us-gaap", {})
    print(f"  us-gaap concept count: {len(usgaap)}")

    for concept in SAMPLE_CONCEPTS:
        entry = usgaap.get(concept)
        if entry is None:
            print(f"  concept '{concept}': NOT PRESENT for this filer")
            continue
        units = entry.get("units", {})
        unit_key = next(iter(units), None)
        rows = units.get(unit_key, []) if unit_key else []
        print(f"  concept '{concept}': unit={unit_key}, datapoint count={len(rows)}")
        if not rows:
            continue
        # Each row already carries both `end` (period end, i.e. the report
        # period date) and `filed` (actual filing date) -- this is the same
        # PIT signal shape as submissions API's reportDate/filingDate pair,
        # just attached per-datapoint instead of per-filing.
        sample = rows[-1]
        print(f"  most recent datapoint keys: {list(sample.keys())}")
        print(f"  most recent datapoint: {sample}")

        gaps = []
        for row in rows:
            end, filed, form = row.get("end"), row.get("filed"), row.get("form")
            if end and filed and form in ("10-K", "10-Q"):
                try:
                    gaps.append((date.fromisoformat(filed) - date.fromisoformat(end)).days)
                except ValueError:
                    continue
        if gaps:
            print(
                f"  10-K/10-Q filed-minus-end gap (days) via company facts: "
                f"n={len(gaps)}, min={min(gaps)}, max={max(gaps)}, avg={sum(gaps) / len(gaps):.1f}"
            )
            earliest_end = min(r["end"] for r in rows if r.get("end"))
            print(f"  earliest period 'end' date across all datapoints for this concept: {earliest_end}")


if __name__ == "__main__":
    for ticker, cik in KNOWN_CIK.items():
        probe_company_facts(ticker, cik)
