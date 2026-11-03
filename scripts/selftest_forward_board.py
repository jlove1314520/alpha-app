# -*- coding: utf-8 -*-
"""先.一四七-0 自測：research/forward_board.py（App 前向模擬看板欄位）。零外部請求、不寫 data/。"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import forward_board as FB  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + name)
    fails += 0 if ok else 1


with tempfile.TemporaryDirectory() as td:
    bp = Path(td) / "bench.jsonl"
    rows = [{"date": f"2026-11-{d:02d}", "tr_index": 1.0 + d / 100} for d in range(2, 10)]
    bp.write_text("\n".join(json.dumps(r) for r in rows) + "\n壞行\n", encoding="utf-8")
    ser = [("2026-11-03", 100), ("2026-11-04", 110), ("2026-11-05", 88), ("2026-11-04", 120)]  # 同日多筆取最後
    b = FB.board(ser, n_holdings=3, bench_path=bp)
    check("同日多筆取最後一筆", dict(b["nav_series"])["2026-11-04"] == 120)
    check("最大回撤 120→88 = −26.67%", b["max_drawdown_pct"] == -26.67)
    check("0050 含息：起跑日收盤到最後一天（1.05/1.03−1）", b["bench_0050_tr_pct"] == round((1.05 / 1.03 - 1) * 100, 2))
    check("壞行略過、bench 序列對齊日期", [d for d, _ in b["bench_0050"]] == ["2026-11-03", "2026-11-04", "2026-11-05"])
    check("持股檔數照呼叫端", b["n_holdings"] == 3)
    check("nav_start＝第一天", b["nav_start"] == 100)
    long = [(f"2026-{m:02d}-{d:02d}", 100 + d) for m in (9, 10) for d in range(1, 29)]
    check("只留近 30 筆", len(FB.board(long, bench_path=bp)["nav_series"]) == 30)
    b2 = FB.board([("2026-11-20", 100)], bench_path=bp)
    check("as_of 晚於 bench 最後一天：起跑日不在 bench → 0050 報酬 None", b2["bench_0050_tr_pct"] is None)
    b3 = FB.board([("2026-11-08", 100), ("2026-11-20", 101)], bench_path=bp)
    check("as_of 超過 bench → 取 ≤ as_of 最近一筆並標 bench_to", b3["bench_to"] == "2026-11-09")
    b4 = FB.board(ser, bench_path=Path(td) / "不存在.jsonl")
    check("bench 檔不存在 → 0050 None、淨值照給", b4["bench_0050_tr_pct"] is None and len(b4["nav_series"]) == 3)
    check("空帳本 → 空序列不拋錯", FB.board([], bench_path=bp)["nav_series"] == [])
    check("壞輸入 → 只回 error 欄（十二節）", "error" in FB.safe_board("garbage"))
    check("淨值 0／負數略過", len(FB.board([("2026-11-03", 0), ("2026-11-04", 100)], bench_path=bp)["nav_series"]) == 1)

# 真實 data/paper_*.json：14 支都讀得到 label（前端缺 label 會顯示「資料尚未產生」）
missing = [n for n in range(5, 19) if not (json.loads((ROOT / "data" / f"paper_{n}.json").read_text(encoding="utf-8")) or {}).get("label")]
check("14 支 data/paper_N.json 都有 label", not missing)
print(f"合計 失敗 {fails}")
sys.exit(1 if fails else 0)
