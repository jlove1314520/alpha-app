"""US track's second PIT-fundamental factor: `f_us_gross_profitability`
(Novy-Marx 2013 "The Other Side of Value": GrossProfit / Assets), the first
genuinely new economic mechanism tested on the US track since #20/#21
(`f_us_value_bm`/`f_us_low_vol`) were downgraded to FAIL for a DATA
integrity reason (back-adjusted `adj_close` on the short leg, see
`US_LEADS.md` #20 round425), not an economic-mechanism reason -- so this is
not a "reskin" of a dead line under MARATHON_PROTOCOL.md 0a's operational
definition: it is a different accounting ratio (profitability, not value)
testing a different behavioral story (the market underprices profitable-but-
cheap-LOOKING firms because naive value screens conflate "cheap" with
"good"), not the same factor re-run on a new universe/window.

**Why gross profitability, and why it is cheaper to test than it looks:**
Both `GrossProfit` and `Assets` are STANDARD us-gaap XBRL tags already
present in the SAME cached SEC EDGAR companyfacts JSON payload that
`us_factors_value.py`'s `book_value_per_share_pit()` already downloaded for
every CIK in the clean stratified universe (`get_companyfacts()` fetches
the WHOLE companyfacts document per CIK, not per-concept -- `get_concept_series()`
just slices a different key out of an already-cached JSON). This means
testing this factor on the same 248-ticker clean universe costs ZERO new
SEC EDGAR HTTP requests for any ticker whose companyfacts payload is
already on disk from round383's `f_us_value_bm` clean-universe run.

**Why `forms=("10-K",)` only (annual, no 10-Q) -- unlike
`book_value_per_share_pit()` which takes both:** `StockholdersEquity` is a
balance-sheet STOCK (a snapshot as of `end`, comparable whether `end` is a
fiscal-year-end or a fiscal-quarter-end). `GrossProfit` is an income-
statement FLOW (an amount accrued OVER the period between the prior report
and `end`) -- a 10-K's `GrossProfit` for a fiscal year and a 10-Q's
`GrossProfit` for one fiscal quarter are NOT the same kind of number (roughly
4x apart, before seasonality), so mixing them in one series the way
`book_value_per_share_pit()` mixes 10-K+10-Q StockholdersEquity would inject
a large, mechanical, non-economic 4x-ish sawtooth into the ratio. Restricting
both `GrossProfit` and `Assets` to `forms=("10-K",)` keeps every datapoint on
a consistent annual basis (this DOES cost some resolution -- the factor only
updates once a year per filer, not quarterly -- documented here as a
deliberate simplification for this first test, not an oversight; a future
round could extend to a proper TTM rolling-4-quarters construction instead).

**No split-adjustment step needed here (unlike `book_value_per_share_pit()`):**
both `GrossProfit` and `Assets` are already whole-company dollar totals, not
per-share figures -- a stock split changes shares outstanding, not a
company's total assets or total gross profit, so there is nothing to
correct for here. This makes this factor's PIT plumbing strictly simpler
than the value factor's.

PIT correctness: `pit_date` for a given fiscal `end` = max(gp_pit_date,
assets_pit_date) -- same "both inputs must have actually been publicly
disclosed" convention as `book_value_per_share_pit()`.

Does NOT touch FinMind or alpha.db -- only the SEC EDGAR modules and
pandas; the holdout boundary only applies to the price side (same
convention as `us_factors_value.py`, see its module docstring).
"""
from __future__ import annotations

import pandas as pd

from sec_edgar_client import get_cik
from us_fundamentals import get_concept_series

GROSS_PROFIT_CONCEPT = "GrossProfit"
ASSETS_CONCEPT = "Assets"
ANNUAL_ONLY = ("10-K",)


def gross_profitability_pit(ticker: str, cik_override: int | None = None) -> pd.DataFrame:
    """PIT-aligned gross-profitability (GrossProfit/Assets) series for one
    ticker, annual (10-K) datapoints only -- see module docstring for why.

    Returns an empty DataFrame if the ticker has no resolvable CIK, no
    `GrossProfit` 10-K datapoints, or no `Assets` 10-K datapoints. Never
    raises for a missing/absent filer, same convention as
    `book_value_per_share_pit()`.

    Columns: ticker, cik, end (fiscal year end), pit_date (=
    max(gp_pit_date, assets_pit_date)), gp_val (GrossProfit, raw USD),
    assets_val (Assets, raw USD), gross_profitability (= gp_val/assets_val).
    """
    cik = cik_override if cik_override is not None else get_cik(ticker)
    if cik is None:
        return pd.DataFrame()

    gp = get_concept_series(cik, GROSS_PROFIT_CONCEPT, forms=ANNUAL_ONLY)
    if gp.empty:
        return pd.DataFrame()

    assets = get_concept_series(cik, ASSETS_CONCEPT, forms=ANNUAL_ONLY)
    if assets.empty:
        return pd.DataFrame()

    gp2 = gp[["end", "pit_date", "val"]].rename(columns={"pit_date": "gp_pit_date", "val": "gp_val"})
    a2 = assets[["end", "pit_date", "val"]].rename(columns={"pit_date": "assets_pit_date", "val": "assets_val"})
    merged = gp2.merge(a2, on="end", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged = merged[merged["assets_val"] > 0].copy()  # non-positive assets is not a valid divisor
    if merged.empty:
        return pd.DataFrame()

    merged["gross_profitability"] = merged["gp_val"] / merged["assets_val"]
    merged["pit_date"] = merged[["gp_pit_date", "assets_pit_date"]].max(axis=1)
    merged["ticker"] = ticker
    merged["cik"] = cik
    return merged[
        ["ticker", "cik", "end", "pit_date", "gp_val", "assets_val", "gross_profitability"]
    ].sort_values("pit_date").reset_index(drop=True)


def add_quality_factor(price_df: pd.DataFrame, gp_df: pd.DataFrame) -> pd.DataFrame:
    """price_df: `us_factors.us_price_series()` output. gp_df:
    `gross_profitability_pit()` output for the same ticker.

    Adds `f_us_gross_profitability` = gross_profitability (dimensionless
    ratio, no price division needed -- unlike `f_us_value_bm`, this factor
    does not touch price at all, only the two fundamental inputs. Higher =
    more profitable per dollar of assets; economic prior is a *positive*
    IC (Novy-Marx: profitable firms outperform, orthogonal to and in some
    specifications stronger than the classic value premium).

    Uses `pd.merge_asof(..., direction='backward')` against `pit_date`,
    same genuine as-of join (no look-ahead) as `add_value_factor()`. NaN
    before the first disclosure.
    """
    d = price_df.sort_values("date").reset_index(drop=True).copy()
    if gp_df.empty:
        d["f_us_gross_profitability"] = float("nan")
        return d

    d["_dt"] = pd.to_datetime(d["date"])
    g = gp_df.sort_values("pit_date").reset_index(drop=True).copy()
    g["_dt"] = pd.to_datetime(g["pit_date"])

    merged = pd.merge_asof(d, g[["_dt", "gross_profitability"]], on="_dt", direction="backward")
    merged["f_us_gross_profitability"] = merged["gross_profitability"]
    return merged.drop(columns=["_dt", "gross_profitability"])


US_QUALITY_FACTOR_COLUMNS = ["f_us_gross_profitability"]


if __name__ == "__main__":
    # Smoke test: same three CIKs `us_factors_value.py`'s smoke test already
    # validated (AAPL/MSFT/PLTR) -- expect AAPL/MSFT to hit on-disk cache
    # (fetched during round383's value-factor clean-universe run), PLTR may
    # or may not have GrossProfit as a standalone tag (some filers only
    # report Revenues/CostOfRevenue separately without a GrossProfit line).
    from us_factors import us_price_series

    known_cik = {"AAPL": 320193, "MSFT": 789019, "PLTR": 1321655}
    for ticker, cik in known_cik.items():
        print(f"\n=== {ticker} (CIK={cik}) ===")
        gp = gross_profitability_pit(ticker, cik_override=cik)
        print(f"  gross_profitability_pit: {len(gp)} periods"
              + (f", range {gp['end'].min()}..{gp['end'].max()}" if not gp.empty else " -- EMPTY (no GrossProfit/Assets 10-K tag)"))
        if gp.empty:
            continue
        px = us_price_series(ticker, "1990-01-01")
        if px.empty:
            print("  price EMPTY -- skipping add_quality_factor")
            continue
        d = add_quality_factor(px, gp)
        valid = d["f_us_gross_profitability"].dropna()
        print(f"  f_us_gross_profitability: {len(valid)}/{len(d)} non-NaN rows"
              + (f", range [{valid.min():.4f}, {valid.max():.4f}]" if len(valid) else ""))
