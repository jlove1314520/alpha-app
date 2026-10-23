# -*- coding: utf-8 -*-
"""補.資料-FinMind 股利 2007～2014 漏記逐檔分類（零請求；來源：exright_official_vs_finmind_2007_2014.json）。

官方有（research/data/official_exright_2007_2014.csv）、FinMind TaiwanStockDividend 本機快取同日沒有的事件，分三類：
  (a) empty_cache：該股 FinMind 快取整段空表（零筆股利）
  (b) date_shift：FinMind 有同股事件，但日期差 1～7 天（日期錯位）
  (c) absent：FinMind 有該股其他事件，但這次事件 ±7 天內都沒有
另列 no_cache（該股沒有涵蓋整段的 FinMind 快取，不算漏記）。只數件數，不改 adjust.py、不算報酬、不碰 holdout。
輸出 research/data/exright_finmind_miss_breakdown_2007_2014.json。
用法：python research/exright_finmind_miss_breakdown.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from fetch_exright_2007_2014 import OUT_CSV, finmind_ex_dates  # noqa: E402

OUT = HERE / "data" / "exright_finmind_miss_breakdown_2007_2014.json"
SHIFT_DAYS = 7


def main() -> int:
    ev = pd.read_csv(OUT_CSV, dtype={"stock_id": str})
    fm = finmind_ex_dates()
    counts: dict = defaultdict(lambda: defaultdict(int))
    examples: dict = defaultdict(list)
    shifts: dict = defaultdict(int)
    for r in ev.itertuples():
        key = f"{r.ex_date[:4]}_{r.market}"
        if r.stock_id not in fm:
            counts[key]["no_cache"] += 1
            continue
        ds = fm[r.stock_id]
        if r.ex_date in ds:
            counts[key]["same_day"] += 1
            continue
        if not ds:
            cat = "empty_cache"
        else:
            d0 = date.fromisoformat(r.ex_date)
            diffs = [(date.fromisoformat(x) - d0).days for x in ds]
            near = [k for k in diffs if 0 < abs(k) <= SHIFT_DAYS]
            if near:
                cat = "date_shift"
                shifts[min(near, key=abs)] += 1
            else:
                cat = "absent"
        counts[key][cat] += 1
        if len(examples[cat]) < 20:
            examples[cat].append(f"{r.stock_id} {r.ex_date} {r.market}")
    tot: dict = defaultdict(int)
    for v in counts.values():
        for k, n in v.items():
            tot[k] += n
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "task": "補.資料-FinMind 股利 2007～2014 漏記逐檔分類（零請求）",
           "input": [OUT_CSV.name, "TaiwanStockDividend 本機快取（同 fetch_exright_2007_2014.finmind_ex_dates）"],
           "categories": {"same_day": "FinMind 同日有", "empty_cache": "FinMind 快取整段零筆股利",
                          "date_shift": f"FinMind 同股事件日期差 1～{SHIFT_DAYS} 天", "absent": f"FinMind 有該股其他事件但 ±{SHIFT_DAYS} 天內沒有",
                          "no_cache": "沒有涵蓋整段的 FinMind 快取（不算漏記）"},
           "total": dict(tot),
           "by_year_market": {k: dict(counts[k]) for k in sorted(counts)},
           "date_shift_days_hist": {str(k): v for k, v in sorted(shifts.items())},
           "examples": dict(examples),
           "notes": ["2009 年的 absent 主要就是 FinMind 2009 整年缺漏（先.一三三-1c）。",
                     "只數事件、不改 adjust.py、不算報酬、不碰 holdout。"]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["total"], ensure_ascii=False))
    for k in sorted(counts):
        print(k, json.dumps(dict(counts[k]), ensure_ascii=False))
    print("shift", out["date_shift_days_hist"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
