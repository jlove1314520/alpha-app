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
**Cheap-gate result: FAIL** (see US_LEADS.md #1 / TRIALS_LEDGER.md #41) --
kept in the module (not deleted) as the honesty-log convention this project
follows for every FAIL, same as TW's factors.py keeping failed factors.

**f_us_momentum_12m** (2026-08-26, marathon round, US track's second
factor): classic Jegadeesh-Titman "12-1" cross-sectional momentum -- trailing
cumulative return from t-MOM_LOOKBACK to t-MOM_SKIP trading days ago,
deliberately skipping the most recent ~1 month (MOM_SKIP) to avoid
confounding with the well-documented short-term reversal effect, which is a
different (opposite-signed) phenomenon from 12-month momentum. Per
US_MARATHON_STATE.md's "下一步" (round-82 writeup: "建議擴充us_factors.py加
第二個因子（動能/相對強度，繼續避開PIT依賴）"), this is deliberately
price-only like f_us_low_vol -- no financial-statement / SEC EDGAR PIT
dependency, same reasoning as f_us_low_vol's docstring above (this track's
open PIT-reliability questions are sidestepped entirely for now). Unlike TW's
`f_rel_strength` (return relative to TAIEX), this is *not* benchmark-relative
-- this track has no broad-market return series computed yet (only AAPL's
date column is used, as a calendar proxy, not a return proxy -- see
us_factor_ic.py's own docstring on why), and a cross-sectional IC test does
not need a benchmark anyway (it ranks stocks against each other on the same
day, not against the market). A benchmark-relative variant is a reasonable
follow-up once a US market-return series exists, not a blocker for this
round's cheap gate.

**f_us_reversal_1m** (2026-08-26, marathon round, US track's third factor):
short-term reversal, the well-documented opposite-signed counterpart to
12-month momentum (Jegadeesh 1990, Lehmann 1990) -- negative of trailing
1-month (REV_LOOKBACK trading days) cumulative return, so recent losers
score high and recent winners score low. Deliberately reuses the exact same
REV_LOOKBACK=MOM_SKIP window (21 trading days) that f_us_momentum_12m
already skips, on purpose: that window is precisely the horizon the
momentum literature identifies as reversal-dominated rather than
momentum-dominated, so this factor is testing "the part of recent price
action f_us_momentum_12m deliberately excludes", not an arbitrary new
window choice. Per US_MARATHON_STATE.md round-88 writeup's "下一步建議"
("擴充第三個因子（短期反轉1週/1個月...）"), this is the 1-month variant
(not 1-week) -- picked because it shares the same lookback constant already
in use, minimizing new untested window choices in one round. Price-only,
zero PIT dependency, same reasoning as the other two factors above.

A factor being defined here is not a claim that it works -- same honesty
rule as TW's factors.py: nothing here has been through a cheap gate yet.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev

LOW_VOL_WINDOW = 60  # trading days -- matches TW's factors.py LOW_VOL_WINDOW exactly, see docstring
MOM_LOOKBACK = 252  # trading days ~= 12 months
MOM_SKIP = 21  # trading days ~= 1 month, excluded to avoid short-term-reversal confound
REV_LOOKBACK = MOM_SKIP  # trading days ~= 1 month -- deliberately the same window MOM_SKIP
                         # excludes, see f_us_reversal_1m docstring above


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

    # f_us_momentum_12m -- 12-1 動能：t-252 到 t-21 交易日累積報酬，排除近1個月避開短期反轉混淆。
    # 純價格資料，天然 point-in-time，同 f_us_low_vol 精神。
    px_lag_skip = d["adj_close"].shift(MOM_SKIP)
    px_lag_lookback = d["adj_close"].shift(MOM_LOOKBACK)
    d["f_us_momentum_12m"] = px_lag_skip / px_lag_lookback - 1.0

    # f_us_reversal_1m -- 短期反轉：近1個月累積報酬取負號，purely price-only.
    # 天然 point-in-time，同 f_us_low_vol/f_us_momentum_12m 精神。
    ret_1m = d["adj_close"] / d["adj_close"].shift(REV_LOOKBACK) - 1.0
    d["f_us_reversal_1m"] = -ret_1m

    return d


US_FACTOR_COLUMNS = ["f_us_low_vol", "f_us_momentum_12m", "f_us_reversal_1m"]


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

        # f_us_momentum_12m warm-up: shift(MOM_LOOKBACK) is the binding constraint
        # (MOM_LOOKBACK > MOM_SKIP), so exactly MOM_LOOKBACK leading NaN rows expected.
        n_nan_mom = d["f_us_momentum_12m"].isna().sum()
        valid_mom = d["f_us_momentum_12m"].dropna()
        expected_nan_mom = MOM_LOOKBACK
        print(f"  f_us_momentum_12m: {n_nan_mom} NaN (expect exactly {expected_nan_mom} warm-up rows), "
              f"{len(valid_mom)} valid, range [{valid_mom.min():.5f}, {valid_mom.max():.5f}]" if len(valid_mom) else "  NO valid rows")
        assert n_nan_mom == expected_nan_mom, f"{sid}: expected {expected_nan_mom} NaN warm-up rows, got {n_nan_mom}"

        # f_us_reversal_1m warm-up: shift(REV_LOOKBACK) is the only constraint, so exactly
        # REV_LOOKBACK leading NaN rows expected (REV_LOOKBACK == MOM_SKIP == 21).
        n_nan_rev = d["f_us_reversal_1m"].isna().sum()
        valid_rev = d["f_us_reversal_1m"].dropna()
        expected_nan_rev = REV_LOOKBACK
        print(f"  f_us_reversal_1m: {n_nan_rev} NaN (expect exactly {expected_nan_rev} warm-up rows), "
              f"{len(valid_rev)} valid, range [{valid_rev.min():.5f}, {valid_rev.max():.5f}]" if len(valid_rev) else "  NO valid rows")
        assert n_nan_rev == expected_nan_rev, f"{sid}: expected {expected_nan_rev} NaN warm-up rows, got {n_nan_rev}"
    print("\nOK: f_us_low_vol, f_us_momentum_12m, and f_us_reversal_1m all compute end-to-end on both smoke-test tickers with the expected warm-up shape.")
