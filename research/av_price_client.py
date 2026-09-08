# -*- coding: utf-8 -*-
"""Alpha Vantage 價格客戶端（2026-09-08 資料源一.3）。

**為什麼需要這支**：美股存活者偏誤唯一還沒補起來的缺口是「已下市股的價格」。
- `us_universe_pit.py` 已把**宇宙**修成 survivorship-free（SEC EDGAR，含 Form 25 下市）
- `us_fundamentals.py` 的**財報**走 SEC XBRL，以 `min(filed)` 對齊申報日 PIT
- **但價格沒有**：yfinance 對 TWTR／SIVB／FRC／ATVI **4/4 全滅**，
  775 檔下市股（佔母體 7.1%）沒有任何價格來源。

**只修宇宙不修價格等於沒修**——我們知道誰倒了，卻拿不到它倒之前的價格，
回測實際仍只跑得動在市股。

**額度紀律（免費層，寫死不可繞）**：
Alpha Vantage 免費層約**每日 25 次請求、每分鐘 5 次**。
這支客戶端採**硬性預算**：額度用完就誠實拒絕，**不排隊、不重試、不換來源硬取**
（比照 CLAUDE.md 對 Shioaji 的同一原則——排隊只是把違規往後推）。
每次請求都落地計數，跨行程共用同一份預算檔。

**取得方式**：官方 API＋官方發放的免費 key，符合取得方式鐵律。
key 不進 repo：優先讀環境變數 `ALPHA_ALPHAVANTAGE_KEY`，
其次讀 `secrets/alphavantage_key.txt`（`secrets/` 已在 .gitignore 第 29 行）。
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = ROOT / "secrets" / "alphavantage_key.txt"
BUDGET = ROOT / "research" / ".alphavantage_budget.json"
CACHE = ROOT / "research" / "data" / "av_cache"
TZ = timezone(timedelta(hours=8))

BASE = "https://www.alphavantage.co/query"
# 官方免費層上限：25 次/日、5 次/分。我們的保守值再往下壓一級，
# 理由同 CLAUDE.md 的 Shioaji 條目：寧可慢，不要被停權。
DAILY_BUDGET = 22
MIN_INTERVAL_SEC = 13.0     # 每分鐘 5 次 → 12 秒/次，取 13 秒留餘裕

_last_call = [0.0]


class BudgetExhausted(RuntimeError):
    """當日額度用盡。**這是誠實拒絕，不是錯誤**——不要在上層 retry。"""


def get_api_key() -> str:
    k = (os.environ.get("ALPHA_ALPHAVANTAGE_KEY") or "").strip()
    if k:
        return k
    try:
        k = KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        k = ""
    if not k:
        raise RuntimeError(
            "找不到 Alpha Vantage key。請設 ALPHA_ALPHAVANTAGE_KEY 環境變數，"
            f"或把 key 放進 {KEY_FILE}（該目錄已 gitignore）")
    return k


def _budget_state() -> dict:
    try:
        d = json.loads(BUDGET.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        d = {}
    today = date.today().isoformat()
    if d.get("date") != today:
        d = {"date": today, "used": 0}
    return d


def budget_left() -> int:
    return max(0, DAILY_BUDGET - _budget_state().get("used", 0))


def _spend(n: int = 1) -> None:
    d = _budget_state()
    d["used"] = int(d.get("used", 0)) + n
    BUDGET.parent.mkdir(parents=True, exist_ok=True)
    BUDGET.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _call(params: dict, timeout: int = 40) -> dict | str:
    """打一次 API。額度不足直接拋 BudgetExhausted，不排隊不重試。"""
    if budget_left() <= 0:
        raise BudgetExhausted(
            f"Alpha Vantage 當日額度已用完（上限 {DAILY_BUDGET}）。"
            "依額度紀律誠實拒絕，不排隊不重試——明天再來。")
    wait = MIN_INTERVAL_SEC - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    q = dict(params)
    q["apikey"] = get_api_key()
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "Alpha Research"})
    _last_call[0] = time.time()
    _spend(1)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    if q.get("datatype") == "csv":
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw[:400]}


def daily_prices(symbol: str, full: bool = True) -> tuple[list, str]:
    """日線 OHLCV。

    回傳 (rows, note)。rows 是 [{date, open, high, low, close, volume}, ...]
    由舊到新。**拿不到就回空 list 並在 note 說明原因，不假裝、不補零。**

    註：`TIME_SERIES_DAILY_ADJUSTED` 在 Alpha Vantage 已改為付費端點，
    免費層只有未調整的 `TIME_SERIES_DAILY`。
    **所以這裡的價格未做除權息調整**——用於報酬計算前必須自行處理，
    這一點必須隨資料一起傳下去，不能默默當成調整後價格用。
    """
    d = _call({
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "full" if full else "compact",
    })
    if not isinstance(d, dict):
        return [], "回傳非 JSON"
    if "Error Message" in d:
        return [], f"API 拒絕：{str(d['Error Message'])[:120]}"
    if "Note" in d or "Information" in d:
        msg = d.get("Note") or d.get("Information")
        return [], f"限流/說明訊息：{str(msg)[:160]}"
    ts = d.get("Time Series (Daily)")
    if not ts:
        return [], f"無時間序列欄位（回傳鍵：{list(d.keys())[:4]}）"
    rows = []
    for day, v in sorted(ts.items()):
        try:
            rows.append({
                "date": day,
                "open": float(v["1. open"]), "high": float(v["2. high"]),
                "low": float(v["3. low"]), "close": float(v["4. close"]),
                "volume": float(v["5. volume"]),
            })
        except (KeyError, ValueError):
            continue
    return rows, "ok（未做除權息調整）"


def listing_status(state: str = "delisted", on_date: str | None = None) -> str:
    """上市/下市名冊 CSV。這一半已證實免費可用。"""
    p = {"function": "LISTING_STATUS", "state": state, "datatype": "csv"}
    if on_date:
        p["date"] = on_date
    r = _call(p)
    return r if isinstance(r, str) else json.dumps(r)[:400]


if __name__ == "__main__":
    print(f"當日剩餘額度：{budget_left()} / {DAILY_BUDGET}")
    print(f"key 來源：{'環境變數' if os.environ.get('ALPHA_ALPHAVANTAGE_KEY') else KEY_FILE}")
