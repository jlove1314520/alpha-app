# -*- coding: utf-8 -*-
"""抓 USD/TWD 匯率，寫成 data/fx.json（2026-08-27 新增，取代 client-side FinMind
TaiwanExchangeRate——那是 STATUS.json 列出的 P0 項目：NT$/US$ 幣值切換依賴
FinMind，額度耗盡就失效，這裡改用 yfinance `TWD=X`（免費、無明顯流量限制，
跟 `fetch_market_us.py` 同一個資料源），掛進 market.yml 每日跑一次即可
（匯率不需要盤中頻率）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "fx.json"
TW_TZ = timezone(timedelta(hours=8))


def main():
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "errors": []}
    try:
        hist = yf.Ticker("TWD=X").history(period="5d")
        if hist.empty:
            raise RuntimeError("yfinance TWD=X 回傳空資料")
        last = hist.iloc[-1]
        last_date = hist.index[-1].strftime("%Y-%m-%d")
        payload["usd_twd"] = {
            "rate": round(float(last["Close"]), 4),
            "date": last_date,
            "source": "yfinance TWD=X",
        }
    except Exception as e:
        print(f"匯率抓取失敗：{e}")
        payload["errors"].append(f"usd_twd: {e}")
        payload["usd_twd"] = None

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：{payload.get('usd_twd')}")


if __name__ == "__main__":
    main()
