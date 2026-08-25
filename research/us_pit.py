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

import pandas as pd

from sec_edgar_client import get_cik, get_filing_dates

# SEC Release 33-9002 phase 1: large accelerated filers with public float
# >= $5B, fiscal periods ending on or after this date. Kept as a documented
# constant for future work that DOES touch the XBRL company-facts endpoint
# (where this cutoff is actually relevant) -- deliberately NOT applied as a
# reliability flag in filing_pit() below. See module docstring.
XBRL_MANDATE_PHASE1_CUTOFF = "2009-06-15"


def filing_pit(
    ticker: str, cik_override: int | None = None, forms: tuple[str, ...] = ("10-K", "10-Q")
) -> pd.DataFrame:
    """One row per matching filing (10-K/10-Q by default) with pit_date =
    the real SEC filingDate. Columns: ticker, cik, form, fiscal_period_end
    (SEC's reportDate), pit_date, gap_days, pit_source (always 'real' --
    see module docstring for why there is no 'assumed' branch here).

    cik_override lets a caller supply a hand-verified CIK for a ticker
    where the current ticker->CIK map would be wrong (ticker reuse -- see
    us_delisting_client.py / US_MARATHON_STATE.md "美股存活者偏差" notes).
    Without it, this resolves CIK via sec_edgar_client.get_cik(), which is
    the *current* mapping only -- not safe for known-reused tickers.

    Returns an empty DataFrame if the ticker has no resolvable CIK or no
    matching filings in the submissions API's `filings.recent` window
    (does not paginate into `filings.files[]` archive pointers -- neither
    does sec_edgar_client.get_filing_dates(), which this wraps).
    """
    cik = cik_override if cik_override is not None else get_cik(ticker)
    if cik is None:
        return pd.DataFrame()
    filings = get_filing_dates(cik, forms=forms)
    if not filings:
        return pd.DataFrame()
    out = pd.DataFrame(filings)
    out = out.rename(columns={"reportDate": "fiscal_period_end", "filingDate": "pit_date"})
    out["pit_source"] = "real"
    out["ticker"] = ticker
    out["cik"] = cik
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


def coverage_probe(ticker: str, cik_override: int | None = None) -> dict:
    """Diagnostic (not used by filing_pit() itself): how far back does this
    ticker's `filings.recent` window actually reach? Answers the open
    question in the module docstring -- run once per ticker of interest,
    don't assume the answer transfers across tickers with different filing
    histories/filer sizes.
    """
    df = filing_pit(ticker, cik_override=cik_override, forms=("10-K", "10-Q"))
    if df.empty:
        return {"ticker": ticker, "n_filings": 0}
    return {
        "ticker": ticker,
        "n_filings": len(df),
        "earliest_fiscal_period_end": df["fiscal_period_end"].min(),
        "earliest_pit_date": df["pit_date"].min(),
        "latest_pit_date": df["pit_date"].max(),
    }


if __name__ == "__main__":
    # Smoke test: same three tickers already validated in prior rounds
    # (sec_edgar_client.py's own smoke test), so this should hit the
    # on-disk cache rather than burning fresh SEC requests. Prints both
    # filing_pit() output shape and the coverage_probe() diagnostic to
    # answer the "how far back does filings.recent actually reach"
    # question for real, not just in theory.
    for ticker in ["AAPL", "MSFT", "PLTR"]:
        df = filing_pit(ticker)
        print(f"{ticker}: {len(df)} filings, any_assumed={any_assumed(df)}")
        if not df.empty:
            print(f"  columns: {list(df.columns)}")
            print(f"  gap_days: min={df['gap_days'].min()}, max={df['gap_days'].max()}, "
                  f"median={df['gap_days'].median():.0f}")
        print(f"  coverage: {coverage_probe(ticker)}")
