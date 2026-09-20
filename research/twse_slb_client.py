# -*- coding: utf-8 -*-
"""TWSE 借券餘額（出借總量）逐日全市場快取（2026-09-20 DevQueue 213101，債務帽）。

來源＝`www.twse.com.tw/rwd/zh/lending/TWT72U`（`selectType=SLBNLB`：證交所借券系統＋證商/證金營業處所合計），
三來源查證與實測見 `docs/FIRST_HAND_SOURCES.md` 5b。**一次請求＝一個交易日全市場**，快取單位是日期
（仿 `twse_t86_client.py`）：`research/data/raw_twse_slb/SLB_YYYYMMDD.parquet`，檔案存在即完成。

這是 `rwd` 主站家族（跟T86同類，有反爬蟲封鎖頁，見 twse_t86_client.py 說明）：偵測到封鎖頁／非JSON
一律直接拋 `TWSEBlockedError`，**不重試**（重試只會延長封鎖）。非交易日 `stat!="OK"` 存空表，不重複請求。
欄位：date、stock_id、prev_bal、borrow、return_、bal（=prev+borrow−return，股）、close、mv、market。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "https://www.twse.com.tw/rwd/zh/lending/TWT72U"
DATA_DIR = Path(__file__).parent / "data" / "raw_twse_slb"
DATA_DIR.mkdir(parents=True, exist_ok=True)
COLS = ["date", "stock_id", "prev_bal", "borrow", "return_", "bal", "close", "mv", "market"]
UA = {"User-Agent": "Mozilla/5.0 (alpha-research)"}


class TWSEBlockedError(RuntimeError):
    pass


def cache_path(date_str: str) -> Path:
    return DATA_DIR / f"SLB_{date_str}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_slb_day(date_str: str, timeout: float = 20.0) -> pd.DataFrame:
    """date_str='YYYYMMDD'。已快取直接讀檔；非交易日回空表（有正確欄位）並快取。"""
    path = cache_path(date_str)
    if path.exists():
        return pd.read_parquet(path)
    resp = requests.get(URL, params={"response": "json", "date": date_str, "selectType": "SLBNLB"},
                        headers=UA, timeout=timeout)
    if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
        raise TWSEBlockedError(f"TWSE反爬蟲封鎖頁（date={date_str}）")
    resp.raise_for_status()
    try:
        body = resp.json()
    except ValueError as e:  # 空body／HTML：不快取，讓呼叫端判斷是否連續失敗
        raise TWSEBlockedError(f"非JSON回應（date={date_str}，len={len(resp.content)}）") from e
    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=COLS)
    else:
        f = body["fields"]
        if len(f) < 9 or "借券餘額" not in "".join(f[5:6]):
            raise RuntimeError(f"TWT72U欄位與預期不符（date={date_str}）：{f}")
        d = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        out = pd.DataFrame(
            [{"date": d, "stock_id": str(r[0]).strip(), "prev_bal": _num(r[2]), "borrow": _num(r[3]),
              "return_": _num(r[4]), "bal": _num(r[5]), "close": _num(r[6]), "mv": _num(r[7]),
              "market": str(r[8]).strip()} for r in body["data"]], columns=COLS)
    tmp = path.with_suffix(".tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return out
