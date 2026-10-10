# -*- coding: utf-8 -*-
"""抓美股分析師評等分佈（Finnhub 免費層 /stock/recommendation），寫成 data/us_analyst_reco.json。

常備.開發-15（2026-10-11）：個股頁「券商報告雷達」改為「目標價與評等（公開來源）」。
三來源查證紀錄見 docs/FIRST_HAND_SOURCES.md「常備.開發-15」小節，結論：
- 美股「評等分佈」（強力買進/買進/持有/賣出/強力賣出 家數）：Finnhub /stock/recommendation，
  官方 swagger（https://finnhub.io/static/swagger.json）該端點沒有 premium 標記 → 免費層可用。
- 美股「目標價」：Finnhub /stock/price-target 官方標「Premium required.」→ 待採購，本腳本不打。
- 台股：證交所／櫃買 OpenAPI 與 FinMind 都沒有券商目標價／評等資料集 → App 只顯示誠實說明。

涵蓋範圍：跟 fetch_quotes_us.py 共用同一份 US_TICKERS（目前 9 檔），不另外維護清單。
頻率：評等每月才更新一次，所以掛在 quotes.yml（每 10 分鐘）但**本腳本自己節流**：
既有檔案 generated_at 未滿 20 小時就直接結束、不打 API → 實際約每日 1 次 × 9 檔 = 9 次/日，
遠低於 Finnhub 免費層約 60 次/分鐘。
API key 從環境變數 FINNHUB_API_KEY 讀（GitHub Secrets），絕不寫進檔案；印錯誤前先遮蔽 key。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_quotes_us import US_TICKERS  # noqa: E402  共用同一份清單

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "us_analyst_reco.json"
URL = "https://finnhub.io/api/v1/stock/recommendation"
MIN_REFRESH_HOURS = 20
KEEP_PERIODS = 4  # 只留最近 4 期（月），夠看調升／調降趨勢


def _fresh_enough(now: datetime) -> bool:
    try:
        old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(old["generated_at"])
        return now - ts < timedelta(hours=MIN_REFRESH_HOURS) and bool(old.get("tickers"))
    except Exception as e:  # 檔案不存在或格式壞掉 → 視為需要重抓
        print(f"既有檔案無法判斷新鮮度，照常抓取：{e}")
        return False


def main():
    now = datetime.now(timezone.utc)
    if _fresh_enough(now):
        print(f"us_analyst_reco.json 未滿 {MIN_REFRESH_HOURS} 小時，略過（評等每月才更新）")
        return
    api_key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        print("錯誤：環境變數 FINNHUB_API_KEY 未設定，不產生 us_analyst_reco.json（不能假裝有資料）。")
        sys.exit(1)

    tickers, failed = {}, []
    for tk in US_TICKERS:
        try:
            r = requests.get(URL, params={"symbol": tk, "token": api_key}, timeout=15)
            print(f"  ・{tk}: HTTP {r.status_code}，回應前120字元：{r.text[:120].replace(api_key, '***')!r}")
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list):
                failed.append({"symbol": tk, "reason": "回應不是陣列"})
                continue
            rows = [x for x in rows if isinstance(x, dict) and x.get("period")]
            rows.sort(key=lambda x: x["period"], reverse=True)
            if not rows:
                failed.append({"symbol": tk, "reason": "Finnhub 回傳空陣列（無分析師覆蓋）"})
                continue
            tickers[tk] = [{k: x.get(k) for k in ("period", "strongBuy", "buy", "hold", "sell", "strongSell")}
                           for x in rows[:KEEP_PERIODS]]
        except Exception as e:
            failed.append({"symbol": tk, "reason": str(e).replace(api_key, "***")[:200]})
            print(f"  ・{tk} 失敗：{failed[-1]['reason']}")
        time.sleep(1.1)

    if not tickers:
        print(f"錯誤：{len(US_TICKERS)} 檔全部失敗，不覆寫既有檔案。")
        sys.exit(1)
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "source": "Finnhub /stock/recommendation（免費層；彙整多家券商評等家數，非單一券商報告）",
        "coverage": US_TICKERS,
        "price_target": "未提供：Finnhub /stock/price-target 為付費端點（Premium required），待採購",
        "tickers": tickers,
        "failed": failed,
    }
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"寫出 {OUT_PATH.name}：成功 {len(tickers)} 檔、失敗 {len(failed)} 檔")


if __name__ == "__main__":
    main()
