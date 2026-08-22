"""AI 選股引擎 Phase A -- factor library.

Six factors computed from free FinMind data. Every daily/volume-based
input is naturally point-in-time (a trading day's OHLCV is known at that
day's close). Every fundamentals-based input (monthly revenue, quarterly
EPS) is joined onto the daily price series via `pandas.merge_asof(...,
direction="backward")` keyed on `pit.py`'s `pit_date` column, NOT the
fiscal period date -- this is what makes "the revenue-acceleration factor
value on trading day T" mean "the most recently DISCLOSED figure as of T",
never a figure that wouldn't actually have been public yet. See pit.py's
own docstring for what `pit_date` means and its `assumed` vs `real`
distinction; any factor built on `pit_source='assumed'` rows inherits that
same experimental status.

A factor being defined here is not a claim that it works. factor_ic.py is
what decides which of these six actually carry predictive information;
CONSTITUTION.md's honesty rule applies here just as much as to a full
strategy -- a factor that fails IC testing gets weight 0 in score.py, not
quietly dropped from the record.

**Known substitution, disclosed (not hidden):** factor (d) is described in
the project design doc as "三大法人淨買/市值" (institutional net buy / market
cap), but `TaiwanStockMarketValue` is paid-tier only (same class of gate as
`TaiwanStockPriceAdj` -- see DATA.md). Market cap is substituted with a
20-day average trading VALUE (`Trading_money`, free) as the denominator
instead -- a liquidity-normalized proxy, not literally market cap. Still a
reasonable normalization (big, liquid stocks have both bigger market caps
and bigger trading values, so the two are correlated), but not the same
number the design doc names.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from finmind_client import load_dev
from pit import month_revenue_pit, quarterly_pit

FOREIGN_STREAK_VOL_WINDOW = 20
INST_FLOW_WINDOW = 20
REL_STRENGTH_WINDOW = 60
MA_WINDOW = 60
VOL_SHORT_WINDOW = 20
VOL_LONG_WINDOW = 60


def _institutional_daily_net(stock_id: str, start_date: str) -> pd.DataFrame:
    """Daily net buy (shares) per institutional category, wide format:
    date, foreign_net, trust_net, dealer_net, total_net.
    """
    raw = load_dev("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date)
    cols = ["date", "foreign_net", "trust_net", "dealer_net", "total_net"]
    if raw.empty:
        return pd.DataFrame(columns=cols)
    raw = raw.copy()
    raw["net"] = raw["buy"] - raw["sell"]

    def _cat(name: str) -> str | None:
        if name == "Foreign_Investor":
            return "foreign_net"
        if name == "Investment_Trust":
            return "trust_net"
        if name in ("Dealer_self", "Dealer_Hedging"):
            return "dealer_net"
        return None  # Foreign_Dealer_Self observed always 0 in spot checks; excluded on purpose

    raw["cat"] = raw["name"].map(_cat)
    raw = raw.dropna(subset=["cat"])
    if raw.empty:
        return pd.DataFrame(columns=cols)
    wide = raw.pivot_table(index="date", columns="cat", values="net", aggfunc="sum").reset_index()
    for c in ("foreign_net", "trust_net", "dealer_net"):
        if c not in wide.columns:
            wide[c] = 0.0
    wide["total_net"] = wide[["foreign_net", "trust_net", "dealer_net"]].sum(axis=1)
    return wide[cols]


def _foreign_streak_strength(net: np.ndarray, avg_vol: np.ndarray) -> np.ndarray:
    """(c) 外資連續買超強度: at each day, the cumulative net-buy over the
    CURRENT unbroken streak of positive-net-buy days (streak resets to 0 the
    moment net buy turns non-positive), normalized by that day's trailing
    average volume. Inherently causal/sequential (each value depends only on
    days up to and including itself) -- not vectorizable via pandas rolling,
    so a plain loop is used; correctness matters more than speed here and
    the series lengths involved (thousands of rows) make this fast enough.
    """
    out = np.zeros(len(net))
    streak_sum = 0.0
    for i in range(len(net)):
        if net[i] > 0:
            streak_sum += net[i]
        else:
            streak_sum = 0.0
        denom = avg_vol[i]
        out[i] = streak_sum / denom if denom and not np.isnan(denom) and denom > 0 else 0.0
    return out


def _asof_join(price_df: pd.DataFrame, pit_df: pd.DataFrame, value_col: str, out_col: str) -> pd.DataFrame:
    """Point-in-time join: for each row in price_df (sorted by date), attach
    the most recent pit_df row whose pit_date <= price_df's date. This is
    the mechanism that makes fundamentals-derived factors lookahead-safe.

    merge_asof requires a numeric/datetime join key (pandas rejects plain
    string columns even when both sides match), so both date columns are
    cast to datetime64 for the join only -- the rest of the codebase
    standardizes on plain "YYYY-MM-DD" strings (e.g. validation.holdout's
    string comparisons against VAL_END), so the output keeps the original
    string `date` column, not the datetime64 one.
    """
    if pit_df.empty or value_col not in pit_df.columns:
        price_df[out_col] = np.nan
        return price_df
    p = (
        pit_df[["pit_date", value_col]]
        .dropna()
        .sort_values("pit_date")
        .rename(columns={value_col: out_col})
    )
    if p.empty:
        price_df[out_col] = np.nan
        return price_df
    left = price_df.sort_values("date").copy()
    left["_date_dt"] = pd.to_datetime(left["date"])
    p = p.copy()
    p["_pit_date_dt"] = pd.to_datetime(p["pit_date"])
    merged = pd.merge_asof(
        left, p, left_on="_date_dt", right_on="_pit_date_dt", direction="backward"
    )
    return merged.drop(columns=["_date_dt", "_pit_date_dt", "pit_date"])


def _revenue_yoy_acceleration(stock_id: str, start_date: str) -> pd.DataFrame:
    """(a) 月營收 YoY 加速度: this month's YoY growth minus last month's YoY
    growth (i.e. is revenue growth itself speeding up or slowing down, not
    just "is revenue growing"). Returns columns: pit_date, yoy_accel.
    """
    rev = month_revenue_pit(stock_id, start_date)
    if rev.empty:
        return pd.DataFrame(columns=["pit_date", "yoy_accel"])
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    prior = prior.rename(columns={"revenue": "revenue_prior_year"})
    rev = rev.merge(prior, on=["revenue_year", "revenue_month"], how="left")
    rev["yoy"] = (rev["revenue"] - rev["revenue_prior_year"]) / rev["revenue_prior_year"].abs()
    rev["yoy_accel"] = rev["yoy"] - rev["yoy"].shift(1)
    return rev[["pit_date", "yoy_accel"]]


def _eps_yoy_growth(stock_id: str, start_date: str) -> pd.DataFrame:
    """(b) EPS 成長: this quarter's EPS vs the same quarter one year prior
    (shift(4), assuming no gaps in the quarterly series -- reasonable for
    an ongoing listed company; a stock with reporting gaps would just get
    NaN for those quarters, not a wrong number). Returns pit_date, eps_yoy.
    """
    q = quarterly_pit(stock_id, start_date)
    if q.empty or "EPS" not in q.columns:
        return pd.DataFrame(columns=["pit_date", "eps_yoy"])
    q = q.sort_values("fiscal_period_end").reset_index(drop=True)
    q["eps_yoy"] = (q["EPS"] - q["EPS"].shift(4)) / q["EPS"].shift(4).abs()
    return q[["pit_date", "eps_yoy"]]


def prepare_factors(
    stock_id: str,
    price_df: pd.DataFrame,
    market_df: pd.DataFrame,
    start_date: str = "2010-01-01",
) -> pd.DataFrame:
    """price_df: adjust.adjusted_price_series() output for this stock
    (already load_dev()-capped). market_df: prepared TAIEX df (needs at
    least date, close). Returns price_df with six factor columns added:
    f_rev_accel, f_eps_growth, f_foreign_streak, f_inst_flow,
    f_rel_strength, f_ma_breakout.
    """
    d = price_df.sort_values("date").reset_index(drop=True).copy()

    # (e) 相對強度 vs 大盤 60 日
    mkt_close = market_df.set_index("date")["close"]
    d["mkt_close"] = d["date"].map(mkt_close)
    ret60 = d["adj_close"] / d["adj_close"].shift(REL_STRENGTH_WINDOW) - 1
    mkt_ret60 = d["mkt_close"] / d["mkt_close"].shift(REL_STRENGTH_WINDOW) - 1
    d["f_rel_strength"] = ret60 - mkt_ret60

    # (f) 站上季線 + 量能放大
    ma60 = d["adj_close"].rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    above_ma_pct = d["adj_close"] / ma60 - 1
    vol20 = d["Trading_Volume"].rolling(VOL_SHORT_WINDOW, min_periods=VOL_SHORT_WINDOW).mean()
    vol60 = d["Trading_Volume"].rolling(VOL_LONG_WINDOW, min_periods=VOL_LONG_WINDOW).mean()
    d["f_ma_breakout"] = above_ma_pct * (vol20 / vol60)

    # (c)/(d) 三大法人相關
    inst = _institutional_daily_net(stock_id, start_date)
    d = d.merge(inst, on="date", how="left")
    for c in ("foreign_net", "trust_net", "dealer_net", "total_net"):
        d[c] = d[c].fillna(0.0)
    avg_vol20 = d["Trading_Volume"].rolling(FOREIGN_STREAK_VOL_WINDOW, min_periods=1).mean().to_numpy()
    d["f_foreign_streak"] = _foreign_streak_strength(d["foreign_net"].to_numpy(), avg_vol20)
    net_amount = d["total_net"] * d["close"]
    value20 = d["Trading_money"].rolling(INST_FLOW_WINDOW, min_periods=INST_FLOW_WINDOW).mean()
    d["f_inst_flow"] = net_amount.rolling(INST_FLOW_WINDOW, min_periods=INST_FLOW_WINDOW).sum() / (value20 * INST_FLOW_WINDOW)

    # (a) 月營收 YoY 加速度 -- point-in-time via pit_date
    rev_pit = _revenue_yoy_acceleration(stock_id, start_date)
    d = _asof_join(d, rev_pit, "yoy_accel", "f_rev_accel")

    # (b) EPS 成長 -- point-in-time via pit_date
    eps_pit = _eps_yoy_growth(stock_id, start_date)
    d = _asof_join(d, eps_pit, "eps_yoy", "f_eps_growth")

    return d


FACTOR_COLUMNS = [
    "f_rev_accel", "f_eps_growth", "f_foreign_streak",
    "f_inst_flow", "f_rel_strength", "f_ma_breakout",
]
