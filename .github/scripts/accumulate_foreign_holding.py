# -*- coding: utf-8 -*-
"""外資及陸資持股比率逐檔逐日累積器（稽核.三B組第1類，2026-09-29總司令裁示【驗.八】一）。

背景：`fetch_foreign_holding.py` 每天只覆寫 `data/foreign_holding.json` 的
「最新一天」快照，前一天的數字就永久消失，無法回頭分析外資持股比率的變化
趨勢。本腳本**不額外打任何 TWSE 請求**（零成本），只讀當次管線已經抓好的
`data/foreign_holding.json`，把它併入一份逐檔逐日的歷史檔
`data/foreign_holding_history.json`，沿用 `accumulate_institutional.py`
已驗證過的「讀回上次 JSON → 併入今天 → 去重 → 存緊湊陣列格式」模式（同一個
作者、同一套慣例，避免發明新格式）。

**刻意保留 `foreign_holding.json` 本身不變**（欄位、結構、單日快照語意都不動）：
`generate_status_json.py`／`index.html` 現有讀取者假設它只有「今天」一筆，
改動它會有破壞既有功能的風險；累積需求改用這支新腳本輸出的獨立檔案滿足，
新增檔案不影響任何既有下游。

**格式選擇：不設滾動視窗上限**（[自行裁量]，理由：跟 `institutional_history.json`
不同——那支是為了 60 日 z-score 這個明確的固定需求而生，本腳本目前沒有已知的
固定視窗下游需求，稽核/分析用途通常越長越好；先讓它自然累積，檔案大小在
`meta.size_mb` 誠實揭露，成長到需要瘦身時再回頭加視窗上限，不在沒有需求的
情況下先手動剪掉未來可能用得到的歷史）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "data" / "foreign_holding.json"
OUT = ROOT / "data" / "foreign_holding_history.json"
TZ = timezone(timedelta(hours=8))

# series[code][date] = [foreign_holding_ratio, foreign_can_invest_ratio, foreign_shares_held]
FIELDS = ["foreign_holding_ratio", "foreign_can_invest_ratio", "foreign_shares_held"]


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    snap = _load(SNAPSHOT, {})
    stocks = snap.get("stocks") or {}
    if not stocks:
        print("! foreign_holding.json 沒有 stocks，中止（不寫出空檔覆蓋既有累積）")
        return 1

    prior = _load(OUT, {})
    series: dict[str, dict[str, list]] = {}
    for code, rows in (prior.get("series") or {}).items():
        if isinstance(rows, dict):
            series[code] = dict(rows)

    added = 0
    seen_dates: set[str] = set()
    for code, rec in stocks.items():
        d = str(rec.get("date") or "")
        if len(d) != 8:
            continue
        seen_dates.add(d)
        vals = [rec.get(f) for f in FIELDS]
        if all(v is None for v in vals):
            continue
        bucket = series.setdefault(code, {})
        if d not in bucket:
            added += 1
        bucket[d] = vals

    all_dates = sorted({d for b in series.values() for d in b})
    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "source": "data/foreign_holding.json（每日管線既有 TWSE MI_QFIIS 呼叫，本腳本零額外請求）",
            "dates_available": len(all_dates),
            "date_range": [all_dates[0], all_dates[-1]] if all_dates else None,
            "stocks": len(series),
            "fields": FIELDS,
            "note": "往前累積，不是回補；不設滾動視窗上限（見檔頭說明）；"
                    "foreign_holding.json 本身維持單日快照語意不變，既有讀取者不受影響。",
        },
        "dates": all_dates,
        "series": series,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"foreign_holding_history.json：{len(series)} 檔 × {len(all_dates)} 個交易日"
          f"（本次快照日期 {sorted(seen_dates)}，新增 {added} 筆），{size_mb:.2f}MB")
    if all_dates:
        print(f"  日期範圍 {all_dates[0]} ~ {all_dates[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
