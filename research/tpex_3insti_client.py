"""TPEx（上櫃）三大法人買賣超歷史 client（金流一.2，2026-09-10）。

背景：`twse_t86_client.py` 的 T86 端點只涵蓋**上市**證券，`data/stock_detail.json`
既有的 `tpex_3insti_daily_trading` openapi 端點（見 `.github/scripts/fetch_market_tw.py`
`fetch_institutional_tpex()`）只回傳「當次執行當下最新一期」、不支援指定日期查詢，
所以現有管線完全沒有**上櫃股票的法人歷史**，`build_sector_flow.py` 的 20／60 日視窗
對上櫃股票永遠湊不出來。這支 client 補上有日期參數的官方端點。

端點：`https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=YYYY/MM/DD&response=json`
（總司令 2026-09-06 指令已驗證可用，2026-09-10 本次實作前重新驗證：2026/09/04 回 889 列，
2025/09/10 回 853 列，2026/09/06(週日) 回 `stat:"ok"` 但 `data:[]`——非交易日的正常回應，
不是錯誤，要當成「已完成但無資料」快取起來，不要重試。）

欄位結構（用兩筆不同股票的實際回應逐欄核對過，`總額 = idx10 + idx13 + idx22`）：
每列 24 欄，index0=代號、1=名稱，之後是 7 組「買進股數/賣出股數/買賣超股數」三欄一組：
外資及陸資(idx2-4)、外資自營商(idx5-7)、外資合計(idx8-10)、投信(idx11-13)、
自營商自行(idx14-16)、自營商避險(idx17-19)、自營商合計(idx20-22)，
最後 idx23=三大法人買賣超股數合計。
本專案沿用 `外資=外資合計、投信=投信、自營商=自營商合計` 的既有慣例
（跟 T86／`fetch_institutional_tpex()` 一致），故取 idx10／idx13／idx22。

**⚠ Holdout 邊界提醒（不是這支檔案的自我警告，是給後續開發者的邊界說明）**：
這裡回補的是「近 250 個交易日」（截至執行當天），落在
`validation/holdout.py` 的 `VAL_END=2024-12-31` **之後**。這份快取目前
**只餵 `data/sector_flow.json`（產品側，市場頁「產業金流」卡）**，
**沒有、也不得**被接進任何 train/val/holdout 切分的回測/因子 loader——
那會跟 `twse_t86_client.py` 明確迴避的「回補等於解鎖 holdout」問題撞在一起
（見該檔與 `.github/scripts/accumulate_institutional.py` 的說明）。
之後若有人想把這份資料接進研究/回測，必須先確認會不會讓某段本該是
holdout 的期間變成訓練可見，需總司令明確同意。

只做「快取原始逐日資料」，不做 ETF/權證過濾——過濾邏輯留給
`build_sector_flow.py`（跟 T86 raw cache 職責劃分一致：raw client 只管
「有效抓回來、正確快取」，資料是否進產業合計是聚合層的事）。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    """跟 `twse_t86_client.py::_atomic_read_parquet()` 同一份修法，自成一體
    複製（本專案既有慣例，見 `finmind_client.py` 等其他 client 模組）：
    讀取端偶爾在另一個 process 正在 `os.replace()` 換名的瞬間開檔會遇到
    Windows 暫時性 PermissionError（不是資料損毀），加短重試。"""
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """跟 `twse_t86_client.py::_atomic_to_parquet()` 同一份修法：寫進
    pid+uuid 專屬臨時檔，`os.replace()` 原子性換名，避免併發寫出截斷檔。"""
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    df.to_parquet(tmp_path, index=False)
    for attempt in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


DATA_DIR = Path(__file__).parent / "data" / "raw_tpex_3insti"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TPEX_3INSTI_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"

_COLS = ["date", "stock_id", "foreign_net", "trust_net", "dealer_net", "total_net"]

# row 陣列裡（扣掉代號/名稱兩欄後）三個要取的淨額欄位 index，見檔頭欄位結構說明。
_IDX_FOREIGN_NET = 10
_IDX_TRUST_NET = 13
_IDX_DEALER_NET = 22
_IDX_TOTAL_NET = 23


class TPExBlockedError(RuntimeError):
    """TPEx 端點回傳非預期格式（可能是反爬蟲封鎖或無效路徑回傳的 HTML），
    比照 `twse_t86_client.py` 的 `TWSEBlockedError`：呼叫端（回補腳本）應該
    立刻停止本批次，不要重試。"""


def _cache_path(date_str: str) -> Path:
    return DATA_DIR / f"TPEX3INSTI_{date_str}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_tpex_3insti_day(date_str: str, force_refresh: bool = False, timeout: float = 15.0,
                           max_retries: int = 3) -> pd.DataFrame:
    """一個交易日、全部上櫃證券的三大法人買賣超。

    date_str：'YYYYMMDD'。非交易日（週末/國定假日）TPEx 回 `stat:"ok"` 但
    `tables[0]["data"]:[]`——這是正常回應不是錯誤，一樣快取成空 DataFrame，
    之後不會再重打這一天。
    """
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    date_slash = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(TPEX_3INSTI_URL, params={
                "type": "Daily", "sect": "EW", "date": date_slash, "response": "json",
            }, timeout=timeout)
            if resp.status_code == 307 or "FOR SECURITY REASONS" in resp.text[:2000]:
                raise TPExBlockedError(
                    f"TPEx dailyTrade 端點疑似反爬蟲封鎖（date={date_str}）——不重試，"
                    "直接停止本批次，下次執行前先手動測試單一日期確認封鎖是否已解除。"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except TPExBlockedError:
            raise
        except Exception as e:  # noqa: BLE001 -- 網路/5xx/timeout：值得重試
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"TPEx dailyTrade fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "ok" or not body.get("tables"):
        raise TPExBlockedError(
            f"TPEx dailyTrade 回傳非預期格式（date={date_str}，可能是無效路徑回傳的 HTML "
            f"或端點改版）：{str(body)[:200]}"
        )

    table = body["tables"][0]
    rows = table.get("data") or []
    if not rows:
        # 正常的非交易日回應（週末/國定假日），快取成空 DataFrame，不算錯誤。
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    out_rows = []
    for r in rows:
        if len(r) <= _IDX_TOTAL_NET:
            continue  # 欄位數不足，格式跟預期不符，跳過這列而非整批中止
        code = str(r[0]).strip()
        foreign = _num(r[_IDX_FOREIGN_NET])
        trust = _num(r[_IDX_TRUST_NET])
        dealer = _num(r[_IDX_DEALER_NET])
        total = _num(r[_IDX_TOTAL_NET])
        if total is None:
            continue
        out_rows.append({
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
            "stock_id": code, "foreign_net": foreign, "trust_net": trust,
            "dealer_net": dealer, "total_net": total,
        })

    out = pd.DataFrame(out_rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_date_range() -> tuple[str | None, str | None, int]:
    """(最早快取日期, 最新快取日期, 已快取天數)——給回補腳本／進度回報用。"""
    files = sorted(DATA_DIR.glob("TPEX3INSTI_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("TPEX3INSTI_", "") for f in files]
    return min(dates), max(dates), len(files)
