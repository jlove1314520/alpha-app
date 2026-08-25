"""US track universe-building building block: per-ticker delisting status.

Marathon round 50 (2026-08-25, US track). This is the first piece of actual
`universe.py`-style delisting-detection logic for the US track -- everything
before this round (`sec_edgar_client.py`, `fdic_client.py`) was a reusable
*query* wrapper, not a *decision* function. US_MARATHON_STATE.md's "下一輪
建議工作單位" item 2 flagged this gap explicitly: "這個候選家族（FDIC-insured
銀行下市股）目前已經有可重用的查詢工具，但還沒有整合進任何實際的
`universe.py`下市偵測邏輯（那個模組本身還不存在）". This module does not
build the full `universe.py` -- it builds the one function a future
`universe.py` will call per-candidate-ticker to answer "was this delisted,
and if so when/how do we know".

Two independent data sources, tried in order:
1. SEC EDGAR Form 25 / 25-NSE / 15-12B / 15-12G filing (via sec_edgar_client's
   get_submissions -- this module adds the delisting-form-scan on top, lifted
   from sec_edgar_delisting_probe.py's DELISTING_FORM_PREFIXES logic).
2. FDIC BankFind Suite `failures` record (via fdic_client), for the subset of
   tickers that are FDIC-insured banks and never file with SEC at all (12(i)
   of the Exchange Act -- see fdic_client.py's module docstring and
   US_MARATHON_STATE.md "美股存活者偏差調查（根本原因）").

CRITICAL, hard-won lesson this module bakes in (see sec_edgar_delisting_probe.py
and US_MARATHON_STATE.md for the full history): SEC's CURRENT
company_tickers.json ticker->CIK map is NOT safe to trust blindly for a
ticker suspected of being delisted. Ticker reuse is real (BBBY's ticker now
resolves to an unrelated company, "NEIGHBORHOOD INTELLIGENCE, INC.", CIK
1130713) and the live map will silently hand back the WRONG entity's CIK
with no error. This module therefore requires the caller to pass an
independently-verified `cik_override` for any ticker where the live map is
known or suspected to be unreliable -- it does NOT fall back to the live map
automatically for such cases. For tickers where the live map is known-good
(rare for delisted names -- most delisted tickers either vanish from the map
or get reused), a caller can still pass cik_override=None to use the live
lookup, but should not do so without first confirming (as this module's own
smoke test does) that the resolved company name matches expectation.

This module deliberately does NOT attempt automatic CIK/CERT discovery for a
new, previously-unverified ticker -- see sec_edgar_frc_cik_probe.py for how
hard that manual disambiguation problem can get (round 7 burned a full
marathon round on FRC alone). The identifiers this module accepts as input
must already be independently verified by a human/prior marathon round,
exactly like FALLBACK_CIK in sec_edgar_delisting_probe.py. A future
universe.py's job is to accumulate a growing table of {ticker: verified
identifier} pairs (this module is just the lookup-and-classify step once
that identifier is known) -- building that accumulation table is explicitly
OUT OF SCOPE for this round.

Status values returned by get_delisting_status():
- "confirmed_sec_form25": found exactly one distinct EVENT, anchored on
  Form 25-family (25-NSE/25-NSE(A)/etc, the exchange-delisting filing) --
  date is that anchor filing's date. A trailing Form 15-12G/15-12B
  (SEC deregistration, always filed after the Form 25 for the same event)
  does NOT count as a second event, no matter how long the gap: this round
  discovered the gap between the two can be as short as 10 days (TWTR) or
  as long as ~630 days (SIVB's real 2023 event -- 25-NSE 2023-05-02,
  15-12G not until 2025-01-24, presumably a receivership-related
  administrative delay), so any fixed time-window heuristic to "merge"
  25+15 into one event would have been wrong for one or the other. Anchoring
  on Form 25 alone and treating Form 15 as purely informational sidesteps
  the problem instead of guessing a window.
- "confirmed_sec_form25_multiple_events_ambiguous": found Form 25-family
  filings (the anchor form) on MORE THAN ONE distinct date -- e.g. an
  earlier delisting of a different security class years before the actual
  common-stock delisting (discovered for SIVB this round: a 2017-12-22
  Form 25-NSE/25-NSE(A) cluster, for what was very likely a preferred-stock
  or debt-security delisting, is unrelated to the real 2023-05-02
  collapse-driven common-stock delisting). date is None; caller must
  inspect source_detail["all_hits"] (which still includes every 25- and
  15-12-family filing found, not just the anchors) and disambiguate by
  hand -- this module deliberately does not guess min()/max().
- Round 50's first draft of this module used "any distinct filingDate across
  25- and 15-12-family filings combined" to decide single-vs-multiple-event,
  which is WRONG: it flagged TWTR and BBBY (both genuinely single, clean
  delistings per US_MARATHON_STATE.md's hand-verified history) as ambiguous
  purely because their routine Form-25-then-Form-15 two-step process spans
  two different calendar dates, which is normal for every delisting, not a
  sign of multiple events. Caught by this round re-running the smoke test
  and comparing against the hand-verified history in US_MARATHON_STATE.md
  before trusting/committing the draft -- see US_LOG.md for the full note.
- "confirmed_fdic_failure": found an FDIC failures-table record. date given.
- "no_delisting_filing_found": a CIK was resolved and its filings.recent
  window was scanned, but no delisting-form filing appears in that window.
  NOTE this is NOT proof the company is still listed -- filings.recent is a
  rolling window (see sec_edgar_client.py docstring) and an old delisting
  could be sitting in the unfetched filings.files[] archive. Caller must NOT
  treat this as "confirmed still active".
- "no_identifier_available": neither a usable CIK nor an FDIC CERT was
  provided/resolvable. Cannot determine anything -- this is the "silently
  looks like a data gap" trap the whole FDIC-bank investigation exists to
  catch (see fdic_client.py docstring), surfaced explicitly instead of
  silently returning empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import fdic_client
import sec_edgar_client

DELISTING_FORM_PREFIXES = ("25", "15-12")


@dataclass
class DelistingStatus:
    ticker: str
    status: str
    date: str | None = None
    source_detail: dict = field(default_factory=dict)


ANCHOR_FORM_PREFIX = "25"  # exchange-delisting filing; see module docstring
# for why only this (not the trailing Form 15 deregistration) is used to
# count distinct delisting *events*.


def _scan_sec_delisting_filings(cik: int) -> list[dict]:
    """Return delisting-form-family filings (both Form 25-family and Form
    15-12-family) from the submissions 'recent' window, sorted
    earliest-first. Reuses sec_edgar_client's cached get_submissions()
    rather than re-fetching (same cache key)."""
    data = sec_edgar_client.get_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    hits = [
        {"form": forms[i], "filingDate": dates[i]}
        for i in range(len(forms))
        if forms[i].startswith(DELISTING_FORM_PREFIXES)
    ]
    hits.sort(key=lambda h: h["filingDate"])
    return hits, data.get("name")


def get_delisting_status(
    ticker: str,
    cik_override: int | None = None,
    fdic_cert: int | None = None,
    expected_name_fragment: str | None = None,
) -> DelistingStatus:
    """Determine delisting status for one ticker given already-verified
    identifiers. See module docstring for why cik_override/fdic_cert must
    come from prior verification, not be guessed here.

    expected_name_fragment: optional case-insensitive substring checked
    against the SEC-reported company name, purely as an informational
    warning surfaced in source_detail["name_check"] -- it does NOT gate the
    result when cik_override is used. Round 50 discovered why a hard gate
    is wrong here: SEC's `name` field reflects the CURRENT registered name,
    which can change AFTER delisting (e.g. BBBY's CIK 886158 shows as
    "20230930-DK-Butterfly-1, Inc." post-Chapter-11, a bankruptcy-successor
    shell rename -- not a wrong CIK, just a renamed one). Since cik_override
    is defined as already-independently-verified (see module docstring),
    trust it; a name mismatch is a fact worth logging for a human to notice,
    not a reason to discard an otherwise-valid Form 25 hit. The earlier
    ticker-reuse danger this check was meant to guard against lives in the
    LIVE TICKER MAP path (not exercised by this function at all -- callers
    must resolve/verify CIKs themselves before calling), not in a verified
    cik_override.
    """
    if cik_override is not None:
        hits, company_name = _scan_sec_delisting_filings(cik_override)
        name_check = (
            "not_checked" if expected_name_fragment is None
            else "match" if (company_name and expected_name_fragment.lower() in company_name.lower())
            else "mismatch_see_docstring"
        )
        if hits:
            # Event count is anchored on Form 25-family filings only -- a
            # trailing Form 15-12G/15-12B is the normal, always-later
            # deregistration paperwork for the SAME event (see module
            # docstring for why a fixed time-window merge doesn't work: the
            # 25->15 gap ranges from ~10 days to ~630 days in the 5 known
            # cases). Counting every distinct filingDate (25 AND 15 mixed
            # together) was round 50's original, WRONG approach -- it flagged
            # every normal two-step delisting as "ambiguous".
            anchor_hits = [h for h in hits if h["form"].startswith(ANCHOR_FORM_PREFIX)]
            distinct_anchor_dates = sorted({h["filingDate"] for h in anchor_hits})
            if len(distinct_anchor_dates) > 1:
                # Round 50 (SIVB) finding: a company can have MULTIPLE, unrelated
                # Form-25-family events on file -- e.g. an earlier delisting of a
                # different security class (preferred stock, a debt issue) years
                # before the actual common-stock delisting everyone means when
                # they say "SIVB delisted in 2023". Silently picking min() or
                # max() risks confidently returning the WRONG event's date --
                # exactly the kind of silent-wrong-answer this whole investigation
                # exists to avoid. Surface the ambiguity instead of resolving it
                # here; a future universe.py caller (or a human) must disambiguate
                # using the actual filing content (not done by this module).
                return DelistingStatus(
                    ticker=ticker,
                    status="confirmed_sec_form25_multiple_events_ambiguous",
                    date=None,
                    source_detail={
                        "cik": cik_override, "company_name": company_name,
                        "name_check": name_check, "all_hits": hits,
                    },
                )
            if distinct_anchor_dates:
                anchor_date = distinct_anchor_dates[0]
                return DelistingStatus(
                    ticker=ticker,
                    status="confirmed_sec_form25",
                    date=anchor_date,
                    source_detail={
                        "cik": cik_override, "company_name": company_name,
                        "name_check": name_check,
                        "all_hits": hits if len(hits) > 1 else None,
                    },
                )
            # Hits exist but none are Form-25-family (only 15-12-family) --
            # e.g. a company that deregistered without ever being exchange-
            # listed. No case in the 5 known-delisted smoke-test tickers
            # exercises this path; treat the earliest 15-12 date as a
            # lower-confidence proxy and say so explicitly rather than
            # silently returning the same "confirmed_sec_form25" status.
            distinct_15_dates = sorted({h["filingDate"] for h in hits})
            return DelistingStatus(
                ticker=ticker,
                status="confirmed_sec_form15_only_no_form25_anchor",
                date=distinct_15_dates[0],
                source_detail={
                    "cik": cik_override, "company_name": company_name,
                    "name_check": name_check, "all_hits": hits,
                },
            )
        sec_no_filing_result = DelistingStatus(
            ticker=ticker,
            status="no_delisting_filing_found",
            source_detail={"cik": cik_override, "company_name": company_name, "name_check": name_check},
        )
    else:
        sec_no_filing_result = None

    if fdic_cert is not None:
        failure = fdic_client.get_failure(fdic_cert)
        if failure is not None:
            return DelistingStatus(
                ticker=ticker,
                status="confirmed_fdic_failure",
                date=failure.get("FAILDATE"),
                source_detail={"cert": fdic_cert, "name": failure.get("NAME"), "restype": failure.get("RESTYPE")},
            )

    if sec_no_filing_result is not None:
        return sec_no_filing_result

    return DelistingStatus(ticker=ticker, status="no_identifier_available")


if __name__ == "__main__":
    # Smoke test: re-derive the same classification US_MARATHON_STATE.md
    # already recorded by hand across rounds 5/7/44/47, using ONLY this
    # module's function, to prove the wrapping didn't change the answer.
    # Expected: TWTR/BBBY -> confirmed_sec_form25 (single clean event, dates
    # 2022-10-28 / 2023-07-10); SIVB -> confirmed_sec_form25_multiple_events_
    # ambiguous (2017-2018 unrelated cluster + real 2023-05-02 event);
    # SBNY/FRC -> confirmed_fdic_failure (2023-03-12 / 2023-05-01).
    cases = [
        # ticker, cik_override, fdic_cert, expected_name_fragment
        ("TWTR", 1418091, None, "TWITTER"),
        ("SIVB", 719739, None, "SVB FINANCIAL"),
        ("BBBY", 886158, None, "BED BATH"),
        ("SBNY", None, 57053, None),
        ("FRC", None, 59017, None),
    ]
    for ticker, cik, cert, name_fragment in cases:
        result = get_delisting_status(ticker, cik_override=cik, fdic_cert=cert, expected_name_fragment=name_fragment)
        print(f"{ticker}: status={result.status}, date={result.date}, detail={result.source_detail}")
