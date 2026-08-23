"""US track, marathon round 2026-08-24 (round: US_MARATHON_STATE.md next-step
item "修正後（取最小filed分組）的gap統計還沒重新算").

Round 10 (sec_edgar_xbrl_facts_probe.py) discovered that the XBRL company
facts API is per-datapoint, not per-filing: the same reporting period `end`
date gets re-disclosed as a comparative-period figure in later filings, so a
naive `filed - end` gap computation double-counts and produces absurd
outliers (up to 772 days for AAPL EarningsPerShareDiluted).

This script fixes that: group datapoints by `end`, take the MINIMUM `filed`
per group (the first time that period's number was ever publicly disclosed),
and recompute the gap statistics on the deduplicated set. This is the
explicitly-flagged "next step" left open by round 10 -- not a new probe
target, just the corrected version of the same analysis.

Same three CIKs already validated live in round 3 (sec_edgar_probe.py) and
reused in round 10 -- no new ticker->CIK lookups needed, so this stays
independent of the still-open FRC/SBNY survivorship CIK problem.

Only fetches SEC EDGAR data (not FinMind, not alpha.db) -- the holdout
boundary in MARATHON_PROTOCOL.md section 4 doesn't apply here. This script
prints; it does not write to other research/*.md files itself (those get
updated by hand after reading its output, same convention as prior probes).
"""
from __future__ import annotations

from datetime import date

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}

KNOWN_CIK = {"AAPL": 320193, "MSFT": 789019, "PLTR": 1321655}

SAMPLE_CONCEPTS = ["EarningsPerShareDiluted", "Revenues"]


def dedup_gap_stats(ticker: str, cik: int) -> None:
    print(f"\n=== Deduped gap stats ({ticker}, CIK={cik}) ===")
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    print(f"  status={r.status_code}")
    if r.status_code != 200:
        print(f"  FAILED, body snippet: {r.text[:300]}")
        return
    data = r.json()
    usgaap = data.get("facts", {}).get("us-gaap", {})

    for concept in SAMPLE_CONCEPTS:
        entry = usgaap.get(concept)
        if entry is None:
            print(f"  concept '{concept}': NOT PRESENT for this filer")
            continue
        units = entry.get("units", {})
        unit_key = next(iter(units), None)
        rows = units.get(unit_key, []) if unit_key else []
        if not rows:
            print(f"  concept '{concept}': no datapoints")
            continue

        # Raw (round-10, per-datapoint, NOT deduped) gap stats -- kept here
        # for direct before/after comparison in the same run.
        raw_gaps = []
        for row in rows:
            end, filed, form = row.get("end"), row.get("filed"), row.get("form")
            if end and filed and form in ("10-K", "10-Q"):
                try:
                    raw_gaps.append((date.fromisoformat(filed) - date.fromisoformat(end)).days)
                except ValueError:
                    continue

        # Deduped: group by `end`, take min `filed` per group (first-ever
        # disclosure of that period's number), 10-K/10-Q only.
        first_filed_by_end: dict[str, str] = {}
        for row in rows:
            end, filed, form = row.get("end"), row.get("filed"), row.get("form")
            if not (end and filed and form in ("10-K", "10-Q")):
                continue
            if end not in first_filed_by_end or filed < first_filed_by_end[end]:
                first_filed_by_end[end] = filed

        dedup_gaps = []
        for end, filed in first_filed_by_end.items():
            try:
                dedup_gaps.append((date.fromisoformat(filed) - date.fromisoformat(end)).days)
            except ValueError:
                continue

        print(f"  concept '{concept}': raw datapoints n={len(raw_gaps)}, distinct 'end' periods n={len(dedup_gaps)}")
        if raw_gaps:
            print(
                f"    RAW (round-10, not deduped):    min={min(raw_gaps)}, "
                f"max={max(raw_gaps)}, avg={sum(raw_gaps) / len(raw_gaps):.1f}"
            )
        if dedup_gaps:
            sorted_gaps = sorted(dedup_gaps)
            median = sorted_gaps[len(sorted_gaps) // 2]
            print(
                f"    DEDUPED (min filed per end):    min={min(dedup_gaps)}, "
                f"max={max(dedup_gaps)}, avg={sum(dedup_gaps) / len(dedup_gaps):.1f}, "
                f"median={median}"
            )
            outliers = [g for g in dedup_gaps if g > 120]
            if outliers:
                print(f"    still-outlier gaps (>120 days) after dedup: {sorted(outliers)}")
            else:
                print(f"    no gaps >120 days after dedup -- outliers were purely a dedup artifact")


if __name__ == "__main__":
    for ticker, cik in KNOWN_CIK.items():
        dedup_gap_stats(ticker, cik)
