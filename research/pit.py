"""Point-in-time (PIT) availability dates for TW financial data.

FinMind's free tier does not carry a real disclosure-date field for
TaiwanStockFinancialStatements (see DATA.md milestone-1 audit) -- only the
fiscal period end date. Using the period-end date as if it were "known that
day" is a severe lookahead bias: TW quarterly reports are disclosed roughly
45+ days after the period ends, by regulation.

Per the user's 2026-08-22 decision, until real disclosure dates are
available:
  - Quarterly financial statements: assume available at the statutory filing
    deadline (see `statutory_quarterly_pit_date()`) -- Q1-Q3 at period_end +
    45 days, Q4 (annual report) at next-year 3/31 per 證交法§36. **2026-09-20
    correction**: this module previously used period_end + 45 days for every
    quarter including Q4, which puts the annual report at 2/14 -- about six
    weeks *before* the real statutory deadline of 3/31, a genuine lookahead
    bias (found while investigating 原子.四's PIT alignment; three of the
    project's four PASS factors -- eps_growth/eps_surprise/revenue_surprise
    -- are built on `quarterly_pit()` and therefore inherited this bias on
    every Q4 observation until this fix).
  - Month revenue: prefer the real `create_time` field when FinMind actually
    populated it (observed roughly 2026-04 onward -- see DATA.md); fall back
    to the regulatory rule (must be disclosed by the 10th of the following
    month) otherwise.

Every value handed back here is tagged with how its pit_date was derived
(`'real'` vs `'assumed'`), and any_assumed() checks whether a DataFrame is
contaminated with any assumed dates. CONSTITUTION.md / the user's 2026-08-22
instruction requires: any backtest result that touches assumed-PIT data must
be reported as experimental, not a clean/trustworthy result, until real
disclosure dates replace the assumption. Pure price-based strategies
(Weinstein stage 2, momentum, ...) never call this module and are not
subject to this restriction.

Both fetches below go through finmind_client.load_dev(), so everything this
module returns is also capped at VAL_END by construction (see adjust.py's
module docstring for the same note, in more detail).
"""
from __future__ import annotations

import pandas as pd

from finmind_client import load_dev

QUARTERLY_DISCLOSURE_LAG_DAYS = 45
MONTH_REVENUE_DISCLOSURE_DAY = 10  # TW rule: month revenue must be disclosed by the 10th of next month


def _next_month_10th(year: int, month: int) -> str:
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{y:04d}-{m:02d}-{MONTH_REVENUE_DISCLOSURE_DAY:02d}"


def statutory_quarterly_pit_date(period_end) -> pd.Timestamp:
    """期別日 -> 保守可得日（法定申報期限），取代舊版「一律期末+45日」的
    近似值（2026-09-20總司令裁示【Q4前視與#23無法重現】一發現並要求修正：
    證交法§36規定年報3個月內、季報45日內申報，但舊版對Q4也套用45天，
    把年報可得日算成2/14（期末12/31+45天），比法定期限3/31**提早約6週**，
    是真的前視偏誤，不是保守估計。

    本函式是`research/FIN_ATOM_LIBRARY.py::statutory_pit_date()`的原始
    出處——**這裡是新的canonical來源**，`FIN_ATOM_LIBRARY.py`改成從這裡
    import，不再各自維護一份，避免兩份拷貝日後不同步（跟本次裁示部四
    「規則寫在CLAUDE.md、提示詞檔是另一份拷貝，兩者會不同步」同一個
    教訓，只是這裡是程式碼版本，一樣要收斂成單一來源）。

    Q1~Q3維持期末+45日（本身沒有問題，法定期限就是45日內）；**Q4改用
    次年3/31**。2012年（含）以前的舊制期限較寬，統一取保守（較晚）日期：
    Q4→次年4/30、Q2→8/31，Q1/Q3不變——**這條舊制期限的限制未逐條查證
    原始法條，僅為保守估計**（較晚只會損失時效、不會製造前視，所以即使
    估計不精確也不會反過來製造新的lookahead bias）。
    """
    pe = pd.Timestamp(period_end)
    q = (pe.month - 1) // 3 + 1
    y = pe.year
    if q == 4:
        return pd.Timestamp(y + 1, 3, 31) if y >= 2013 else pd.Timestamp(y + 1, 4, 30)
    if q == 1:
        return pd.Timestamp(y, 5, 15)
    if q == 2:
        return pd.Timestamp(y, 8, 14) if y >= 2013 else pd.Timestamp(y, 8, 31)
    return pd.Timestamp(y, 11, 14)


def _pivot_with_statutory_pit(raw: pd.DataFrame) -> pd.DataFrame:
    """`quarterly_pit()`/`balance_sheet_pit()`/`cash_flow_pit()`共用的
    pivot＋PIT對齊邏輯，2026-09-20抽出來避免三處各自维护一份一样的程式碼
    （這正是本次事件教訓「同一段邏輯散落多處會漂移」的具體實踐，不是
    只寫成文件說說而已）。"""
    if raw.empty:
        return pd.DataFrame()
    wide = raw.pivot_table(index="date", columns="type", values="value", aggfunc="first").reset_index()
    wide = wide.rename(columns={"date": "fiscal_period_end"})
    wide["pit_date"] = pd.to_datetime(wide["fiscal_period_end"]).map(
        statutory_quarterly_pit_date
    ).dt.strftime("%Y-%m-%d")
    # 刻意維持"assumed"（不是"assumed_statutory"）：`any_assumed()`既有
    # 呼叫端逐字比對這個字串，改標籤會讓既有的「有沒有碰到assumed資料」
    # 檢查悄悄失效（回False但實際上還是assumed），這比日期算錯更危險——
    # 日期算法有沒有用法定期限是`pit_date`本身的精確度問題，跟「這筆
    # 資料是不是assumed來源」是兩件事，不需要靠改標籤來紀錄前者。
    wide["pit_source"] = "assumed"
    return wide


def quarterly_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockFinancialStatements pivoted to one row per quarter, with a
    `pit_date` column: the earliest date this quarter's numbers may be used
    without lookahead bias. `pit_source` is always 'assumed' for this
    dataset -- FinMind has no real disclosure date to fall back to yet, so
    `pit_date` is the statutory filing deadline (see
    `statutory_quarterly_pit_date()`), not an observed real disclosure date.
    """
    raw = load_dev("TaiwanStockFinancialStatements", stock_id, start_date)
    return _pivot_with_statutory_pit(raw)


def month_revenue_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockMonthRevenue with `pit_date`/`pit_source` columns: use the
    real `create_time` when FinMind populated it, else assume the 10th of
    the month after the revenue month (the TW disclosure-deadline rule).
    """
    raw = load_dev("TaiwanStockMonthRevenue", stock_id, start_date)
    if raw.empty:
        return raw
    out = raw.copy()
    has_real = out["create_time"].astype(str).str.len() > 0
    assumed = out.apply(lambda r: _next_month_10th(int(r["revenue_year"]), int(r["revenue_month"])), axis=1)
    out["pit_date"] = out["create_time"].where(has_real, assumed)
    out["pit_source"] = has_real.map({True: "real", False: "assumed"})
    return out


def balance_sheet_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockBalanceSheet pivoted to one row per quarter, with the same
    `pit_date`/`pit_source='assumed'` treatment as quarterly_pit() -- balance
    sheets are disclosed alongside the income statement in the same
    quarterly filing, so the same statutory-deadline PIT date applies (see
    `statutory_quarterly_pit_date()`). Added 2026-08-22 for factors.py's
    quality/value factors (ROE stability needs equity; PB needs it too if
    book value per share isn't available directly).
    """
    raw = load_dev("TaiwanStockBalanceSheet", stock_id, start_date)
    return _pivot_with_statutory_pit(raw)


def cash_flow_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockCashFlowsStatement pivoted to one row per quarter, with the
    same `pit_date`/`pit_source='assumed'` treatment as quarterly_pit()/
    balance_sheet_pit() (period end + 45 days) -- the cash flow statement is
    disclosed alongside the income statement and balance sheet in the same
    quarterly filing, so the same lag assumption applies.

    Added 2026-09-20 for `ATOM_LIBRARY.py`'s fundamental atom family
    (原子.四，營運現金流原子). **This function was referenced but never
    defined**: `piotroski_fscore_sanity.py` already imports
    `from pit import balance_sheet_pit, cash_flow_pit, quarterly_pit` and
    checks for `NetCashInflowFromOperatingActivities` /
    `CashFlowsFromOperatingActivities` columns on its result, but the
    function itself was missing from this module (confirmed: `factors.py`
    line ~389 says "本專案沒有現金流量表資料源...從未抓取過", which was
    the more accurate statement of the codebase's actual state until now).
    Verified live: `TaiwanStockCashFlowsStatement` **does** return real data
    via FinMind free tier (e.g. 2330 since 2018 has both column names
    present), so this was a documentation/implementation gap, not a real
    data-availability limitation. Adding this fixes both `piotroski_fscore_
    sanity.py`'s dangling import and gives the fundamental atom family a
    real 營運現金流 source.
    2026-09-20更正：PIT日期改用`statutory_quarterly_pit_date()`（法定
    申報期限），不是原本的「一律期末+45日」——Q4原本算成2/14，比法定
    期限3/31提早約6週，是真的前視偏誤（見`statutory_quarterly_pit_date()`
    docstring）。
    """
    raw = load_dev("TaiwanStockCashFlowsStatement", stock_id, start_date)
    return _pivot_with_statutory_pit(raw)


def any_assumed(df: pd.DataFrame) -> bool:
    """True if any row relies on an assumed (not real) disclosure date.
    A backtest that touches any assumed-PIT data must be reported as
    experimental -- see CONSTITUTION.md / STRATEGY_LOG.md 2026-08-22.
    """
    return "pit_source" in df.columns and bool((df["pit_source"] == "assumed").any())
