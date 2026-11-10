# -*- coding: utf-8 -*-
"""先.一五八-3 自測：除權息日 0 報酬補正（research/paper_opt_exright_fix.py）。零外部請求。

1. 合成 bars：現金除息（FinMind 快取路徑）、ex_dividend_events 路徑、無事件但收盤≠前收（raw_close）、真的 0（不動）、
   超過 last_date 的日子不動。
2. 冪等：apply_once 第二次呼叫不再改。
3. 真快取：research/data/paper_opt/f12_bars.json 的 0050 在 2026-01-22、07-21 不再是 0，且等於 收盤÷(前收−現金)−1
   （現金 1.0／0.6 元，FinMind 本機快取）；回看期內不再有「ret＝0 但收盤≠前收」的列。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "research"))
import paper_opt_exright_fix as XF  # noqa: E402

ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS {name}")
    else:
        fail += 1
        print(f"FAIL {name} {info}")


# 1. 合成（用不存在的代號避開本機 price_history；FinMind／帳本路徑用 monkeypatch）
XF._price_history_real = XF._price_history
XF._price_history = lambda: {}
XF._ledger_events = lambda: {("ZZ2", "2026-01-05"): 0.98}
_orig_fm = XF._finmind_div
XF._finmind_div = lambda sid, cache: {"2026-01-05": (1.0, 0.0)} if sid == "ZZ1" else {}
bars = {
    "ZZ1": {"2026-01-02": [0, 0, 0, 50.0, 0.01], "2026-01-05": [0, 0, 0, 49.5, 0.0]},
    "ZZ2": {"2026-01-02": [0, 0, 0, 100.0, None], "2026-01-05": [0, 0, 0, 99.0, 0.0]},
    "ZZ3": {"2026-01-02": [0, 0, 0, 20.0, None], "2026-01-05": [0, 0, 0, 20.4, 0.0]},
    "ZZ4": {"2026-01-02": [0, 0, 0, 30.0, None], "2026-01-05": [0, 0, 0, 30.0, 0.0]},
    "ZZ5": {"2026-01-02": [0, 0, 0, 30.0, None], "2026-02-05": [0, 0, 0, 31.0, 0.0]},
}
cache = {"bars": bars}
fx = XF.apply_once(cache, "2026-01-31")
src = {f[0]: f[4] for f in fx}
check("FinMind 現金除息", abs(bars["ZZ1"]["2026-01-05"][4] - (49.5 / 49.0 - 1)) < 1e-12 and src.get("ZZ1") == "finmind_dividend_cache")
check("帳本事件", abs(bars["ZZ2"]["2026-01-05"][4] - (99.0 / 98.0 - 1)) < 1e-12 and src.get("ZZ2") == "ex_dividend_events")
check("無事件收盤≠前收→raw_close", abs(bars["ZZ3"]["2026-01-05"][4] - 0.02) < 1e-12 and src.get("ZZ3") == "raw_close")
check("真的 0 不動", bars["ZZ4"]["2026-01-05"][4] == 0.0 and "ZZ4" not in src)
check("超過 last_date 不動", bars["ZZ5"]["2026-02-05"][4] == 0.0)
check("冪等", XF.apply_once(cache, "2026-01-31") == [] and cache["exright_fix"]["n"] == 3)
XF._finmind_div = _orig_fm

# 3. 真快取
p = REPO / "research" / "data" / "paper_opt" / "f12_bars.json"
if p.exists():
    c = json.loads(p.read_text(encoding="utf-8"))
    b = c["bars"]["0050"]
    check("f12_bars 帶補正標記", (c.get("exright_fix") or {}).get("version") == XF.VERSION)
    for d, pdt, cash in (("2026-01-22", "2026-01-21", 1.0), ("2026-07-21", "2026-07-20", 0.6)):
        want = b[d][3] / (b[pdt][3] - cash) - 1.0
        check(f"0050 {d} 含息報酬", abs((b[d][4] or 0) - want) < 1e-6, f"got={b[d][4]} want={want}")
    last = c["exright_fix"]["last_date"]
    ph = XF._price_history_real()
    left = 0
    for sid, bb in c["bars"].items():
        ds = sorted(bb)
        rows = {r["date"]: r for r in ph.get(sid, [])}
        for i in range(1, len(ds)):
            if ds[i] <= last and bb[ds[i]][4] == 0 and abs(bb[ds[i]][3] - bb[ds[i - 1]][3]) > 1e-9:
                a, b0 = rows.get(ds[i], {}).get("adj_close"), rows.get(ds[i - 1], {}).get("adj_close")
                if a and b0 and abs(a / b0 - 1.0) < 1e-9:  # 除權息後參考價＝收盤，price_history 還原價確認真的是 0（例：1527 2026-08-03）
                    continue
                left += 1
    check("回看期內無 ret=0 但收盤≠前收", left == 0, f"剩 {left} 筆")
else:
    print("SKIP 真快取（本機沒有 f12_bars.json）")

print(f"\n{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
