"""AI 選股引擎 Phase A -- factor library.

Originally six factors computed from free FinMind data; **expanded
2026-08-22** (Cowork review) with six more candidates: value (PB/PE),
quality (ROE stability), low volatility, and two SUE-style "surprise"
factors (EPS surprise / revenue surprise) that are deliberately DIFFERENT
hypotheses from the original growth/acceleration factors -- see each
function's docstring for exactly how they differ.

Every daily/volume-based input is naturally point-in-time (a trading day's
OHLCV is known at that day's close). Every fundamentals-based input
(monthly revenue, quarterly EPS, quarterly balance sheet) is joined onto
the daily price series via `pandas.merge_asof(..., direction="backward")`
keyed on `pit.py`'s `pit_date` column, NOT the fiscal period date -- this
is what makes "the revenue-acceleration factor value on trading day T"
mean "the most recently DISCLOSED figure as of T", never a figure that
wouldn't actually have been public yet. Verified against real 2330 data
(see REPORT.md 2026-08-22 entries) that the daily factor value only changes
on/after the real pit_date. See pit.py's own docstring for what `pit_date`
means and its `assumed` vs `real` distinction; any factor built on
`pit_source='assumed'` rows inherits that same experimental status.

A factor being defined here is not a claim that it works. factor_ic.py is
what decides which actually carry predictive information; CONSTITUTION.md's
honesty rule applies here just as much as to a full strategy -- a factor
that fails IC testing gets weight 0 in score.py, not quietly dropped from
the record.

**Known substitution, disclosed (not hidden):** factor (d) is described in
the project design doc as "三大法人淨買/市值" (institutional net buy / market
cap), but `TaiwanStockMarketValue` is paid-tier only (same class of gate as
`TaiwanStockPriceAdj` -- see DATA.md). Market cap is substituted with a
20-day average trading VALUE (`Trading_money`, free) as the denominator
instead -- a liquidity-normalized proxy, not literally market cap. Still a
reasonable normalization (big, liquid stocks have both bigger market caps
and bigger trading values, so the two are correlated), but not the same
number the design doc names.

**Value factors' PIT status is UNVERIFIED, disclosed:** `f_value_pb` /
`f_value_pe` read `TaiwanStockPER`'s daily PBR/PER directly, which FinMind
computes itself from that day's price and *some* trailing EPS/book-value
figure. Whether FinMind updates that trailing figure the moment a fiscal
quarter ENDS (a hidden lookahead bias baked into FinMind's own data, not
introduced by this codebase) or only once the quarter is actually
DISCLOSED has not been checked -- the FinMind rate limit was hit (see
FACTORS.md/REPORT.md 2026-08-22) before this could be tested with real
data. Do not trust these two factors' IC results (once run) as PIT-clean
until this is explicitly verified the same way f_rev_accel/f_eps_growth
were.

**分點集中度 (broker-branch concentration) was investigated and dropped, not
silently skipped**: the plausible free-tier dataset (`TaiwanStockTradingDailyReport`)
returned a confirmed paid-tier rejection on a live request (2026-08-22);
`TaiwanSecuritiesTraderInfo` only gives broker metadata (name/address), not
per-stock branch trading volume. No FinMind free-tier path exists for this
factor as far as this investigation found.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from finmind_client import load_dev
from pit import balance_sheet_pit, month_revenue_pit, quarterly_pit

FOREIGN_STREAK_VOL_WINDOW = 20
INST_FLOW_WINDOW = 20
REL_STRENGTH_WINDOW = 60
MA_WINDOW = 60
VOL_SHORT_WINDOW = 20
VOL_LONG_WINDOW = 60
LOW_VOL_WINDOW = 60
SUE_TRAILING_QUARTERS = 8
REVENUE_SUE_TRAILING_MONTHS = 12
ROE_STABILITY_TRAILING_QUARTERS = 8


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


def _quarterly_eps(stock_id: str, start_date: str) -> pd.DataFrame:
    """Shared base for (b) and the EPS-surprise factor: quarterly EPS sorted
    by fiscal period, with pit_date attached. Returns pit_date, EPS.
    """
    q = quarterly_pit(stock_id, start_date)
    if q.empty or "EPS" not in q.columns:
        return pd.DataFrame(columns=["pit_date", "fiscal_period_end", "EPS"])
    return q.sort_values("fiscal_period_end").reset_index(drop=True)[["pit_date", "fiscal_period_end", "EPS"]]


def _eps_yoy_growth(stock_id: str, start_date: str) -> pd.DataFrame:
    """(b) EPS 成長: this quarter's EPS vs the same quarter one year prior
    (shift(4), assuming no gaps in the quarterly series -- reasonable for
    an ongoing listed company; a stock with reporting gaps would just get
    NaN for those quarters, not a wrong number). Returns pit_date, eps_yoy.
    """
    q = _quarterly_eps(stock_id, start_date)
    if q.empty:
        return pd.DataFrame(columns=["pit_date", "eps_yoy"])
    q["eps_yoy"] = (q["EPS"] - q["EPS"].shift(4)) / q["EPS"].shift(4).abs()
    return q[["pit_date", "eps_yoy"]]


def _eps_surprise_sue(stock_id: str, start_date: str) -> pd.DataFrame:
    """(g) PEAD / 財報意外 -- Standardized Unexpected Earnings (SUE), the
    academic-literature proxy used when no analyst-estimate consensus is
    available (Bernard & Thomas methodology): seasonally-differenced EPS
    change, standardized by the trailing volatility of that same seasonal
    difference. **Deliberately different hypothesis from (b) f_eps_growth**:
    (b) is a raw growth RATE; this is the seasonal CHANGE standardized by
    its own historical variability -- a company with huge, choppy EPS swings
    needs a much bigger change to register as a real "surprise" than a
    stable one does, which plain YoY growth doesn't distinguish.
    """
    q = _quarterly_eps(stock_id, start_date)
    if q.empty:
        return pd.DataFrame(columns=["pit_date", "eps_sue"])
    q["eps_diff"] = q["EPS"] - q["EPS"].shift(4)
    q["eps_diff_std"] = q["eps_diff"].rolling(SUE_TRAILING_QUARTERS, min_periods=SUE_TRAILING_QUARTERS).std()
    q["eps_sue"] = q["eps_diff"] / q["eps_diff_std"]
    return q[["pit_date", "eps_sue"]]


def _revenue_surprise_sue(stock_id: str, start_date: str) -> pd.DataFrame:
    """(h) 營收意外 -- same SUE standardization idea applied to monthly
    revenue YoY instead of quarterly EPS. **Deliberately different
    hypothesis from (a) f_rev_accel**: (a) asks "is YoY growth speeding up
    month over month"; this asks "is this month's YoY growth unusually
    large relative to how volatile this stock's YoY growth normally is".
    """
    rev = month_revenue_pit(stock_id, start_date)
    if rev.empty:
        return pd.DataFrame(columns=["pit_date", "revenue_sue"])
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    prior = prior.rename(columns={"revenue": "revenue_prior_year"})
    rev = rev.merge(prior, on=["revenue_year", "revenue_month"], how="left")
    rev["yoy"] = (rev["revenue"] - rev["revenue_prior_year"]) / rev["revenue_prior_year"].abs()
    rev["yoy_std"] = rev["yoy"].rolling(REVENUE_SUE_TRAILING_MONTHS, min_periods=REVENUE_SUE_TRAILING_MONTHS).std()
    rev["revenue_sue"] = rev["yoy"] / rev["yoy_std"]
    return rev[["pit_date", "revenue_sue"]]


def _roe_stability(stock_id: str, start_date: str) -> pd.DataFrame:
    """(j) 品質 ROE穩定度: quarterly ROE = this quarter's net income
    attributable to parent (quarterly_pit's `EquityAttributableToOwnersOfParent`,
    an income-statement line despite the name -- see App's index.html for
    the same field reused the same way) divided by that quarter's ending
    equity (balance_sheet_pit's `EquityAttributableToOwnersOfParent`, the
    balance-sheet line). Stability score = negative rolling std of the
    trailing 8 quarterly ROE values (lower volatility = higher "quality"
    score, hence the negation). Merged on fiscal_period_end -- both PIT
    functions use the same +45-day lag assumption so this doesn't introduce
    a new lookahead path, just combines two already-lagged series.
    """
    inc = quarterly_pit(stock_id, start_date)
    bs = balance_sheet_pit(stock_id, start_date)
    if inc.empty or bs.empty or "EquityAttributableToOwnersOfParent" not in inc.columns \
            or "EquityAttributableToOwnersOfParent" not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "roe_stability"])
    inc = inc[["fiscal_period_end", "pit_date", "EquityAttributableToOwnersOfParent"]].rename(
        columns={"EquityAttributableToOwnersOfParent": "net_income"})
    bs = bs[["fiscal_period_end", "EquityAttributableToOwnersOfParent"]].rename(
        columns={"EquityAttributableToOwnersOfParent": "equity"})
    merged = inc.merge(bs, on="fiscal_period_end", how="inner").sort_values("fiscal_period_end").reset_index(drop=True)
    if merged.empty:
        return pd.DataFrame(columns=["pit_date", "roe_stability"])
    merged["roe"] = merged["net_income"] / merged["equity"]
    merged["roe_stability"] = -merged["roe"].rolling(
        ROE_STABILITY_TRAILING_QUARTERS, min_periods=ROE_STABILITY_TRAILING_QUARTERS
    ).std()
    return merged[["pit_date", "roe_stability"]]


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

    # (g) PEAD/財報意外 (SUE) -- point-in-time via pit_date
    sue_pit = _eps_surprise_sue(stock_id, start_date)
    d = _asof_join(d, sue_pit, "eps_sue", "f_eps_surprise")

    # (h) 營收意外 (SUE) -- point-in-time via pit_date
    rev_sue_pit = _revenue_surprise_sue(stock_id, start_date)
    d = _asof_join(d, rev_sue_pit, "revenue_sue", "f_revenue_surprise")

    # (i) 低波動: 60 日日報酬標準差取負號（波動越低分數越高），純價格資料，天然 point-in-time
    daily_ret = d["adj_close"].pct_change()
    d["f_low_vol"] = -daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).std()

    # (j) 品質 ROE穩定度 -- point-in-time via pit_date（合併季報+資產負債表兩個 PIT 序列）。
    # 用 TaiwanStockBalanceSheet，這是這批新因子裡第一次用到的資料集，捕捉例外而不是讓
    # 整檔股票的其他 11 個因子也一起報廢（2026-08-22 遇到 FinMind 流量限制時發現這個問題）。
    try:
        roe_pit = _roe_stability(stock_id, start_date)
        d = _asof_join(d, roe_pit, "roe_stability", "f_quality_roe_stability")
    except RuntimeError as e:
        print(f"    [factors] f_quality_roe_stability skipped for {stock_id}: {e}")
        d["f_quality_roe_stability"] = np.nan

    # (k)/(l) 價值 PB/PE -- 直接讀 FinMind 算好的 PER/PBR。
    # **PIT 安全性未驗證，見檔案最上面的揭露**：FinMind 用來算這兩個數字的 EPS/淨值，
    # 更新時點是不是也有提早看到還沒公告財報的問題，還沒有像 f_rev_accel/f_eps_growth
    # 那樣用真實資料逐日核對過（流量限制擋住了驗證，見 FACTORS.md）。同樣捕捉例外。
    try:
        per_raw = load_dev("TaiwanStockPER", stock_id, start_date)
        if not per_raw.empty and "PBR" in per_raw.columns and "PER" in per_raw.columns:
            per_raw = per_raw[["date", "PBR", "PER"]].copy()
            d = d.merge(per_raw, on="date", how="left")
            d["f_value_pb"] = np.where(d["PBR"] > 0, -d["PBR"], np.nan)
            d["f_value_pe"] = np.where(d["PER"] > 0, -d["PER"], np.nan)  # 排除虧損公司的負/零 PER
            d = d.drop(columns=["PBR", "PER"])
        else:
            d["f_value_pb"] = np.nan
            d["f_value_pe"] = np.nan
    except RuntimeError as e:
        print(f"    [factors] f_value_pb/f_value_pe skipped for {stock_id}: {e}")
        d["f_value_pb"] = np.nan
        d["f_value_pe"] = np.nan

    return d


def prepare_score_factors(
    stock_id: str, price_df: pd.DataFrame, start_date: str = "2010-01-01",
) -> pd.DataFrame:
    """Lean variant of prepare_factors(): only the 4 raw columns score.py's
    composite actually reads (f_eps_growth, f_eps_surprise,
    f_revenue_surprise, f_low_vol), reusing the exact same PIT helper
    functions -- correctness is identical to prepare_factors()'s versions
    of these same 4 columns, just without also fetching the 5 datasets
    (institutional buy/sell, balance sheet, PER) that feed the OTHER 8
    factors score.py never uses.

    Added 2026-08-24 for long_short_backtest.py's full-universe run: a
    real, measured problem, not a hypothetical optimization -- scanning
    universe.py's full ~3200-name market through prepare_factors() burns
    through FinMind's free-tier rate limit largely on TaiwanStockBalanceSheet/
    TaiwanStockPER calls whose results are silently discarded downstream
    (score.py never reads f_value_pb/f_value_pe/f_quality_roe_stability).
    No market_df/institutional data needed either, unlike prepare_factors().
    """
    d = price_df.sort_values("date").reset_index(drop=True).copy()

    eps_pit = _eps_yoy_growth(stock_id, start_date)
    d = _asof_join(d, eps_pit, "eps_yoy", "f_eps_growth")

    sue_pit = _eps_surprise_sue(stock_id, start_date)
    d = _asof_join(d, sue_pit, "eps_sue", "f_eps_surprise")

    rev_sue_pit = _revenue_surprise_sue(stock_id, start_date)
    d = _asof_join(d, rev_sue_pit, "revenue_sue", "f_revenue_surprise")

    daily_ret = d["adj_close"].pct_change()
    d["f_low_vol"] = -daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).std()

    return d


FACTOR_COLUMNS = [
    "f_rev_accel", "f_eps_growth", "f_foreign_streak",
    "f_inst_flow", "f_rel_strength", "f_ma_breakout",
]

# 2026-08-22 新增（Cowork 要求擴充因子庫）。PIT 對齊方式跟原本六個因子完全一致；
# f_value_pb/f_value_pe 的 PIT 安全性尚未驗證，見檔案最上面的揭露，IC 結果出來前不要
# 假設它們是乾淨的。
NEW_FACTOR_COLUMNS = [
    "f_eps_surprise", "f_revenue_surprise", "f_low_vol",
    "f_quality_roe_stability", "f_value_pb", "f_value_pe",
]

ALL_FACTOR_COLUMNS = FACTOR_COLUMNS + NEW_FACTOR_COLUMNS
