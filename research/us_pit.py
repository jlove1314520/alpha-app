"""Point-in-time (PIT) filing-availability dates for the US track.

Analog of pit.py (TW), but structurally different because the underlying
data source is different: TW's TaiwanStockFinancialStatements has NO real
disclosure-date field (pit.py has to assume period_end + 45 days), while
SEC EDGAR's submissions API (sec_edgar_client.get_filing_dates()) gives a
genuine `filingDate` per 10-K/10-Q filing -- so every row this module
produces is pit_source='real', not 'assumed'. That is a real structural
advantage over the TW quarterly/balance-sheet case, not a shortcut.

Deliberately does NOT reuse the XBRL company-facts endpoint
(sec_edgar_xbrl_facts_probe.py / sec_edgar_xbrl_facts_dedup_probe.py,
US_MARATHON_STATE.md 第十/十一輪). That endpoint is per-datapoint (a
period's number gets re-disclosed in later filings as comparative-period
data) and needs a dedup step (group by `end`, take min `filed`) before its
gaps are usable -- see the two probe scripts for the full story. The
submissions API used here is per-FILING (one filingDate per actual 10-K/
10-Q document), so that specific dedup artifact does not apply to this
module by construction -- there's no comparative-period re-disclosure
concept at the filing-list level, only at the per-datapoint XBRL level.

Because of that, this module does deliberately NOT copy over the
"pre-XBRL-mandate gap (period end < ~2009-06)" flag from the XBRL work
(US_MARATHON_STATE.md 下一輪建議工作單位 item 7 asked for this to be
"納入設計" -- taken into account in the design). XBRL_MANDATE_PHASE1_CUTOFF
below is kept as a documented constant for that reason, but is NOT applied
as a reliability flag in filing_pit(): the XBRL gap was diagnosed as an
artifact of the per-datapoint re-disclosure mechanism in the *company
facts* endpoint specifically, not a property of the *submissions* endpoint
used here. Applying it here without re-verifying it actually happens on
this data source would be copying a conclusion across two different APIs
without evidence -- exactly the kind of thing MARATHON_PROTOCOL.md's
honesty rule (section 4) says not to do quietly. This is recorded as an
open methodological question below, not resolved.

Round 63 (2026-08-25T15:xx) adds two things asked for by
US_MARATHON_STATE.md item 11: (a) filing_pit()/coverage_probe() now accept
full_history, threading it straight through to
sec_edgar_client.get_filing_dates(full_history=...); (b) a period-segmented
reliability flag, era_reliability(), for the "historical gap ceiling is
wider than recent years" finding from round 62 (AAPL max_gap 37->181 days,
MSFT 30->91 days once full_history pagination was added). The segmentation
boundaries are NOT invented -- they are SEC Release 33-8128's real,
publicly documented accelerated-filer phase-in schedule (confirmed via web
search this round, see US_LOG.md round 63 for the source): before FY-end
2002-12-15, ALL filers had a flat 90-day 10-K / 45-day 10-Q deadline; the
phase-in for accelerated filers then tightened this in three annual steps
(90->75->60 days for 10-K; 45->45->40->35 days for 10-Q) completing by
FY-end 2005-12-15. era_reliability() uses these dates as the segment
boundaries and the flat pre-2002 deadline (plus this round's own
AAPL/MSFT/PLTR empirical gap distribution, logged below) as the
expected-range ceiling per segment -- but see the important caveat in the
function's own docstring: it does NOT know each filer's accelerated-filer
status per period (that would need public-float history per company,
which this module does not have), so a "final era" (post-2005-12-15)
filer that was actually non-accelerated in some later fiscal year would
still legitimately see gaps up to 90/45 days and this function does not
distinguish that from a non-large-accelerated-filer 60/40-day expectation.
This is a genuine, unresolved gap in the design, not an oversight -- see
"KNOWN LIMITATION" in era_reliability()'s docstring.

What IS a real, verified-this-round caveat (see coverage_probe() and
US_LOG.md for the smoke-test numbers): `filings.recent` is a rolling
window, and its depth is NOT the same for every filer -- for a company
with a long filing history, `filings.recent` may not reach all the way
back to IPO. filing_pit() does not silently paper over this: a caller can
tell how far back real filingDate coverage extends for a given ticker by
looking at the returned DataFrame's own date range. There is no fallback
to an assumed date when recent-window coverage runs out -- unlike TW
pit.py's month_revenue_pit(), which falls back from real create_time to
an assumed disclosure-deadline date, this module has no assumed branch at
all. A period with no covered filing simply does not appear in the output
(same effect as pit.py's `if raw.empty: return pd.DataFrame()`, but for
a caller doing a per-quarter join it means "no PIT date available for a
period this old", not "the disclosure is assumed but real"). This also
means pre-IPO periods are correctly absent (no filings exist before a
company started filing, so nothing here would ever fabricate a pre-IPO
PIT date) -- confirming what US_MARATHON_STATE.md flagged as a
"theoretically should be fine, not empirically verified" open question
for PLTR is, for this specific data path, structurally guaranteed rather
than merely assumed.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from sec_edgar_client import get_cik, get_filing_dates

# SEC Release 33-9002 phase 1: large accelerated filers with public float
# >= $5B, fiscal periods ending on or after this date. Kept as a documented
# constant for future work that DOES touch the XBRL company-facts endpoint
# (where this cutoff is actually relevant) -- deliberately NOT applied as a
# reliability flag in filing_pit() below. See module docstring.
XBRL_MANDATE_PHASE1_CUTOFF = "2009-06-15"

# SEC Release 33-8128 accelerated-filer phase-in schedule (real, publicly
# documented -- confirmed via web search round 63, see US_LOG.md). Ordered
# (cutoff_fiscal_year_end_on_or_after, max_gap_10k, max_gap_10q). Applies
# to `fiscal_period_end` (SEC's reportDate), not `pit_date`. Before the
# first cutoff, ALL filers (not just accelerated ones) had a flat 90-day
# 10-K / 45-day 10-Q deadline -- that's segment 0 below.
_ERA_SEGMENTS: list[tuple[str, int, int]] = [
    ("0001-01-01", 90, 45),  # pre-accelerated-filer-rules (flat deadline, all filers)
    ("2002-12-15", 90, 45),  # phase-in year 1 (accelerated filers only; matches segment 0's ceiling)
    ("2003-12-15", 75, 45),  # phase-in year 2
    ("2004-12-15", 60, 40),  # phase-in year 3
    ("2005-12-15", 60, 35),  # final (10-Q reaches 35d; 10-K stays 60d for accelerated filers)
]


def era_reliability(fiscal_period_end: str, form: str, gap_days: int) -> str:
    """Flag one filing's gap_days against the SEC deadline that applied to
    ITS fiscal_period_end (not today's rules) -- see _ERA_SEGMENTS.

    Returns 'within_era_deadline' if gap_days is at or below the applicable
    ceiling for that era + form, else 'exceeds_era_deadline' (a LATE filing
    relative to the deadline that applied then, not necessarily a data
    error -- companies do file late, e.g. after an NT 10-K/10-Q extension
    notice, and this function has no way to distinguish "genuinely late"
    from "PIT data artifact" from the gap number alone).

    KNOWN LIMITATION (deliberately unresolved, not an oversight): the
    tightened deadlines (75/60/40/35 days) only ever applied to
    *accelerated* filers. This function has no per-company, per-fiscal-year
    accelerated-filer status (that requires public-float history this
    module does not have), so it applies the accelerated-filer ceiling to
    every filer after 2002-12-15 regardless of actual filer size. A
    small-cap company that was legitimately non-accelerated (still on the
    90/45-day deadline) filing e.g. 70 days after a 2010 fiscal year end
    would be wrongly flagged 'exceeds_era_deadline' by this function even
    though it broke no rule. This is acceptable for the two large-cap
    filers (AAPL/MSFT) this module has been validated against so far, but
    callers using this on small/mid-cap tickers should treat
    'exceeds_era_deadline' as "needs a closer look", not "confirmed bad
    data" -- see US_LOG.md round 63 for the reasoning.
    """
    end = date.fromisoformat(fiscal_period_end)
    ceiling_10k, ceiling_10q = _ERA_SEGMENTS[0][1], _ERA_SEGMENTS[0][2]
    for cutoff, c10k, c10q in _ERA_SEGMENTS:
        if end >= date.fromisoformat(cutoff):
            ceiling_10k, ceiling_10q = c10k, c10q
    ceiling = ceiling_10k if form == "10-K" else ceiling_10q
    return "within_era_deadline" if gap_days <= ceiling else "exceeds_era_deadline"


def filing_pit(
    ticker: str,
    cik_override: int | None = None,
    forms: tuple[str, ...] = ("10-K", "10-Q"),
    full_history: bool = False,
) -> pd.DataFrame:
    """One row per matching filing (10-K/10-Q by default) with pit_date =
    the real SEC filingDate. Columns: ticker, cik, form, fiscal_period_end
    (SEC's reportDate), pit_date, gap_days, pit_source (always 'real' --
    see module docstring for why there is no 'assumed' branch here),
    era_reliability (see era_reliability() -- KNOWN LIMITATION there
    applies to this column too).

    cik_override lets a caller supply a hand-verified CIK for a ticker
    where the current ticker->CIK map would be wrong (ticker reuse -- see
    us_delisting_client.py / US_MARATHON_STATE.md "美股存活者偏差" notes).
    Without it, this resolves CIK via sec_edgar_client.get_cik(), which is
    the *current* mapping only -- not safe for known-reused tickers.

    full_history mirrors sec_edgar_client.get_filing_dates()'s parameter of
    the same name: False (default, unchanged from prior rounds) only
    covers the `filings.recent` rolling window; True also paginates
    `filings.files[]` archive pointers for full EDGAR-history depth (see
    round 62/US_MARATHON_STATE.md item 10) at the cost of one extra cached
    HTTP request per archive file on first call.

    Returns an empty DataFrame if the ticker has no resolvable CIK or no
    matching filings in the requested window.
    """
    cik = cik_override if cik_override is not None else get_cik(ticker)
    if cik is None:
        return pd.DataFrame()
    filings = get_filing_dates(cik, forms=forms, full_history=full_history)
    if not filings:
        return pd.DataFrame()
    out = pd.DataFrame(filings)
    out = out.rename(columns={"reportDate": "fiscal_period_end", "filingDate": "pit_date"})
    out["pit_source"] = "real"
    out["ticker"] = ticker
    out["cik"] = cik
    out["era_reliability"] = out.apply(
        lambda r: era_reliability(r["fiscal_period_end"], r["form"], r["gap_days"]), axis=1
    )
    return out.sort_values("fiscal_period_end").reset_index(drop=True)


def any_assumed(df: pd.DataFrame) -> bool:
    """True if any row relies on an assumed (not real) disclosure date.
    Mirrors pit.py's any_assumed() for interface parity with the TW module,
    but for this module it should always return False by construction --
    see module docstring. Kept so calling code can use the same pattern
    ("check any_assumed() before treating a backtest as clean") across both
    tracks without branching on which track it is.
    """
    return "pit_source" in df.columns and bool((df["pit_source"] == "assumed").any())


def coverage_probe(
    ticker: str, cik_override: int | None = None, full_history: bool = False
) -> dict:
    """Diagnostic (not used by filing_pit() itself): how far back does this
    ticker's filing coverage actually reach? Answers the open question in
    the module docstring -- run once per ticker of interest, don't assume
    the answer transfers across tickers with different filing
    histories/filer sizes. Set full_history=True to probe depth including
    `filings.files[]` archive pagination (round 62/63); default False
    still only reflects the `filings.recent` rolling window, matching
    filing_pit()'s own default.
    """
    df = filing_pit(
        ticker, cik_override=cik_override, forms=("10-K", "10-Q"), full_history=full_history
    )
    if df.empty:
        return {"ticker": ticker, "n_filings": 0}
    n_exceeds = int((df["era_reliability"] == "exceeds_era_deadline").sum())
    return {
        "ticker": ticker,
        "n_filings": len(df),
        "earliest_fiscal_period_end": df["fiscal_period_end"].min(),
        "earliest_pit_date": df["pit_date"].min(),
        "latest_pit_date": df["pit_date"].max(),
        "n_exceeds_era_deadline": n_exceeds,
    }


if __name__ == "__main__":
    # Smoke test: same three tickers already validated in prior rounds
    # (sec_edgar_client.py's own smoke test), so this should hit the
    # on-disk cache from round 62 rather than burning fresh SEC requests.
    # Round 63 addition: run with full_history=True and break gap_days down
    # by fiscal-period-end decade + era_reliability, to see empirically
    # whether the phase-in-based ceiling in _ERA_SEGMENTS actually holds up
    # against real data (not just the theoretical deadline text) before
    # trusting the flag for anything downstream.
    for ticker in ["AAPL", "MSFT", "PLTR"]:
        df = filing_pit(ticker, full_history=True)
        print(f"{ticker}: {len(df)} filings (full_history=True), any_assumed={any_assumed(df)}")
        if not df.empty:
            print(f"  columns: {list(df.columns)}")
            print(f"  gap_days: min={df['gap_days'].min()}, max={df['gap_days'].max()}, "
                  f"median={df['gap_days'].median():.0f}")
            n_exceeds = int((df["era_reliability"] == "exceeds_era_deadline").sum())
            print(f"  era_reliability: {n_exceeds}/{len(df)} exceed_era_deadline")
            decade = df["fiscal_period_end"].str.slice(0, 3) + "0s"
            by_decade = df.groupby(decade)["era_reliability"].apply(
                lambda s: f"{(s == 'exceeds_era_deadline').sum()}/{len(s)} exceed"
            )
            for dec, summary in by_decade.items():
                print(f"    {dec}: {summary}")
        print(f"  coverage: {coverage_probe(ticker, full_history=True)}")
