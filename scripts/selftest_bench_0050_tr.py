# -*- coding: utf-8 -*-
"""research/bench_0050_tr.py 合成資料自測（先.一三五-1ib 甲）。零外部請求、不碰真帳本。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import bench_0050_tr as B  # noqa: E402

FAILS = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def row(d, adj, close=None):
    return {"date": d, "adj_close": adj, "close": close if close is not None else adj}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bench.jsonl"
        v1 = [row("2026-01-02", 100.0), row("2026-01-05", 101.0), row("2026-01-06", 99.99)]
        r = B.run(v1, p)
        led = B.read_ledger(p)
        check("首次建檔：inception＋2 日", r["appended"] == 3 and led[0]["kind"] == "inception")
        check("累乘正確", abs(led[-1]["tr_index"] - 0.9999) < 1e-9)

        r = B.run(v1, p)
        check("同日只寫一次（重跑零新增）", r["appended"] == 0 and len(B.read_ledger(p)) == 3)

        # 除息：01-07 除息 1 元，price_history 新版回溯改寫除息前 adj（×0.99），收盤 98.99 → 含息報酬 0%
        f = 0.99
        v2 = [row("2026-01-05", 101.0 * f, 101.0), row("2026-01-06", 99.99 * f, 99.99), row("2026-01-07", 98.99 * 1.0, 98.99)]
        B.run(v2, p)
        led = B.read_ledger(p)
        check("除息日用同版比值＝含息報酬", abs(led[-1]["ret"] - (98.99 / (99.99 * f) - 1)) < 1e-9)
        check("舊列未被改寫", abs(led[2]["tr_index"] - 0.9999) < 1e-9)

        # 漏跑兩天：視窗內補
        v3 = v2 + [row("2026-01-08", 100.0), row("2026-01-09", 101.0)]
        r = B.run(v3, p)
        check("漏跑日依序補", r["appended"] == 2 and B.read_ledger(p)[-1]["date"] == "2026-01-09")

        # 零成交：補到前一天為止
        v4 = v3 + [row("2026-01-12", 0), row("2026-01-13", 102.0)]
        r = B.run(v4, p)
        check("adj_close=0 停在前一天＋警告", r["appended"] == 0 and r["warning"])

        # 斷檔：最後日期滾出視窗
        before = p.read_text(encoding="utf-8")
        r = B.run([row("2026-05-01", 90.0), row("2026-05-04", 91.0)], p)
        check("斷檔不硬接", r["appended"] == 0 and r["warning"] and p.read_text(encoding="utf-8") == before)

        # 壞檔不覆蓋
        p.write_text(before + "{壞行\n", encoding="utf-8")
        bad = p.read_text(encoding="utf-8")
        try:
            B.run(v4, p)
            raised = False
        except RuntimeError:
            raised = True
        check("壞檔拋錯且不覆蓋", raised and p.read_text(encoding="utf-8") == bad)
    print("全部通過" if not FAILS else f"{len(FAILS)} 項失敗")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
