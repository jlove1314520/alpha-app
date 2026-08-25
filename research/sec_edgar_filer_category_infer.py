"""Sub-step (b) of US_MARATHON_STATE.md item 12: derive a per-company,
per-fiscal-year filer-category proxy from XBRL EntityPublicFloat + revenue,
using the historical threshold schedule confirmed by WebSearch in round 74
(DATA.md "美股 PIT 資料源調查（四續）").

Context: era_reliability() in us_pit.py applies ONE SEC-wide accelerated-
filer deadline schedule to every filer regardless of that filer's own
historical size, which round 65 found unreliable for a recent IPO (PLTR,
14/24 mismatch). Round 70 found EntityPublicFloat has real per-year data
that could in principle drive a per-company classification instead. Round
74 (WebSearch, no code) confirmed the threshold numbers themselves but
flagged that the 2020-03-12 rule change (Release 34-88365) added a REVENUE
test to the exit-side determination -- meaning float alone is not enough
for filings after that date, which is exactly PLTR's entire filing history
(2020-09 IPO onward). This script is the first attempt at (b): the actual
derivation logic, deliberately SIMPLIFIED (see LIMITATIONS below), tested
against AAPL/MSFT/PLTR (sub-step (c), same round -- doing (b) without any
empirical check would repeat the "wrote code, never verified" trap this
protocol explicitly warns against).

THRESHOLD TABLE (sourced from DATA.md round 74, not re-derived here):
  Era A: before 2005-12-27           -- only accelerated/non-accelerated exists (no LAF class yet).
                                         AF if float >= $75M, else NAF.
  Era B: 2005-12-27 to 2020-04-26     -- LAF class added. LAF if float >= $700M;
                                         AF if $75M <= float < $700M; else NAF.
  Era C: on/after 2020-04-27          -- same float bands as era B, PLUS: if
                                         revenue < $100M AND float < $700M -> NAF
                                         regardless of the float band (SRC
                                         revenue-test carve-out, Release 34-88365).

LIMITATIONS (deliberate scope decisions for this round, not oversights):
1. **No entry/exit hysteresis.** Real SEC rules distinguish the threshold to
   FIRST become accelerated (entry, e.g. $75M) from the threshold to STOP
   being accelerated once you already are (exit, e.g. $50M pre-2020 /
   $60M post-2020 -- and the LAF exit number pre-2020, $500M, is itself
   flagged in DATA.md as an unconfirmed inference, not a directly-cited
   figure). Modeling hysteresis correctly requires knowing each filer's
   PRIOR-YEAR category, which this script does not track (each fiscal year
   is classified independently, using only entry-side thresholds). This
   will misclassify a filer in the narrow band between exit and entry
   thresholds (e.g. float between $50M-$75M, or $500M-$700M pre-2020) in a
   year where it should still count its PRIOR status -- this is a KNOWN,
   ACCEPTED simplification for this round, not a bug found later.
2. **Revenue concept instability** (round 10/70's known finding): tries a
   short list of common `us-gaap` revenue concept names in order and uses
   whichever exists for that company; if none exist for a given fiscal
   year, the revenue test cannot be evaluated and the row is flagged
   `revenue_available=False` -- era-C rows with no revenue data fall back
   to float-only classification (documented as `revenue_missing_fallback`
   in the caveat column), which is NOT the real rule and known to
   understate NAF classifications in that case.
3. **2018 SRC overlay not implemented at all** -- DATA.md round 74 flagged
   SRC as a parallel, independent classification system this round does
   not touch (SRC is not the same axis as AF/LAF/NAF).
4. **No ground truth to validate against.** There is no per-company,
   per-year "actual historical filer category" dataset available to check
   this classifier's output against (that is exactly the gap this whole
   item 12 exists to work around) -- sub-step (c) below can only check for
   PLAUSIBILITY (does AAPL/MSFT look LAF basically the whole XBRL era? does
   PLTR show a lower category early and NAF/AF status makes qualitative
   sense for a recent, revenue-thin-at-first tech IPO?), not correctness.
   A classifier that "looks plausible" is not the same as a verified one --
   flagged here explicitly so a future round does not mistake this script's
   smoke-test output for validation.
"""
from __future__ import annotations

from datetime import date

import requests

from sec_edgar_client import HEADERS, get_cik, get_cik_map

_REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]

_ERA_B_START = date(2005, 12, 27)
_ERA_C_START = date(2020, 4, 27)

_LAF_FLOAT = 700_000_000
_AF_FLOAT = 75_000_000
_SRC_REVENUE_TEST = 100_000_000


def _era(fiscal_year_end: date) -> str:
    if fiscal_year_end < _ERA_B_START:
        return "A"
    if fiscal_year_end < _ERA_C_START:
        return "B"
    return "C"


def _fetch_company_facts(cik: int) -> dict:
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def _annual_float_series(facts: dict) -> list[dict]:
    """One entry per EntityPublicFloat datapoint (dei taxonomy, USD units).
    No dedup applied -- unlike sec_edgar_xbrl_facts_dedup_probe.py's
    concern (comparative-period re-disclosure), EntityPublicFloat is
    reported once per 10-K cover page as of a fixed measurement date, not
    repeated as comparative data across periods -- this has NOT been
    independently re-verified this round (carried over assumption from
    round 70's probe, which only printed raw entries and did not check for
    duplicates), flagged here rather than silently assumed correct.
    """
    entries = (
        facts.get("facts", {}).get("dei", {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
    )
    return [e for e in entries if e.get("end") and e.get("val") is not None]


def _revenue_for_year(facts: dict, fiscal_year_end: str) -> tuple[float | None, str | None]:
    """Best-effort revenue lookup for the same fiscal_year_end, trying
    concept names in _REVENUE_CONCEPTS order. Returns (value, concept_used)
    or (None, None) if no concept has a matching `end` date.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in _REVENUE_CONCEPTS:
        entries = gaap.get(concept, {}).get("units", {}).get("USD", [])
        for e in entries:
            if e.get("end") == fiscal_year_end and e.get("val") is not None:
                return float(e["val"]), concept
    return None, None


def infer_filer_category(ticker: str, cik_override: int | None = None) -> list[dict]:
    """One row per EntityPublicFloat datapoint, with an inferred category
    label (LAF/AF/NAF) per the simplified rules above. See module docstring
    LIMITATIONS -- this is NOT a verified ground truth, only a documented
    best-effort proxy.
    """
    cik = cik_override if cik_override is not None else get_cik(ticker)
    if cik is None:
        return []
    facts = _fetch_company_facts(cik)
    rows = []
    for e in _annual_float_series(facts):
        end = date.fromisoformat(e["end"])
        era = _era(end)
        float_val = float(e["val"])
        revenue, revenue_concept = _revenue_for_year(facts, e["end"])
        caveat = None
        if float_val >= _LAF_FLOAT:
            category = "LAF"
        elif float_val >= _AF_FLOAT:
            category = "AF"
        else:
            category = "NAF"
        if era == "C":
            if revenue is None:
                caveat = "revenue_missing_fallback"
            elif revenue < _SRC_REVENUE_TEST and float_val < _LAF_FLOAT and category != "NAF":
                category = "NAF"
                caveat = "src_revenue_test_applied"
        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "fiscal_year_end": e["end"],
                "public_float_usd": float_val,
                "fy": e.get("fy"),
                "filed": e.get("filed"),
                "era": era,
                "revenue_usd": revenue,
                "revenue_concept": revenue_concept,
                "inferred_category": category,
                "caveat": caveat,
            }
        )
    return sorted(rows, key=lambda r: r["fiscal_year_end"])


if __name__ == "__main__":
    cik_map = get_cik_map()
    for ticker in ["AAPL", "MSFT", "PLTR"]:
        cik = get_cik(ticker, cik_map)
        print(f"\n=== {ticker} (CIK={cik}) ===")
        rows = infer_filer_category(ticker, cik_override=cik)
        if not rows:
            print("  no EntityPublicFloat data")
            continue
        for r in rows:
            rev_str = f"${r['revenue_usd']:,.0f}" if r["revenue_usd"] is not None else "N/A"
            print(
                f"  {r['fiscal_year_end']} (era {r['era']}, fy={r['fy']}): "
                f"float=${r['public_float_usd']:,.0f} revenue={rev_str} "
                f"-> {r['inferred_category']}"
                + (f"  [{r['caveat']}]" if r["caveat"] else "")
            )
        cats = [r["inferred_category"] for r in rows]
        print(f"  category distribution: {dict((c, cats.count(c)) for c in sorted(set(cats)))}")
