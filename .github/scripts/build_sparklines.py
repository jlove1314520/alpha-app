# -*- coding: utf-8 -*-
"""從 `data/price_history.json` 產出全市場走勢線 `data/sparklines.json`（2026-09-05，總司令「零」）。

**取代什麼**：舊架構是 `fetch_quotes_tw.py` 對「自選股＋三榜前100名」**逐檔**打 TWSE STOCK_DAY
（一檔一個請求、每檔間隔 3 秒節流），問題一大堆：
- 只有被列進清單的股票有走勢線，使用者新加入的自選股要等下一次排程才會有；
- 上櫃股完全沒有（STOCK_DAY 是上市專屬端點）；
- 一次抓不完（240 秒預算只夠約 40 檔），還會被 TWSE 軟性限流打斷；
- 千元以上股票曾因千分位逗號解析失敗整批消失（2026-09-04/05 各中一次）。

**新架構**：`update_price_history.py` 每天已經用**兩個請求**（TWSE STOCK_DAY_ALL 全上市、
TPEx tpex_mainboard_quotes 全上櫃）把全市場 OHLCV append 進 `price_history.json`。這支只是
從那份既有資料切出每檔最近 N 天的收盤價，產出一個小檔給 App 讀——**零額外網路請求**。

輸出 `data/sparklines.json`：
    {"meta": {...}, "sparklines": {"2330": [2385.0, 2390.0, ...], ...}}
每檔最多 `SPARK_DAYS` 個收盤價（由舊到新）。只收 >=2 筆的股票（1 筆畫不出線）。

跑法：`python .github/scripts/build_sparklines.py`（掛在 market.yml，update_price_history 之後）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
OUT_PATH = REPO_ROOT / "data" / "sparklines.json"
TW_TZ = timezone(timedelta(hours=8))
SPARK_DAYS = 20


def main() -> None:
    if not PRICE_HISTORY_PATH.exists():
        raise SystemExit(f"{PRICE_HISTORY_PATH} 不存在——要先跑 update_price_history.py")
    doc = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    prices = doc.get("prices") or {}

    out: dict[str, list[float]] = {}
    latest_date = None
    skipped_too_short = 0
    for code, rows in prices.items():
        if not rows:
            skipped_too_short += 1
            continue
        closes = []
        for r in rows[-SPARK_DAYS:]:
            c = r.get("close")
            if isinstance(c, (int, float)) and c == c and c > 0:
                closes.append(round(float(c), 4))
        if len(closes) < 2:
            skipped_too_short += 1
            continue
        out[code] = closes
        d = rows[-1].get("date")
        if d and (latest_date is None or d > latest_date):
            latest_date = d

    payload = {
        "meta": {
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "source": "從 data/price_history.json 切出（TWSE STOCK_DAY_ALL 全上市 + TPEx tpex_mainboard_quotes 全上櫃，"
                      "每日各一次請求；本腳本零額外網路請求）",
            "days": SPARK_DAYS,
            "stocks": len(out),
            "skipped_too_short": skipped_too_short,
            "data_asof": latest_date,
            "note": "每檔最多 20 個收盤價，由舊到新，原始收盤價（未還原權息）。App 所有頁面的走勢線都讀這個檔，"
                    "不再逐檔打 STOCK_DAY——新加入的自選股只要在全市場歷史裡就立刻有線。",
        },
        "sparklines": out,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"寫入 {OUT_PATH}：{len(out)} 檔走勢線（{size_kb:.0f} KB），資料日期 {latest_date}，"
          f"略過 {skipped_too_short} 檔（歷史不足2筆）")


if __name__ == "__main__":
    main()
