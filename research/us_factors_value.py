"""US track's first PIT-fundamental factor: `f_us_value_bm` (book-to-market),
marathon round following US_MARATHON_STATE.md round-333/336/342's repeated
"下一步" pointer at "SEC EDGAR基本面因子家族（價值/品質），尚未開始" -- the US
track's three price-only factors (`f_us_low_vol`/`f_us_momentum_12m`/
`f_us_reversal_1m`) are all fully closed out (US_LEADS.md #1-15), so this is
the first genuinely new factor FAMILY for the track, not another price-only
variant.

**Why book-to-market, and why this is the first fundamental factor to try:**
`us_fundamentals.py` (an earlier round, see its own docstring) already built
the reusable, PIT-correct XBRL company-facts wrapper
(`get_concept_series()`) but deliberately stopped short of computing any
actual factor -- this round is the first to consume it. Book-to-market
(Fama-French HML's defining ratio) needs only two XBRL concepts
(StockholdersEquity + a shares-outstanding tag) and one price series, no
income-statement or cash-flow-statement concepts -- the smallest possible
"real financial-statement number" factor to validate the whole PIT plumbing
(CIK resolution -> XBRL concept fetch -> dedup -> per-datapoint pit_date ->
as-of join against a daily price series) end to end before attempting
anything requiring more concepts (ROE/Piotroski F-score/accruals all need
several line items each and multi-period joins).

**PIT correctness, the part that matters most here:** a book-to-market
ratio is only knowable once BOTH numbers (book equity AND shares
outstanding for the same fiscal period) have actually been publicly
disclosed. `book_value_per_share_pit()` below takes
`max(se_pit_date, shares_pit_date)` per period as the ratio's true
availability date -- NOT `se_pit_date` alone -- because a caller who only
gated on the equity number's disclosure date would be assuming the shares
count was already known too, which is not always true (the two concepts
can appear in different filings, e.g. a shares count amended in a later
10-K/A). This mirrors `factors_us_financials.py`'s FCF-margin logic (must
wait for financials AND cashflow to both have the same period before
computing a ratio), applied here to two XBRL concepts instead of two
yfinance statements.

**Shares-outstanding tag fallback, and why it's a fallback not a first
choice:** `us_fundamentals.py`'s own `__main__` smoke test already flagged
that `CommonStockSharesOutstanding` (us-gaap, balance-sheet-date figure) is
not guaranteed to exist for every filer, while `EntityCommonStockSharesOutstanding`
(dei taxonomy, cover-page figure -- typically as-of the filing date, not the
fiscal period end) usually does. `book_value_per_share_pit()` tries the
us-gaap tag first (a proper balance-sheet-date figure, semantically cleaner
for pairing with a balance-sheet-date book-equity number) and only falls
back to the dei tag if the us-gaap one is completely absent for that filer.
This IS a semantic mismatch when the fallback fires (cover-page share count
!= balance-sheet-date share count, sometimes weeks apart) -- the output
records which tag was actually used per ticker (`shares_source` column) so
this is visible, not silently swept under the rug. Not re-solved this
round; a future round could try reconciling instead of just falling back.

**Foreign private issuers are silently excluded, not a bug:** many large US-
listed non-US companies (TSM, etc.) file Form 20-F/6-K, not 10-K/10-Q --
`get_concept_series()`'s default `forms=("10-K","10-Q")` filter means those
tickers simply produce an empty book-value series here (falls through
`book_value_per_share_pit()`'s `if se.empty / if shares.empty` guards), the
same "absent, not crashed" behavior every other empty-DataFrame guard in
this track's modules already uses. This is a known, expected sample-
coverage gap for this round, not investigated further here.

Does NOT touch FinMind or alpha.db -- only the SEC EDGAR modules
(`sec_edgar_client.py`, `us_fundamentals.py`) and pandas, so the holdout
boundary in MARATHON_PROTOCOL.md section 4 does not apply to the SEC-side
calls in this module (same convention every other sec_edgar_*.py/us_pit.py/
us_fundamentals.py module in this directory already follows) -- only the
price side (`us_factors.us_price_series()`, called by the companion IC-test
script, not by this module) goes through `load_dev()`'s holdout cap.
"""
from __future__ import annotations

import pandas as pd

from sec_edgar_client import get_cik
from us_fundamentals import get_concept_series

SE_CONCEPT = "StockholdersEquity"
SHARES_CONCEPT_GAAP = "CommonStockSharesOutstanding"
SHARES_CONCEPT_DEI = "EntityCommonStockSharesOutstanding"


def book_value_per_share_pit(ticker: str, cik_override: int | None = None) -> pd.DataFrame:
    """PIT-aligned book-value-per-share series for one ticker.

    Returns an empty DataFrame if the ticker has no resolvable CIK, no
    StockholdersEquity 10-K/10-Q datapoints, or neither shares-outstanding
    tag has any 10-K/10-Q datapoints (see module docstring on why 20-F
    filers fall into this last case). Never raises for a missing/absent
    filer -- same "absent, not exceptional" convention as
    `us_pit.filing_pit()`.

    Columns: ticker, cik, end (fiscal period end), pit_date (=
    max(se_pit_date, shares_pit_date), see module docstring), se_val
    (StockholdersEquity, raw USD), sh_val (shares outstanding, raw count),
    book_value_per_share (= se_val / sh_val), shares_source (which XBRL tag
    supplied sh_val, for the fallback-visibility reason in the module
    docstring).
    """
    cik = cik_override if cik_override is not None else get_cik(ticker)
    if cik is None:
        return pd.DataFrame()

    se = get_concept_series(cik, SE_CONCEPT)
    if se.empty:
        return pd.DataFrame()

    shares = get_concept_series(cik, SHARES_CONCEPT_GAAP)
    shares_source = f"us-gaap:{SHARES_CONCEPT_GAAP}"
    if shares.empty:
        shares = get_concept_series(cik, SHARES_CONCEPT_DEI, taxonomy="dei")
        shares_source = f"dei:{SHARES_CONCEPT_DEI}"
    if shares.empty:
        return pd.DataFrame()

    se2 = se[["end", "pit_date", "val"]].rename(columns={"pit_date": "se_pit_date", "val": "se_val"})
    sh2 = shares[["end", "pit_date", "val"]].rename(columns={"pit_date": "sh_pit_date", "val": "sh_val"})
    merged = se2.merge(sh2, on="end", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged = merged[merged["sh_val"] > 0].copy()  # non-positive share count is not a valid divisor
    if merged.empty:
        return pd.DataFrame()

    # XBRL data-quality guard (found this round on live AAPL data, not a
    # theoretical concern): `get_concept_series()` picks the first-disclosed
    # datapoint per `end` but does NOT filter by XBRL dimensional context
    # (segment/member qualifiers) -- a filer can occasionally have a
    # mis-scoped datapoint slip through under the entity-wide tag (observed:
    # AAPL's CommonStockSharesOutstanding for end=2014-03-29 came back as
    # 861,745 -- three orders of magnitude below both neighboring periods'
    # ~890M/~5,989M share counts, an obvious data error, not a real 1000x
    # single-quarter share count crash). A real stock split moves this
    # series by a few multiples at most (AAPL's actual 7:1 and 4:1 splits
    # show up as ~6-7x and ~4x single-period jumps in this same table), so
    # a relative floor against the ticker's OWN median (not a hardcoded
    # external constant, since share-count scale varies hugely across
    # market caps) safely drops implausible outliers like this one without
    # also dropping legitimate splits.
    median_sh = merged["sh_val"].median()
    plausible = (merged["sh_val"] >= median_sh * 0.01) & (merged["sh_val"] <= median_sh * 100)
    dropped = int((~plausible).sum())
    if dropped:
        merged = merged[plausible].copy()
    if merged.empty:
        return pd.DataFrame()

    # Split-adjustment correction (found this round on live AAPL data --
    # see add_value_factor()'s docstring for the full mechanism this fixes).
    # `sh_val` here is the RAW disclosed share count as of each period --
    # NOT split-adjusted for any split that happens in a LATER period --
    # while the price series this eventually gets divided by (`close`) IS
    # split-adjusted (rescaled down for every future split). Without this
    # correction, every pre-split period's book-value-per-share would be
    # inflated by the cumulative product of every split ratio that happens
    # after it. Detects splits via the share-count series itself (a split
    # moves `sh_val` by an integer-ish multiple between consecutive
    # disclosed periods; ordinary issuance/buyback moves it gradually, not
    # by a clean multiple) and back-adjusts every period's `sh_val` by the
    # cumulative product of every later detected split, so `sh_val`
    # (and therefore book_value_per_share) ends up expressed in the SAME
    # share-count convention as the price series' own adjustment.
    merged = merged.sort_values("end").reset_index(drop=True)
    _SPLIT_CANDIDATES = [2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20,
                         1 / 2, 1 / 2.5, 1 / 3, 1 / 4, 1 / 5, 1 / 6, 1 / 7, 1 / 8, 1 / 9, 1 / 10]
    _TOL = 0.15  # relative tolerance -- AAPL's real transitions this round measured 6.71x (vs 7,
                 # 4.1% off) and 3.96x (vs 4, 1.0% off), so 15% gives comfortable margin without
                 # being loose enough to false-positive on ordinary issuance/buyback noise
    n = len(merged)
    transition_ratio = [1.0] * n  # transition_ratio[i] = detected split multiple between period i and i+1
    for i in range(n - 1):
        raw = merged.loc[i + 1, "sh_val"] / merged.loc[i, "sh_val"]
        best = min(_SPLIT_CANDIDATES, key=lambda c: abs(raw - c) / c)
        if abs(raw - best) / best <= _TOL:
            transition_ratio[i] = best
    cumulative_forward = [1.0] * n
    running = 1.0
    for i in range(n - 2, -1, -1):
        running *= transition_ratio[i]
        cumulative_forward[i] = running
    merged["sh_val_split_adjusted"] = merged["sh_val"] * pd.Series(cumulative_forward)
    merged["n_splits_detected_after"] = [
        sum(1 for r in transition_ratio[i:] if r != 1.0) for i in range(n)
    ]

    merged["book_value_per_share"] = merged["se_val"] / merged["sh_val_split_adjusted"]
    # PIT: the ratio is not knowable until BOTH inputs have been disclosed -- see module docstring.
    merged["pit_date"] = merged[["se_pit_date", "sh_pit_date"]].max(axis=1)
    merged["ticker"] = ticker
    merged["cik"] = cik
    merged["shares_source"] = shares_source
    return merged[
        ["ticker", "cik", "end", "pit_date", "se_val", "sh_val", "sh_val_split_adjusted",
         "n_splits_detected_after", "book_value_per_share", "shares_source"]
    ].sort_values("pit_date").reset_index(drop=True)


def add_value_factor(price_df: pd.DataFrame, bvps_df: pd.DataFrame) -> pd.DataFrame:
    """price_df: us_factors.us_price_series() output (date, adj_close, ...
    -- already load_dev()-capped by the caller). bvps_df:
    book_value_per_share_pit() output for the same ticker.

    Adds `f_us_value_bm` = book_value_per_share / `adj_close` (book-to-
    market; higher = "cheaper"/more value-like, same direction convention
    as the classic Fama-French HML value premium -- historically value
    stocks outperform growth stocks, so this factor's economic prior is a
    *positive* IC, unlike e.g. f_us_low_vol/f_us_reversal_1m which are
    already negated in their own definitions).

    **Why `adj_close` and not raw `close` here (found and fixed this
    round, on live AAPL data):** `book_value_per_share_pit()`'s raw XBRL
    inputs are inherently NOT split-adjusted (a period's disclosed share
    count is the real count that existed at that fiscal period end),
    while BOTH of `us_price_series()`'s price columns (`close` AND
    `adj_close`) turned out to already be split-adjusted in this data
    source (only `adj_close` additionally carries dividend adjustment on
    top -- confirmed this round: AAPL's close/adj_close ratio in 2009 was
    ~1.19x, consistent with ~15 years of cumulative dividends, nowhere
    near the ~28x a 7:1-then-4:1 split-adjustment gap would produce, so
    `close` alone does NOT give a genuinely un-split-adjusted price here).
    `book_value_per_share_pit()` therefore does its OWN split detection
    and back-adjustment on the share-count series itself (see that
    function's `sh_val_split_adjusted`/`n_splits_detected_after` columns
    and inline comments) so `book_value_per_share` ends up expressed in
    the SAME (most-recent, i.e. current) share-count convention that
    `adj_close` is already scaled to -- once that correction is applied
    upstream, dividing by `adj_close` (not raw `close`) is correct again,
    and also the more standard choice for a value ratio (dividend-adjusted,
    consistent with how total-return-based factor comparisons are usually
    done). Before this fix, dividing un-adjusted book-value-per-share by
    `adj_close` put AAPL's 2009-era book-to-market at an implausible ~12x
    (a pure artifact of the 7x*4x=28x future-split gap, not a real
    valuation) -- see `book_value_per_share_pit()`'s comments for the fix.

    Uses `pd.merge_asof(..., direction='backward')` against `pit_date`: for
    each trading day, only the most recently DISCLOSED book value (pit_date
    <= that day) is used, forward-filled until the next disclosure -- a
    genuine as-of join, no look-ahead. Returns NaN for every day before the
    first disclosure (including the entire series if bvps_df is empty),
    same "NaN until warmed up" convention as every rolling-window factor in
    this project.
    """
    d = price_df.sort_values("date").reset_index(drop=True).copy()
    if bvps_df.empty:
        d["f_us_value_bm"] = float("nan")
        return d

    d["_dt"] = pd.to_datetime(d["date"])
    b = bvps_df.sort_values("pit_date").reset_index(drop=True).copy()
    b["_dt"] = pd.to_datetime(b["pit_date"])

    merged = pd.merge_asof(d, b[["_dt", "book_value_per_share"]], on="_dt", direction="backward")
    merged["f_us_value_bm"] = merged["book_value_per_share"] / merged["adj_close"]
    return merged.drop(columns=["_dt", "book_value_per_share"])


US_VALUE_FACTOR_COLUMNS = ["f_us_value_bm"]


if __name__ == "__main__":
    # Smoke test: the same three CIKs us_fundamentals.py's own smoke test
    # already validated (AAPL/MSFT/PLTR), so this hits the on-disk
    # companyfacts cache rather than burning a fresh SEC request per name.
    from us_factors import us_price_series

    known_cik = {"AAPL": 320193, "MSFT": 789019, "PLTR": 1321655}
    for ticker, cik in known_cik.items():
        print(f"\n=== {ticker} (CIK={cik}) ===")
        bvps = book_value_per_share_pit(ticker, cik_override=cik)
        print(f"  book_value_per_share_pit: {len(bvps)} periods"
              + (f", shares_source={bvps['shares_source'].iloc[0]}, "
                 f"range {bvps['end'].min()}..{bvps['end'].max()}" if not bvps.empty else " -- EMPTY"))
        if bvps.empty:
            continue
        px = us_price_series(ticker, "1990-01-01")
        if px.empty:
            print("  price EMPTY -- skipping add_value_factor")
            continue
        d = add_value_factor(px, bvps)
        valid = d["f_us_value_bm"].dropna()
        print(f"  f_us_value_bm: {len(valid)}/{len(d)} non-NaN rows"
              + (f", range [{valid.min():.4f}, {valid.max():.4f}]" if len(valid) else ""))
