"""Weinstein Stage 2 scan -- Milestone 4's first baseline strategy.

Stan Weinstein's four-stage model was invented for stocks (not adapted from
crypto), so this is the most natural first port from CONSTITUTION.md's
suggested baseline list. Daily-bar approximation of the classic weekly-chart
method:

  - Stock-level Stage 2 filter: adj_close > 150-trading-day SMA (≈ 30-week
    SMA), and that SMA itself is rising (compared to its value 10 trading
    days ago) -- price above a rising long moving average is the
    operational definition of "Stage 2 advancing" used here.
  - Momentum ranking: among stocks passing the filter, rank by 60-trading-
    day return and take engine's top `max_positions`.
  - Market-level gate: no new entries unless TAIEX close > TAIEX 200-day
    SMA (the "大盤總體閘門") -- this is the Cybex BTC-stage-2-gate analog,
    applied to 加權指數 instead.

All rolling stats are precomputed with pandas .rolling()/.shift(), which by
construction only ever use the current row and rows before it -- looking
them up at `as_of_date` cannot leak future data. This is deliberately
simpler than recomputing a fresh slice-and-mean on every call (which would
also be lookahead-safe, just slower).
"""
from __future__ import annotations

import pandas as pd

MA_WINDOW = 150
MA_RISING_LOOKBACK = 10
MOMENTUM_WINDOW = 60
MARKET_MA_WINDOW = 200


def prepare_price_data(price_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add ma150/ma150_prev/momentum columns to each stock's price frame.
    Call this once before run_backtest() -- the engine also reads `ma150`
    directly for its tier-1 exit check, so this must run first.
    """
    out = {}
    for sid, df in price_data.items():
        d = df.sort_values("date").reset_index(drop=True).copy()
        d["ma150"] = d["adj_close"].rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
        d["ma150_prev"] = d["ma150"].shift(MA_RISING_LOOKBACK)
        d["momentum"] = d["adj_close"] / d["adj_close"].shift(MOMENTUM_WINDOW) - 1
        out[sid] = d
    return out


def prepare_market_data(market_df: pd.DataFrame) -> pd.DataFrame:
    """Add ma200/gate columns to the market (TAIEX) DataFrame."""
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    d["ma200"] = d["close"].rolling(MARKET_MA_WINDOW, min_periods=MARKET_MA_WINDOW).mean()
    d["gate"] = d["close"] > d["ma200"]
    return d


def stage2_signal(price_data: dict[str, pd.DataFrame], as_of_date: str, market_df: pd.DataFrame) -> dict[str, float]:
    """signal_fn for backtest.engine.run_backtest(). Returns {stock_id: momentum}
    for stocks in Stage 2 as of as_of_date, or {} if the market gate is off.

    Assumes prepare_price_data()/prepare_market_data() have already been
    applied to price_data/market_df (the engine is given the prepared
    versions directly; this function just looks values up, it does not
    recompute the rolling stats itself).
    """
    if as_of_date not in market_df["date"].values:
        return {}
    gate_row = market_df.loc[market_df["date"] == as_of_date].iloc[0]
    if not bool(gate_row["gate"]):
        return {}

    scores: dict[str, float] = {}
    for sid, df in price_data.items():
        matches = df.loc[df["date"] == as_of_date]
        if matches.empty:
            continue
        row = matches.iloc[0]
        ma, ma_prev, close, mom = row["ma150"], row["ma150_prev"], row["adj_close"], row["momentum"]
        if pd.isna(ma) or pd.isna(ma_prev) or pd.isna(mom):
            continue
        if close <= ma:
            continue
        if ma <= ma_prev:
            continue
        scores[sid] = float(mom)
    return scores
