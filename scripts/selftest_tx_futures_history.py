# -*- coding: utf-8 -*-
"""先.一〇九-1（2026-10-17）：台指期日線累積檔 data/tx_futures_history.json 缺日自測。

1. tx_history_missing_dates() 用假資料驗：週末、休市日不算缺；中間漏一個交易日要抓到；最後一筆之後不算缺。
2. 實際檔案：第一筆到最後一筆之間的交易日（data/trading_calendar.json）不得缺。
   最後一筆之後不檢查——TAIFEX DailyMarketReportFut 固定落後約一個交易日（見 PROGRESS 2026-10-17）。

用法：python scripts/selftest_tx_futures_history.py（全過 exit 0，任一失敗 exit 1）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fetch_market_tw", ROOT / ".github" / "scripts" / "fetch_market_tw.py")
fm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fm)

fails = []

# 1. 假資料：2026-10-08（四）→ 10-09、10-10 休市、10-11 週日 → 10-12（一）連續；10-14 漏掉
closed = {"2026-10-09", "2026-10-10"}
got = fm.tx_history_missing_dates(["2026-10-08", "2026-10-12", "2026-10-13", "2026-10-15"], closed)
if got != ["2026-10-14"]:
    fails.append(f"假資料應只缺 2026-10-14，實得 {got}")
if fm.tx_history_missing_dates(["2026-10-08", "2026-10-12"], closed) != []:
    fails.append("休市日／週末被誤判成缺日")
if fm.tx_history_missing_dates(["2026-10-15"], closed) != []:
    fails.append("只有一筆時不應有缺日")

# 2. 實際檔案
doc = json.loads((ROOT / "data" / "tx_futures_history.json").read_text(encoding="utf-8"))
dates = [r["date"] for r in doc.get("rows") or []]
real_closed = fm._tw_closed_days()
if real_closed is None:
    fails.append("data/trading_calendar.json 讀不到")
else:
    miss = fm.tx_history_missing_dates(dates, real_closed)
    print(f"實際檔：{len(dates)} 筆（{dates[0] if dates else '-'}～{dates[-1] if dates else '-'}），缺日 {miss}")
    if miss:
        fails.append(f"實際檔缺日：{miss}")

if fails:
    for f in fails:
        print("FAIL -", f)
    sys.exit(1)
print("PASS - 台指期日線缺日自測全過")
