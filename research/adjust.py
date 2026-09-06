"""還原股價 (back-adjusted TW stock price).

**2026-08-26 architecture change:** FinMind's free tier hit a hard 402
(quota exhausted) wall this day, and the user directed a hybrid source
switch -- price/volume history now comes PRIMARILY from yfinance
(`yf_price_client.py`), which returns already dividend/split-adjusted
closes for free with no comparable rate limit. The FinMind-based manual
back-adjustment below (raw TaiwanStockPrice + TaiwanStockDividend) is kept
as the FALLBACK for stock_ids yfinance doesn't carry -- mainly older
delisted names not on Yahoo Finance at all. `adjusted_price_series()`
tries yfinance first and only falls through to the FinMind reconstruction
if yfinance comes back empty; the returned DataFrame carries a `source`
column ('yfinance' or 'finmind') so callers/audits can tell which path
served any given row.

Below this point is the ORIGINAL FinMind-based fallback path, unchanged
except for being demoted from primary to fallback:

FinMind's free tier does not offer adjusted prices for TW stocks
(TaiwanStockPriceAdj is paid-tier only -- see DATA.md, milestone-1 audit,
2026-08-22). Every return-based backtest needs correct returns across
ex-dividend dates, or the backtest is silently polluted: an ex-dividend price
drop looks like a real loss that never actually happened to a holder. This
module reconstructs a back-adjusted series from raw TaiwanStockPrice +
TaiwanStockDividend, which are both free.

Method: standard cumulative backward adjustment, using TWSE's own
ex-rights/ex-dividend reference-price formula to turn each corporate action
into a single multiplicative factor:

    ref_price = (prev_close - cash_dividend + rights_price * rights_ratio)
                / (1 + stock_dividend_ratio + rights_ratio)
    factor = ref_price / prev_close

Applied in reverse chronological order (most recent event first) to every
raw price strictly BEFORE that event's ex-date. This keeps the most recent
price in the series equal to the raw price (the usual convention -- the
final day is never adjusted) while making day-over-day returns correct
across every ex-date in the history.

**Data source note (2026-08-22):** both fetches below go through
finmind_client.load_dev(), which caps everything at VAL_END
(validation.holdout) -- so "the most recent price" here means the most
recent price *within the dev window*, not literally today. That is
intentional: this module feeds backtests, and per CONSTITUTION.md no
backtest-facing data may see past the holdout boundary by default. Callers
doing an actual one-time holdout evaluation should use
finmind_client.load_full_history() directly and route the result through
validation.holdout.unlock_holdout_once() themselves, rather than expecting
this module to do it for them.

Known gap (documented, not silently ignored): capital reductions (減資) are
NOT handled here. TaiwanStockCapitalReductionReferencePrice hasn't been
wired in yet. A stock that underwent a capital reduction will show an
unadjusted jump in this series on that date. See DATA.md.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev


def adjustment_events(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """One row per ex-date with the multiplicative back-adjustment factor."""
    div = load_dev("TaiwanStockDividend", stock_id, start_date)
    if div.empty:
        return pd.DataFrame(columns=["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio"])

    raw = load_dev("TaiwanStockPrice", stock_id, start_date)
    if raw.empty:
        raise ValueError(f"no raw price data for {stock_id}, cannot compute adjustment factors")
    raw = raw.sort_values("date").reset_index(drop=True)
    close_by_date = dict(zip(raw["date"], raw["close"]))
    trading_dates = raw["date"].tolist()

    events = []
    for _, row in div.iterrows():
        # Cash and stock dividends normally share one ex-date; use whichever is populated.
        ex_date = row.get("CashExDividendTradingDate") or row.get("StockExDividendTradingDate")
        if not ex_date:
            continue
        cash = row.get("CashEarningsDistribution") or 0.0
        stock_ratio = row.get("StockEarningsDistribution") or 0.0
        rights_ratio = row.get("CashIncreaseSubscriptionRate") or 0.0
        rights_price = row.get("CashIncreaseSubscriptionpRrice") or 0.0
        if cash == 0 and stock_ratio == 0 and rights_ratio == 0:
            continue  # record exists but nothing was actually distributed this period

        prior = [d for d in trading_dates if d < ex_date]
        if not prior:
            continue  # ex-date is before our price history starts; can't anchor a factor
        prev_date = prior[-1]
        prev_close = close_by_date[prev_date]
        if prev_close in (None, 0) or pd.isna(prev_close):
            continue

        numerator = prev_close - cash + rights_price * rights_ratio
        denominator = 1 + stock_ratio + rights_ratio
        if denominator <= 0 or numerator <= 0:
            continue  # malformed event data -- skip rather than produce a nonsense factor
        ref_price = numerator / denominator
        factor = ref_price / prev_close
        events.append({
            "ex_date": ex_date, "prev_trading_date": prev_date, "factor": factor,
            "cash": cash, "stock_ratio": stock_ratio,
        })

    if not events:
        # Bug fixed 2026-08-22 (found via a 100-stock random-universe run): pd.DataFrame([])
        # has zero columns, so .sort_values("ex_date") on it raises KeyError('ex_date') --
        # must return the properly-columned empty frame directly instead of falling through.
        return pd.DataFrame(columns=["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio"])
    return pd.DataFrame(events).sort_values("ex_date").reset_index(drop=True)


def adjusted_price_series(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """Adjusted daily price series, capped at VAL_END. Tries yfinance first
    (see module docstring, 2026-08-26); falls back to the FinMind-based
    manual back-adjustment below if yfinance has no data for this stock_id.

    Columns: date, open, high, low, close, volume, adj_close, adj_open,
    adj_high, adj_low, source.
    `close`/`open`/`high`/`low` are the raw (unadjusted) values on the
    yfinance path too, for column-shape compatibility with the FinMind path
    -- yfinance's auto_adjust=True OHLC IS the adjusted value, so on that
    path close == adj_close (and open == adj_open etc.) by construction
    (there is no separately-fetchable raw OHLC from yfinance without a
    second, unadjusted request, which isn't worth the extra API call here).
    Empirically verified 2026-09-06 (see HYPOTHESIS_QUEUE.md#49 known-risk #2):
    yfinance's auto_adjust=True applies the IDENTICAL multiplicative factor
    to open/high/low/close on every date (checked 2330.TW 2024, all 241
    rows: open_factor == close_factor to 1e-6), so aliasing adj_open to the
    already-adjusted `open` column here is not an assumption, it's confirmed.

    2026-09-06: adj_open/adj_high/adj_low added on the FinMind fallback path
    (previously only adj_close existed) -- needed so overnight/intraday
    return decomposition (open_t / close_{t-1}) isn't polluted by ex-dividend
    jumps in an unadjusted `open` column (HYPOTHESIS_QUEUE.md#49 known-risk #2).
    """
    from yf_price_client import fetch_yf_adjusted

    yf_df = fetch_yf_adjusted(stock_id, start_date)
    if not yf_df.empty:
        out = yf_df.copy()
        out["adj_close"] = out["close"]
        out["adj_open"] = out["open"]
        out["adj_high"] = out["high"]
        out["adj_low"] = out["low"]
        out.attrs["n_events_applied"] = None  # not tracked on this path -- yfinance handles it internally
        return out

    raw = load_dev("TaiwanStockPrice", stock_id, start_date)
    if raw.empty:
        # Bug fixed 2026-08-22: this used to call .sort_values("date") before checking
        # emptiness -- an empty DataFrame has zero columns, so that raised KeyError('date')
        # instead of just returning the (correctly empty) result.
        raw["source"] = None  # keep column-shape consistent even in the empty case
        return raw
    raw = raw.sort_values("date").reset_index(drop=True)
    events = adjustment_events(stock_id, start_date)

    factor_cum = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        mask = raw["date"] < ev["ex_date"]
        factor_cum.loc[mask] = factor_cum.loc[mask] * ev["factor"]

    out = raw.copy()
    out["adj_close"] = raw["close"].astype(float) * factor_cum
    out["adj_open"] = raw["open"].astype(float) * factor_cum
    # FinMind's raw TaiwanStockPrice uses "max"/"min" for daily high/low
    # (confirmed empirically 2026-09-06 -- there is no "high"/"low" column on
    # this path; only the yfinance path in this function uses those names).
    out["adj_high"] = raw["max"].astype(float) * factor_cum
    out["adj_low"] = raw["min"].astype(float) * factor_cum
    out["source"] = "finmind"
    out.attrs["n_events_applied"] = len(events)
    return out
