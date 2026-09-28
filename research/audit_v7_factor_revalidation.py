# -*- coding: utf-8 -*-
"""驗.七第三點：#7 `f_eps_surprise`／#8 `f_revenue_surprise` 重驗（2026-09-29
總司令裁示【驗.七】三）。**屬上線因子的驗證，不是新試驗，凍結.二不適用。
原#7/#8判定鎖定不動，結果登記為新編號。**

方法與原#7/#8完全相同：`factor_ic.py::run_ic_test()`（同一個抽樣種子
`SAMPLE_SEED=20260822`／300檔樣本／打散對照null distribution／Bonferroni
n=6／門檻98.33／期間`SNAPSHOT_START=2015-01-01`~`VAL_END`），只有資料層
不同。為了分開原因各跑兩組：
  (i)  舊還原公式＋新財報時點：`adjust.py`凍結在修.六重構前的版本
       （commit 7a8fd5cd，無分割/減資/面額變更處理、無÷1000/÷10修正），
       用`sys.modules`注入，`factors.py`用現行版本（含財報PIT.一之後的
       新財報時點）
  (ii) 新還原公式＋新財報時點：全部現行版本
原#7/#8（2026-08-23登記）= 舊還原公式＋舊財報時點；所以 原→(i) 看財報
時點的影響，(i)→(ii) 看還原公式的影響。

流程（裁示三.1「先預先登記」）：
  python audit_v7_factor_revalidation.py --prereg            # 登記2筆事前登記列(未結案)，先commit
  python audit_v7_factor_revalidation.py --group i          # 跑(i)
  python audit_v7_factor_revalidation.py --group ii         # 跑(ii)
  python audit_v7_factor_revalidation.py --register-results # 登記2筆結果列(新編號)
狀態檔：research/data/diag_v7_factor_revalidation.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import argparse
import importlib.util
import json
from pathlib import Path

STATE = Path(__file__).parent / "data" / "diag_v7_factor_revalidation.json"
FACTORS = ["f_eps_surprise", "f_revenue_surprise"]
ORIGINAL = {"f_eps_surprise": {"trial_id": 7, "null_percentile": 100.0},
            "f_revenue_surprise": {"trial_id": 8, "null_percentile": 99.0}}
FROZEN_ADJUST = Path(r"C:\Users\user\AppData\Local\Temp\claude\C--alpha\a8c8437e-502f-4bad-8e82-8f220f3b1158\scratchpad\adjust_pre_q2_frozen.py")
BONFERRONI_N = 6
REQUIRED_PCT = 98.33


def _load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def _save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def cmd_prereg() -> None:
    import trial_registry
    state = _load_state()
    if state.get("prereg"):
        print("已有事前登記，不重複登記：", state["prereg"])
        return
    state["prereg"] = {}
    for f in FACTORS:
        orig = ORIGINAL[f]
        tid, row = trial_registry.register_trial(
            track="TW",
            name=f"{f}_revalidation_v7_prereg",
            design=(f"驗.七(總司令2026-09-29裁示)事前登記：重驗原#{orig['trial_id']} `{f}`。方法與原登記完全相同"
                    f"（factor_ic.run_ic_test：SAMPLE_SEED=20260822/300檔/打散對照百分位/Bonferroni n={BONFERRONI_N}/"
                    f"門檻{REQUIRED_PCT}/期間SNAPSHOT_START~VAL_END），資料改用修正後資料層。各跑兩組分開原因："
                    f"(i)舊還原公式(adjust.py凍結於commit 7a8fd5cd，修.六重構前)＋新財報時點(現行factors.py)；"
                    f"(ii)新還原公式(現行adjust.py，含修.六/查.三/修.七四項修正)＋新財報時點。"
                    f"判定依(ii)：百分位>={REQUIRED_PCT}且train/val同號才PASS。屬上線因子驗證非新試驗，凍結.二不適用。"
                    f"原#{orig['trial_id']}判定鎖定不動，本筆為事前登記列，結果另登記新編號。"),
            result=f"n=0（事前登記，尚未執行；原#{orig['trial_id']}登記百分位={orig['null_percentile']}）",
            verdict="未結案",
            notes=("登記時間戳早於任何重驗執行。若(ii)過不了門檻：不得自行改score.py，改提降權或移除方案等Cowork核可，"
                   "App端核可前先在FACTORS.md註記「重驗未過，待處理」（裁示三.4）。"),
            round_note="驗.七事前登記（非馬拉松固定輪次）",
            no_stats_reason="事前登記列，尚未執行",
        )
        state["prereg"][f] = {"trial_id": tid}
        print(f"事前登記 {f} → #{tid}")
    _save_state(state)


def _run_group(group: str) -> None:
    if group == "i":
        assert FROZEN_ADJUST.exists(), f"凍結版adjust.py不存在：{FROZEN_ADJUST}"
        spec = importlib.util.spec_from_file_location("adjust", FROZEN_ADJUST)
        frozen = importlib.util.module_from_spec(spec)
        sys.modules["adjust"] = frozen
        spec.loader.exec_module(frozen)
        print("[group i] 已注入凍結版adjust.py（修.六重構前，commit 7a8fd5cd）")
    import factor_ic as fic
    import adjust as adj_check
    print(f"[group {group}] adjust module file = {getattr(adj_check, '__file__', '?')}")
    sample_ids = fic.sample_universe_ids(fic.SAMPLE_SIZE, fic.SAMPLE_SEED)
    results = fic.run_ic_test(FACTORS, sample_ids, f"驗.七 group ({group})", bonferroni_n=BONFERRONI_N)
    state = _load_state()
    state.setdefault("groups", {})[group] = {
        r.factor: {"null_percentile": round(r.null_percentile, 2), "required_percentile": round(r.required_percentile, 2),
                   "train_mean_ic": round(r.train_mean_ic, 4), "val_mean_ic": round(r.val_mean_ic, 4),
                   "val_ic_ir": round(r.val_ic_ir, 3), "n_dates_train": r.n_dates_train, "n_dates_val": r.n_dates_val,
                   "same_sign": bool(r.same_sign), "passes": bool(r.passes), "reasons": list(r.reasons)}
        for r in results}
    _save_state(state)
    print(f"[group {group}] 已存入狀態檔")


def cmd_register_results() -> None:
    import trial_registry
    state = _load_state()
    gi, gii = state.get("groups", {}).get("i"), state.get("groups", {}).get("ii")
    assert gi and gii, "兩組都跑完才可登記結果"
    if state.get("results"):
        print("結果已登記過，不重複：", state["results"]); return
    state["results"] = {}
    for f in FACTORS:
        orig, pre = ORIGINAL[f], state["prereg"][f]
        a, b = gi[f], gii[f]
        verdict = "PASS" if b["passes"] else "FAIL"
        tid, _ = trial_registry.register_trial(
            track="TW",
            name=f"{f}_revalidation_v7",
            design=(f"驗.七重驗結果（事前登記列#{pre['trial_id']}，原#{orig['trial_id']}判定鎖定不動）。方法同原登記，"
                    f"資料層(ii)=現行adjust.py+現行factors.py；(i)=凍結舊adjust.py+現行factors.py，僅供拆解原因。"),
            result=(f"原#{orig['trial_id']}百分位={orig['null_percentile']}；(i)舊還原公式+新財報時點：百分位={a['null_percentile']}"
                    f"(val_ic={a['val_mean_ic']:+.4f},n={a['n_dates_val']})；(ii)新還原公式+新財報時點：百分位={b['null_percentile']}"
                    f"(val_ic={b['val_mean_ic']:+.4f},IR={b['val_ic_ir']:+.3f},n={b['n_dates_val']},same_sign={b['same_sign']})，"
                    f"門檻{REQUIRED_PCT}"),
            verdict=verdict,
            notes=(("原→(i)的差距歸因於財報時點(PIT)修正，(i)→(ii)的差距歸因於還原公式修正。"
                    + ("(ii)未過門檻：依裁示三.4不改score.py，另提降權/移除方案等Cowork核可，FACTORS.md已註記「重驗未過，待處理」。"
                       if verdict == "FAIL" else "(ii)通過門檻。"))),
            round_note="驗.七重驗（非馬拉松固定輪次）",
            failed_gates=(["unknown"] if verdict == "FAIL" else None),
        )
        state["results"][f] = {"trial_id": tid, "verdict": verdict}
        print(f"結果登記 {f} → #{tid} {verdict}")
    _save_state(state)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prereg", action="store_true")
    ap.add_argument("--group", choices=["i", "ii"])
    ap.add_argument("--register-results", action="store_true")
    a = ap.parse_args()
    if a.prereg:
        cmd_prereg()
    elif a.group:
        _run_group(a.group)
    elif a.register_results:
        cmd_register_results()
    else:
        ap.print_help()
