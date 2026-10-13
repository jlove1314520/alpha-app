# -*- coding: utf-8 -*-
"""先.八十一-6（2026-10-13 總司令裁示②）：#418 聯集日曆更正後的整串重跑。

#418 core_allocation_backtest.load_all 原本以台股日曆左合併美股腿（台股休市、美股照常交易的日子，美股報酬整天消失），
先.八十-12 已改為聯集日曆（預設）並另存 core_allocation_result_unioncal.json。下游全部依賴同一個 load_all：
  #421 leveraged_bb90_backtest（--formula 421）→ #424 crisis_gate_leveraged_bb90 → 延後一日敏感度 → #429 r1_0050_credit_gate
  → 達標機率 win_probability_2026_10 → data/strategy_monthly_returns.json（App 讀）
本檔依序重跑，**不改任何事前參數、不改原判定**；各結果另存 *_unioncal.json，已登記的原結果檔一律不覆蓋。
唯一例外：data/strategy_monthly_returns.json 是 App 讀的展示檔，依裁示改成更正後序列（原版另存 _leftjoin 備份）。
#421 的對照值原本讀 #418 原結果檔，這裡改指向聯集日曆版。資料一律截至 2024-12-31，holdout 未動。
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if "--formula" not in sys.argv:
    sys.argv += ["--formula", "421"]          # LB 在 import 時讀 argv 決定公式；整串都用 #421
import core_allocation_backtest as CA  # noqa: E402

CA.OUT = CA.OUT_UNION                         # #421 的 #418 對照值改讀聯集日曆版
DATA = HERE / "data"


def run(mod_name: str, out_name: str) -> dict:
    mod = __import__(mod_name)
    mod.OUT = DATA / out_name
    t0 = time.time()
    print(f"=== {mod_name} → {out_name}", flush=True)
    rc = mod.main()
    print(f"    exit={rc}（{time.time() - t0:.0f} 秒）", flush=True)
    return json.loads(mod.OUT.read_text(encoding="utf-8"))


def main() -> int:
    run("leveraged_bb90_backtest", "leveraged_bb90_421_result_unioncal.json")
    run("crisis_gate_leveraged_bb90", "crisis_gate_leveraged_bb90_result_unioncal.json")
    run("crisis_gate_timing_sensitivity", "crisis_gate_timing_sensitivity_unioncal.json")
    run("r1_0050_credit_gate", "r1_0050_credit_gate_result_unioncal.json")
    run("win_probability_2026_10", "win_probability_2026_10_unioncal.json")
    smr = HERE.parent / "data" / "strategy_monthly_returns.json"
    bak = HERE.parent / "data" / "strategy_monthly_returns_leftjoin.json"
    if not bak.exists():
        shutil.copy2(smr, bak)
    import build_strategy_monthly_returns as B
    B.main()
    print("完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
