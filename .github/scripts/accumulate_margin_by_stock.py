# -*- coding: utf-8 -*-
"""融資融券逐檔逐日累積器（稽核.三B組第2類，2026-09-29總司令裁示【驗.八】一）。

背景：`update_margin_maintenance.py::merge_stock_detail_margin()` 每天把
TWSE MI_MARGN／TPEx tpex_mainboard_margin_balance 的逐股「融資今日餘額／
融資前日餘額／融券今日餘額」寫進 `data/stock_detail.json` 的
`stocks[code]["margin"]`，但每天覆寫同一個欄位，前一天的數字不會保留。
本腳本**不額外打任何 TWSE/TPEx 請求**（零成本），只讀當次管線已經寫好的
`data/stock_detail.json`，把逐股 margin 併入一份逐檔逐日的歷史檔
`data/margin_by_stock_history.json`，沿用 `accumulate_foreign_holding.py`
／`accumulate_institutional.py` 已驗證過的「讀回上次 JSON → 併入今天 →
去重 → 存緊湊陣列格式」慣例，同一套慣例第三次套用，不發明新格式。

**刻意保留 `stock_detail.json` 本身不變**：個股頁「融資融券」分頁現有
讀取者假設 `stocks[code]["margin"]` 只有「今天」一筆，改動它有破壞既有
功能的風險；累積需求改用這支新腳本輸出的獨立檔案滿足。

**日期來源**：`stock_detail.json` 本身沒有逐股日期欄位（`margin` 只有
today/prev 兩個數值，沒有日期字串），改用 `meta.generated_at`
（ISO格式時間戳，同一次管線寫入）取日期部分，跟同一批資料綁在一起，
不額外猜測或另外打 API 問日期。

**格式選擇：不設滾動視窗上限**（[自行裁量]，理由同 `accumulate_foreign_
holding.py`——沒有已知的固定視窗下游需求，先自然累積，`meta.size_mb`
誠實揭露檔案大小，成長到需要瘦身時再加視窗上限）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "data" / "stock_detail.json"
OUT = ROOT / "data" / "margin_by_stock_history.json"

# series[code][date] = [margin_balance_today, margin_balance_prev, short_balance_today]
FIELDS = ["margin_balance_today", "margin_balance_prev", "short_balance_today"]


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    snap = _load(SNAPSHOT, {})
    stocks = snap.get("stocks") or {}
    generated_at = str((snap.get("meta") or {}).get("generated_at") or "")
    date_str = generated_at[:10]  # "YYYY-MM-DD"
    if len(date_str) != 10 or not stocks:
        print("! stock_detail.json 沒有 stocks 或 meta.generated_at 缺日期，中止（不寫出空檔覆蓋既有累積）")
        return 1
    d = date_str.replace("-", "")  # 跟 foreign_holding_history.json 一致用 YYYYMMDD 當鍵

    prior = _load(OUT, {})
    series: dict[str, dict[str, list]] = {}
    for code, rows in (prior.get("series") or {}).items():
        if isinstance(rows, dict):
            series[code] = dict(rows)

    added = 0
    n_with_margin = 0
    for code, rec in stocks.items():
        margin = rec.get("margin")
        if not isinstance(margin, dict):
            continue
        vals = [margin.get(f) for f in FIELDS]
        if all(v is None for v in vals):
            continue
        n_with_margin += 1
        bucket = series.setdefault(code, {})
        if d not in bucket:
            added += 1
        bucket[d] = vals

    all_dates = sorted({dt for b in series.values() for dt in b})
    doc = {
        "meta": {
            "generated_at": snap.get("meta", {}).get("generated_at"),
            "source": "data/stock_detail.json stocks[code].margin（每日管線既有 TWSE MI_MARGN"
                      "／TPEx tpex_mainboard_margin_balance 呼叫，本腳本零額外請求）",
            "dates_available": len(all_dates),
            "date_range": [all_dates[0], all_dates[-1]] if all_dates else None,
            "stocks": len(series),
            "fields": FIELDS,
            "note": "往前累積，不是回補；不設滾動視窗上限（見檔頭說明）；"
                    "stock_detail.json 本身維持單日快照語意不變，既有讀取者不受影響。",
        },
        "dates": all_dates,
        "series": series,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"margin_by_stock_history.json：{len(series)} 檔 × {len(all_dates)} 個交易日"
          f"（本次快照日期 {d}，本次含margin的股票數 {n_with_margin}，新增 {added} 筆），{size_mb:.2f}MB")
    if all_dates:
        print(f"  日期範圍 {all_dates[0]} ~ {all_dates[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
