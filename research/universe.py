"""Survivorship-bias-mitigated TW equity universe construction.

FinMind's free tier only reliably has price history for stocks delisted from
roughly 2003 onward (see DATA.md milestone-1 audit: a stock delisted in 2001
had zero TaiwanStockPrice rows; one delisted in 2006 had full coverage up to
its last trading day. The exact boundary between 2001 and 2006 was not
pinned down further -- see DATA.md for that residual gap).

Per the user's 2026-08-22 decision: the TW backtest universe is restricted
to UNIVERSE_CUTOFF onward, and within that window we DO include delisted
names (not just survivors), pulled from TaiwanStockDelisting. Anything
before the cutoff is out of scope -- using this universe for an earlier
period would silently reintroduce survivorship bias.

This module does NOT try to determine "was stock X actually tradeable on
date D" via a listing-date field (FinMind's TaiwanStockInfo doesn't reliably
carry one). Instead, callers should treat the presence of a price row in
TaiwanStockPrice for stock X on date D as ground truth for "tradeable that
day": a newly-IPO'd stock naturally has no earlier rows, a delisted stock
naturally has none after its last trading day. This module's only job is to
hand back the correct *set of stock_ids* to even look at for a given period.

**Why this uses _fetch() directly instead of load_dev() (2026-08-22):**
TaiwanStockDelisting and TaiwanStockInfo are membership/reference lists, not
the price/volume time series load_dev() is built to cap -- their `date`
column is a record/snapshot stamp (e.g. TaiwanStockInfo's rows are stamped
with roughly today's date), not a trading date whose future values would
leak analysis results. Routing them through load_dev() would in fact break
this module outright: capping TaiwanStockInfo at VAL_END would filter out
literally every row (they're all stamped near-today) and return an empty
universe. This is a deliberate, documented exemption, not an oversight --
see finmind_client.load_dev()'s own docstring for the same warning.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import _fetch

UNIVERSE_CUTOFF = "2003-01-01"


def delisted_stock_ids(cutoff: str = UNIVERSE_CUTOFF) -> pd.DataFrame:
    """Stocks delisted on/after `cutoff`. Columns: stock_id, stock_name, delist_date."""
    d = _fetch("TaiwanStockDelisting", "", "1990-01-01")
    d = d.rename(columns={"date": "delist_date"})
    return d[d["delist_date"] >= cutoff][["stock_id", "stock_name", "delist_date"]].reset_index(drop=True)


def active_stock_ids() -> pd.DataFrame:
    """Currently-listed names from TaiwanStockInfo, filtered the same way the phone
    App's search does (drop warrants etc. via the id-length heuristic)."""
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    info = info[info["stock_id"].str.len().between(4, 6)]
    is_warrant = info["stock_id"].str.len().eq(6) & info["stock_id"].str.match(r"^\d+$")
    info = info[~is_warrant]
    return info[["stock_id", "stock_name", "industry_category"]].reset_index(drop=True)


def universe(cutoff: str = UNIVERSE_CUTOFF) -> pd.DataFrame:
    """Combined survivorship-bias-mitigated universe.

    Returns columns: stock_id, stock_name, industry_category, status
    ('active'|'delisted'), delist_date (NaT if active).

    This is NOT a claim that the universe is bias-free -- see DATA.md for
    the documented residual gaps (pre-cutoff period excluded entirely;
    membership within the window is approximated, not verified against a
    true continuous listing-status record).
    """
    active = active_stock_ids().assign(status="active", delist_date=pd.NaT)
    delisted = delisted_stock_ids(cutoff).assign(status="delisted", industry_category=None)
    cols = ["stock_id", "stock_name", "industry_category", "status", "delist_date"]

    # 2026-09-18（Cowork【最優先·上游】查證發現，取代原本「重疊時保留active」
    # 的防呆邏輯，那個邏輯本身就是bug）：TaiwanStockInfo（active_stock_ids()
    # 的來源）對已經下市的公司常常仍留著舊資料列，不是可靠的「目前真的還在
    # 上市」訊號——實測`delisted_stock_ids()`回傳452檔（cutoff=2003-01-01），
    # 但舊版combined邏輯偏好active，導致其中230檔（51%！）被錯誤歸類成
    # active，只剩222檔留在delisted。逐檔核對這230檔，stock_id與公司名稱
    # （含全名/簡稱這種文字差異，例如「萬洲化學」vs「萬洲」，共26筆屬於
    # 這種文字差異，其餘204筆名稱完全相同）全部對得起來，不是代碼被重新
    # 分配給新公司的合法情境，是TaiwanStockInfo資料過期的殘留列。
    # `TaiwanStockDelisting`是有日期戳記的下市事件登記，`TaiwanStockInfo`
    # 是「目前」快照且無從驗證是否過期——事件登記的證據力應該蓋過快照，
    # 所以改成delisted優先（concat時delisted排在active前面，drop_duplicates
    # keep="first"留delisted那筆），不是「重疊時保留active」。
    combined = pd.concat([delisted[cols], active[cols]], ignore_index=True)
    combined = combined.drop_duplicates(subset="stock_id", keep="first")
    # 上面delisted優先的判斷會讓這230檔的industry_category變成None（delisted
    # 資料源本身沒有這個欄位），但active_stock_ids()其實留著這些股票下市前
    # 最後一次快照的真實產業分類——status判斷交給delisted優先（正確），
    # industry_category這種不影響存活者偏誤判斷的次要欄位就從active補回來，
    # 不浪費本來就是對的資訊。
    industry_lookup = active.set_index("stock_id")["industry_category"]
    missing = combined["industry_category"].isna() & combined["stock_id"].isin(industry_lookup.index)
    combined.loc[missing, "industry_category"] = combined.loc[missing, "stock_id"].map(industry_lookup)
    return combined.reset_index(drop=True)
