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

**Value factors' PIT status, spot-checked (2026-08-23 marathon round 4),
not fully verified:** `f_value_pb` / `f_value_pe` read `TaiwanStockPER`'s
daily PBR/PER directly, which FinMind computes itself from that day's price
and *some* trailing EPS/book-value figure. `verify_pit_value_pb.py` ran a
jump-detection check on a single stock (2330, 2015-2024, 40/42 quarters):
the implied book-value-per-share (`close / PBR`) only steps on specific
dates, and those step dates land 32-62 days (median 45, matching this
project's own assumed quarterly disclosure lag AND Taiwan's regulatory
45-day quarterly filing deadline) after each fiscal period end -- never
near 0 days, which is what a severe lookahead bias would look like. See
`TRIALS_LEDGER.md`'s "investigated but not counted as a trial" table and
`TW_LOG.md` for the full numbers. **This is one stock with an indirect
detection method, not an official FinMind confirmation of their update
logic** -- treat as "no severe lookahead bias found on a spot check", not
"PIT-clean, fully verified". `f_value_pe` shares the same data source and
this finding is assumed to extend to it, but was not independently
re-tested.

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
SHORT_REVERSAL_WINDOW = 21  # ~1 calendar month in trading days
AMIHUD_WINDOW = 20  # Amihud (2002) illiquidity, ~1 trading month
SUE_TRAILING_QUARTERS = 8
REVENUE_SUE_TRAILING_MONTHS = 12
ROE_STABILITY_TRAILING_QUARTERS = 8
ASSET_GROWTH_LAG_QUARTERS = 4  # YoY (同比，避開季節性), Cooper/Gulen/Schill 2008
ACCRUALS_LAG_QUARTERS = 4  # YoY (同比，避開季節性), Sloan 1996 balance-sheet approach
RESIDUAL_MOMENTUM_WINDOW = 252  # ~12 個月交易日, Blitz/Huij/Martens 2011
HIGH_52W_WINDOW = 252  # ~52 週交易日, George & Hwang 2004
SHORT_TERM_REVERSAL_1W_WINDOW = 5  # ~1 週交易日, Jegadeesh 1990


def _finmind_institutional_wide(stock_id: str, start_date: str) -> pd.DataFrame:
    """Original (pre-2026-08-26) FinMind-based path. Kept as the fallback for
    whatever date range twse_t86_client's cache doesn't cover yet."""
    cols = ["date", "foreign_net", "trust_net", "dealer_net", "total_net"]
    raw = load_dev("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date)
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


def _institutional_daily_net(stock_id: str, start_date: str) -> pd.DataFrame:
    """Daily net buy (shares) per institutional category, wide format:
    date, foreign_net, trust_net, dealer_net, total_net.

    **2026-08-26 hybrid switch:** TWSE's own T86 open data
    (`twse_t86_client`, cached per-date via `backfill_t86.py`) is now
    PRIMARY -- FinMind's free tier hit a 402 quota wall this day. Since
    `backfill_t86.py` fills its date cache incrementally (like
    `backfill_universe.py` does for price), any given stock/range request
    may only be PARTIALLY covered by T86 at a given point in time. Rather
    than an all-or-nothing fallback (which would silently zero out
    institutional flow on every T86-uncovered date once T86 has *any* data
    at all), this fills exactly the gap dates from FinMind -- and if
    FinMind itself is unavailable (402, or any other error), degrades
    gracefully to "T86-only, gap dates absent" instead of raising, since a
    factor computation for one stock should not abort the whole backfill
    batch over one missing side-channel.
    """
    from twse_t86_client import institutional_daily_net_t86

    t86 = institutional_daily_net_t86(stock_id, start_date)
    if t86.empty:
        try:
            return _finmind_institutional_wide(stock_id, start_date)
        except Exception:  # noqa: BLE001 -- e.g. FinMind 402; degrade to "no data" rather than abort
            return pd.DataFrame(columns=["date", "foreign_net", "trust_net", "dealer_net", "total_net"])

    try:
        fm = _finmind_institutional_wide(stock_id, start_date)
    except Exception:  # noqa: BLE001 -- FinMind unavailable: T86-only is still a valid, honest result
        return t86
    if fm.empty:
        return t86
    fm_gap = fm[~fm["date"].isin(set(t86["date"]))]
    if fm_gap.empty:
        return t86
    combined = pd.concat([t86, fm_gap], ignore_index=True).sort_values("date").reset_index(drop=True)
    return combined


def _consecutive_positive_streak_days(net: np.ndarray) -> np.ndarray:
    """三大法人合計連續買超天數 (`HYPOTHESIS_QUEUE.md` #13，2026-09-02 自動排程
    新增，佇列排隊第一起跑)。經濟理由：三大法人在台股普遍被視為資訊優勢方，
    連續買超天數代表持續性的資訊優勢累積，比單日金額更能過濾雜訊（單日大額
    買超可能只是換股操作或程式交易雜訊，連續多日同方向較可能反映真實優勢）。

    跟已經FAIL的`f_foreign_streak`/`_foreign_streak_strength()`刻意做出兩點
    區隔（不是換皮重測同一個已死機制）：(1) 這裡用**三大法人合計**
    (`total_net`)，`f_foreign_streak`只算**外資單一法人**(`foreign_net`)；
    (2) 這裡衡量的統計量是**連續天數本身**（計數/次序統計量），
    `f_foreign_streak`衡量的是「用成交量正規化的連續期間累積買超金額」（連續
    量的大小），是根本不同的統計量，不是同一個訊號換個寫法。每日輸出「截至
    當天為止、連續同方向(>0)未中斷的天數」，net[i]<=0當天歸零。跟
    `_foreign_streak_strength()`同一種因果/序列邏輯（每個值只依賴到當天為止
    的歷史，天然point-in-time），故意沿用同一套loop寫法保持風格一致，不是
    重複造輪子。
    """
    out = np.zeros(len(net))
    streak = 0
    for i in range(len(net)):
        if net[i] > 0:
            streak += 1
        else:
            streak = 0
        out[i] = float(streak)
    return out


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


def _asset_growth(stock_id: str, start_date: str) -> pd.DataFrame:
    """資產成長異常 (asset growth anomaly, Cooper, Gulen & Schill 2008)：資產
    成長越快的公司，後續報酬文獻上越低（過度投資/擴張過快的訊號）。定義為
    `TotalAssets` 同比成長（跟 4 季前比較，YoY 而非季對季，避開季節性），取負號
    （低成長分數較高，符合本專案「分數高=預期未來報酬較好」的慣例）。用
    `balance_sheet_pit` 同一個資料源、同一組 pit_date +45 天延遲假設，跟
    `_roe_stability` 完全同一個快取鍵（同一 stock_id/start_date），零額外
    FinMind 呼叫。2026-08-26 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「資產
    成長/保守投資」家族，尚未測過）。
    """
    bs = balance_sheet_pit(stock_id, start_date)
    if bs.empty or "TotalAssets" not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "asset_growth"])
    bs = bs[["fiscal_period_end", "pit_date", "TotalAssets"]].sort_values(
        "fiscal_period_end"
    ).reset_index(drop=True)
    bs["asset_growth"] = -(
        bs["TotalAssets"] / bs["TotalAssets"].shift(ASSET_GROWTH_LAG_QUARTERS) - 1
    )
    return bs[["pit_date", "asset_growth"]]


def _accruals(stock_id: str, start_date: str) -> pd.DataFrame:
    """盈餘品質應計項目 (accruals, Sloan 1996)：應計項目占比越高的公司，後續報酬
    文獻上越低（會計盈餘裡「非現金」部分較多，較不具持續性，市場常對此定價不足）。
    本專案沒有現金流量表資料源（`TaiwanStockCashFlowsStatement` 從未抓取過），無法用
    Sloan 原始的「NI - CFO」定義，改用 Sloan (1996) 論文本身也採用過的資產負債表法
    (balance-sheet approach，Richardson/Sloan/Soliman/Tuna 2005 同款簡化)：
    ΔWC = Δ(CurrentAssets - Cash) - Δ(CurrentLiabilities - ShorttermBorrowings)，
    accruals = ΔWC(YoY，4季前) / TotalAssets，取負號（低應計分數較高）。
    **已知簡化，非完整版**：省略了折舊費用調整項（Sloan 原公式是 ΔWC - Depreciation，
    這裡沒有折舊資料來源，等同假設折舊調整項相對次要，未驗證這個假設的影響量級，
    誠實揭露而非假裝完整）。用 `balance_sheet_pit` 同一個資料源、同一組 pit_date +45
    天延遲假設，跟 `_asset_growth`/`_roe_stability` 完全同一個快取鍵，零額外 FinMind
    呼叫。2026-08-26 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「品質」家族 accruals
    盈餘品質，尚未測過）。
    """
    bs = balance_sheet_pit(stock_id, start_date)
    required = ["CurrentAssets", "CashAndCashEquivalents", "CurrentLiabilities",
                "ShorttermBorrowings", "TotalAssets"]
    if bs.empty or any(c not in bs.columns for c in required):
        return pd.DataFrame(columns=["pit_date", "accruals"])
    bs = bs[["fiscal_period_end", "pit_date"] + required].sort_values(
        "fiscal_period_end"
    ).reset_index(drop=True)
    noncash_ca = bs["CurrentAssets"] - bs["CashAndCashEquivalents"]
    op_cl = bs["CurrentLiabilities"] - bs["ShorttermBorrowings"]
    wc = noncash_ca - op_cl
    delta_wc = wc - wc.shift(ACCRUALS_LAG_QUARTERS)
    bs["accruals"] = -(delta_wc / bs["TotalAssets"])
    return bs[["pit_date", "accruals"]]


def _gross_margin_stability(stock_id: str, start_date: str) -> pd.DataFrame:
    """品質：毛利率穩定度 (Novy-Marx 精神的品質異常變體，`MARATHON_PROTOCOL.md`
    第3節「品質」家族明列的項目，尚未測過)。季毛利率 = GrossProfit / Revenue，
    穩定度分數 = 負的近 8 季毛利率滾動標準差（波動度越低分數越高），統計構造
    跟 `_roe_stability` 完全一樣，只是把「淨利/權益」換成「毛利/營收」——概念上
    是不同的品質訊號（毛利率反映核心業務定價力/成本控制的穩定度，ROE 還混雜了
    財務槓桿跟業外損益）。用 `quarterly_pit` 同一個資料源/同一個快取鍵
    （TaiwanStockFinancialStatements，同 stock_id/start_date），跟
    `_roe_stability`/`_asset_growth`/`_accruals` 共用同一批已快取的原始回應，
    零額外 FinMind 呼叫。
    """
    inc = quarterly_pit(stock_id, start_date)
    if inc.empty or "Revenue" not in inc.columns or "GrossProfit" not in inc.columns:
        return pd.DataFrame(columns=["pit_date", "gross_margin_stability"])
    inc = inc[["fiscal_period_end", "pit_date", "Revenue", "GrossProfit"]].sort_values(
        "fiscal_period_end"
    ).reset_index(drop=True)
    gross_margin = inc["GrossProfit"] / inc["Revenue"].replace(0, np.nan)
    inc["gross_margin_stability"] = -gross_margin.rolling(
        ROE_STABILITY_TRAILING_QUARTERS, min_periods=ROE_STABILITY_TRAILING_QUARTERS
    ).std()
    return inc[["pit_date", "gross_margin_stability"]]


def _gross_profitability(stock_id: str, start_date: str) -> pd.DataFrame:
    """`HYPOTHESIS_QUEUE.md` #20 純毛利率因子 (Gross Profitability, Novy-Marx
    2013)：GP = GrossProfit / TotalAssets，橫截面排序做多GP最高分位，不取負號
    （分數定義本身就是「越高越好」，跟f_dividend_yield_ttm同一種慣例）。

    經濟機制：核心業務真正的獲利能力（毛利，不受財務槓桿/業外損益污染）相對
    公司資產規模，市場對這個訊號的定價效率不足，超額報酬被認為是行為性（低估
    持續）而非承擔額外系統性風險的補償。**跟已FAIL的`f_gross_margin_stability`
    （`TRIALS_LEDGER.md`#67）不是同一個構造**——那條測的是毛利率隨時間的
    「穩定性」（近8季滾動標準差），這條測的是毛利率相對總資產的「水位」
    （Novy-Marx原始論文定義），本專案至今沒有直接測過這個版本。

    合併方式跟`_roe_stability`完全同一個模式：GrossProfit來自`quarterly_pit`
    （損益表），TotalAssets來自`balance_sheet_pit`（資產負債表），兩個PIT
    函式用同一組`fiscal_period_end`+45天延遲假設，`merge(on="fiscal_period_end")`
    不會引入新的前瞻偏誤路徑，只是合併兩個已經延遲過的序列。零額外FinMind呼叫
    ——跟`_gross_margin_stability`/`_asset_growth`共用同一批已快取的原始回應
    （`quarterly_pit`已經抓過GrossProfit、`balance_sheet_pit`已經抓過
    TotalAssets，兩者都被`_accruals`/`_asset_growth`用過）。

    2026-09-03 `HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#20第1關起跑。
    """
    inc = quarterly_pit(stock_id, start_date)
    bs = balance_sheet_pit(stock_id, start_date)
    if inc.empty or bs.empty or "GrossProfit" not in inc.columns \
            or "TotalAssets" not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "gross_profitability"])
    inc = inc[["fiscal_period_end", "pit_date", "GrossProfit"]]
    bs = bs[["fiscal_period_end", "TotalAssets"]]
    merged = inc.merge(bs, on="fiscal_period_end", how="inner").sort_values(
        "fiscal_period_end"
    ).reset_index(drop=True)
    if merged.empty:
        return pd.DataFrame(columns=["pit_date", "gross_profitability"])
    merged["gross_profitability"] = merged["GrossProfit"] / merged["TotalAssets"].replace(0, np.nan)
    return merged[["pit_date", "gross_profitability"]]


DIVIDEND_YIELD_TRAILING_DAYS = 365  # 近12個月現金股利加總的視窗


def _dividend_yield_ttm_cash(stock_id: str, start_date: str) -> pd.DataFrame:
    """`HYPOTHESIS_QUEUE.md` #4股票股利率carry：TW股票近12個月現金股利/股價
    （殖利率），高殖利率排名靠前。這裡只算分子（trailing 12個月現金股利加總，
    元/股），除以股價的動作留到`prepare_factors()`（跟f_value_pb/pe直接讀
    PER/PBR再除的做法一致）。

    **PIT安全性天然成立、不需要`pit_date`延遲假設**（跟財報類因子不同）：
    `TaiwanStockDividend`的`CashExDividendTradingDate`（除息交易日）本身就是
    市場公開資訊的生效日——除息當天全市場都看得到這件事發生了，不像財報有
    申報延遲，所以這裡直接把ex-date當成`pit_date`使用，不套用`quarterly_pit`
    那種+45天假設。用`adjust.py::adjustment_events()`已經在用的同一個資料集
    （`TaiwanStockDividend`），沿用`load_dev()`（VAL_END自動截斷），零額外
    新資料源需求，但這是這批因子第一次直接讀這個資料集本身（不是透過
    adjust.py的還原價邏輯），所以走FinMind呼叫（非零額外呼叫）。

    2026-09-01 HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#4起跑。
    """
    div = load_dev("TaiwanStockDividend", stock_id, start_date)
    if div.empty or "CashExDividendTradingDate" not in div.columns:
        return pd.DataFrame(columns=["pit_date", "ttm_cash_dividend"])
    events = div[["CashExDividendTradingDate", "CashEarningsDistribution"]].copy()
    events = events.rename(columns={"CashExDividendTradingDate": "ex_date",
                                     "CashEarningsDistribution": "cash"})
    events["ex_date"] = events["ex_date"].replace("", np.nan)
    events = events.dropna(subset=["ex_date"])
    events["cash"] = pd.to_numeric(events["cash"], errors="coerce").fillna(0.0)
    events = events[events["cash"] > 0].sort_values("ex_date").reset_index(drop=True)
    if events.empty:
        return pd.DataFrame(columns=["pit_date", "ttm_cash_dividend"])
    ex_dates = pd.to_datetime(events["ex_date"])
    # 每個 ex-date 事件當天的 pit_date，值 = 該事件往回 TRAILING_DAYS 內（含自己）
    # 所有已發生 ex-date 的現金股利加總——只用「已經發生」的事件，天然 PIT-safe。
    ttm = []
    for i in range(len(events)):
        window_start = ex_dates.iloc[i] - pd.Timedelta(days=DIVIDEND_YIELD_TRAILING_DAYS)
        mask = (ex_dates <= ex_dates.iloc[i]) & (ex_dates > window_start)
        ttm.append(events.loc[mask, "cash"].sum())
    events["ttm_cash_dividend"] = ttm
    events["pit_date"] = events["ex_date"]
    return events[["pit_date", "ttm_cash_dividend"]]


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
    d["f_inst_streak_days"] = _consecutive_positive_streak_days(d["total_net"].to_numpy())

    # (a)/(b)/(g)/(h) 月營收/財報衍生因子 -- 全部依賴 FinMind
    # TaiwanStockMonthRevenue/TaiwanStockFinancialStatements，額度用盡時個別捕捉
    # 例外（2026-08-26 補上，跟下面 f_quality_roe_stability/f_value_pb/pe 同一套
    # 降級模式一致）：不能讓其中一個資料集額度用盡就讓這檔股票其他 7 個因子
    # （價格/成交量/三大法人為基礎的）也一起報廢，那正是使用者這輪要求解決的
    # 「整條停擺」問題。
    try:
        rev_pit = _revenue_yoy_acceleration(stock_id, start_date)  # (a) 月營收 YoY 加速度
        d = _asof_join(d, rev_pit, "yoy_accel", "f_rev_accel")
    except RuntimeError as e:
        print(f"    [factors] f_rev_accel skipped for {stock_id}: {e}")
        d["f_rev_accel"] = np.nan

    try:
        eps_pit = _eps_yoy_growth(stock_id, start_date)  # (b) EPS 成長
        d = _asof_join(d, eps_pit, "eps_yoy", "f_eps_growth")
    except RuntimeError as e:
        print(f"    [factors] f_eps_growth skipped for {stock_id}: {e}")
        d["f_eps_growth"] = np.nan

    try:
        sue_pit = _eps_surprise_sue(stock_id, start_date)  # (g) PEAD/財報意外 (SUE)
        d = _asof_join(d, sue_pit, "eps_sue", "f_eps_surprise")
    except RuntimeError as e:
        print(f"    [factors] f_eps_surprise skipped for {stock_id}: {e}")
        d["f_eps_surprise"] = np.nan

    try:
        rev_sue_pit = _revenue_surprise_sue(stock_id, start_date)  # (h) 營收意外 (SUE)
        d = _asof_join(d, rev_sue_pit, "revenue_sue", "f_revenue_surprise")
    except RuntimeError as e:
        print(f"    [factors] f_revenue_surprise skipped for {stock_id}: {e}")
        d["f_revenue_surprise"] = np.nan

    # (i) 低波動: 60 日日報酬標準差取負號（波動越低分數越高），純價格資料，天然 point-in-time
    daily_ret = d["adj_close"].pct_change()
    d["f_low_vol"] = -daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).std()

    # (m) 短期反轉: 近 21 個交易日（~1 個月）累積報酬取負號，純價格資料，天然 point-in-time。
    # 2026-08-26 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「動量變體/短期反轉」家族，尚未測過），
    # 跟 f_rel_strength（60 日相對大盤動能）刻意用不同窗口、不同定義（這裡是自身絕對報酬，不是
    # 相對大盤），文獻上短期反轉跟中期動能是兩個獨立、方向常相反的異常，值得分開測。
    d["f_short_reversal_1m"] = -(d["adj_close"] / d["adj_close"].shift(SHORT_REVERSAL_WINDOW) - 1)

    # (n) Amihud 流動性因子: 20 日 |日報酬|/成交金額 均值（Amihud 2002），純價格/成交量
    # 資料，天然 point-in-time。**方向刻意不取負號**：文獻上流動性越差（數值越大）要求
    # 的預期報酬溢酬越高，跟 f_low_vol/f_short_reversal_1m 取負號的慣例相反，是設計選擇
    # 不是疏漏。2026-08-26 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「流動性」家族，尚未
    # 測過）。Trading_money 為 0（該日無成交）時整段視為缺值，不當作流動性極佳處理。
    illiq_daily = np.where(d["Trading_money"] > 0, daily_ret.abs() / d["Trading_money"], np.nan)
    d["f_amihud_illiq"] = pd.Series(illiq_daily, index=d.index).rolling(
        AMIHUD_WINDOW, min_periods=AMIHUD_WINDOW
    ).mean()

    # (o) 特異波動率 (idiosyncratic volatility, Ang et al. 2006)：60 日窗口用市場模型
    # 變異數分解 Var(r) = beta^2*Var(rm) + Var(residual) 的封閉解算出特異變異數，取負號
    # （高特異波動率文獻上對應「較低」未來報酬，跟 f_low_vol 的取負號慣例方向一致，但這是
    # 獨立機制——f_low_vol 是總波動度，這裡扣掉了 beta*大盤波動的部分，兩者可能高度相關但
    # 概念上不同，文獻上分開列為兩個異常）。純價格資料，天然 point-in-time，2026-08-26
    # 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「低風險」家族第二個測試，f_low_vol 是第一個）。
    mkt_ret = d["mkt_close"].pct_change()
    roll_var_stock = daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).var()
    roll_var_mkt = mkt_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).var()
    roll_cov = daily_ret.rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).cov(mkt_ret)
    beta_60 = roll_cov / roll_var_mkt
    idio_var = (roll_var_stock - beta_60 ** 2 * roll_var_mkt).clip(lower=0.0)
    d["f_idio_vol"] = -np.sqrt(idio_var)

    # (p) Betting-against-beta (Frazzini & Pedersen 2014)：沿用上面 f_idio_vol
    # 已經算好的 60 日滾動 beta（beta_60），取負號（低 beta 分數較高）。文獻上的解釋是
    # 槓桿受限的投資人無法直接借錢放大低 beta 股票的報酬，只能改買高 beta 股票追求同樣的
    # 期望報酬，導致高 beta 股票被系統性追捧、風險調整後報酬反而較差。純價格資料，天然
    # point-in-time，2026-08-26 馬拉松新增（MARATHON_PROTOCOL.md 第 3 節「低風險」家族
    # 第三個測試，f_low_vol/f_idio_vol 是前兩個）。零額外計算成本、零額外資料（重用同一個
    # beta_60）。
    d["f_bab"] = -beta_60

    # (u) 殘差動量 Residual Momentum (Blitz/Huij/Martens 2011,
    # `HYPOTHESIS_QUEUE.md` #9，2026-09-02自動排程新增，佇列排隊第一起跑)。
    # 經濟理由：目前已死的三條假設（Weinstein第二階段/CTA趨勢跟隨/PEAD策略層）
    # 共同死因是「表面報酬漂亮但拆解後是beta曝險、alpha不顯著」，傳統動量訊號
    # 本身常隱含大量市場beta。這裡先用CAPM單因子迴歸剝離beta，只對「剝離後的
    # 殘差報酬」做動量排序，文獻上發現這樣波動更低、動量崩盤現象更輕微。
    # 實作：用trailing 252個交易日（~12個月）窗口估計滾動beta（跟f_bab/
    # f_idio_vol同一套cov/var算法，只是窗口從60天換成252天，不是新機制），
    # 再用「12個月股票報酬 - beta*12個月大盤報酬」近似12個月累積殘差報酬
    # （這是簡化的一階近似，跟f_rel_strength用「股票報酬-大盤報酬」隱含
    # beta=1的簡化方式同一種近似程度，不是逐日複利精確重算，方法論上一致，
    # 不是這條因子獨有的簡化）。跟已死的`f_rel_strength_regime_switch`/
    # Weinstein第二階段/`cta_momentum_12m`不同之處：那些都是原始價格/相對
    # 強度動量，沒有先剝離beta；這是本項目第一次測試「剝離beta後的動量」。
    # 純價格資料，天然point-in-time，零額外API呼叫（重用daily_ret/mkt_ret）。
    ret_252 = d["adj_close"] / d["adj_close"].shift(RESIDUAL_MOMENTUM_WINDOW) - 1
    mkt_ret_252 = d["mkt_close"] / d["mkt_close"].shift(RESIDUAL_MOMENTUM_WINDOW) - 1
    roll_var_mkt_252 = mkt_ret.rolling(RESIDUAL_MOMENTUM_WINDOW, min_periods=RESIDUAL_MOMENTUM_WINDOW).var()
    roll_cov_252 = daily_ret.rolling(RESIDUAL_MOMENTUM_WINDOW, min_periods=RESIDUAL_MOMENTUM_WINDOW).cov(mkt_ret)
    beta_252 = roll_cov_252 / roll_var_mkt_252
    d["f_residual_momentum"] = ret_252 - beta_252 * mkt_ret_252

    # (v) 52週高點接近度 52-Week High Proximity (George & Hwang 2004,
    # `HYPOTHESIS_QUEUE.md` #17，2026-09-02自動排程新增，佇列排隊第一起跑)。
    # 經濟理由：股價接近52週高點時，投資人對「創新高」這個顯著錨點反應不足
    # （anchoring/underreaction），文獻上發現這個訊號比傳統動量更強、更不容易
    # 被動量因子解釋掉。跟f_rel_strength（60日相對大盤報酬）本質不同：這裡量
    # 的是「價格水位相對歷史極值的位置」，不是報酬率本身，同一檔股票兩者可能
    # 給出不同排序（例如近期報酬普通但前期大漲、現在仍貼近52週高點的股票）。
    # 實作：當前收盤價 / 過去252個交易日(含當日)最高價，比率越接近1代表越
    # 接近52週高點。純價格資料，天然point-in-time，零額外API呼叫。
    d["f_52w_high_prox"] = d["adj_close"] / d["adj_close"].rolling(
        HIGH_52W_WINDOW, min_periods=HIGH_52W_WINDOW
    ).max()

    # (w) 短期反轉（1週）Short-Term Reversal (Jegadeesh 1990, `HYPOTHESIS_QUEUE.md`
    # #18，2026-09-02自動排程新增，佇列排隊第一起跑)。經濟理由：流動性提供者
    # 承接短期價格壓力後要求的溢酬——短期內被過度賣壓的股票，很快被流動性
    # 提供者買入承接、推回真實價值附近，產生反轉；是流動性機制，跟本佇列已測
    # 過的所有假設（動量/財報意外/籌碼/beta類）經濟機制不同類別。**跟已FAIL
    # 的`f_short_reversal_1m`（21交易日/~1個月窗口，`TRIALS_LEDGER.md`#46）
    # 刻意用不同窗口**——那筆FAIL紀錄本身明寫「若改用更短窗口（1週）可再測」，
    # 這是遵照那個建議、真正測試更短窗口，不是同一個已死機制換皮。純價格
    # 資料，天然point-in-time，零額外API呼叫（重用daily adj_close序列）。
    d["f_short_term_reversal_1w"] = -(
        d["adj_close"] / d["adj_close"].shift(SHORT_TERM_REVERSAL_1W_WINDOW) - 1
    )

    # (j) 品質 ROE穩定度 -- point-in-time via pit_date（合併季報+資產負債表兩個 PIT 序列）。
    # 用 TaiwanStockBalanceSheet，這是這批新因子裡第一次用到的資料集，捕捉例外而不是讓
    # 整檔股票的其他 11 個因子也一起報廢（2026-08-22 遇到 FinMind 流量限制時發現這個問題）。
    try:
        roe_pit = _roe_stability(stock_id, start_date)
        d = _asof_join(d, roe_pit, "roe_stability", "f_quality_roe_stability")
    except RuntimeError as e:
        print(f"    [factors] f_quality_roe_stability skipped for {stock_id}: {e}")
        d["f_quality_roe_stability"] = np.nan

    # (q) 資產成長異常 -- point-in-time via pit_date（沿用 balance_sheet_pit，同
    # `f_quality_roe_stability` 的快取鍵，零額外 API 呼叫）。
    try:
        ag_pit = _asset_growth(stock_id, start_date)
        d = _asof_join(d, ag_pit, "asset_growth", "f_asset_growth")
    except RuntimeError as e:
        print(f"    [factors] f_asset_growth skipped for {stock_id}: {e}")
        d["f_asset_growth"] = np.nan

    # (r) 盈餘品質應計項目 (accruals, Sloan 1996 balance-sheet approach) -- 沿用
    # balance_sheet_pit 同一個快取鍵，零額外 API 呼叫。
    try:
        acc_pit = _accruals(stock_id, start_date)
        d = _asof_join(d, acc_pit, "accruals", "f_accruals")
    except RuntimeError as e:
        print(f"    [factors] f_accruals skipped for {stock_id}: {e}")
        d["f_accruals"] = np.nan

    # (s) 毛利率穩定度 (Novy-Marx 精神的品質異常變體) -- 沿用 quarterly_pit 同一個
    # 快取鍵（跟 f_quality_roe_stability/f_asset_growth/f_accruals 完全同源），
    # 零額外 FinMind 呼叫。
    try:
        gm_pit = _gross_margin_stability(stock_id, start_date)
        d = _asof_join(d, gm_pit, "gross_margin_stability", "f_gross_margin_stability")
    except RuntimeError as e:
        print(f"    [factors] f_gross_margin_stability skipped for {stock_id}: {e}")
        d["f_gross_margin_stability"] = np.nan

    # (x) 純毛利率因子 Gross Profitability (Novy-Marx 2013) -- 沿用
    # quarterly_pit/balance_sheet_pit 同一個快取鍵（跟 f_gross_margin_stability/
    # f_quality_roe_stability/f_asset_growth/f_accruals 完全同源），零額外
    # FinMind 呼叫。`HYPOTHESIS_QUEUE.md` #20，2026-09-03自動排程新增。
    try:
        gp_pit = _gross_profitability(stock_id, start_date)
        d = _asof_join(d, gp_pit, "gross_profitability", "f_gross_profitability")
    except RuntimeError as e:
        print(f"    [factors] f_gross_profitability skipped for {stock_id}: {e}")
        d["f_gross_profitability"] = np.nan

    # (k)/(l) 價值 PB/PE -- 直接讀 FinMind 算好的 PER/PBR。
    # **PIT 狀態（2026-08-23 馬拉松第四輪更新）**：2330 單檔跳變偵測（`verify_pit_value_pb.py`，
    # 40/42 季度）顯示 implied_bvps 跳變日距季末天數 min=32/median=45/max=62，從未貼近 0 天，
    # 無明顯前瞻偏誤；已從「完全未驗證」升級為「單檔抽測無嚴重前瞻偏誤」（不是完全驗證，只測
    # 1 檔+間接偵測法，見 `TRIALS_LEDGER.md`「已調查但不計入試驗數」表、`TW_LOG.md`）。f_value_pe
    # 沿用同一資料源，結論延伸適用但未單獨驗證。同樣捕捉例外。
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

    # (t) 股票股利率 carry（`HYPOTHESIS_QUEUE.md` #4，2026-09-01自動排程新增）
    # -- trailing 12個月現金股利(_dividend_yield_ttm_cash)除以當日收盤價，
    # 高殖利率排名靠前，不取負號（跟f_value_pb/pe取負號慣例相反，因為這裡
    # 分數定義本身就是「越高越好」，不是像PBR/PER那樣「越低越好」再取負）。
    try:
        div_pit = _dividend_yield_ttm_cash(stock_id, start_date)
        d = _asof_join(d, div_pit, "ttm_cash_dividend", "_ttm_cash_dividend_raw")
        d["f_dividend_yield_ttm"] = np.where(
            d["close"] > 0, d["_ttm_cash_dividend_raw"] / d["close"], np.nan
        )
        d = d.drop(columns=["_ttm_cash_dividend_raw"])
    except RuntimeError as e:
        print(f"    [factors] f_dividend_yield_ttm skipped for {stock_id}: {e}")
        d["f_dividend_yield_ttm"] = np.nan

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
