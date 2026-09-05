"""TWSE 全市場現股當沖交易量（TWTASU）client——`HYPOTHESIS_QUEUE.md` #37
第1關資料源，取代FinMind`TaiwanStockDayTrading`（該端點免費層只從
2024-01-02起有資料，涵蓋不到TRAIN期，見`twse_market_volume_client.py`
docstring完整背景說明）。

**端點**：`https://www.twse.com.tw/rwd/zh/afterTrading/TWTASU?date=
YYYYMMDD&response=json`——一次一天、全市場個股逐檔列出，本輪不需要
個股明細，只取回應資料最後一列的「合計」列（本輪實測確認每日回應皆有
此彙總列，欄位為：股票代號欄放「合計」文字、其後四欄依序是[當沖賣出
成交數量, 當沖賣出成交金額, 資券互抵成交數量, 資券互抵成交金額]）。

**day_trade_volume定義（本輪方法論假設，供未來覆核）**：取
「當沖賣出成交數量+資券互抵成交數量」兩者加總近似當日全市場現股當沖
成交量——這是本輪從實際回應欄位反推的假設（TWSE官方對這兩欄的精確
定義未在本輪詳查，只確認欄位存在+加總量級跟FinMind`TaiwanStockDayTrading`
2024年後資料量級數量級相符，見`backfill_day_trading_ratio.py`sanity
檢查段落），並非官方文件逐字引用，未來deep_dive若要更嚴謹應找TWSE
官方統計名詞定義稿核對。

反爬蟲封鎖偵測跟`twse_t86_client.py`同一套邏輯（`TWSEBlockedError`），
自成一體複製，理由同該檔案docstring。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_day_trading"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TWTASU_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/TWTASU"
_COLS = ["date", "day_trade_sell_volume", "day_trade_sell_value",
         "margin_offset_volume", "margin_offset_value"]


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


def _cache_path(date_str: str) -> Path:
    return DATA_DIR / f"TWTASU_{date_str}.parquet"


def fetch_day_trading_ratio_day(date_str: str, force_refresh: bool = False,
                                 timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """date_str: 'YYYYMMDD'。回傳單列（或非交易日回傳空frame，同樣快取
    避免重複打）：date、day_trade_sell_volume、day_trade_sell_value、
    margin_offset_volume、margin_offset_value（單位：張/元，取自TWSE
    回應「合計」列，非本函式加總逐股列——直接信任TWSE官方合計，避免
    自己加總時漏掉分頁/欄位對齊問題）。"""
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(TWTASU_URL, params={
                "response": "json", "date": date_str,
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE TWTASU端點回傳反爬蟲封鎖頁（date={date_str}）——立刻停止，不要重試。"
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
        raise RuntimeError(f"TWTASU fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    def _num(v: str) -> float | None:
        s = str(v).replace(",", "").strip()
        if s in ("", "-", "--"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    total_row = None
    for r in body["data"]:
        if str(r[0]).strip() in ("合計", "合 計"):
            total_row = r
            break
    if total_row is None:
        # 找不到合計列（結構變動或非預期回應），視為這天無可用資料，
        # 快取空frame避免每次重跑都重新打，但不當作blocked錯誤。
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    row = {
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
        "day_trade_sell_volume": _num(total_row[1]),
        "day_trade_sell_value": _num(total_row[2]),
        "margin_offset_volume": _num(total_row[3]),
        "margin_offset_value": _num(total_row[4]),
    }
    out = pd.DataFrame([row], columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_date_range() -> tuple[str | None, str | None, int]:
    files = sorted(DATA_DIR.glob("TWTASU_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("TWTASU_", "") for f in files]
    return min(dates), max(dates), len(files)
