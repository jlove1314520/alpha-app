# -*- coding: utf-8 -*-
"""ADR 溢價卡：quotes_us × fx.json ÷ ADR 比率，對 quotes_tw，算溢價 %（建置一.3）。

寫成 data/adr_premium.json。純計算腳本，不打任何外部 API——三個輸入檔
（data/quotes_us.json／data/quotes_tw.json／data/fx.json）都已經由
quotes.yml 的其他步驟抓好，這裡只做除法，零額外請求，可以安心放進10分鐘
一次的高頻迴圈。

溢價％定義：implied_tw_price = 美股ADR現價(USD) × 美元/台幣匯率 ÷ ADR比率
            premium_pct = (implied_tw_price − 台股現價) ÷ 台股現價 × 100

ADR 比率是固定值（公司股本結構變動才會改，不是每天變的資料），寫死在這裡
並附官方來源，不是憑印象猜的數字（2026-09-10 三來源查證紀錄）：

- TSM（台積電2330）：1 ADS＝5股普通股。
  來源1（SEC EDGAR官方）：CIK 1046179 20-F系列申報
  （https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001046179&type=20-F）。
  來源2：多筆Form 4內部人申報换算一致確認5:1（stocktitan.net彙整之SEC filings）。
  來源3：市場慣例引用（FXBrokerTrust等第三方說明頁）與1997年ADR掛牌以來比率
  未變的公開紀錄一致。
- UMC（聯電2303）：1 ADS＝5股普通股。
  來源1（公司官方）：UMC官方FAQ（https://www.umc.com/en/Html/faqs）揭露
  總ADS數117,228,617對應普通股數586,143,085，586,143,085÷117,228,617≈5。
  來源2（SEC EDGAR官方）：CIK 1033767 20-F系列申報，J.P. Morgan為存託機構。
  來源3：市場資料頁（Morningstar等）一致列為NYSE:UMC對應5股普通股。
- ASX（日月光投控3711，ASE Technology Holding）：1 ADS＝2股普通股。
  來源1（Nasdaq官方）：上市名稱本身即為「American Depositary Shares (each
  representing Two Common Shares)」。
  來源2（SEC EDGAR官方）：CIK 1122411 申報文件（S-8等）一致。
  來源3：Nasdaq市場資料頁（financials/earnings等分頁標題）一致標註。
- CHT（中華電信2412）：1 ADS＝10股普通股。
  來源1（SEC EDGAR官方）：CIK 1132924 歷年20-F申報
  （https://www.sec.gov/Archives/edgar/data/1132924/）一致揭露
  「each ADS represents ten common shares」，JPMorgan Chase Bank為存託機構。
  來源2：第三方新聞頁（ad-hoc-news.de等）轉述一致。
  來源3：2018/2021/2024多個年度20-F封面比率一致，未變動過。

**已知限制誠實揭露**：比率寫死，若未來發生存託比率調整（歷史上部分ADR
確曾發生過比率變更），這裡不會自動反映，需要人工比對官方公告後手動改
常數——SEC沒有一個「即時回傳目前比率」的官方端點，每次重新核對官方申報
文件比每天打一次高成本查詢更符合「取得方式鐵律」。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "adr_premium.json"

ADR_RATIOS = {
    "TSM": {
        "tw_code": "2330", "ratio": 5,
        "source": "SEC EDGAR 20-F CIK 1046179；1 ADS＝5股普通股（1997年掛牌以來未變）",
    },
    "UMC": {
        "tw_code": "2303", "ratio": 5,
        "source": "UMC官方FAQ（umc.com/en/Html/faqs）+ SEC EDGAR 20-F CIK 1033767；1 ADS＝5股普通股",
    },
    "ASX": {
        "tw_code": "3711", "ratio": 2,
        "source": "Nasdaq官方上市名稱 + SEC EDGAR CIK 1122411；1 ADS＝2股普通股",
    },
    "CHT": {
        "tw_code": "2412", "ratio": 10,
        "source": "SEC EDGAR 20-F CIK 1132924；1 ADS＝10股普通股",
    },
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    quotes_us = load_json(DATA_DIR / "quotes_us.json")
    quotes_tw = load_json(DATA_DIR / "quotes_tw.json")
    fx = load_json(DATA_DIR / "fx.json")

    us_quotes = quotes_us.get("quotes", {})
    tw_quotes = quotes_tw.get("quotes", {})
    usd_twd = fx.get("usd_twd", {})
    fx_rate = usd_twd.get("rate")
    fx_date = usd_twd.get("date")

    rows = {}
    errors = []
    for us_ticker, info in ADR_RATIOS.items():
        tw_code = info["tw_code"]
        ratio = info["ratio"]
        us_q = us_quotes.get(us_ticker)
        tw_q = tw_quotes.get(tw_code)
        if not us_q or us_q.get("price") is None:
            errors.append({"ticker": us_ticker, "reason": "美股報價缺失（data/quotes_us.json 未涵蓋此檔或尚未抓到）"})
            print(f"  ・{us_ticker}: 美股報價缺失")
            continue
        if not tw_q or tw_q.get("price") is None:
            errors.append({"ticker": us_ticker, "reason": f"台股 {tw_code} 報價缺失"})
            print(f"  ・{us_ticker}: 台股 {tw_code} 報價缺失")
            continue
        if not fx_rate:
            errors.append({"ticker": us_ticker, "reason": "匯率缺失（data/fx.json）"})
            print(f"  ・{us_ticker}: 匯率缺失")
            continue
        us_price = us_q["price"]
        tw_price = tw_q["price"]
        implied_tw_price = us_price * fx_rate / ratio
        premium_pct = (implied_tw_price - tw_price) / tw_price * 100
        rows[us_ticker] = {
            "tw_code": tw_code,
            "ratio": ratio,
            "source": info["source"],
            "us_price": us_price,
            "us_quote_time": us_q.get("quote_time"),
            "tw_price": tw_price,
            "tw_quote_time": tw_q.get("time"),
            "tw_quote_date": tw_q.get("date"),
            "fx_rate": fx_rate,
            "fx_date": fx_date,
            "implied_tw_price": round(implied_tw_price, 3),
            "premium_pct": round(premium_pct, 3),
        }
        print(f"  ・{us_ticker}: implied={implied_tw_price:.2f} tw={tw_price} premium={premium_pct:.2f}%")

    out = {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "quotes_us.json × fx.json ÷ ADR比率，對 quotes_tw.json 計算溢價（比率來源見各檔ADR_RATIOS/rows.source，三來源查證紀錄見本檔檔頭docstring）",
        "rows": rows,
        "errors": errors,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(rows)}/{len(ADR_RATIOS)} 檔成功" + (f"，缺漏：{errors}" if errors else ""))


if __name__ == "__main__":
    main()
