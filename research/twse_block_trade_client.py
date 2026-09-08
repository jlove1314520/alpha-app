"""TWSE 鉅額逐筆交易（大宗交易/block trade）client——`HYPOTHESIS_QUEUE.md` #62
第1關資料源，經濟理由/完整假設定義見`HYPOTHESIS_QUEUE.md`#62條目。

**端點**：`https://www.twse.com.tw/rwd/zh/block/BFIAUU?date=YYYYMMDD&response=json`
（跟`twse_t86_client.py`/`twse_day_trading_client.py`同一個`rwd`網域模式，非
openapi開放資料集）。一次一天、逐筆列出當日每一筆鉅額交易（同一檔股票當天
可有多筆）。實測欄位（`fields`）：`["證券代號","證券名稱","交易別","成交價",
"成交股數","成交金額"]`。`交易別`實測值含「配對交易」與空字串（後者疑似
非資料列的雜訊，本函式原樣保留、由下游過濾決定要不要丟棄，不在client層
自行篩選以免遺漏未來可能出現的「拍賣」「標購」類型）。

**編碼備註（2026-09-09踩過）**：`response.encoding`宣稱`UTF-8`且HTTP header
也是`application/json;charset=UTF-8`，但直接`resp.json()`偶爾在某些終端機
顯示會出現亂碼——經查證是**顯示端（終端機）的問題，不是資料本身**，原始
bytes本來就是合法UTF-8（`resp.content.decode('utf-8')`與`resp.json()`
結果一致），本函式沿用`resp.json()`標準路徑，不做任何額外轉碼，避免自己
發明的轉碼邏輯反而把好資料弄壞。

**歷史回溯**：`20150105`/`20180102`/`20200102`三個測試日期皆有資料，確認
涵蓋2015~2024完整TRAIN/VAL窗口（見`HYPOTHESIS_QUEUE.md`#62條目(a)段落）。

反爬蟲封鎖偵測跟`twse_t86_client.py`/`twse_day_trading_client.py`同一套
邏輯（`TWSEBlockedError`），自成一體複製，理由同那些檔案docstring：這幾支
client各自獨立、不共用基底類別，是刻意的隔離取捨（一支壞掉不牽連其他）。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_block_trade"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BFIAUU_URL = "https://www.twse.com.tw/rwd/zh/block/BFIAUU"
_COLS = ["date", "stock_id", "stock_name", "trade_type", "price", "volume", "value"]


class TWSEBlockedError(RuntimeError):
    """跟`twse_t86_client.py`/`twse_day_trading_client.py`同一種反爬蟲封鎖偵測，自成一體複製。"""


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
    return DATA_DIR / f"BFIAUU_{date_str}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_block_trade_day(date_str: str, force_refresh: bool = False,
                           timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """date_str: 'YYYYMMDD'。回傳當天逐筆鉅額交易（非交易日/無資料回傳空
    frame，同樣落地快取避免重複打）：date、stock_id、stock_name、
    trade_type（原始中文字串，例如「配對交易」，下游自行決定過濾規則）、
    price、volume、value（單位：元/股/元，取自TWSE原始欄位，不做任何
    衍生計算——方向代理等衍生邏輯留給下游gate腳本，client只負責忠實
    落地原始資料）。"""
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(BFIAUU_URL, params={
                "response": "json", "date": date_str,
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE BFIAUU端點回傳反爬蟲封鎖頁（date={date_str}）——立刻停止，不要重試。"
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
        raise RuntimeError(f"BFIAUU fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    rows = []
    for r in body["data"]:
        if len(r) < 6:
            continue  # 結構異常列，丟棄比硬解更安全（同CLAUDE.md已知地雷段落一致的謹慎原則）
        rows.append({
            "date": date_iso,
            "stock_id": str(r[0]).strip(),
            "stock_name": str(r[1]).strip(),
            "trade_type": str(r[2]).strip(),
            "price": _num(r[3]),
            "volume": _num(r[4]),
            "value": _num(r[5]),
        })
    out = pd.DataFrame(rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def cached_date_range() -> tuple[str | None, str | None, int]:
    files = sorted(DATA_DIR.glob("BFIAUU_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("BFIAUU_", "") for f in files]
    return min(dates), max(dates), len(files)


def load_all_cached() -> pd.DataFrame:
    """讀回目前所有已快取的交易日，合併成單一DataFrame（跨檔讀取，
    給下游gate腳本一次性載入用，不含即時抓取邏輯）。"""
    files = sorted(DATA_DIR.glob("BFIAUU_*.parquet"))
    if not files:
        return pd.DataFrame(columns=_COLS)
    frames = [_atomic_read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=_COLS)
    return pd.concat(frames, ignore_index=True)
