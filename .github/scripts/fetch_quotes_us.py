# -*- coding: utf-8 -*-
"""抓美股盤中近即時報價，寫成 data/quotes_us.json。

資料源：Finnhub 免費額度（/quote 端點，每檔一次呼叫，免費層約 60 次/分鐘，這裡
涵蓋的檔數遠低於這個上限）。API key 從環境變數 FINNHUB_API_KEY 讀（GitHub Actions
裡對應 secrets.FINNHUB_API_KEY），**絕對不寫死在程式碼裡**。沒有設定 key 時明確
失敗、印出清楚的錯誤訊息，不會生出假資料或悄悄跳過。

涵蓋範圍：alpha-data/config.py 的 US_TICKERS（跟 SEC EDGAR 財報抓取共用同一份
清單，不重複維護第二份）+ App 預設美股自選股（目前沒有，先只用 US_TICKERS）。
"""
from __future__ import annotations

import json
import os
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_us.json"

# 跟 alpha-data/config.py 的 US_TICKERS 保持一致（兩個獨立 repo，這裡沒有 import
# 路徑可以直接重用，用複製一份常數 + 註解交代來源的方式，不是遺漏同步）。
US_TICKERS = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN"]

FINNHUB_URL = "https://finnhub.io/api/v2/quote"


def main():
    api_key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        print("錯誤：環境變數 FINNHUB_API_KEY 未設定。這支腳本設計上一定要從 GitHub "
              "Secrets 讀 key（workflow 檔案裡是 ${{ secrets.FINNHUB_API_KEY }}），"
              "本機測試要跑這支腳本，先 export FINNHUB_API_KEY=你的key 再執行。"
              "沒有 key 就不產生 quotes_us.json，不能假裝有資料。")
        sys.exit(1)

    quotes = {}
    failed = []
    for tk in US_TICKERS:
        try:
            r = requests.get(FINNHUB_URL, params={"symbol": tk, "token": api_key}, timeout=15)
            r.raise_for_status()
            d = r.json()
            price = d.get("c")  # current price
            prev_close = d.get("pc")
            if not price:
                failed.append(tk)
                continue
            chg = round(price - prev_close, 4) if prev_close else None
            pct = round(chg / prev_close * 100, 3) if (chg is not None and prev_close) else None
            quotes[tk] = {
                "price": price,
                "prev_close": prev_close,
                "change": chg,
                "change_pct": pct,
                "high": d.get("h"),
                "low": d.get("l"),
                "open": d.get("o"),
                "quote_time": d.get("t"),  # Finnhub 回傳 unix timestamp
            }
        except Exception as e:
            print(f"  ・{tk} 失敗：{e}")
            failed.append(tk)

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Finnhub /quote（免費額度）",
        "quotes": quotes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(quotes)}/{len(US_TICKERS)} 檔成功" + (f"，失敗：{failed}" if failed else ""))

    if not quotes:
        sys.exit(1)


if __name__ == "__main__":
    main()
