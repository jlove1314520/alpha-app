"""US equity factor library -- first version (marathon round, US track).

**Why this exists / scope of this round:** per US_MARATHON_STATE.md's "下一步"
section, the US track's remaining foundation gap (after us_universe.py,
us_pit.py, validation/us_costs.py all have a first version) was "還沒有人
評估過是否夠格開始1a" -- i.e. no us_factors.py existed at all, so there was
nothing to run a cheap-gate IC test against. This round adds exactly one
factor, deliberately price-only (no financial-statement / PIT dependency),
to get the pipeline end-to-end working before spending API quota on anything
fundamentals-based. Running the actual factor_ic.py-style IC test against
this is next round's job, not this round's -- this round is infra (protocol
section 1c), not a hypothesis test.

**Why price-only for the first factor:** `USStockPrice`'s `Adj_Close` is
already split/dividend-adjusted (DATA.md's NVDA 2024-06 10:1-split check,
US_MARATHON_STATE.md "已知資訊" list) -- unlike TW, there is no separate
us_adjust.py needed before a factor can be computed. A daily-OHLCV-only
input is also, per factors.py's own docstring for TW's f_low_vol, naturally
point-in-time: a trading day's close is known at that day's close, no
PIT/pit_date machinery required. This sidesteps every open PIT-reliability
question this track still has (era_reliability()'s known unreliability on
recent-IPO names, filing-gap variability -- see US_MARATHON_STATE.md items
11/12) for the very first smoke test of "does a US factor column even
compute sensibly end to end".

**f_us_low_vol**: negative rolling std of daily returns over
LOW_VOL_WINDOW trading days -- literally the same definition and window as
TW's f_low_vol (factors.py's factor (i)), chosen deliberately so any later
comparison of "does low-vol work the same way in both markets" isn't
confounded by a definition difference. Lower realized volatility scores
higher (the negation), same convention as the TW version.

A factor being defined here is not a claim that it works -- same honesty
rule as TW's factors.py: nothing here has been through a cheap gate yet.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev

LOW_VOL_WINDOW = 60  # trading days -- matches TW's factors.py LOW_VOL_WINDOW exactly, see docstring


def us_price_series(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """load_dev()-capped USStockPrice for one ticker, columns renamed to this
    project's lowercase convention (date, adj_close, close, high, low, open,
    volume) for interface consistency with adjust.py's TW output. Empty
    DataFrame (not an exception) if the ticker has no dev-window price rows
    -- callers should check for this the same way factor_ic.py's
    load_sample_with_factors() does for TW, e.g. delisted-and-gone tickers
    like TWTR return empty here (see us_universe.py's docstring on this
    exact gap).
    """
    raw = load_dev("USStockPrice", stock_id, start_date)
    if raw.empty:
        return pd.DataFrame(columns=["date", "adj_close", "close", "high", "low", "open", "volume"])
    d = raw.rename(columns={
        "Adj_Close": "adj_close", "Close": "close", "High": "high",
        "Low": "low", "Open": "open", "Volume": "volume",
    })
    return d.sort_values("date").reset_index(drop=True)[
        ["date", "adj_close", "close", "high", "low", "open", "volume"]
    ]


def prepare_us_factors(price_df: pd.DataFrame) -> pd.DataFrame:
    """price_df: us_price_series() output for one stock (already
    load_dev()-capped). Returns price_df with US_FACTOR_COLUMNS added.
    """
    d = price_df.sort_values("date").reset_index(drop=True).copy()

    # f_us_low_vol -- 60 日日報酬標準差取負號，純價格資料，天然 point-in-time.
    daily_ret = d["adj_close"].pct_change()
    d["f_us_low_vol"] = -daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).std()

    return d


US_FACTOR_COLUMNS = ["f_us_low_vol"]


if __name__ == "__main__":
    # Smoke test only -- not a cheap-gate IC test (that's factor_ic.py's job,
    # next round). Just confirms the column computes sensibly end to end on
    # two tickers already known-good from milestone-1 (DATA.md, deep history,
    # no gaps): does it produce non-all-NaN values of a plausible magnitude,
    # and does the min_periods warm-up window behave as expected (NaN for
    # the first LOW_VOL_WINDOW-1 rows, real values after).
    for sid in ("AAPL", "MSFT"):
        # 1990-01-01 deliberately matches the exact start_date already used by
        # milestone-1's probe (us_probe_milestone1.py) and cached to parquet --
        # this round hit a live 402 (quota exhausted, see US_LOG.md) on any
        # other start_date/cache-key, so this reuses the existing cache file
        # instead of spending fresh quota just to smoke-test a column formula.
        px = us_price_series(sid, "1990-01-01")
        print(f"{sid}: {len(px)} price rows")
        if px.empty:
            print("  EMPTY -- skipping")
            continue
        d = prepare_us_factors(px)
        n_nan = d["f_us_low_vol"].isna().sum()
        valid = d["f_us_low_vol"].dropna()
        # pct_change() itself yields 1 leading NaN (no prior row for row 0), then
        # rolling(min_periods=LOW_VOL_WINDOW) needs LOW_VOL_WINDOW valid pct_change
        # values before it emits anything -- so the warm-up is LOW_VOL_WINDOW total
        # NaN rows, not LOW_VOL_WINDOW - 1 (this project's own factors.py uses the
        # identical pct_change->rolling(min_periods=W) pattern for TW's f_low_vol,
        # so this shape is expected/consistent, not a bug specific to this module).
        expected_nan = LOW_VOL_WINDOW
        print(f"  f_us_low_vol: {n_nan} NaN (expect exactly {expected_nan} warm-up rows), "
              f"{len(valid)} valid, range [{valid.min():.5f}, {valid.max():.5f}]" if len(valid) else "  NO valid rows")
        assert n_nan == expected_nan, f"{sid}: expected {expected_nan} NaN warm-up rows, got {n_nan}"
    print("\nOK: f_us_low_vol computes end-to-end on both smoke-test tickers with the expected warm-up shape.")
