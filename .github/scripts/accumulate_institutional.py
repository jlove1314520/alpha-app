# -*- coding: utf-8 -*-
"""個股三大法人歷史累積器（金流一.1 的資料地基，2026-09-08）。

**為什麼需要這支**：金流一規格要 5／20／60 日視窗與 60 日 z 分數分布，
但現有磁碟資料湊不出來：

- `data/stock_detail.json` 的 `institutional.history` **最多只有 5 天**
  （實測 18,768 檔有法人資料，`≥20 天的有 0 檔`）。
- `research/data/raw_twse_t86/` 的 parquet **停在 2024-12-31**——
  而且那**不是疏漏，是 holdout 邊界**：`validation/holdout.py` 定義
  `VAL_END=2024-12-31`、`HOLDOUT=(VAL_END, today]`，
  `backfill_t86.py` 的預設結束日就是 `VAL_END`。
  近 60 個交易日**整段都在 holdout 裡**，回補它等於解鎖 holdout，
  依 CLAUDE.md 第八條必須總司令明確同意，**不是我可以順手做的事**。

**所以走這條路**：沿用 `fetch_market_tw.py` 既有的
「讀回上次 JSON → 併入今天 → 去重 → 只留最近 N 天」累積模式，
把個股層的法人資料**往前累積**。

- **零額外請求**：只讀 `data/stock_detail.json`（每日管線已經抓好的），
  不對 TWSE/TPEx 多打任何一次。
- **零 holdout 汙染**：資料寫在產品側 `data/`，不進 `research/`，
  也不會被 `validation/holdout.py` 的載入器讀到。
- **代價誠實揭露**：視窗是**往前長出來的**，不是回補的。
  今天只有 5 天，20 日視窗約 1 個月後可用，60 日約 3 個月後可用。
  在那之前 `build_sector_flow.py` 只會輸出當下算得出來的那些，
  並在檔案裡標明還缺幾個交易日——**不補零、不外插、不假裝有**。

存成緊湊格式（欄位陣列而非物件）控制檔案大小：
只留官方在市名冊內的股票（規格要求「ETF、權證、DR 不得混進產業合計」），
2,138 檔 × 70 天 × 3 個數字，比每天存一個 dict 小很多。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DETAIL = ROOT / "data" / "stock_detail.json"
UNIVERSE = ROOT / "data" / "listed_universe.json"
OUT = ROOT / "data" / "institutional_history.json"
TZ = timezone(timedelta(hours=8))

# 60 日 z 分數需要 60 個交易日，多留 10 天緩衝讓「近 60 日」永遠取得滿。
KEEP_DAYS = 70


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    detail = _load(DETAIL, {})
    stocks = detail.get("stocks") or {}
    if not stocks:
        print("! stock_detail.json 沒有 stocks，中止（不寫出空檔覆蓋既有累積）")
        return 1

    uni = _load(UNIVERSE, {})
    active = set(uni.get("active") or [])
    if len(active) < 1000:
        print(f"! listed_universe.json 只有 {len(active)} 檔，不完整，中止")
        return 1

    prior = _load(OUT, {})
    # series[code] = {date: [foreign, trust, dealer]}
    series: dict[str, dict[str, list]] = {}
    for code, rows in (prior.get("series") or {}).items():
        if isinstance(rows, dict):
            series[code] = dict(rows)

    added = 0
    for code, s in stocks.items():
        if code not in active:
            continue                      # ETF／權證／DR 一律排除，規格要求
        inst = s.get("institutional") or {}
        # 今天這筆 + 檔案裡帶的最多 5 天歷史，一起併進來
        rows = list(inst.get("history") or [])
        if inst.get("date"):
            rows.append(inst)
        for r in rows:
            d = str(r.get("date") or "")
            if len(d) != 8:
                continue
            f, t, dl = r.get("foreign_lots"), r.get("trust_lots"), r.get("dealer_lots")
            if f is None and t is None and dl is None:
                continue
            bucket = series.setdefault(code, {})
            if d not in bucket:
                added += 1
            bucket[d] = [f, t, dl]

    # 只留最近 KEEP_DAYS 個「有資料的日期」（用全體日期聯集，個股缺一天不影響對齊）
    all_dates = sorted({d for b in series.values() for d in b})
    keep = set(all_dates[-KEEP_DAYS:])
    for code in list(series):
        series[code] = {d: v for d, v in series[code].items() if d in keep}
        if not series[code]:
            del series[code]

    dates = sorted(keep)
    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "source": "data/stock_detail.json 的 institutional（每日管線既有 T86／TPEx 呼叫，本腳本零額外請求）",
            "keep_days": KEEP_DAYS,
            "dates_available": len(dates),
            "date_range": [dates[0], dates[-1]] if dates else None,
            "stocks": len(series),
            "note": "往前累積，不是回補。近 60 個交易日的 T86 落在 holdout "
                    "(VAL_END=2024-12-31, today]，回補需總司令明確解鎖，故不做。",
            "unit": "lots（張），依 stock_detail 原始單位",
            "fields": ["foreign_lots", "trust_lots", "dealer_lots"],
        },
        "dates": dates,
        "series": series,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"institutional_history.json：{len(series)} 檔 × {len(dates)} 個交易日"
          f"（新增 {added} 筆），{size_mb:.1f}MB")
    if dates:
        print(f"  日期範圍 {dates[0]} ~ {dates[-1]}")
    for w in (5, 20, 60):
        have = len(dates)
        print(f"  {w:2d} 日視窗：{'可用' if have >= w else f'還缺 {w-have} 個交易日'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
