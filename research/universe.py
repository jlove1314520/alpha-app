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

import re

import pandas as pd

from finmind_client import _fetch

UNIVERSE_CUTOFF = "2003-01-01"

# ── 宇.二（2026-09-24總司令裁示【開考前修正——宇宙限普通股＋MDD判準回復原
# 裁示】「修訂一」）：universe()／active_stock_ids() 只用代號長度篩選
# （見上面 active_stock_ids()），完全沒有排除 ETF／債券型 ETF／特別股／TDR
# ——宇.一實測 300 檔抽樣裡有 49 檔非普通股，f52w VAL 期持股天數裡有
# 16.68% 落在債券型 ETF。這裡補上分類規則，供 2007-2014 單發檢定的候選
# 宇宙限定為普通股（common_stock_only()）。**分類規則跟
# `audit_universe_composition_val.py::classify_holding()`（宇.一，已完成的
# 量測用途）是同一套規則，這裡是它的權威/可重用版本**——之後兩邊若要再
# 改分類規則，只改這裡，`audit_universe_composition_val.py` 改成 import 這裡
# 的函式，不維護第二份重複邏輯。
_BOND_ETF_NAME_KEYWORDS = ("債",)
_PREFERRED_NAME_SUFFIX_RE = re.compile(r"特$")
_TDR_NAME_SUFFIX_RE = re.compile(r"-DR$", re.IGNORECASE)
_REIT_KEYWORDS = ("受益證券", "不動產投資信託", "REIT")
_ETF_CODE_PREFIX_RE = re.compile(r"^00\d")  # 台股ETF代號慣例：00開頭


def classify_security(stock_id: str, stock_name: str | None, industry_category: str | None) -> str:
    """回傳分類標籤之一：普通股／股票型ETF／債券型ETF／特別股／TDR／其他／無法分類。

    主規則（`industry_category` 有值時，權威依據）：
      - 含「ETF」字樣 -> 股票型/債券型ETF（用股票名稱是否含「債」字弱代理
        區分——FinMind 沒有把兩者拆成不同 industry_category，如實承認這是
        弱代理規則，不是精確分類）。
      - =="存託憑證" 或名稱以 "-DR" 結尾 -> TDR。
      - 含「受益證券」/「不動產投資信託」/"REIT" -> 其他。
      - 名稱以「特」字結尾（台股特別股命名慣例：原公司簡稱＋甲/乙/丙/…
        ＋特，例如「台新戊特」「中信金乙特」）-> 特別股。
      - 其餘 -> 普通股。

    退回規則（`industry_category` 缺值時——常見於很早下市、已從
    TaiwanStockInfo 現況快照掉出去的股票，例如 2003~2012 年間下市的樣本，
    這批只有 `delisted_stock_ids()` 給得出的 stock_name，沒有產業分類）：
      - 代號以「00」開頭 -> ETF（同樣用名稱是否含「債」字區分）。
      - 名稱以 "-DR" 結尾 -> TDR。
      - 名稱以「特」字結尾 -> 特別股。
      - 代號是純數字且不是「00」開頭、名稱不含上述任何特徵 -> 普通股
        （台股傳統4碼數字代號是普通股的強訊號，早期下市股票尤其如此
        ——ETF/特別股/TDR這幾類金融商品在台股的普及時間點本身就晚於這批
        早期下市公司的存續期間）。
      - 其餘（代號格式本身就異常）-> 無法分類，不得靜默歸類成普通股。
    """
    name = stock_name or ""
    cat = industry_category if isinstance(industry_category, str) else None

    if cat is not None:
        if "ETF" in cat:
            return "債券型ETF" if any(k in name for k in _BOND_ETF_NAME_KEYWORDS) else "股票型ETF"
        if cat == "存託憑證" or _TDR_NAME_SUFFIX_RE.search(name):
            return "TDR"
        if any(k in cat for k in _REIT_KEYWORDS) or "REIT" in name.upper():
            return "其他"
        if _PREFERRED_NAME_SUFFIX_RE.search(name):
            return "特別股"
        return "普通股"

    # ── 退回規則（industry_category缺值）──
    if _ETF_CODE_PREFIX_RE.match(stock_id):
        return "債券型ETF" if any(k in name for k in _BOND_ETF_NAME_KEYWORDS) else "股票型ETF"
    if _TDR_NAME_SUFFIX_RE.search(name):
        return "TDR"
    if _PREFERRED_NAME_SUFFIX_RE.search(name):
        return "特別股"
    if stock_id.isdigit() and not stock_id.startswith("00"):
        return "普通股"
    return "無法分類"


def common_stock_only(df: pd.DataFrame) -> pd.DataFrame:
    """過濾掉 ETF／ETN／債券型ETF／特別股／TDR，只留普通股。`df` 必須含
    `stock_id`／`stock_name`／`industry_category` 三欄（`universe()` 與
    `active_stock_ids()` 回傳的 DataFrame 都符合）。`無法分類` 的列**不會**
    被當成普通股保留——會被排除，並印一行警告（含代號清單），因為「排除
    了不確定的東西」比「靜默混入非普通股」安全，跟本函式存在的理由一致。
    """
    category = df.apply(lambda r: classify_security(r["stock_id"], r.get("stock_name"), r.get("industry_category")), axis=1)
    unclassified = sorted(df.loc[category == "無法分類", "stock_id"].tolist())
    if unclassified:
        print(f"[common_stock_only] 警告：{len(unclassified)}檔無法分類，已排除（非普通股，"
              f"但也不確定是哪一類，寧可排除不確定的東西）：{unclassified}")
    return df.loc[category == "普通股"].reset_index(drop=True)


def _self_test_common_stock_only() -> None:
    """0050/00878/00718B/2887I/2891B/9105 必須被排除；2330/2317 必須保留。"""
    rows = [
        {"stock_id": "0050", "stock_name": "元大台灣50", "industry_category": "ETF"},
        {"stock_id": "00878", "stock_name": "國泰永續高股息", "industry_category": "ETF"},
        {"stock_id": "00718B", "stock_name": "富邦中國政策債", "industry_category": "上櫃ETF"},
        {"stock_id": "2887I", "stock_name": "台新新光辛特", "industry_category": "金融保險"},
        {"stock_id": "2891B", "stock_name": "中信金乙特", "industry_category": "金融保險"},
        {"stock_id": "9105", "stock_name": "泰金寶-DR", "industry_category": "存託憑證"},
        {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"},
        {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "其他電子業"},
    ]
    df = pd.DataFrame(rows)
    kept = set(common_stock_only(df)["stock_id"])
    expected_kept = {"2330", "2317"}
    assert kept == expected_kept, f"common_stock_only()自我測試失敗：預期保留{expected_kept}，實際保留{kept}"
    print(f"[self-test] common_stock_only() 通過：{len(rows)}檔樣本中只保留{sorted(kept)}")


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


if __name__ == "__main__":
    _self_test_common_stock_only()
