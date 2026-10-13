# -*- coding: utf-8 -*-
"""先.八十二-10（2026-10-13）：真錢持股卡 holdings_view 自測（假帳本列，不讀真帳本、不印真金額）。
① 股數／成本／均價／市值／損益正確  ② T+2 交割跨週末  ③ T+2 跨休市日  ④ 交割日已過→已交割  ⑤ 非白名單代號不列  ⑥ 順序 0050 在前
用法：python scripts/selftest_holdings_view.py
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import auto_ledger_view as V  # noqa: E402

V._closed_days = lambda: {"2026-10-26"}
fills = [{"symbol": "00697B", "qty": 1, "filled_qty": 1, "avg_price": 34.0, "ts": "2026-10-22T09:30:00+08:00"},
         {"symbol": "0050", "qty": 2, "filled_qty": 2, "avg_price": 110.0, "ts": "2026-10-16T09:30:00+08:00"},
         {"symbol": "9999", "qty": 5, "filled_qty": 5, "avg_price": 10.0, "ts": "2026-10-16T09:30:00+08:00"}]
series = {"0050": [{"date": "2026-10-22", "close": 115.0}], "00697B": [{"date": "2026-10-22", "close": 33.0}], "00646": []}
h = V.holdings_view(fills, series, today=date(2026, 10, 21))
by = {x["symbol"]: x for x in h}
a, b = by["0050"], by["00697B"]
res = [("①0050 2 股成本 220、市值 230、損益 +10（+4.55%）", a["qty"] == 2 and a["cost"] == 220 and a["avg_cost"] == 110 and a["value"] == 230 and a["pnl"] == 10 and a["pnl_pct"] == 4.55),
       ("②10/16（五）成交 T+2＝10/20（二），10/21 看→已交割", a["settlement"] == {"status": "settled", "date": "2026-10-20"}),
       ("③10/22（四）成交 T+2 跨 10/26 休市＝10/27，10/21 看→待交割", b["settlement"] == {"status": "pending", "date": "2026-10-27"}),
       ("④00697B 損益 -1", b["pnl"] == -1),
       ("⑤非白名單 9999 不列", "9999" not in by),
       ("⑥順序 0050 在前", [x["symbol"] for x in h] == ["0050", "00697B"])]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
