"""TWSE 全市場每日成交量/值（FMTQIK）client——`HYPOTHESIS_QUEUE.md` #37
全市場現股當沖比重的分母來源（2026-09-05）。

背景：#37原始設計打算用FinMind `TaiwanStockDayTrading`（300檔快取樣本近似
全市場），但本輪查證發現該端點**免費層資料只從2024-01-02起有**——
TRAIN_END=2020-12-31（見`validation/holdout.py`），代表TRAIN期完全沒有
觀測值，標準cheap gate（要求train/val同號）無法照原設計執行。改查TWSE
官方端點，本輪確認`FMTQIK`（全市場單日成交股數/金額/加權指數）跟
`TWTASU`（全市場當沖成交量值，見`twse_day_trading_client.py`）皆有完整
2015年起資料，改用這兩個端點自建全市場當沖比重時序，取代FinMind近似版。

**已排除的替代分母**：曾考慮直接用`yf_price_client.py`已快取的TAIEX
（^TWII）`volume`欄位當分母省一個資料源，但實測其量級（約200~300萬）
遠小於FMTQIK的全市場真實成交股數（約40~50億），確認Yahoo這個volume欄位
不是台股全市場成交股數（可能是指數本身某種內部量而非成分股加總成交量），
**不可用**，必須另外抓FMTQIK。

**端點行為**：`https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date=
YYYYMM01&response=json`——傳入該月任一天的日期，回傳**整個月**每個交易日
一列（跟T86/TWTASU的「一次一天」相反，是「一次一個月」，效率高很多，
全範圍2015-01~2024-12僅需120次呼叫）。欄位（本輪實測確認，非猜測）：
日期(民國年/月/日字串，例如"104/01/28")、成交股數、成交金額、成交筆數、
發行量加權股價指數、漲跌點數。

快取單位：一個parquet檔案對應一個(年,月)，跟`twse_t86_client.py`的
per-date快取同一種「檔案存在=完成」精神，只是粒度改成月。反爬蟲封鎖偵測
（`TWSEBlockedError`）跟`twse_t86_client.py`完全同一套邏輯，自成一體複製
（本專案既有慣例，見該檔案docstring說明理由），不共用import。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_market_volume"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FMTQIK_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
_COLS = ["date", "total_volume", "total_value"]


class TWSEBlockedError(RuntimeError):
    """跟`twse_t86_client.py`同一種反爬蟲封鎖偵測，自成一體複製。"""


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


def _cache_path(year_month: str) -> Path:
    return DATA_DIR / f"FMTQIK_{year_month}.parquet"


def _roc_date_to_iso(roc_str: str) -> str | None:
    """'104/01/28' -> '2015-01-28'。民國年+1911=西元年。"""
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    try:
        roc_year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return f"{roc_year + 1911:04d}-{month:02d}-{day:02d}"


def fetch_market_volume_month(year: int, month: int, force_refresh: bool = False,
                               timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """回傳該月每個交易日一列：date(ISO字串)、total_volume(成交股數)、
    total_value(成交金額)。查詢月份若尚無資料（例如查詢未來月份）回傳空
    frame並照樣快取，避免重複呼叫注定落空的月份。"""
    year_month = f"{year:04d}{month:02d}"
    path = _cache_path(year_month)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(FMTQIK_URL, params={
                "response": "json", "date": f"{year_month}01",
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE FMTQIK端點回傳反爬蟲封鎖頁（{year_month}）——立刻停止，不要重試。"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except TWSEBlockedError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"FMTQIK fetch failed after {max_retries} attempts for {year_month}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    rows = []
    for r in body["data"]:
        iso_date = _roc_date_to_iso(r[0])
        if iso_date is None:
            continue

        def _num(v: str) -> float | None:
            s = str(v).replace(",", "").strip()
            if s in ("", "-", "--"):
                return None
            try:
                return float(s)
            except ValueError:
                return None

        vol = _num(r[1])
        val = _num(r[2])
        if vol is None:
            continue
        rows.append({"date": iso_date, "total_volume": vol, "total_value": val})

    out = pd.DataFrame(rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_months() -> list[str]:
    files = sorted(DATA_DIR.glob("FMTQIK_*.parquet"))
    return [f.stem.replace("FMTQIK_", "") for f in files]
