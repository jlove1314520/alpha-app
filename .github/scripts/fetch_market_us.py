# -*- coding: utf-8 -*-
"""抓美股四大指數，寫成 data/market_us.json（2026-08-26，P0-1 架構修正同一批）。

資料源：yfinance（免費、無明顯流量限制，跟 `research/yf_price_client.py` 用同一個
套件，這裡是 GitHub Actions 自成一體的獨立複製，不跨目錄 import，同
`fetch_quotes_tw.py`/`fetch_market_tw.py` 的既有慣例）。

四大指數：道瓊(^DJI)、S&P 500(^GSPC)、那斯達克(^IXIC)、費城半導體(^SOX)。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "market_us.json"

INDICES = {
    "^DJI": "道瓊工業指數",
    "^GSPC": "S&P 500",
    "^IXIC": "那斯達克綜合指數",
    "^SOX": "費城半導體指數",
}


def main():
    indices = {}
    failed = []
    for ticker, name in INDICES.items():
        try:
            # 2026-08-27：period 從 5d 改 1mo，多抓的天數用來附上近20日收盤序列給
            # App畫sparkline（STATUS.json列的P0項目：大盤速覽目前只有價格沒有走勢
            # 線），不需要額外對FinMind多打一次請求。
            h = yf.Ticker(ticker).history(period="1mo", auto_adjust=False)
            if len(h) < 2:
                failed.append(ticker)
                continue
            last, prev = h["Close"].iloc[-1], h["Close"].iloc[-2]
            indices[ticker] = {
                "name": name,
                "close": round(float(last), 2),
                "change": round(float(last - prev), 2),
                "change_pct": round(float((last / prev - 1) * 100), 3),
                "as_of": h.index[-1].strftime("%Y-%m-%d"),
                "sparkline": [round(float(c), 2) for c in h["Close"].tail(20).tolist()],
            }
        except Exception as e:
            print(f"  ・{ticker} 失敗：{e}")
            failed.append(ticker)

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "indices": indices,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(indices)}/{len(INDICES)} 檔成功" + (f"，失敗：{failed}" if failed else ""))

    if not indices:
        sys.exit(1)


if __name__ == "__main__":
    main()
