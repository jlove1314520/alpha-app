# -*- coding: utf-8 -*-
"""抓追蹤美股標的的下一次財報公布日期，寫成 data/earnings_calendar.json。

背景（使用者原話）：「盤前盤後的價值來自『知道誰要公布財報』。」財報前後常見
股價劇烈波動，搭配 P2「美股盤前盤後」功能，讓使用者知道接下來哪一天要注意。

資料源：yfinance `Ticker.get_calendar()`（免金鑰）——回傳下一次財報日期（可能是
單一日期或一段區間，Yahoo Finance 自己有時候只能給出估計區間）+ EPS/營收估計值。
涵蓋範圍跟 `fetch_quotes_us.py` 的 `US_TICKERS` 保持一致（同一份清單，複製常數+
註解交代來源，不跨檔案 import，同既有慣例）。

**公布時段（盤前/盤後）是推估值，不是保證**：yfinance 沒有直接給「這次公布是
盤前(BMO)還是盤後(AMC)」的明確欄位，這裡改用「這家公司過去財報公布時間點」
（`get_earnings_dates()` 歷史紀錄裡最近一筆的時間）當推估依據——公司通常固定
在盤前或盤後公布（例如蘋果一直都是盤後），但**這是推估，不是官方保證**，公司
偶爾會改變公布時間，這裡誠實標記 `session_basis` 說明推估邏輯，不是把推估值
當成確定的官方時段。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "earnings_calendar.json"
TW_TZ = timezone(timedelta(hours=8))

# 跟 fetch_quotes_us.py 的 US_TICKERS 保持一致（兩支腳本各自獨立、不跨檔案
# import，同既有慣例——這份清單改動時要記得同步兩邊）。
US_TICKERS = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN"]


def _estimate_session(ticker: yf.Ticker) -> tuple[str, str]:
    """回傳 (推估時段'pre'/'post'/'unknown', 推估依據說明字串)。"""
    try:
        hist = ticker.get_earnings_dates(limit=4)
        if hist is None or hist.empty:
            return "unknown", "無歷史財報公布時間紀錄可供推估"
        # 找最近一筆「已經發生過」（Reported EPS不是NaN）的歷史紀錄，用它的公布
        # 時刻（小時）推估：接近開盤前(<12點)算盤前，接近收盤後(>=12點)算盤後。
        reported = hist.dropna(subset=["Reported EPS"]) if "Reported EPS" in hist.columns else hist
        if reported.empty:
            return "unknown", "無已公布(非估計)的歷史財報時間可供推估"
        last_dt = reported.index[0]  # get_earnings_dates()回傳依日期新到舊排序
        hour = last_dt.hour
        if hour < 12:
            return "pre", f"依最近一次歷史財報公布時間({last_dt.strftime('%Y-%m-%d %H:%M %Z')})推估，通常在開盤前"
        return "post", f"依最近一次歷史財報公布時間({last_dt.strftime('%Y-%m-%d %H:%M %Z')})推估，通常在收盤後"
    except Exception as e:
        return "unknown", f"推估失敗：{e}"


def fetch_one(ticker_str: str) -> dict | None:
    t = yf.Ticker(ticker_str)
    try:
        cal = t.get_calendar()
    except Exception as e:
        print(f"  ・{ticker_str} get_calendar() 失敗：{e}")
        return None
    if not cal or not cal.get("Earnings Date"):
        print(f"  ・{ticker_str} 沒有下一次財報日期資料")
        return None
    dates = cal["Earnings Date"]
    session, basis = _estimate_session(t)
    return {
        "next_earnings_date": dates[0].isoformat() if dates else None,
        "next_earnings_date_range": [d.isoformat() for d in dates] if len(dates) > 1 else None,
        "estimated_session": session,
        "session_basis": basis,
        "eps_estimate": cal.get("Earnings Average"),
        "revenue_estimate": cal.get("Revenue Average"),
    }


def main():
    earnings = {}
    errors = []
    for tk in US_TICKERS:
        try:
            row = fetch_one(tk)
            if row:
                earnings[tk] = row
        except Exception as e:
            print(f"  ・{tk} 失敗：{e}")
            errors.append(f"{tk}: {e}")

    payload = {
        "meta": {
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "source": "yfinance Ticker.get_calendar() + get_earnings_dates()（免金鑰）",
            "coverage": f"{len(earnings)}/{len(US_TICKERS)} 檔",
            "errors": errors,
            "session_disclaimer": (
                "estimated_session（盤前/盤後）是根據該公司過去財報公布時間點的推估，"
                "不是官方保證的公布時段，公司偶爾會改變公布時間。"
            ),
        },
        "earnings": earnings,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(earnings)}/{len(US_TICKERS)} 檔有資料")
    if errors:
        print(f"部分失敗（不中止）：{errors}")


if __name__ == "__main__":
    main()
