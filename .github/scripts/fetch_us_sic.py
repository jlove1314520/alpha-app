# -*- coding: utf-8 -*-
"""美股類股分類：抓 SEC EDGAR 官方 SIC 代碼，寫成 data/us_sic.json（建置一.3）。

資料源：SEC EDGAR 官方公開端點，免金鑰。
1. https://www.sec.gov/files/company_tickers.json —— ticker → CIK 對映表
2. https://data.sec.gov/submissions/CIK{cik}.json —— 該公司的 sic / sicDescription

涵蓋範圍：跟 fetch_quotes_us.py 的 US_TICKERS 用同一份清單（含 2026-09-10
建置一.3 新增的 UMC/ASX/CHT 三檔台股ADR），兩支腳本各自維護一份常數（理由同
fetch_quotes_us.py 檔頭：兩個獨立腳本沒有共用 import 路徑，複製常數比硬拉
相依乾淨；research/sec_edgar_client.py 是研究帽擁有的檔案，見 CLAUDE.md
「帽子規則」檔案歸屬，這裡不跨帽子import，改自己重寫一份精簡版）。

SIC 是公司登記類別，變動極罕見（公司變更主要業務才會改），不需要每次盤中
都重抓——這支腳本跟 fetch_market_us.py 排在同一個 market.yml（每日最多3次），
不進 quotes.yml 那個10分鐘一次的高頻迴圈。

SEC 公平使用政策要求識別用的 User-Agent，這裡刻意不用使用者本人 email（
jlove201314@yahoo.com.tw）——那是給不相關第三方服務的請求，不該外流個資，
用專案識別用的佔位信箱即可（跟 research/sec_edgar_client.py 同款作法）。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "us_sic.json"

# 跟 fetch_quotes_us.py 的 US_TICKERS 同一份清單。
US_TICKERS = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN", "UMC", "ASX", "CHT"]

HEADERS = {"User-Agent": "AlphaApp-USSectorSIC contact@alpha-app-project.example"}
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def get_cik_map() -> dict[str, int]:
    r = requests.get(TICKER_MAP_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()
    return {v["ticker"]: v["cik_str"] for v in data.values()}


def main():
    try:
        cik_map = get_cik_map()
    except Exception as e:
        print(f"錯誤：抓 SEC ticker→CIK 對映表（company_tickers.json）失敗：{e}")
        sys.exit(1)

    tickers_out = {}
    errors = []
    for tk in US_TICKERS:
        cik = cik_map.get(tk)
        if cik is None:
            errors.append({"ticker": tk, "reason": "在 SEC company_tickers.json 找不到對映的 CIK"})
            print(f"  ・{tk}: 找不到 CIK")
            continue
        cik_padded = str(cik).zfill(10)
        url = SUBMISSIONS_URL.format(cik=cik_padded)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            d = r.json()
            sic = d.get("sic")
            sic_desc = d.get("sicDescription")
            if not sic:
                errors.append({"ticker": tk, "reason": "submissions 回應沒有 sic 欄位"})
                print(f"  ・{tk}: 沒有 sic 欄位")
                continue
            tickers_out[tk] = {
                "cik": cik,
                "sic": sic,
                "sic_description": sic_desc,
                "entity_name": d.get("name"),
            }
            print(f"  ・{tk}: SIC {sic}（{sic_desc}）")
        except Exception as e:
            errors.append({"ticker": tk, "reason": str(e)})
            print(f"  ・{tk} 失敗：{e}")
        time.sleep(0.15)  # SEC 公平使用政策建議 ~10 req/sec 上限內，保守間隔（9檔遠低於門檻）

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "SEC EDGAR company_tickers.json（ticker→CIK）+ submissions/CIK{cik}.json（sic/sicDescription），官方免金鑰",
        "tickers": tickers_out,
        "errors": errors,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(tickers_out)}/{len(US_TICKERS)} 檔成功" + (f"，失敗：{errors}" if errors else ""))

    if not tickers_out:
        print("錯誤：一檔都沒抓到")
        sys.exit(1)


if __name__ == "__main__":
    main()
