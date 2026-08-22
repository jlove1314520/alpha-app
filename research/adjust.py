"""還原股價 (back-adjusted TW stock price) built from raw price + dividend data.

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

    return pd.DataFrame(events).sort_values("ex_date").reset_index(drop=True)


def adjusted_price_series(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """Raw TaiwanStockPrice rows (capped at VAL_END, see module docstring) with
    an added `adj_close` column (back-adjusted)."""
    raw = load_dev("TaiwanStockPrice", stock_id, start_date).sort_values("date").reset_index(drop=True)
    if raw.empty:
        return raw
    events = adjustment_events(stock_id, start_date)

    adj = raw["close"].astype(float).copy()
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        mask = raw["date"] < ev["ex_date"]
        adj.loc[mask] = adj.loc[mask] * ev["factor"]

    out = raw.copy()
    out["adj_close"] = adj
    out.attrs["n_events_applied"] = len(events)
    return out
