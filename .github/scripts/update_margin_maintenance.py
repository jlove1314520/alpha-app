# -*- coding: utf-8 -*-
"""每日排程更新 data/margin_maintenance.json（大盤融資維持率），取代原本卡在
C:\\alpha\\alpha-data\\compute_margin_maintenance.py 的手動、無排程狀態（STATUS.json
列的 P1 項目：目前只有1筆、手動執行、會安靜過期）。

公式：大盤融資維持率 = 全市場融資擔保品市值 ÷ 全市場融資金額 × 100%。

**逐股融資擔保品市值（分子）改用 TWSE 官方開放資料，不用 FinMind**：
- `MI_MARGN`：全市場每檔股票的融資今日餘額（張）。
- `STOCK_DAY_ALL`：全市場每檔股票的當日收盤價。
兩個都是免金鑰、一次回傳全市場的官方端點（跟 `alpha-data/compute_margin_maintenance.py`
用的是同一組，這裡是自成一體的獨立複製，不跨目錄 import，同 `fetch_market_tw.py`
等既有慣例）。

**已知限制，誠實揭露，不是隱藏**：分母（全市場融資金額，即銀行/證金公司實際
貸出去的錢）目前沒有對應的 TWSE openapi 端點可以直接拿到——TWSE 只公布逐股
「融資餘額(張)」，沒有公布全市場加總的「融資金額(元)」。這裡仍然使用 FinMind
`TaiwanStockTotalMarginPurchaseShortSale`（免token）當分母來源，是這支腳本
唯一保留的 FinMind 依賴，風險遠低於之前逐股迴圈打 FinMind：**這裡一天只呼叫
一次、抓的是全市場單一加總數字，不是逐股歷史**，額度耗盡機率低很多。如果這
唯一一次呼叫還是失敗，腳本會誠實跳過今天這筆（不寫入錯誤或猜測值），讓
history 停在最後一筆有效資料，App 的診斷橫幅會偵測到超過3天沒更新並提示。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "margin_maintenance.json"
TW_TZ = timezone(timedelta(hours=8))

MI_MARGN_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
FINMIND_URL = (
    "https://api.finmindtrade.com/api/v4/data"
    "?dataset=TaiwanStockTotalMarginPurchaseShortSale&start_date={start}"
)
HISTORY_DAYS_KEEP = 60


def _num(v):
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def fetch_margin_by_stock() -> tuple[dict[str, float], dict[str, dict]]:
    """回傳 (代號:融資今日餘額張數（給維持率算擔保品市值用）,
    代號:{today,prev,short_today}（給個股頁「融資融券」分頁用，merge進stock_detail.json）)。"""
    r = requests.get(MI_MARGN_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("MI_MARGN 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    lots_only = {}
    per_stock = {}
    for row in rows:
        code = row.get("股票代號")
        lots = _num(row.get("融資今日餘額"))
        if code and lots is not None:
            lots_only[code] = lots
        if code:
            per_stock[code] = {
                "margin_balance_today": lots,
                "margin_balance_prev": _num(row.get("融資前日餘額")),
                "short_balance_today": _num(row.get("融券今日餘額")),
            }
    return lots_only, per_stock


def fetch_close_by_stock() -> dict[str, float]:
    r = requests.get(STOCK_DAY_ALL_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("STOCK_DAY_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("Code")
        px = _num(row.get("ClosingPrice"))
        if code and px is not None:
            out[code] = px
    return out


def fetch_market_margin_money() -> tuple[str, float]:
    start = (datetime.now(TW_TZ).date() - timedelta(days=10)).isoformat()
    r = requests.get(FINMIND_URL.format(start=start), timeout=30)
    r.raise_for_status()
    data = r.json()
    rows = data.get("data", [])
    money_rows = [row for row in rows if row.get("name") == "MarginPurchaseMoney"]
    if not money_rows:
        raise RuntimeError("FinMind 沒有回傳 MarginPurchaseMoney（額度用盡或資料集異常）")
    last = money_rows[-1]
    return last["date"], last["TodayBalance"]


def merge_stock_detail_margin(per_stock: dict[str, dict]) -> None:
    """merge進 data/stock_detail.json（個股頁「融資融券」分頁用）。只合併「已經
    存在於stocks的代碼」（由update_stock_financials.py用t187ap06_L_ci「上市公司」
    清單建立），避免MI_MARGN涵蓋的非股票證券（若有）灌進來造成雜訊，跟
    fetch_market_tw.py合併三大法人時同一個原則。"""
    detail_path = REPO_ROOT / "data" / "stock_detail.json"
    if not detail_path.exists():
        return
    try:
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
    except Exception:
        return
    stocks = detail.setdefault("stocks", {})
    matched = 0
    for code, row in per_stock.items():
        if code in stocks:
            stocks[code]["margin"] = row
            matched += 1
    detail.setdefault("meta", {})["margin_source"] = "TWSE MI_MARGN（同一次呼叫，跟大盤融資維持率共用，不額外打）"
    detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"併入 {detail_path}：融資融券合併 {matched} 檔")


def main():
    margin_by_stock, margin_per_stock_detail = fetch_margin_by_stock()
    close_by_stock = fetch_close_by_stock()
    print(f"融資個股 {len(margin_by_stock)} 檔，收盤價個股 {len(close_by_stock)} 檔")

    collateral_value = 0.0
    matched = 0
    for code, lots in margin_by_stock.items():
        px = close_by_stock.get(code)
        if px is None or lots <= 0:
            continue
        collateral_value += lots * 1000 * px
        matched += 1
    print(f"可配對算擔保品市值的個股 {matched} 檔")

    merge_stock_detail_margin(margin_per_stock_detail)

    try:
        fm_date, margin_money = fetch_market_margin_money()
    except Exception as e:
        print(f"分母（FinMind全市場融資金額）取得失敗，今天這筆不寫入，維持既有history：{e}")
        sys.exit(0)  # 不算工作流程失敗——這是已知的優雅降級，不是需要人工介入的錯誤

    ratio = collateral_value / margin_money * 100 if margin_money else None
    today = datetime.now(TW_TZ).date().isoformat()
    record = {
        "date": today,
        "finmind_margin_money_date": fm_date,
        "collateral_value": round(collateral_value),
        "margin_money": margin_money,
        "matched_stocks": matched,
        "ratio_pct": round(ratio, 2) if ratio is not None else None,
    }
    print(f"維持率估算：{record['ratio_pct']}%")

    history = []
    if OUT_PATH.exists():
        try:
            history = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history = [h for h in history if h.get("date") != today]
    history.append(record)
    history.sort(key=lambda h: h["date"])
    history = history[-HISTORY_DAYS_KEEP:]
    OUT_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}（累積 {len(history)} 天）")


if __name__ == "__main__":
    main()
