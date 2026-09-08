"""TWSE 借券成交費率（Securities Lending Fee Rate）client——`HYPOTHESIS_QUEUE.md`
#63 第1關資料源，經濟理由/完整假設定義見`HYPOTHESIS_QUEUE.md` #63條目。

**端點**：`https://www.twse.com.tw/rwd/zh/lending/t13sa710?response=json&startDate=YYYYMMDD&endDate=YYYYMMDD`
（跟`twse_t86_client.py`/`twse_block_trade_client.py`同一個`rwd`網域模式，非
openapi開放資料集）。單參數`date=`會被伺服器忽略、預設今天，**必須用
`startDate`/`endDate`區間**（已於#63條目資料可行性查證段落實測確認）。

**歷史回溯**：實測`20150101`~`20151231`（整年）回傳70,637筆，無明顯單次
查詢筆數上限（比`twse_block_trade_client.py`的BFIAUU端點只能逐日查好很多），
所以本client**以年為批次單位**，不是逐日（省下365倍的請求量）。

**欄位（`fields`，2026-09-09本輪探測確認，UTF-8乾淨、無亂碼——之前終端機
顯示亂碼純粹是Windows cp950顯示限制，同`mops_material_news_client.py`
docstring記錄的同一種假警報）**：
`成交日期`（民國年格式"115年09月01日"）、`證券代號名稱`（代號+名稱以空白
連接於同一欄，如"1101 台泥"，需要下游拆分）、`交易方式`（實測見過"競價"
"議借"兩種，尚未見過`#63`條目原始假設提及的"定價"——不代表不存在，只是
本輪抽樣的3天窗口沒出現，需更大樣本才能下結論，見下方`explore_trade_types()`）、
`成交數量(交易單位)`、`成交費率`（本假設的核心變數，年利率%，如1.50/2.00/
0.01/6.00，數字已證實實際上會變動，不是官方假設中"定價交易固定3.5%"那種
單一常數——但那個假設只針對"定價"類型，本輪樣本未見"定價"類型，此點留白）、
`成交日收盤價`、`約定還券日期`（民國年格式）、`約定借券天數`、`費率異動`
（本輪樣本全為空字串，語意未知，原樣保留由下游決定如何使用）。

**設計取捨（跟`twse_block_trade_client.py`同一個精神）**：client只負責
忠實落地原始資料（含拆分證券代號名稱、轉換民國年為ISO日期這兩個純格式轉換，
不做任何統計/衍生欄位），交易方式的過濾/分組邏輯留給下游gate腳本決定，
避免client層自作主張排除掉未來可能需要的資料列。

反爬蟲封鎖偵測跟`twse_t86_client.py`/`twse_block_trade_client.py`同一套
邏輯（`TWSEBlockedError`），自成一體複製，理由同那些檔案docstring：這幾支
client各自獨立、不共用基底類別，是刻意的隔離取捨（一支壞掉不牽連其他）。
"""
from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_lending_fee"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LENDING_FEE_URL = "https://www.twse.com.tw/rwd/zh/lending/t13sa710"
_COLS = [
    "date", "stock_id", "stock_name", "trade_type", "volume",
    "fee_rate", "close_price", "return_date", "loan_days", "fee_change",
]

_ROC_DATE_RE = re.compile(r"^(\d{2,3})年(\d{1,2})月(\d{1,2})日$")
_STOCK_ID_NAME_RE = re.compile(r"^(\S+)\s+(.+)$")


class TWSEBlockedError(RuntimeError):
    """跟`twse_t86_client.py`/`twse_block_trade_client.py`同一種反爬蟲封鎖偵測，自成一體複製。"""


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
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


def _cache_path(year: int) -> Path:
    return DATA_DIR / f"LENDING_FEE_{year}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    """民國年"115年09月01日" -> ISO "2026-09-01"。格式不符回傳None（不硬猜）。"""
    m = _ROC_DATE_RE.match(str(s).strip())
    if not m:
        return None
    roc_year, month, day = m.groups()
    ad_year = int(roc_year) + 1911
    return f"{ad_year:04d}-{int(month):02d}-{int(day):02d}"


def _split_stock_id_name(s: str) -> tuple[str, str]:
    """"1101 台泥" -> ("1101", "台泥")。格式不符時整欄塞進stock_name、
    stock_id留空字串，不拋錯（同CLAUDE.md已知地雷段落一致的謹慎原則）。"""
    m = _STOCK_ID_NAME_RE.match(str(s).strip())
    if not m:
        return "", str(s).strip()
    return m.group(1), m.group(2)


def fetch_lending_fee_year(year: int, force_refresh: bool = False,
                            timeout: float = 30.0, max_retries: int = 3) -> pd.DataFrame:
    """year: 西元年（例如2015）。回傳當年度全部借券成交費率逐筆資料（非交易日
    區間無資料回傳空frame，同樣落地快取避免重複打）。以年為批次單位（不是
    逐日），理由見本檔docstring「歷史回溯」段落。"""
    path = _cache_path(year)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    start_date = f"{year}0101"
    end_date = f"{year}1231"

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(LENDING_FEE_URL, params={
                "response": "json", "startDate": start_date, "endDate": end_date,
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE t13sa710端點回傳反爬蟲封鎖頁（year={year}）——立刻停止，不要重試。"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except TWSEBlockedError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    else:
        raise RuntimeError(f"t13sa710 fetch failed after {max_retries} attempts for year={year}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    rows = []
    for r in body["data"]:
        if len(r) < 9:
            continue  # 結構異常列，丟棄比硬解更安全
        date_iso = _roc_date_to_iso(r[0])
        return_date_iso = _roc_date_to_iso(r[6])
        stock_id, stock_name = _split_stock_id_name(r[1])
        rows.append({
            "date": date_iso,
            "stock_id": stock_id,
            "stock_name": stock_name,
            "trade_type": str(r[2]).strip(),
            "volume": _num(r[3]),
            "fee_rate": _num(r[4]),
            "close_price": _num(r[5]),
            "return_date": return_date_iso,
            "loan_days": _num(r[7]),
            "fee_change": str(r[8]).strip(),
        })
    out = pd.DataFrame(rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_year_range() -> tuple[int | None, int | None, int]:
    files = sorted(DATA_DIR.glob("LENDING_FEE_*.parquet"))
    if not files:
        return None, None, 0
    years = [int(f.stem.replace("LENDING_FEE_", "")) for f in files]
    return min(years), max(years), len(files)


def load_all_cached() -> pd.DataFrame:
    """讀回目前所有已快取的年度，合併成單一DataFrame（跨檔讀取，給下游
    gate腳本一次性載入用，不含即時抓取邏輯）。"""
    files = sorted(DATA_DIR.glob("LENDING_FEE_*.parquet"))
    if not files:
        return pd.DataFrame(columns=_COLS)
    frames = [_atomic_read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=_COLS)
    return pd.concat(frames, ignore_index=True)
