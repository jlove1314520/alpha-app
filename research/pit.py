"""Point-in-time (PIT) availability dates for TW financial data.

FinMind's free tier does not carry a real disclosure-date field for
TaiwanStockFinancialStatements (see DATA.md milestone-1 audit) -- only the
fiscal period end date. Using the period-end date as if it were "known that
day" is a severe lookahead bias: TW quarterly reports are disclosed roughly
45+ days after the period ends, by regulation.

Per the user's 2026-08-22 decision, until real disclosure dates are
available:
  - Quarterly financial statements: assume available at period_end + 45 days.
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
"""
from __future__ import annotations

import pandas as pd

from finmind_client import fetch

QUARTERLY_DISCLOSURE_LAG_DAYS = 45
MONTH_REVENUE_DISCLOSURE_DAY = 10  # TW rule: month revenue must be disclosed by the 10th of next month


def _next_month_10th(year: int, month: int) -> str:
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{y:04d}-{m:02d}-{MONTH_REVENUE_DISCLOSURE_DAY:02d}"


def quarterly_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockFinancialStatements pivoted to one row per quarter, with a
    `pit_date` column: the earliest date this quarter's numbers may be used
    without lookahead bias. `pit_source` is always 'assumed' for this
    dataset -- FinMind has no real disclosure date to fall back to yet.
    """
    raw = fetch("TaiwanStockFinancialStatements", stock_id, start_date)
    if raw.empty:
        return pd.DataFrame()
    wide = raw.pivot_table(index="date", columns="type", values="value", aggfunc="first").reset_index()
    wide = wide.rename(columns={"date": "fiscal_period_end"})
    wide["pit_date"] = (
        pd.to_datetime(wide["fiscal_period_end"]) + pd.Timedelta(days=QUARTERLY_DISCLOSURE_LAG_DAYS)
    ).dt.strftime("%Y-%m-%d")
    wide["pit_source"] = "assumed"
    return wide


def month_revenue_pit(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """TaiwanStockMonthRevenue with `pit_date`/`pit_source` columns: use the
    real `create_time` when FinMind populated it, else assume the 10th of
    the month after the revenue month (the TW disclosure-deadline rule).
    """
    raw = fetch("TaiwanStockMonthRevenue", stock_id, start_date)
    if raw.empty:
        return raw
    out = raw.copy()
    has_real = out["create_time"].astype(str).str.len() > 0
    assumed = out.apply(lambda r: _next_month_10th(int(r["revenue_year"]), int(r["revenue_month"])), axis=1)
    out["pit_date"] = out["create_time"].where(has_real, assumed)
    out["pit_source"] = has_real.map({True: "real", False: "assumed"})
    return out


def any_assumed(df: pd.DataFrame) -> bool:
    """True if any row relies on an assumed (not real) disclosure date.
    A backtest that touches any assumed-PIT data must be reported as
    experimental -- see CONSTITUTION.md / STRATEGY_LOG.md 2026-08-22.
    """
    return "pit_source" in df.columns and bool((df["pit_source"] == "assumed").any())
