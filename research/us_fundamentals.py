"""Reusable SEC EDGAR XBRL company-facts client for the US track (value/
quality factor inputs), marathon round following US_MARATHON_STATE.md's
round-106 next-step recommendation "(a) 需要基本面/PIT資料的新因子家族
（價值/品質），先確認SEC EDGAR資料源可行性再動工，屬於1c地基工作".

This is the "callable version" step for the XBRL company-facts endpoint,
analogous to what sec_edgar_client.py already did for the submissions
endpoint (filing_pit dates) two milestones ago -- that endpoint was wrapped
into a reusable module only after two rounds of ad-hoc probing
(sec_edgar_probe.py -> sec_edgar_client.py). The XBRL side has had its own
two rounds of ad-hoc probing (sec_edgar_xbrl_facts_probe.py round 10,
sec_edgar_xbrl_facts_dedup_probe.py round 11) but was NEVER wrapped into a
reusable module -- us_pit.py's docstring explicitly says it "deliberately
does NOT reuse the XBRL company-facts endpoint" for filing-date PIT (the
submissions endpoint is cleaner for that specific purpose). This module is
the first reusable wrapper for the XBRL side, needed now because value/
quality factors (PB, ROE, etc.) require actual reported NUMBERS
(book value, shares outstanding, net income), which only the XBRL
company-facts endpoint provides -- the submissions endpoint only gives
filing dates, not values.

Reuses sec_edgar_client._cached_get() for the same on-disk JSON caching
convention (dumb, exact-key cache under research/data/raw/, gitignored) --
does not duplicate that caching logic here.

Carries forward round 10/11's key finding without re-deriving it: the XBRL
company-facts endpoint is per-DATAPOINT, not per-filing -- the same
reporting period `end` gets re-disclosed as comparative-period data in
later filings (round 10 found up to 772 raw-gap days for AAPL
EarningsPerShareDiluted before dedup). get_concept_series() below applies
round 11's fix by construction (group by `end`, take min `filed`, 10-K/10-Q
only) -- callers of this module never see the undeduped raw form, unlike
the two probe scripts which computed both for comparison.

This round is 1c infrastructure (confirm feasibility / build the callable
wrapper) -- it does NOT compute or test any value/quality factor yet. That
is explicitly left for a later round, per MARATHON_PROTOCOL.md's "一輪一個
工作單位" discipline and the precedent set by sec_edgar_client.py itself
(wrapper first, factor-consuming code later).

Only fetches SEC EDGAR data (not FinMind, not alpha.db) -- the holdout
boundary in MARATHON_PROTOCOL.md section 4 does not apply here, same
convention as every other sec_edgar_*.py script in this directory.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from sec_edgar_client import _cached_get

_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def get_companyfacts(cik: int) -> dict:
    """Raw companyfacts/CIK{cik}.json payload for a given CIK.

    Cached per-CIK (separate cache namespace from sec_edgar_client's
    submissions cache -- this is a different, much larger endpoint).
    Caller is responsible for verifying the CIK actually corresponds to the
    intended entity, same caveat as sec_edgar_client.get_submissions().
    """
    cik_padded = str(cik).zfill(10)
    url = _COMPANYFACTS_URL.format(cik=cik_padded)
    return _cached_get(url, f"companyfacts_{cik_padded}")


def list_available_concepts(cik: int, taxonomy: str = "us-gaap") -> list[str]:
    """Diagnostic: which concept tags does this filer actually report under
    the given taxonomy? Different filers use different concept tags for
    conceptually-the-same line item (e.g. a filer with no preferred stock
    may report `StockholdersEquity` while one with preferred stock reports
    `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
    for the consolidated figure) -- this exists so a caller can check
    concept availability BEFORE assuming a hardcoded concept name works
    across the whole intended sample, rather than discovering a KeyError
    per-ticker at factor-computation time.
    """
    data = get_companyfacts(cik)
    return sorted(data.get("facts", {}).get(taxonomy, {}).keys())


def get_concept_series(
    cik: int,
    concept: str,
    taxonomy: str = "us-gaap",
    forms: tuple[str, ...] = ("10-K", "10-Q"),
) -> pd.DataFrame:
    """PIT-aligned, deduplicated series for one XBRL concept.

    Applies round 11's dedup fix by construction: groups raw datapoints by
    `end` (fiscal period end), keeps only the row with the MINIMUM `filed`
    per group (the first time that period's number was ever publicly
    disclosed as a 10-K/10-Q's own-period figure, not a later filing's
    comparative-period re-statement of the same period).

    Returns an empty DataFrame if the concept is not present for this
    filer/taxonomy, or has no 10-K/10-Q datapoints. Columns: end (fiscal
    period end, ISO date string), pit_date (= filed, the real SEC filing
    date the number first became public), val, form, unit (the XBRL unit
    key, e.g. 'USD' or 'shares' -- kept so a caller combining two concepts
    can sanity-check they're not mixing incompatible units), gap_days
    (pit_date - end, calendar days, for the same era_reliability-style
    sanity checking us_pit.py already does for filing dates -- NOT run
    through us_pit.era_reliability() here since that function's signature
    expects a form-keyed ceiling table tuned for filing-list gaps, not
    XBRL datapoint gaps; treat this gap_days as informational only until a
    future round explicitly re-validates era_reliability's applicability
    to this different data path).

    Does NOT attempt restated-value reconciliation beyond the min-filed
    dedup above -- if a company later restates a PRIOR period's number
    (accounting restatement, not routine comparative re-disclosure), this
    function has no way to distinguish that from ordinary comparative
    re-disclosure and will still report the earliest `filed` value, which
    would be the pre-restatement (now-known-wrong) figure. This mirrors
    the same "first disclosure, not most-current" choice round 11 made
    deliberately (PIT correctness requires "what was known at the time",
    not "what we know now was true") -- documented here as a carried-over
    property, not a new limitation introduced by this module.
    """
    data = get_companyfacts(cik)
    entry = data.get("facts", {}).get(taxonomy, {}).get(concept)
    if entry is None:
        return pd.DataFrame()
    units = entry.get("units", {})
    unit_key = next(iter(units), None)
    rows = units.get(unit_key, []) if unit_key else []
    if not rows:
        return pd.DataFrame()

    first: dict[str, dict] = {}
    for row in rows:
        end, filed, form = row.get("end"), row.get("filed"), row.get("form")
        val = row.get("val")
        if not (end and filed and form in forms) or val is None:
            continue
        if end not in first or filed < first[end]["pit_date"]:
            first[end] = {"end": end, "pit_date": filed, "val": val, "form": form}

    if not first:
        return pd.DataFrame()

    out = pd.DataFrame(first.values())
    out["unit"] = unit_key
    out["gap_days"] = out.apply(
        lambda r: (date.fromisoformat(r["pit_date"]) - date.fromisoformat(r["end"])).days,
        axis=1,
    )
    return out.sort_values("end").reset_index(drop=True)


if __name__ == "__main__":
    # Smoke test: same three CIKs already validated in prior rounds (round
    # 3/10/11), so this should hit the on-disk cache rather than burning
    # fresh SEC requests for the submissions/ticker-map side (companyfacts
    # itself is a different, larger cached payload -- first run per CIK
    # will be a genuine new HTTP request even though the CIK is known).
    #
    # Concept choice for this smoke test is deliberately about ANSWERING
    # THE FEASIBILITY QUESTION for a first value factor (book-value-per-
    # share, i.e. PB), not about computing the factor itself:
    #   - StockholdersEquity: book value numerator, standard us-gaap tag.
    #   - Two candidate shares-outstanding tags are checked because it is
    #     NOT known ahead of time which one (if either) a given filer
    #     reports reliably every period: `CommonStockSharesOutstanding`
    #     (us-gaap, balance-sheet-date figure) vs
    #     `EntityCommonStockSharesOutstanding` (dei taxonomy, cover-page
    #     figure, usually as-of the filing date rather than the fiscal
    #     period end -- a different point-in-time semantic that a later
    #     round would need to account for explicitly, not silently mix
    #     with the us-gaap tag's semantics).
    known_cik = {"AAPL": 320193, "MSFT": 789019, "PLTR": 1321655}
    for ticker, cik in known_cik.items():
        print(f"\n=== {ticker} (CIK={cik}) ===")
        se = get_concept_series(cik, "StockholdersEquity")
        print(f"  StockholdersEquity (us-gaap): {len(se)} deduped periods"
              + (f", range {se['end'].min()}..{se['end'].max()}, "
                 f"unit={se['unit'].iloc[0]}" if not se.empty else ""))

        shares_gaap = get_concept_series(cik, "CommonStockSharesOutstanding")
        print(f"  CommonStockSharesOutstanding (us-gaap): {len(shares_gaap)} deduped periods"
              + (f", unit={shares_gaap['unit'].iloc[0]}" if not shares_gaap.empty else ""))

        shares_dei = get_concept_series(
            cik, "EntityCommonStockSharesOutstanding", taxonomy="dei"
        )
        print(f"  EntityCommonStockSharesOutstanding (dei): {len(shares_dei)} deduped periods"
              + (f", unit={shares_dei['unit'].iloc[0]}" if not shares_dei.empty else ""))

        if not se.empty:
            print(f"  gap_days (StockholdersEquity): min={se['gap_days'].min()}, "
                  f"max={se['gap_days'].max()}, median={se['gap_days'].median():.0f}")
