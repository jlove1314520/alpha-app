# -*- coding: utf-8 -*-
"""修.八 1.4：減資調整（update_price_history.apply_reduction_adjustments）自我測試。
用合成資料驗證：一般套用、定錨失敗不套、來源已含不重複、未到恢復日不套、
未來事件（參考價為「-」）不進帳、與adjust.py公式等價（factor=ref/pre_close）。"""
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("uph", ROOT / ".github" / "scripts" / "update_price_history.py")
uph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uph)

fails = 0


def check(name, cond):
    global fails
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    fails += 0 if cond else 1


def rows(dates_closes, adj=None):
    out = []
    for i, (d, c) in enumerate(dates_closes):
        out.append({"date": d, "close": c, "adj_close": (adj[i] if adj else c)})
    return out


def ledger(code, resume, pre, ref):
    return {"reductions": {code: [{"code": code, "resume_date": resume, "pre_close": pre, "ref_price": ref,
                                   "applied": False}]}}


# 1 一般套用（彌補虧損型，factor>1）：66.00→84.66，同巧新1563
prices = {"A": rows([("2026-08-26", 66.0), ("2026-09-04", 66.0), ("2026-09-08", 77.1)])}
lg = ledger("A", "2026-09-07", 66.0, 84.66)
n = uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
f = 84.66 / 66.0
check("一般套用：套用1筆", n == 1)
check("一般套用：恢復日前adj_close×factor", abs(prices["A"][0]["adj_close"] - 66.0 * f) < 1e-9 and abs(prices["A"][1]["adj_close"] - 66.0 * f) < 1e-9)
check("一般套用：恢復日後不動", prices["A"][2]["adj_close"] == 77.1)
check("一般套用：與adjust.py公式等價（factor=ref/pre_close）", abs(lg["reductions"]["A"][0]["factor_applied"] - f) < 1e-12)

# 2 定錨失敗（快取停在很久以前）
prices = {"B": rows([("2024-12-31", 196.5), ("2026-08-26", 98.2)])}
lg = ledger("B", "2026-08-24", 81.30, 105.06)
n = uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
check("定錨失敗：不套用且記skip_reason", n == 0 and "定錨失敗" in lg["reductions"]["B"][0]["skip_reason"] and prices["B"][0]["adj_close"] == 196.5)

# 3 來源已含（3356型）
f3 = 68.04 / 59.4
prices = {"C": rows([("2026-09-09", 59.4), ("2026-09-21", 68.6)], adj=[68.04, 68.6])}
lg = ledger("C", "2026-09-21", 59.4, 68.04)
n = uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
check("來源已含：不重複乘", n == 0 and prices["C"][0]["adj_close"] == 68.04 and "已含" in lg["reductions"]["C"][0]["skip_reason"])

# 4 未到恢復日
prices = {"D": rows([("2026-09-22", 5.91)])}
lg = ledger("D", "2026-10-05", 5.91, 7.06)
n = uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
check("未到恢復日：不動、不標applied", n == 0 and not lg["reductions"]["D"][0]["applied"] and prices["D"][0]["adj_close"] == 5.91)

# 5 冪等：第二次執行不再乘
prices = {"E": rows([("2026-09-16", 8.72), ("2026-09-29", 10.15)])}
lg = ledger("E", "2026-09-29", 8.72, 10.13)
uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
once = prices["E"][0]["adj_close"]
uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
check("冪等：重跑不重複乘", prices["E"][0]["adj_close"] == once)

# 6 與既有除權息複合：先有adj（除權息已乘0.98）再減資，仍以原始close為定錨
prices = {"F": rows([("2026-09-01", 10.0), ("2026-09-10", 10.0)], adj=[9.8, 10.0])}
lg = ledger("F", "2026-09-15", 10.0, 20.0)
uph.apply_reduction_adjustments(prices, lg, "2026-09-30")
check("與除權息複合：adj連乘（9.8×2.0）", abs(prices["F"][0]["adj_close"] - 19.6) < 1e-9)

# 7 merge：未來事件（參考價「-」）在fetch階段被濾掉；merge本身不重複
lg = {}
it = [{"code": "Z", "resume_date": "2026-09-01", "pre_close": 1.0, "ref_price": 2.0, "reason": "x"}]
check("merge：首次新增1筆", uph.merge_reductions(lg, it, "2026-09-30") == 1)
check("merge：重複不再新增", uph.merge_reductions(lg, it, "2026-09-30") == 0)

print("全部通過" if fails == 0 else f"有 {fails} 項失敗")
sys.exit(1 if fails else 0)
