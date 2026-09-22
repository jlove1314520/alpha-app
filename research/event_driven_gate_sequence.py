# -*- coding: utf-8 -*-
"""方法.三續.GATE_SEQUENCE驗證（`PENDING_QUEUE.md`方法.三#323「下一步」，
2026-09-22 hypothesis_queue排程接續）。

對`event_driven_prototype.py`已建好的E1(財報SUE)/E2(月營收SUE)事件表，補上
裁示原文指定的四項關卡（不是完整9關GATE_SEQUENCE，是通往下一關的cheap gate
組合）：
  1. 隨機控制組排列檢定（比照control_group_standard.py::evaluate_vs_control()）
  2. train/val樣本外切分（本題只碰train+val，holdout不動）
  3. 成本敏感度——[自行裁量]改用margin_of_safety.py三情境，取代裁示原文字面
     的「1x/2x/3x」：CLAUDE.md「七之三」節2026-09-19裁示【#63邊緣案例】已
     廢止機械倍數規則、全專案統一改用margin_of_safety.py，此處遵循較新的
     專案鐵律而非本條目較舊的字面措辭
  4. leave-one-out（單一時間窗/單一產業移除）

全數通過→CHEAP_PASS；任一項FAIL→FAIL＋failed_gates，寫進STRATEGY_GRAVEYARD.md，
不放寬門檻救活。判定只看t+20（跟`event_driven_prototype.py::direction_summary()`
同一個決定性horizon，其餘horizon只供參考不進判定）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from event_driven_prototype import EVENT_TYPES, TOP_DECILE, build_event_table
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from tail_test import tail_test
from trials_power_audit import DEGENERATE_N_FLOOR
from validation import holdout
from validation.margin_of_safety import passes_worst_case

DECISION_HORIZON = 20
N_DRAWS_PER_VARIANT = 100
RNG_SEED = 20260922
# [自行裁量，2026-09-22馬拉松第592輪]：`tail_test.py`預設N_BOOTSTRAP=10000
# 是裁示原文「各bootstrap 10000次」針對候選最終回報統計量訂的門檻，這裡的
# 用途不同——`gate_random_control`/`gate_leave_one_out`是重複呼叫tail_test
# 上百次來建立null分布或做逐一排除的方向性檢查，不是最終回報的那一個統計量。
# 實測：n_bootstrap=10000時單次tail_test（sig~700/ctl~6000規模）耗時
# 5.28秒，200次排列檢定+leave-one-out合計會遠超過5分鐘門檻
# （MARATHON_PROTOCOL.md 0b節）。改用n_bootstrap=500後單次降到0.12秒
# （43倍），且bootstrap均值本身（median_diff點估計）不隨n_bootstrap有系統性
# 偏移，只是CI精度降低——這裡只需要點估計去比大小/判方向，不需要精確CI。
# 為求同一個統計量前後一致，`actual`統計量與200次排列檢定draws用同一個
# n_bootstrap，才是公平比較（避免用不同精度的估計互相比大小）。
AUX_N_BOOTSTRAP = 500


def _split_signal_control(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_top = max(1, int(np.ceil(len(events) * TOP_DECILE)))
    ordered = events.sort_values("surprise", ascending=False)
    signal_df = ordered.iloc[:n_top]
    non_signal_df = ordered.iloc[n_top:]
    active_buckets = set(signal_df["bucket_key"])
    control_df = non_signal_df[non_signal_df["bucket_key"].isin(active_buckets)]
    return signal_df, control_df


def _direction_ok(out: dict) -> bool:
    if out["insufficient_n"]:
        return False
    return out["median_diff"] > 0 and out["right_tail_share_signal"] > out["right_tail_share_control"]


def gate_random_control(events: pd.DataFrame, signal_df: pd.DataFrame, control_df: pd.DataFrame) -> dict:
    """隨機控制組排列檢定：兩個變體都在null下重抽「假訊號組」，量median_diff。
    變體A：假訊號組限定從實際命中的bucket內抽（維持bucket配對結構）。
    變體B：假訊號組從全部events不設bucket限制隨機抽（較鬆的null，掃過控制組
    自身參數，符合`control_group_standard.py`「控制組自身參數必須掃過」）。
    """
    n_top = len(signal_df)
    actual = tail_test(signal_df["entry_date"].tolist(), signal_df[f"fwd{DECISION_HORIZON}"].tolist(),
                        control_df[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON,
                        n_bootstrap=AUX_N_BOOTSTRAP)
    signal_stat = actual["median_diff"]

    rng = np.random.RandomState(RNG_SEED)
    active_buckets = set(signal_df["bucket_key"])
    bucket_pool = events[events["bucket_key"].isin(active_buckets)]
    variant_a = []
    for _ in range(N_DRAWS_PER_VARIANT):
        idx = rng.choice(bucket_pool.index, size=min(n_top, len(bucket_pool)), replace=False)
        fake_sig = bucket_pool.loc[idx]
        fake_ctl = bucket_pool.drop(idx)
        out = tail_test(fake_sig["entry_date"].tolist(), fake_sig[f"fwd{DECISION_HORIZON}"].tolist(),
                         fake_ctl[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON, min_n=1,
                         n_bootstrap=AUX_N_BOOTSTRAP)
        variant_a.append(out["median_diff"] if not out["insufficient_n"] else 0.0)

    variant_b = []
    for _ in range(N_DRAWS_PER_VARIANT):
        idx = rng.choice(events.index, size=min(n_top, len(events)), replace=False)
        fake_sig = events.loc[idx]
        fake_ctl = events.drop(idx)
        out = tail_test(fake_sig["entry_date"].tolist(), fake_sig[f"fwd{DECISION_HORIZON}"].tolist(),
                         fake_ctl[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON, min_n=1,
                         n_bootstrap=AUX_N_BOOTSTRAP)
        variant_b.append(out["median_diff"] if not out["insufficient_n"] else 0.0)

    verdict = evaluate_vs_control(
        signal_stat=signal_stat,
        control_draws={"同bucket限定重抽": variant_a, "全事件池不限bucket重抽": variant_b},
        selection_spec=(f"事前綁定：以SUE前{int(TOP_DECILE*100)}%為訊號組、t+{DECISION_HORIZON}"
                         "median_diff為統計量，唯一選點，2026-09-22方法.三續.GATE_SEQUENCE驗證"),
    )
    return {"passed": verdict.passed, "reason": verdict.reason, "signal_stat": signal_stat,
            "control_max": verdict.control_max, "n_draws_total": verdict.n_draws_total}


def gate_train_val_oos(signal_df: pd.DataFrame, control_df: pd.DataFrame) -> dict:
    """train/val樣本外切分：訊號組/對照組各自依entry_date切train(<=TRAIN_END)/
    val((TRAIN_END,VAL_END])，兩段方向須一致（同`direction_summary()`定義）。
    """
    sig_train = holdout.cap_to_train(signal_df, date_col="entry_date")
    ctl_train = holdout.cap_to_train(control_df, date_col="entry_date")
    sig_val = holdout.validation_slice(signal_df, date_col="entry_date")
    ctl_val = holdout.validation_slice(control_df, date_col="entry_date")

    out_train = tail_test(sig_train["entry_date"].tolist(), sig_train[f"fwd{DECISION_HORIZON}"].tolist(),
                           ctl_train[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON)
    out_val = tail_test(sig_val["entry_date"].tolist(), sig_val[f"fwd{DECISION_HORIZON}"].tolist(),
                         ctl_val[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON)
    ok = _direction_ok(out_train) and _direction_ok(out_val)
    return {"passed": ok, "train": out_train, "val": out_val,
            "n_sig_train": len(sig_train), "n_sig_val": len(sig_val)}


def gate_cost_sensitivity(signal_df: pd.DataFrame) -> dict:
    """成本敏感度——[自行裁量]用margin_of_safety.py三情境取代裁示原文字面
    「1x/2x/3x」（CLAUDE.md七之三節2026-09-19已全專案廢止機械倍數）。
    判準：最壞情境下訊號組自身期望值（不是diff）仍為正——這是「這個策略
    自己拿去交易會不會賠掉手續費」的問題，不是相對對照組的統計顯著性問題。
    """
    sig = signal_df[f"fwd{DECISION_HORIZON}"].dropna().to_numpy(dtype=float)
    mean_ret = float(np.mean(sig))
    result = passes_worst_case(lambda cost_pct: mean_ret - cost_pct, daytrade=False)
    return {"passed": result["verdict"] == "PASS", "mean_return": mean_ret, "scenarios": result}


def gate_leave_one_out(events: pd.DataFrame) -> dict:
    """單一時間窗(quarter)/單一產業移除後，方向是否仍在。"""
    details = {"removed_time_bucket": {}, "removed_industry": {}}
    all_ok = True
    for tb in sorted(events["time_bucket"].unique()):
        remaining = events[events["time_bucket"] != tb]
        if remaining.empty:
            continue
        sig, ctl = _split_signal_control(remaining)
        out = tail_test(sig["entry_date"].tolist(), sig[f"fwd{DECISION_HORIZON}"].tolist(),
                         ctl[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON, min_n=1,
                         n_bootstrap=AUX_N_BOOTSTRAP)
        ok = _direction_ok(out)
        details["removed_time_bucket"][tb] = ok
        all_ok = all_ok and ok
    for ind in sorted(events["industry"].dropna().unique()):
        remaining = events[events["industry"] != ind]
        if remaining.empty:
            continue
        sig, ctl = _split_signal_control(remaining)
        out = tail_test(sig["entry_date"].tolist(), sig[f"fwd{DECISION_HORIZON}"].tolist(),
                         ctl[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON, min_n=1,
                         n_bootstrap=AUX_N_BOOTSTRAP)
        ok = _direction_ok(out)
        details["removed_industry"][ind] = ok
        all_ok = all_ok and ok
    n_fail_time = sum(1 for v in details["removed_time_bucket"].values() if not v)
    n_fail_ind = sum(1 for v in details["removed_industry"].values() if not v)
    return {"passed": all_ok, "n_time_buckets": len(details["removed_time_bucket"]),
            "n_fail_time_bucket": n_fail_time, "n_industries": len(details["removed_industry"]),
            "n_fail_industry": n_fail_ind, "details": details}


def run_gate_sequence(event_name: str, spec: dict, sample_ids: list[str]) -> dict:
    print(f"\n=== {event_name} ===")
    events = build_event_table(sample_ids, spec["surprise_fn"], spec["surprise_col"], verbose=False)
    if events.empty or len(events) < DEGENERATE_N_FLOOR:
        return {"event_name": event_name, "power_class": "DEGENERATE",
                "reason": f"events={len(events)} < DEGENERATE_N_FLOOR={DEGENERATE_N_FLOOR}",
                "gates": {}, "verdict": "FAIL", "failed_gates": ["unknown"]}

    signal_df, control_df = _split_signal_control(events)
    gates = {}
    failed = []

    g1 = gate_random_control(events, signal_df, control_df)
    gates["random_control"] = g1
    print(f"[隨機控制組] passed={g1['passed']} signal={g1['signal_stat']:+.4f} control_max={g1['control_max']:+.4f}")
    if not g1["passed"]:
        failed.append("gate2")

    g2 = gate_train_val_oos(signal_df, control_df)
    gates["train_val_oos"] = {"passed": g2["passed"], "n_sig_train": g2["n_sig_train"], "n_sig_val": g2["n_sig_val"],
                               "train_median_diff": g2["train"]["median_diff"], "val_median_diff": g2["val"]["median_diff"]}
    print(f"[train/val OOS] passed={g2['passed']} train_n={g2['n_sig_train']} val_n={g2['n_sig_val']} "
          f"train_diff={g2['train']['median_diff']} val_diff={g2['val']['median_diff']}")
    if not g2["passed"]:
        failed.append("unknown")  # FAILED_GATES_VOCAB無專屬train/val槽位，如實標unknown＋notes說明

    g3 = gate_cost_sensitivity(signal_df)
    gates["cost_sensitivity"] = g3
    print(f"[成本敏感度-margin_of_safety] passed={g3['passed']} mean_return={g3['mean_return']:+.4f}")
    if not g3["passed"]:
        failed.append("gate4")

    g4 = gate_leave_one_out(events)
    gates["leave_one_out"] = g4
    print(f"[leave-one-out] passed={g4['passed']} 時間窗失敗{g4['n_fail_time_bucket']}/{g4['n_time_buckets']} "
          f"產業失敗{g4['n_fail_industry']}/{g4['n_industries']}")
    if not g4["passed"]:
        failed.append("gate5")

    verdict = "CHEAP_PASS" if not failed else "FAIL"
    return {"event_name": event_name, "n_events": len(events), "gates": gates,
            "verdict": verdict, "failed_gates": failed}


def main() -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    out = {}
    for name, spec in EVENT_TYPES.items():
        out[name] = run_gate_sequence(name, spec, sample_ids)
    return out


if __name__ == "__main__":
    import json
    result = main()
    out_path = Path(__file__).parent / "event_driven_gate_sequence_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
    for name, r in result.items():
        print(f"{name}: verdict={r['verdict']} failed_gates={r.get('failed_gates')}")
