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


# ---------------------------------------------------------------------------
# 逐檔版本（`HYPOTHESIS_QUEUE.md` #57，2026-09-08新增）
#
# 2026-09-08查證：#57原本以為「逐檔當沖成交量值」需要另找新端點，
# 三來源查證後發現**根本不需要**——TWTASU回應本來就是逐檔列表（本輪
# 實測date=20260904回傳1332列，含個股列如`2330 台積電`，最後一列才是
# `合計`），只是`fetch_day_trading_ratio_day()`（#37用）刻意只取合計列、
# 逐檔列在記憶體裡直接丟棄、從未落地存檔。TWTB4U（openapi.twse.com.tw
# swagger schema核對：只有Date/Code/Name/Suspension四欄）才是「當沖資格
# 標的清單」，不含量值，不是我們要的端點——這是命名相近但完全不同的
# 兩個資料集，之前的『找不到』誤判就是把這兩個搞混。
#
# 因此#57不必新增client、不必等待新端點查證，只需要重新呼叫同一個
# TWTASU端點並且這次把逐檔列存起來（獨立快取目錄，不跟#37的單列彙總
# 快取共用，避免混淆兩種粒度）。代價：#37的既有回補（2015-01-01~VAL_END
# 約2,500個交易日）都得重打一次TWTASU（無法從已快取的彙總parquet反推
# 回逐檔——原始逐檔JSON從未被保存），這是`backfill_day_trading_detail.py`
# 要處理的事，不在本函式範圍。
# ---------------------------------------------------------------------------

DETAIL_DATA_DIR = Path(__file__).parent / "data" / "raw_twse_day_trading_detail"
DETAIL_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DETAIL_COLS = ["date", "code", "name", "day_trade_sell_volume", "day_trade_sell_value",
                "margin_offset_volume", "margin_offset_value"]


def _detail_cache_path(date_str: str) -> Path:
    return DETAIL_DATA_DIR / f"TWTASU_detail_{date_str}.parquet"


def fetch_day_trading_detail_day(date_str: str, force_refresh: bool = False,
                                  timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """date_str: 'YYYYMMDD'。回傳當天逐檔（每檔一列，不含「合計」列）：
    date、code、name、day_trade_sell_volume、day_trade_sell_value、
    margin_offset_volume、margin_offset_value。跟`fetch_day_trading_ratio_day()`
    打同一個TWTASU端點、同一套反爬蟲偵測，但快取到獨立目錄
    （`DETAIL_DATA_DIR`），彼此互不影響、也不共用快取（同一天會被
    兩支函式各打一次API，這是刻意的隔離取捨，不是重工）。"""
    path = _detail_cache_path(date_str)
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
        raise RuntimeError(f"TWTASU detail fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_DETAIL_COLS)
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

    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    rows = []
    for r in body["data"]:
        raw = str(r[0]).strip()
        if raw in ("合計", "合 計"):
            continue
        parts = raw.split(None, 1)
        code = parts[0] if parts else raw
        name = parts[1].strip() if len(parts) > 1 else ""
        rows.append({
            "date": date_iso, "code": code, "name": name,
            "day_trade_sell_volume": _num(r[1]),
            "day_trade_sell_value": _num(r[2]),
            "margin_offset_volume": _num(r[3]),
            "margin_offset_value": _num(r[4]),
        })
    out = pd.DataFrame(rows, columns=_DETAIL_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_detail_date_range() -> tuple[str | None, str | None, int]:
    files = sorted(DETAIL_DATA_DIR.glob("TWTASU_detail_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("TWTASU_detail_", "") for f in files]
    return min(dates), max(dates), len(files)
