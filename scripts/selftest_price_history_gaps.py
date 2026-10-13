# -*- coding: utf-8 -*-
"""先.八十-9 全市場缺日自測（只讀 data/price_history.json，不連網）。
①自 2026-08-03 起每個官方開市日（research/data/auto_trading/calendar_*.json 休市日以外的平日），
  檔數都不得低於全期中位數的 90%（缺一個交易所或只回補一部分股票都會被抓到）
②每檔日期不得重複、必須遞增
③判定函式本身：人為拿掉某天一半股票 → 必須被判為缺日（防止自測恆真）
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import backfill_price_history_gaps as B  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


# 先.八十一-31：本機 git pull 換 price_history.json（先刪再寫）的幾秒內會讀不到或讀到半個檔，重試 4 次、間隔 2 秒
def _load_ph(tries=4):
    import time
    for i in range(tries):
        try:
            return json.loads(B.PH.read_text(encoding="utf-8"))["prices"]
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
            if i == tries - 1:
                raise
            time.sleep(2)


prices = _load_ph()
gaps, counts, med = B.find_gaps(prices)
check(f"①{B.START} 起每個開市日檔數 ≥ 中位數 {med:.0f} 的 90%（缺日：{[(d, counts.get(d, 0)) for d in gaps][:8]}）", not gaps)
bad = [c for c, rows in prices.items() if [r["date"] for r in rows] != sorted({r["date"] for r in rows})]
check(f"②每檔日期遞增且不重複（違規 {len(bad)} 檔：{bad[:5]}）", not bad)
day = sorted(counts)[-1] if counts else None
if day:
    p2 = {c: copy.copy(rows) for c, rows in prices.items()}
    victims = [c for c, rows in p2.items() if rows and rows[-1]["date"] == day][::2]
    for c in victims:
        p2[c] = [r for r in p2[c] if r["date"] != day]
    g2, _, _ = B.find_gaps(p2)
    check(f"③人為拿掉 {day} 一半股票（{len(victims)} 檔）→ 判定為缺日", day in g2)
print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
