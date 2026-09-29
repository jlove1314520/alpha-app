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

import json
import re
from pathlib import Path

import pandas as pd

from finmind_client import _fetch

UNIVERSE_CUTOFF = "2003-01-01"

# ── 查.二（2026-09-27總司令裁示【新.二結案＋紙.一＋查.二放行】）：本模組
# 上面的docstring原本明寫「不試圖用上市日期欄位判斷可交易性，價格列存在
# 就是可交易的證據」——查.二的查證結果推翻了這個假設的一半：FinMind的
# TaiwanStockPrice確實會包含上市/上櫃「之前」的興櫃交易期間資料（興櫃
# 無漲跌幅限制、流動性極低，混入回測會製造假的大幅漲跌）。這不是撤回
# 整份docstring的邏輯（「下市後沒有資料」那一半仍然成立），是新增一層
# 「上市/上櫃前」的過濾，兩者互補、不衝突。
#
# ── 查.三（2026-09-27總司令裁示【查.三＋清.一（合併版）】，Cowork裁示）：
# 查.二完成後發現251檔common-stock抽樣裡有72檔查無官方上市/上櫃日
# （TWSE `t187ap03_L`／TPEx `mopsfin_t187ap03_O`都只涵蓋「現存」公司，
# 查不到不等於「這檔股票有問題」，多數是已經走完生命週期的正常案例）。
# 交叉核對`delisted_stock_ids()`後這72檔**完全被兩類原因解釋**：33檔
# （45.8%）是`TaiwanStockDelisting`登記在案的已下市公司；剩下39檔
# （54.2%）`TaiwanStockInfo.type`皆為`"emerging"`（興櫃），至今尚未正式
# 上市/上櫃。零筆「查不到原因」的殘留（33+39=72，完全對得上）。
#
# **裁示（取代原本「整批排除72檔」的暫定做法）**：預設宇宙**保留**這72檔
# ——只排除其中目前仍是興櫃的39檔（`common_stock_only()`的`security_
# type=="emerging"`判斷已經做這件事，不需要新程式碼），另外33檔已下市
# 公司**原樣保留、不截斷**（`truncate_to_listing_date()`對查無上市日的
# 代號本來就不截斷，同樣不需要新程式碼——這裡記錄的是「預設行為即裁示
# 要求的行為」，不是新增邏輯）。「嚴格宇宙」（整批排除72檔）**降級為
# 敏感度對照專用**，見下面`strict_universe_exclude_unknown_listing()`，
# 不再是任何判準使用的主宇宙。
#
# **理由（Cowork原話精神，量化證據見`research/data/q2_impact_398_399.json`
# 與`q2_ipo_pre_listing_contamination.json`）**：興櫃汙染實測對#398/#399
# 的影響只占持股天數<5%（4.85%/1.92%）、估算報酬貢獻<0.35%（+0.34%/
# -0.22%）——量級很小；但把72檔（其中45.8%是已下市公司）整批排除在
# 「嚴格宇宙」之外，等於系統性排除「活得不夠久」的公司樣本，直接命中
# `CLAUDE.md`七之三節台股偽影家族⑦「存活者偏誤（最貴的一個，優先懷疑）」
# ——用一個影響量級很小的污染去交換一個代價可能更大的偏誤，不划算。
_TWSE_LISTING_PATH = Path(__file__).parent / "data" / "twse_listing_dates.json"
_OTC_LISTING_PATH = Path(__file__).parent / "data" / "otc_listing_dates.json"
_OTC_TO_TWSE_PATH = Path(__file__).parent / "data" / "otc_to_twse_dates.json"


def listing_date_lookup() -> dict[str, str]:
    """公司代號 -> 'YYYY-MM-DD' 上市/上櫃日期，合併TWSE(`t187ap03_L`)與
    TPEx(`mopsfin_t187ap03_O`)兩個官方端點的既有快取。**只涵蓋目前仍在
    市的上市/上櫃公司**——已下市公司或興櫃公司不在這裡面，呼叫端對查不到
    的代號一律視為「上市日不明」，不得猜測（見`build_twse_listing_dates.py`
    /`build_otc_listing_dates.py`各自的docstring範圍界定）。

    評.B-2（2026-09-29）：同一代號兩邊都有日期時取**較早者**（原本是後讀的
    OTC覆蓋TWSE）。另外，櫃轉市股票的TWSE「上市日期」其實是轉上市日，會把
    先前的上櫃期間整段誤砍——`otc_to_twse_dates.json`（官方「櫃轉市」旗標＋
    價格快取估計，見`build_otc_to_twse_dates.py`）有估計上櫃起算日者取較早者，
    沒有估計（null：無價格快取或轉上市日前無價格列）者維持官方日期不變——
    新抓價格快取後要重跑該腳本，估計才會涵蓋到。"""
    out: dict[str, str] = {}
    for path in (_TWSE_LISTING_PATH, _OTC_LISTING_PATH):
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for sid, ymd in doc.get("listing_dates", {}).items():
            d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
            out[sid] = min(out[sid], d) if sid in out else d
    if _OTC_TO_TWSE_PATH.exists():
        try:
            transfers = json.loads(_OTC_TO_TWSE_PATH.read_text(encoding="utf-8")).get("transfers", {})
        except Exception as e:  # noqa: BLE001 -- fail open：估計表壞掉時退回官方日期
            print(f"::warning::櫃轉市估計表讀取失敗，退回官方上市日：{type(e).__name__}: {e}")
            transfers = {}
        for sid, info in transfers.items():
            if sid not in out:
                continue
            est = info.get("otc_start_est")
            if est:
                out[sid] = min(out[sid], est)
    return out


def truncate_to_listing_date(df: pd.DataFrame, stock_id: str, listing_dates: dict[str, str] | None = None) -> pd.DataFrame:
    """把`df`（必須含`date`欄，字串或可比較的日期型別）截斷到只保留
    `date >= 上市/上櫃日`的列。查不到上市日的代號（已下市/興櫃/資料源本身
    缺這檔）**原樣不截斷**——這不是「假設沒問題」，是這個函式的職責邊界：
    「查不到就不截斷」讓呼叫端自己決定要不要把這種代號整檔排除（例如查.二
    要求的「從嚴格宇宙中排除並列出清單」是在更上層的宇宙篩選步驟做，不是
    在這裡默默處理，兩個步驟分開才看得出各自漏了多少）。"""
    if listing_dates is None:
        listing_dates = listing_date_lookup()
    ld = listing_dates.get(stock_id)
    if ld is None or df.empty:
        return df
    return df[df["date"].astype(str) >= ld].reset_index(drop=True)


def strict_universe_exclude_unknown_listing(stock_ids: list[str], listing_dates: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """查.三（2026-09-27裁示，Cowork）：把「整批排除查無上市/上櫃日的
    代號」明確做成一個獨立、**只給敏感度對照用**的函式，不是預設宇宙。

    回傳`(kept, excluded)`：`excluded`是`stock_ids`裡查不到上市/上櫃日的
    代號（不論是已下市還是仍興櫃，這個函式不區分——它本來就代表「更保守
    但可能引入更貴存活者偏誤」的那個對照組，不是正確答案）。**預設宇宙
    請直接用`common_stock_only()`（已排除興櫃）+`truncate_to_listing_
    date()`（已知上市日者截斷，查無者保留），不要呼叫這個函式當主宇宙**
    ——見本模組查.三段落docstring的完整理由（興櫃污染量級小，整批排除的
    存活者偏誤代價更大）。"""
    if listing_dates is None:
        listing_dates = listing_date_lookup()
    kept = [s for s in stock_ids if s in listing_dates]
    excluded = [s for s in stock_ids if s not in listing_dates]
    return kept, excluded

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


def classify_security(stock_id: str, stock_name: str | None, industry_category: str | None,
                       security_type: str | None = None) -> str:
    """回傳分類標籤之一：普通股／股票型ETF／債券型ETF／特別股／TDR／興櫃／
    其他／無法分類。

    **`security_type`（2026-09-27查.二新增，可選參數，預設None＝完全比照
    舊行為）**：傳入`TaiwanStockInfo.type`欄位值（"twse"/"tpex"/"emerging"）
    時，`"emerging"`（興櫃）一律回傳「興櫃」，優先於下面所有其他規則——
    興櫃股無漲跌幅限制、流動性極低，且會在真正上市/上櫃前混入回測（查.二
    查證發現的資料汙染），不論名稱/產業分類是什麼都要排除，不是跟ETF/
    特別股同一層級的分類問題。舊呼叫端沒有傳這個參數時，行為與2026-09-27
    之前完全一致（不會因為新增這個參數就意外改變既有呼叫的分類結果）。

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
    if security_type == "emerging":
        return "興櫃"

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
    """過濾掉 ETF／ETN／債券型ETF／特別股／TDR／興櫃，只留普通股。`df` 必須含
    `stock_id`／`stock_name`／`industry_category` 三欄（`universe()` 與
    `active_stock_ids()` 回傳的 DataFrame 都符合）。`無法分類` 的列**不會**
    被當成普通股保留——會被排除，並印一行警告（含代號清單），因為「排除
    了不確定的東西」比「靜默混入非普通股」安全，跟本函式存在的理由一致。

    **2026-09-27查.二新增**：若`df`含`type`欄（`TaiwanStockInfo.type`，
    "twse"/"tpex"/"emerging"），興櫃(`emerging`)股會被排除——舊呼叫端的
    `df`若沒有這欄（`.get("type")`回`None`），行為完全不變，不受影響。
    """
    category = df.apply(lambda r: classify_security(r["stock_id"], r.get("stock_name"),
                                                     r.get("industry_category"), r.get("type")), axis=1)
    unclassified = sorted(df.loc[category == "無法分類", "stock_id"].tolist())
    if unclassified:
        print(f"[common_stock_only] 警告：{len(unclassified)}檔無法分類，已排除（非普通股，"
              f"但也不確定是哪一類，寧可排除不確定的東西）：{unclassified}")
    n_emerging = int((category == "興櫃").sum())
    if n_emerging:
        print(f"[common_stock_only] 排除{n_emerging}檔興櫃股（查.二2026-09-27新增規則）")
    return df.loc[category == "普通股"].reset_index(drop=True)


def _self_test_common_stock_only() -> None:
    """0050/00878/00718B/2887I/2891B/9105/6559(興櫃) 必須被排除；2330/2317 必須保留。"""
    rows = [
        {"stock_id": "0050", "stock_name": "元大台灣50", "industry_category": "ETF"},
        {"stock_id": "00878", "stock_name": "國泰永續高股息", "industry_category": "ETF"},
        {"stock_id": "00718B", "stock_name": "富邦中國政策債", "industry_category": "上櫃ETF"},
        {"stock_id": "2887I", "stock_name": "台新新光辛特", "industry_category": "金融保險"},
        {"stock_id": "2891B", "stock_name": "中信金乙特", "industry_category": "金融保險"},
        {"stock_id": "9105", "stock_name": "泰金寶-DR", "industry_category": "存託憑證"},
        {"stock_id": "6559", "stock_name": "興櫃樣本股", "industry_category": "半導體業", "type": "emerging"},
        {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"},
        {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "其他電子業", "type": "twse"},
    ]
    df = pd.DataFrame(rows)
    kept = set(common_stock_only(df)["stock_id"])
    expected_kept = {"2330", "2317"}
    assert kept == expected_kept, f"common_stock_only()自我測試失敗：預期保留{expected_kept}，實際保留{kept}"
    print(f"[self-test] common_stock_only() 通過：{len(rows)}檔樣本中只保留{sorted(kept)}")


def _self_test_listing_date_truncation() -> None:
    """truncate_to_listing_date()：上市日已知的代號正確截斷；查不到上市日
    的代號原樣不動（不得猜測）。"""
    lookup = {"2330": "1994-09-05"}
    df = pd.DataFrame({"date": ["1994-06-01", "1994-09-05", "1994-12-01"], "close": [1.0, 2.0, 3.0]})
    truncated = truncate_to_listing_date(df, "2330", lookup)
    assert list(truncated["date"]) == ["1994-09-05", "1994-12-01"], \
        f"truncate_to_listing_date()自我測試失敗：{list(truncated['date'])}"
    unchanged = truncate_to_listing_date(df, "9999", lookup)
    assert list(unchanged["date"]) == list(df["date"]), "查無上市日的代號不應被截斷"
    print("[self-test] truncate_to_listing_date() 通過")


def _self_test_listing_date_lookup_earliest() -> None:
    """評.B-2：兩個官方檔案同代號取較早者；櫃轉市估計表把轉上市日往前拉到上櫃
    起算日；估計為null者維持官方日期不變；估計表壞掉時fail open。"""
    import tempfile
    global _TWSE_LISTING_PATH, _OTC_LISTING_PATH, _OTC_TO_TWSE_PATH
    saved = (_TWSE_LISTING_PATH, _OTC_LISTING_PATH, _OTC_TO_TWSE_PATH)
    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _TWSE_LISTING_PATH, _OTC_LISTING_PATH, _OTC_TO_TWSE_PATH = td / "t.json", td / "o.json", td / "x.json"
            _TWSE_LISTING_PATH.write_text(json.dumps({"listing_dates": {"1111": "20200101", "2222": "20210119", "3333": "20150101"}}), encoding="utf-8")
            _OTC_LISTING_PATH.write_text(json.dumps({"listing_dates": {"1111": "20120601", "4444": "20170926"}}), encoding="utf-8")
            lk = listing_date_lookup()
            assert lk["1111"] == "2012-06-01", f"兩邊都有應取較早者：{lk['1111']}"
            assert lk["2222"] == "2021-01-19" and lk["4444"] == "2017-09-26"
            _OTC_TO_TWSE_PATH.write_text(json.dumps({"transfers": {
                "2222": {"otc_start_est": "2013-11-25"}, "3333": {"otc_start_est": None}, "9999": {"otc_start_est": "2010-01-04"}}}), encoding="utf-8")
            lk = listing_date_lookup()
            assert lk["2222"] == "2013-11-25", f"櫃轉市應拉到上櫃起算日：{lk['2222']}"
            assert lk["3333"] == "2015-01-01", "估計為null應維持官方日期"
            assert "9999" not in lk, "不在官方名單的代號不得憑估計表憑空出現"
            df = pd.DataFrame({"date": ["2013-11-01", "2013-11-25", "2020-06-01", "2021-01-19"], "close": [1.0, 2.0, 3.0, 4.0]})
            assert list(truncate_to_listing_date(df, "2222", lk)["date"]) == ["2013-11-25", "2020-06-01", "2021-01-19"], "櫃轉市上櫃期間不應被砍"
            _OTC_TO_TWSE_PATH.write_text("{壞掉", encoding="utf-8")
            assert listing_date_lookup()["2222"] == "2021-01-19", "估計表壞掉應退回官方日期（fail open）"
    finally:
        _TWSE_LISTING_PATH, _OTC_LISTING_PATH, _OTC_TO_TWSE_PATH = saved
    print("[self-test] listing_date_lookup() 取較早者／櫃轉市估計 通過")


def _self_test_strict_universe_exclude_unknown_listing() -> None:
    lookup = {"2330": "1994-09-05", "2317": "1991-06-18"}
    kept, excluded = strict_universe_exclude_unknown_listing(["2330", "2317", "9999"], lookup)
    assert kept == ["2330", "2317"] and excluded == ["9999"], \
        f"strict_universe_exclude_unknown_listing()自我測試失敗：kept={kept}, excluded={excluded}"
    print("[self-test] strict_universe_exclude_unknown_listing() 通過")


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
    _self_test_listing_date_truncation()
    _self_test_listing_date_lookup_earliest()
    _self_test_strict_universe_exclude_unknown_listing()
