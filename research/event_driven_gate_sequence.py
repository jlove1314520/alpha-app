# -*- coding: utf-8 -*-
"""方法.三續.GATE_SEQUENCE驗證（`PENDING_QUEUE.md`方法.三#323「下一步」，
2026-09-22 hypothesis_queue排程接續）；2026-09-23補正執行偏離（方法.三續
E1重判，見`PENDING_QUEUE.md`「方法.三續.E1重判」）：`gate_random_control`
原本用`signal_stat = actual["median_diff"]`決定生死，但方法.二登記的通過
判準是「(b) P90差異 或 (c) 右尾佔比 顯著」，median_diff從未被登記為判準
——這是執行偏離，不是原本的判定就是錯的統計方法。已改為同時輸出
median_diff(對照用，不再單獨決定生死)/p90_diff(判準b)/right_tail_share_
diff(判準c)，三者共用同一批重抽（500+500=1000，不分開跑），且新增(d)
左尾不顯著惡化檢查，判準寫死為「訊號值嚴格超過1000次重抽第999名」
（見`_exceeds_rank_999()`）。本檔案只重判E1；E2已雙重FAIL（隨機控制組
未過且train/val方向翻轉），依裁示不重跑，維持既有`TRIALS_LEDGER.md`
#326結案。

對`event_driven_prototype.py`已建好的E1(財報SUE)/E2(月營收SUE)事件表，補上
裁示原文指定的四項關卡（不是完整9關GATE_SEQUENCE，是通往下一關的cheap gate
組合）：
  1. 隨機控制組閘門（2026-09-23起判準為方法.二登記的(b)P90差異／(c)右尾
     佔比／(d)左尾不顯著惡化，見上方說明，不再是舊版`control_group_
     standard.py::evaluate_vs_control()`的median_diff-vs-控制組最大值）
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

from event_driven_prototype import EVENT_TYPES, TOP_DECILE, build_event_table
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from tail_test import tail_test
from trials_power_audit import DEGENERATE_N_FLOOR
from validation import holdout
from validation.margin_of_safety import passes_worst_case

DECISION_HORIZON = 20
# 2026-09-23【方法.三續E1重判】裁示原文：「抽樣數從200提高到1000」——
# 200/1000都是「兩個變體合併後的總抽樣數」（既有結構是variant_a+variant_b
# 各N_DRAWS_PER_VARIANT次，合併起來才是拿去跟訊號值比較的null池），
# 故N_DRAWS_PER_VARIANT改成500（500+500=1000），不是把500當成單一變體
# 的「新的100→500」誤解成1000×2=2000。
N_DRAWS_PER_VARIANT = 500
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


def _exceeds_rank_999(value: float, null_draws: list[float]) -> tuple[bool, float]:
    """裁示原文判準：「嚴格超過1000次重抽的第999名」——由大到小排序後，
    第999名(ascending)＝倒數第2大(descending index 1)，因為只有最大值1個
    draw比它更極端，等價單尾p<=1/len(draws)（1000次時p<=0.001）。
    draws實際數量可能<1000（insufficient_n的draw被剔除不硬填0，見
    `_draw_null_stats`），門檻定義隨實際可用draws數調整，函式回傳
    (是否通過, 門檻值)供回報。"""
    s = sorted(null_draws, reverse=True)
    threshold = s[1] if len(s) >= 2 else s[0]
    return value > threshold, threshold


def _draw_null_stats(events: pd.DataFrame, signal_df: pd.DataFrame, n_top: int) -> dict[str, list[float]]:
    """兩個變體（bucket限定／全事件池）各抽`N_DRAWS_PER_VARIANT`次，合併成
    單一null池（不分開跑，避免偷加試驗次數，見裁示原文續.A.1）。每次重抽
    同時算median_diff/p90_diff/right_tail_share_diff/left_tail_share_diff
    四個統計量（用同一批fake_sig/fake_ctl，不同統計量之間不獨立重抽）。
    insufficient_n的draw直接跳過不計入（不用0.0佔位，避免用一個可能失真
    的常數污染null分布——0.0對diff類統計量剛好落在「兩組沒有差異」的位置，
    會系統性地把null分布往「沒有效果」推，讓門檻虛高，反而讓真訊號更容易
    被誤判FAIL，方向對這裡的保守要求不利，故改為跳過）。"""
    active_buckets = set(signal_df["bucket_key"])
    bucket_pool = events[events["bucket_key"].isin(active_buckets)]
    rng = np.random.RandomState(RNG_SEED)
    out = {"median_diff": [], "p90_diff": [], "right_tail_share_diff": [], "left_tail_share_diff": []}
    n_skipped = 0
    for pool, replace_pool_each_draw in ((bucket_pool, True), (events, True)):
        for _ in range(N_DRAWS_PER_VARIANT):
            idx = rng.choice(pool.index, size=min(n_top, len(pool)), replace=False)
            fake_sig = pool.loc[idx]
            fake_ctl = pool.drop(idx)
            r = tail_test(fake_sig["entry_date"].tolist(), fake_sig[f"fwd{DECISION_HORIZON}"].tolist(),
                          fake_ctl[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON, min_n=1,
                          n_bootstrap=AUX_N_BOOTSTRAP)
            if r["insufficient_n"]:
                n_skipped += 1
                continue
            out["median_diff"].append(r["median_diff"])
            out["p90_diff"].append(r["p90_diff"])
            out["right_tail_share_diff"].append(r["right_tail_share_signal"] - r["right_tail_share_control"])
            out["left_tail_share_diff"].append(r["left_tail_share_signal"] - r["left_tail_share_control"])
    out["_n_skipped_insufficient"] = n_skipped
    out["_n_total_requested"] = 2 * N_DRAWS_PER_VARIANT
    return out


def gate_random_control(events: pd.DataFrame, signal_df: pd.DataFrame, control_df: pd.DataFrame) -> dict:
    """隨機控制組閘門（2026-09-23補正版，見模組docstring）：判準只認方法.二
    登記的(b) P90差異／(c) 右尾佔比／(d) 左尾不顯著惡化，median_diff只作
    對照記錄不再單獨決定生死。變體A：假訊號組限定從實際命中的bucket內抽
    （維持bucket配對結構）。變體B：假訊號組從全部events不設bucket限制
    隨機抽（較鬆的null，掃過控制組自身參數，符合`control_group_standard.py`
    「控制組自身參數必須掃過」）。兩變體合併成同一批1000次null（見
    `_draw_null_stats`），(b)(c)(d)共用同一批抽樣，不分開跑。
    """
    n_top = len(signal_df)
    actual = tail_test(signal_df["entry_date"].tolist(), signal_df[f"fwd{DECISION_HORIZON}"].tolist(),
                        control_df[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON,
                        n_bootstrap=AUX_N_BOOTSTRAP)
    actual_right_tail_diff = actual["right_tail_share_signal"] - actual["right_tail_share_control"]
    actual_left_tail_diff = actual["left_tail_share_signal"] - actual["left_tail_share_control"]

    null = _draw_null_stats(events, signal_df, n_top)

    b_pass, b_threshold = _exceeds_rank_999(actual["p90_diff"], null["p90_diff"])
    c_pass, c_threshold = _exceeds_rank_999(actual_right_tail_diff, null["right_tail_share_diff"])
    # (d) 左尾不顯著惡化：訊號組左尾佔比不得顯著高於對照組——用同一套rank-999
    # 門檻反向檢查（訊號值不得超過null分布的999名），跟(b)/(c)同一套嚴謹度，
    # 不另外發明一個新的顯著性判準（見PENDING_QUEUE.md[自行裁量]）。
    d_fail, d_threshold = _exceeds_rank_999(actual_left_tail_diff, null["left_tail_share_diff"])
    d_pass = not d_fail

    bc_pass = b_pass or c_pass
    passed = bool(bc_pass and d_pass)
    reason_bits = [
        f"(b)P90差異訊號{actual['p90_diff']:+.4f} {'>' if b_pass else '<='}999名門檻{b_threshold:+.4f}",
        f"(c)右尾佔比差異訊號{actual_right_tail_diff:+.4f} {'>' if c_pass else '<='}999名門檻{c_threshold:+.4f}",
        f"(d)左尾佔比差異訊號{actual_left_tail_diff:+.4f} {'<=' if d_pass else '>'}999名門檻{d_threshold:+.4f}"
        f"（{'未顯著惡化' if d_pass else '顯著惡化，直接否決'}）",
    ]
    return {
        "passed": passed, "reason": "；".join(reason_bits),
        "b_pass": b_pass, "c_pass": c_pass, "d_pass": d_pass,
        "median_diff_signal": actual["median_diff"], "median_diff_note": "僅供對照，不決定生死",
        "p90_diff_signal": actual["p90_diff"], "p90_diff_threshold_999": b_threshold,
        "right_tail_share_diff_signal": actual_right_tail_diff, "right_tail_share_diff_threshold_999": c_threshold,
        "left_tail_share_diff_signal": actual_left_tail_diff, "left_tail_share_diff_threshold_999": d_threshold,
        "n_null_draws_p90": len(null["p90_diff"]), "n_null_draws_right_tail": len(null["right_tail_share_diff"]),
        "n_null_draws_left_tail": len(null["left_tail_share_diff"]),
        "n_skipped_insufficient": null["_n_skipped_insufficient"], "n_total_requested": null["_n_total_requested"],
    }


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


VOL_COLLAPSE_THRESHOLD = 0.5  # 裁示原文「崩掉一半以上」


def gate_volatility_matched_control(events: pd.DataFrame) -> dict:
    """續.B（PENDING_QUEUE.md「方法.三續.E1重判」）：高SUE個股本質上波動更大，
    P90可能被波動度機械性推高而非真的alpha。新增事件日前`VOL_WINDOW`交易日
    已實現波動度五分位當第4配對維度，3維(`bucket_key`)vs4維(`bucket_key_vol`)
    的p90_diff並列比較。只用有`pre_event_vol`(entry_idx>=VOL_WINDOW)的事件
    子集——沒有波動度資料的事件無法做4維配對，不是又挑了一次訊號好的子集
    （3維/4維在**同一個**子集上重新切訊號/對照組，比較的是「換配對維度」
    本身的效果，不是「換了不同事件集合」造成的差異）。
    """
    has_vol = events["bucket_key_vol"].notna()
    events_vol = events[has_vol].copy()
    n_dropped = len(events) - len(events_vol)

    n_top = max(1, int(np.ceil(len(events_vol) * TOP_DECILE)))
    ordered = events_vol.sort_values("surprise", ascending=False)
    signal_df = ordered.iloc[:n_top]
    non_signal_df = ordered.iloc[n_top:]

    def _control_for(key_col: str) -> pd.DataFrame:
        active = set(signal_df[key_col])
        return non_signal_df[non_signal_df[key_col].isin(active)]

    control_3d = _control_for("bucket_key")
    control_4d = _control_for("bucket_key_vol")

    out_3d = tail_test(signal_df["entry_date"].tolist(), signal_df[f"fwd{DECISION_HORIZON}"].tolist(),
                        control_3d[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON)
    out_4d = tail_test(signal_df["entry_date"].tolist(), signal_df[f"fwd{DECISION_HORIZON}"].tolist(),
                        control_4d[f"fwd{DECISION_HORIZON}"].tolist(), horizon=DECISION_HORIZON)

    p90_3d = None if out_3d["insufficient_n"] else out_3d["p90_diff"]
    p90_4d = None if out_4d["insufficient_n"] else out_4d["p90_diff"]

    collapsed = None
    drop_ratio = None
    if p90_3d is not None and p90_4d is not None and p90_3d != 0:
        drop_ratio = (p90_3d - p90_4d) / abs(p90_3d)
        collapsed = drop_ratio >= VOL_COLLAPSE_THRESHOLD

    return {
        "n_events_with_vol": len(events_vol), "n_dropped_no_vol": n_dropped,
        "n_signal": len(signal_df), "n_control_3d": len(control_3d), "n_control_4d": len(control_4d),
        "p90_diff_3d": p90_3d, "p90_diff_4d": p90_4d, "drop_ratio": drop_ratio,
        "collapsed": collapsed,
        "vol_median_signal": float(signal_df["pre_event_vol"].median()) if not signal_df.empty else None,
        "vol_median_control_3d": float(control_3d["pre_event_vol"].median()) if not control_3d.empty else None,
        "vol_median_control_4d": float(control_4d["pre_event_vol"].median()) if not control_4d.empty else None,
        "out_3d": out_3d, "out_4d": out_4d,
    }


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

    # 2026-09-23【方法.三續E1重判】變數改語意化命名（`g1`~`g4`→
    # `g_random_control`等），避免跟`failed_gates`使用的全域共用語意編號
    # （`trial_registry.py::FAILED_GATES_VOCAB`的gate1~6，含義固定為
    # sanity/隨機控制組/參數高原/成本敏感度/leave-one-out/逐年一致性，
    # 不是本檔案這4關的本地呼叫順序）混淆——下方gate2/gate4/gate5的
    # 對應本身語意正確（隨機控制組=gate2、成本敏感度=gate4、
    # leave-one-out=gate5），已於PENDING_QUEUE.md記錄查證過程，這裡
    # 只是改名字讓下一個讀者不會誤以為「第1個呼叫就該回報gate1」。
    g_random_control = gate_random_control(events, signal_df, control_df)
    gates["random_control"] = g_random_control
    print(f"[隨機控制組] passed={g_random_control['passed']} {g_random_control['reason']}")
    if not g_random_control["passed"]:
        failed.append("gate2")

    g_train_val = gate_train_val_oos(signal_df, control_df)
    gates["train_val_oos"] = {"passed": g_train_val["passed"], "n_sig_train": g_train_val["n_sig_train"],
                               "n_sig_val": g_train_val["n_sig_val"],
                               "train_median_diff": g_train_val["train"]["median_diff"],
                               "val_median_diff": g_train_val["val"]["median_diff"]}
    print(f"[train/val OOS] passed={g_train_val['passed']} train_n={g_train_val['n_sig_train']} "
          f"val_n={g_train_val['n_sig_val']} train_diff={g_train_val['train']['median_diff']} "
          f"val_diff={g_train_val['val']['median_diff']}")
    if not g_train_val["passed"]:
        failed.append("unknown")  # FAILED_GATES_VOCAB無專屬train/val槽位，如實標unknown＋notes說明

    g_cost = gate_cost_sensitivity(signal_df)
    gates["cost_sensitivity"] = g_cost
    print(f"[成本敏感度-margin_of_safety] passed={g_cost['passed']} mean_return={g_cost['mean_return']:+.4f}")
    if not g_cost["passed"]:
        failed.append("gate4")

    g_leave_one_out = gate_leave_one_out(events)
    gates["leave_one_out"] = g_leave_one_out
    print(f"[leave-one-out] passed={g_leave_one_out['passed']} "
          f"時間窗失敗{g_leave_one_out['n_fail_time_bucket']}/{g_leave_one_out['n_time_buckets']} "
          f"產業失敗{g_leave_one_out['n_fail_industry']}/{g_leave_one_out['n_industries']}")
    if not g_leave_one_out["passed"]:
        failed.append("gate5")

    verdict = "CHEAP_PASS" if not failed else "FAIL"

    # 續.B（PENDING_QUEUE.md「方法.三續.E1重判」）：只在續.A（隨機控制組
    # 閘門，g_random_control）通過時才做——這是專門檢驗「(b)/(c)過關是不是
    # 波動度效應而非alpha」的追加檢查，(b)/(c)沒過就沒有東西需要被檢驗。
    g_vol_matched = None
    if g_random_control["passed"]:
        g_vol_matched = gate_volatility_matched_control(events)
        gates["volatility_matched_control"] = g_vol_matched
        print(f"[續.B波動度配對] 3維p90_diff={g_vol_matched['p90_diff_3d']} "
              f"4維p90_diff={g_vol_matched['p90_diff_4d']} "
              f"崩掉比例={g_vol_matched['drop_ratio']} collapsed={g_vol_matched['collapsed']} "
              f"波動度中位數(訊號/3維對照/4維對照)="
              f"{g_vol_matched['vol_median_signal']}/{g_vol_matched['vol_median_control_3d']}/"
              f"{g_vol_matched['vol_median_control_4d']}")

    return {"event_name": event_name, "n_events": len(events), "gates": gates,
            "verdict": verdict, "failed_gates": failed}


def main() -> dict:
    """2026-09-23【方法.三續E1重判】只重判E1——E2已雙重FAIL（隨機控制組
    未過且train/val方向翻轉），裁示原文明寫「不重跑」，維持既有#326結案。
    """
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    out = {}
    name = "E1_財報公布(SUE)"
    out[name] = run_gate_sequence(name, EVENT_TYPES[name], sample_ids)
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
