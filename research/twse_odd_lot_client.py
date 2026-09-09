"""`HYPOTHESIS_QUEUE.md` #67 盤中零股逐檔成交資訊——client（2026-09-09
hypothesis_queue排程接續新增）。

**端點**：`https://www.twse.com.tw/rwd/zh/afterTrading/TWTC7U?date=
YYYYMMDD&response=json`——一次一天、全市場個股逐檔列出。本輪實測
（date=20260908）確認欄位為：
["證券代號","證券名稱","成交股數","成交筆數","成交金額","當日第一次
成交價","當日最後一次成交價","當日最高價","當日最低價","最後揭示買價",
"最後揭示買量","最後揭示賣價","最後揭示賣量"]。

**三來源查證（`CLAUDE.md`「搜尋紀律」，本輪執行）**：
1. 官方端點本身——直接curl測試上述URL，date=20260908拿到即時JSON回應
   （非文件宣稱，是本輪實測結果）。
2. 官方文件——`https://www.twse.com.tw/en/trading/historical/twtc7u.html`
   （及zh版）明載「The following information provided here is available
   since 2020/10/26」，免費CSV下載，非Data E-Shop付費商品。
3. GitHub/社群——`twjackysu/TWSEMCPServer`專案有`get_odd_lot_trading_quotes`
   工具，證實此端點已被社群實際使用過。
四類來源之外另查證FinMind（第4類，其他供應商）：完整dataset清單
（105個dataset）中無零股相關項目，FinMind未把這個資料當商品賣，
但這不影響官方端點本身可行性的結論（只是沒有第二個供應商可交叉核對）。

**重大限制發現（本輪查證後才知道，事前綁定之前必須揭露，不是跑完結果
後才發現）**：TWTC7U**沒有「零股買進金額 vs 賣出金額」的方向拆分**——
每一列只有成交股數/成交金額（單一彙總數字），不像三大法人T86報表那樣
拆買/賣兩欄。`HYPOTHESIS_QUEUE.md` #67原始定義「零股淨額=買進金額-
賣出金額」**無法用這個免費官方端點直接算**，需要逐筆tick方向分類
（buy-initiated vs sell-initiated，比照`#62`鉅額逐筆交易同樣需要的
方法），而tick資料累積（`#50`，`data/ticks/`）本輪查證仍只有2個完整
交易日、距20交易日門檻仍遠，不是本track範圍。

**操作化修正（本輪查證後、跑任何數字之前決定，不是看到結果後換方向，
差別見`HYPOTHESIS_QUEUE_PROTOCOL.md`第2節「快殺標準」精神）**：改用
端點本身就直接提供的「最後揭示買量」與「最後揭示賣量」計算**收盤前
零股委託簿失衡度**（order book imbalance）：
    imbalance = (last_bid_qty - last_ask_qty) / (last_bid_qty + last_ask_qty)
這仍是同一個經濟機制（零股/小額交易人的買賣壓力），只是把「無法取得的
逐筆方向淨額」換成「官方端點本身就有的收盤前委託簿失衡」這個資料可及
的代理變數，且發生在寫任何cheap gate程式碼、跑任何predict結果之前。

反爬蟲封鎖偵測與快取模式跟`twse_day_trading_client.py`同一套邏輯
（`TWSEBlockedError`、`_atomic_to_parquet`/`_atomic_read_parquet`），
自成一體複製，理由同該檔案docstring（各client獨立、不共用狀態）。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_odd_lot"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TWTC7U_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/TWTC7U"

# 官方文件載明本資訊自2020/10/26起開始提供（`www.twse.com.tw/en/trading/
# historical/twtc7u.html`），早於此日期的請求預期一律無資料。
EARLIEST_AVAILABLE_DATE = "2020-10-26"

_COLS = [
    "date", "code", "name", "volume", "trades", "value",
    "first_price", "last_price", "high", "low",
    "last_bid_price", "last_bid_qty", "last_ask_price", "last_ask_qty",
]


class TWSEBlockedError(RuntimeError):
    """跟`twse_day_trading_client.py`/`twse_t86_client.py`同一種反爬蟲
    封鎖偵測，自成一體複製。"""


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
    return DATA_DIR / f"TWTC7U_{date_str}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_odd_lot_day(date_str: str, force_refresh: bool = False,
                       timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """date_str: 'YYYYMMDD'。回傳當天逐檔（每檔一列）：date、code、name、
    volume（成交股數）、trades（成交筆數）、value（成交金額）、
    first_price/last_price/high/low（當日零股盤成交價系列）、
    last_bid_price/last_bid_qty/last_ask_price/last_ask_qty（收盤前最後
    揭示買賣價量，用於計算委託簿失衡度，見本檔案docstring）。非交易日
    或早於`EARLIEST_AVAILABLE_DATE`一律回傳空frame並快取（避免重複打）。
    """
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(TWTC7U_URL, params={
                "response": "json", "date": date_str,
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE TWTC7U端點回傳反爬蟲封鎖頁（date={date_str}）——立刻停止，不要重試。"
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
        raise RuntimeError(f"TWTC7U fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    rows = []
    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    for r in body["data"]:
        # 欄位順序見本檔案docstring：
        # [代號,名稱,成交股數,成交筆數,成交金額,首價,末價,高,低,
        #  最後買價,最後買量,最後賣價,最後賣量]
        if len(r) < 13:
            continue
        rows.append({
            "date": date_fmt,
            "code": str(r[0]).strip(),
            "name": str(r[1]).strip(),
            "volume": _num(r[2]),
            "trades": _num(r[3]),
            "value": _num(r[4]),
            "first_price": _num(r[5]),
            "last_price": _num(r[6]),
            "high": _num(r[7]),
            "low": _num(r[8]),
            "last_bid_price": _num(r[9]),
            "last_bid_qty": _num(r[10]),
            "last_ask_price": _num(r[11]),
            "last_ask_qty": _num(r[12]),
        })
    out = pd.DataFrame(rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_date_range() -> tuple[str | None, str | None, int]:
    files = sorted(DATA_DIR.glob("TWTC7U_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("TWTC7U_", "") for f in files]
    return min(dates), max(dates), len(files)


def load_all_cached() -> pd.DataFrame:
    """把DATA_DIR底下所有TWTC7U_*.parquet讀進來併成一份完整DataFrame，附加
    計算好的`imbalance`欄位（收盤前零股委託簿失衡度，見本檔案docstring
    「操作化修正」段落：`(last_bid_qty-last_ask_qty)/(last_bid_qty+last_ask_qty)`，
    分母為0時回傳NaN，不除以零）。2026-09-09 hypothesis_queue排程接續新增，
    `HYPOTHESIS_QUEUE.md` #67第1關cheap gate用。"""
    files = sorted(DATA_DIR.glob("TWTC7U_*.parquet"))
    if not files:
        return pd.DataFrame(columns=_COLS + ["imbalance"])
    frames = [_atomic_read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=_COLS + ["imbalance"])
    combined = pd.concat(frames, ignore_index=True)
    denom = combined["last_bid_qty"] + combined["last_ask_qty"]
    combined["imbalance"] = np.where(
        denom > 0, (combined["last_bid_qty"] - combined["last_ask_qty"]) / denom, np.nan
    )
    return combined


_ODD_LOT_GROUPED_CACHE: dict[str, pd.DataFrame] | None = None
_ODD_LOT_GROUPED_CACHE_KEY: tuple[int, float] | None = None


def _load_all_odd_lot_grouped() -> dict[str, pd.DataFrame]:
    """跟`twse_t86_client.py::_load_all_t86_grouped()`同一套process內快取
    模式（理由同該函式docstring——避免`load_sample_with_factors()`逐股票
    呼叫時每次都重新掃描讀取全部1092個parquet檔）：依`code`分組快取在這個
    process的記憶體裡。快取有效性用「檔案數量+最新mtime」當key判斷。"""
    global _ODD_LOT_GROUPED_CACHE, _ODD_LOT_GROUPED_CACHE_KEY
    files = sorted(DATA_DIR.glob("TWTC7U_*.parquet"))
    if not files:
        return {}
    key = (len(files), max(p.stat().st_mtime for p in files))
    if _ODD_LOT_GROUPED_CACHE is not None and _ODD_LOT_GROUPED_CACHE_KEY == key:
        return _ODD_LOT_GROUPED_CACHE
    combined = load_all_cached()
    if combined.empty:
        _ODD_LOT_GROUPED_CACHE = {}
        _ODD_LOT_GROUPED_CACHE_KEY = key
        return _ODD_LOT_GROUPED_CACHE
    grouped = {code: g for code, g in combined.groupby("code", sort=False)}
    _ODD_LOT_GROUPED_CACHE = grouped
    _ODD_LOT_GROUPED_CACHE_KEY = key
    return grouped


def odd_lot_imbalance_daily(stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
    """Per-stock時間序列，收盤前零股委託簿失衡度。跟
    `twse_t86_client.py::institutional_daily_net_t86()`同一套語意：只回傳
    已快取的日期，不自行補抓；`end_date`一律截斷在`VAL_END`（holdout聖域
    邊界，物理隔離，不靠人記得）。回傳欄位：date, imbalance。"""
    from validation.holdout import VAL_END

    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    empty = pd.DataFrame(columns=["date", "imbalance"])
    grouped = _load_all_odd_lot_grouped()
    g = grouped.get(stock_id)
    if g is None or g.empty:
        return empty
    sub = g[(g["date"] >= start_date) & (g["date"] <= effective_end)]
    if sub.empty:
        return empty
    out = sub[["date", "imbalance"]].dropna(subset=["imbalance"]).sort_values("date").reset_index(drop=True)
    return out
