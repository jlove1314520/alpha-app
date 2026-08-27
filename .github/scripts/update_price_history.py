# -*- coding: utf-8 -*-
"""每日排程更新 data/price_history.json 的個股OHLCV歷史，累積式寫回（2026-08-27）。

背景：`research/generate_scores_live.py`（P1，JSON-only上線評分路徑）的
`technical`（技術型態）因子需要per股票的每日價量歷史才能算「站上60日均線×
20/60日均量比」——起始種子由 `research/build_price_history.py` 讀research端
FinMind歷史parquet快取一次回補（2101檔、90個交易日），這支腳本負責之後
每天累積式append「今天的最新一筆」，跟 `update_fundamentals_daily.py`/
`update_stock_financials.py` 同一套「累積式寫回」模式。

資料源（全部官方開放資料，免金鑰）：
- TWSE：`openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`——全市場上市
  股票最新一個交易日的OHLCV快照（含ETF/權證等非股票證券，這裡不特別過濾，
  跟fundamentals.json的做法一致：多存不影響評分，評分端只查有股票資料的代碼）。
- TPEx：`www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes`——上櫃股票對應版本，
  欄位命名不同（`Close`/`Open`/`High`/`Low`/`TradingShares`），語意對應。

**已知簡化，誠實揭露**：收盤價是原始收盤價，未還原權息——除權息當天前後
MA60計算會有跳空失真，這是JSON-only路徑的已知限制，不是bug，見
`generate_scores_live.py`檔頭說明。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "price_history.json"
TW_TZ = timezone(timedelta(hours=8))

STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
PRICE_HISTORY_DAYS = 90


def _get_retry(url: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """同 update_fundamentals_daily.py 的 _get_retry()，自成一體複製（既有慣例）。"""
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def fetch_twse() -> dict[str, dict]:
    r = _get_retry(STOCK_DAY_ALL_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("STOCK_DAY_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("Code")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("ClosingPrice"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("OpeningPrice")),
            "high": _num(row.get("HighestPrice")),
            "low": _num(row.get("LowestPrice")),
            "close": close,
            "volume": _num(row.get("TradeVolume")),
        }
    return out


def fetch_tpex() -> dict[str, dict]:
    r = _get_retry(TPEX_QUOTES_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_mainboard_quotes 回傳非預期格式（可能是無效路徑回傳的HTML）")
    out = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("Close"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("Open")),
            "high": _num(row.get("High")),
            "low": _num(row.get("Low")),
            "close": close,
            "volume": _num(row.get("TradingShares")),
        }
    return out


def merge_rows(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = [r for r in (existing or []) if r.get("date") != latest["date"]]
    rows.append(latest)
    rows.sort(key=lambda r: r["date"])
    return rows[-PRICE_HISTORY_DAYS:]


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在——這支腳本設計上只做累積更新，"
              "第一次的完整快照要用 research/build_price_history.py 手動產生並 commit。")
        raise SystemExit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prices = payload.setdefault("prices", {})

    errors = []
    twse_updated = tpex_updated = 0
    try:
        twse = fetch_twse()
        for code, latest in twse.items():
            prices[code] = merge_rows(prices.get(code), latest)
        twse_updated = len(twse)
    except Exception as e:
        print(f"價量(TWSE) 更新失敗：{e}")
        errors.append(f"price_twse: {e}")

    try:
        tpex = fetch_tpex()
        for code, latest in tpex.items():
            prices[code] = merge_rows(prices.get(code), latest)
        tpex_updated = len(tpex)
    except Exception as e:
        print(f"價量(TPEx) 更新失敗：{e}")
        errors.append(f"price_tpex: {e}")

    payload.setdefault("meta", {})
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["twse_updated_count"] = twse_updated
    payload["meta"]["tpex_updated_count"] = tpex_updated
    payload["meta"]["errors"] = errors
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：TWSE {twse_updated} 檔+TPEx {tpex_updated} 檔（合計 {len(prices)} 檔有資料）")
    if errors:
        print(f"部分失敗（不中止，維持既有資料）：{errors}")


if __name__ == "__main__":
    main()
