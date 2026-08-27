# -*- coding: utf-8 -*-
"""抓美股盤中近即時報價，寫成 data/quotes_us.json。

資料源：Finnhub 免費額度（/quote 端點，每檔一次呼叫，免費層約 60 次/分鐘，這裡
涵蓋的檔數遠低於這個上限）。API key 從環境變數 FINNHUB_API_KEY 讀（GitHub Actions
裡對應 secrets.FINNHUB_API_KEY），**絕對不寫死在程式碼裡**。沒有設定 key 時明確
失敗、印出清楚的錯誤訊息，不會生出假資料或悄悄跳過。

涵蓋範圍：alpha-data/config.py 的 US_TICKERS（跟 SEC EDGAR 財報抓取共用同一份
清單，不重複維護第二份）+ App 預設美股自選股（目前沒有，先只用 US_TICKERS）。

**2026-08-26 補上休市/交易時段判斷（呼應 fetch_quotes_tw.py 同一輪修正）**：
Finnhub 的 `/quote` 端點本身在非交易時段也會回傳最後一個已知價位（不是回傳空值），
所以這支腳本原本就不太會像台股那支一樣把「休市」誤判成「故障」——但補上跟台股
一致的 `meta`（是否交易時段、查詢/成功檔數）方便之後比對排查，且改成「非交易
時段即使查到 0 檔也不當硬故障」，跟台股那支的判斷邏輯保持一致。
"""
from __future__ import annotations

import json
import os
import sys
import requests
import yfinance as yf
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

US_TZ = ZoneInfo("America/New_York")  # 用 zoneinfo 而非固定 UTC offset：美股有夏令時間，
# 固定 offset 會在夏令/冬令切換時算錯交易時段，台股沒有這個問題（台灣不實施夏令時間）。

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_us.json"

# 跟 alpha-data/config.py 的 US_TICKERS 保持一致（兩個獨立 repo，這裡沒有 import
# 路徑可以直接重用，用複製一份常數 + 註解交代來源的方式，不是遺漏同步）。
US_TICKERS = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN"]

FINNHUB_URL = "https://finnhub.io/api/v1/quote"  # 2026-08-26 修正：原本寫成 v2，Finnhub
# 沒有 v2/quote 這個端點——實測 v2 回傳 HTTP 200 但內容是一個 HTML 頁面（不是 JSON），
# r.raise_for_status() 不會發現異常（200 本身不是錯誤狀態碼），但 r.json() 解析 HTML
# 會丟例外，被下面的 try/except 吃掉、記成該檔「失敗」——6 檔全部這樣失敗，
# matched=0。真正的端點是 v1（實測：不帶有效 key 時回傳 401 + 正確的 JSON 錯誤訊息
# {"error":"Invalid API key."}，證實 v1 才是有在處理請求的正確端點）。


def is_us_trading_window(now: datetime) -> bool:
    """粗略判斷：週一至五 09:30–16:00 美東時間。**已知簡化，誠實揭露**：沒有扣除
    美股國定假日，理由跟 fetch_quotes_tw.py 的 `is_tw_trading_window()` 一樣——
    這裡也只拿來決定 exit code，不影響資料本身正確性。"""
    wd = now.weekday()
    minutes = now.hour * 60 + now.minute
    return wd <= 4 and 9 * 60 + 30 <= minutes < 16 * 60


def main():
    now_us = datetime.now(US_TZ)
    trading_window = is_us_trading_window(now_us)
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
            # 2026-08-26 新增診斷輸出：每檔印HTTP狀態碼+回應前120字元，之後端點/格式
            # 出問題能一眼看出，不用再靠猜（這次v1/v2打錯的教訓）。回應本身理論上不會
            # 回顯金鑰，但保險起見還是先把字串裡任何看起來像金鑰的片段遮掉再印。
            body_preview = r.text[:120].replace(api_key, "***") if api_key else r.text[:120]
            print(f"  ・{tk}: HTTP {r.status_code}，回應前120字元：{body_preview!r}")
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
            # requests 的 HTTPError 訊息本身會echo回完整請求URL（含?token=...），這裡
            # 印例外前也要遮蔽，不能只顧到上面body_preview那一行——這是實測時才發現的
            # 遮蔽漏洞，不是理論上的顧慮（本機測試時親眼看到金鑰被印進錯誤訊息）。
            msg = str(e).replace(api_key, "***") if api_key else str(e)
            print(f"  ・{tk} 失敗：{msg}")
            failed.append(tk)

    # 2026-08-27 新增：自選股sparkline（STATUS.json列的P0缺口）。只有6檔，每次都
    # 直接重抓（不像台股那支要對STOCK_DAY做每日快取），yfinance批次抓不會對Finnhub
    # 造成額外負擔（兩個不同資料源）。
    try:
        hist = yf.download(US_TICKERS, period="1mo", auto_adjust=False, progress=False, group_by="ticker")
        for tk in US_TICKERS:
            if tk not in quotes:
                continue
            try:
                closes = hist[tk]["Close"].dropna().tail(20).tolist()
                if closes:
                    quotes[tk]["sparkline"] = [round(float(c), 2) for c in closes]
            except Exception as e:
                print(f"  - {tk} sparkline 解析失敗：{e}")
    except Exception as e:
        print(f"  - sparkline 批次抓取失敗（不影響報價本身）：{e}")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Finnhub /quote（免費額度）",
        "meta": {
            "trading_window": trading_window,
            "queried": len(US_TICKERS),
            "matched": len(quotes),
        },
        "quotes": quotes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(quotes)}/{len(US_TICKERS)} 檔成功" + (f"，失敗：{failed}" if failed else "")
          + f"，目前{'在' if trading_window else '不在'}交易時段（美東時間 {now_us.strftime('%Y-%m-%d %H:%M:%S')}）")

    if not quotes and trading_window:
        print("錯誤：交易時段內卻一檔報價都沒抓到，判定為真故障")
        sys.exit(1)
    if not quotes:
        print("非交易時段且一檔報價都沒抓到——理論上不該發生(Finnhub通常連休市都回傳最後價位)，"
              "但既然發生了仍誠實回報非0結束碼")
        sys.exit(1)


if __name__ == "__main__":
    main()
