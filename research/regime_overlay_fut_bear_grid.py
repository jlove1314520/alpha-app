"""FUT軌`bear_exposure`事前網格測試（`REGIME_OVERLAY_PROTOCOL.md`第15節，
2026-09-19總司令裁示【裁示】三）。

不重寫`regime_overlay_trend_filter_gate_fut.py`（已測試過、`#244`結果
仍是有效紀錄），完全複用它的函式（`build_exposure`/`apply_overlay`/
`metrics`/`capture_ratios`/`crisis_window_results`/`control_a_random_
switch`/`control_c_costs`），只是對`bear_exposure ∈ {0.25, 0.35, 0.45}`
（`MA_WINDOW=200`固定）各自跑一次完整協定，三格全部報告，不挑最好看
的一格。參數懸崖判準見協定第15節。
"""
from __future__ import annotations

import json

from regime_overlay_trend_filter_gate_fut import (
    MA_WINDOW, apply_overlay, build_exposure, capture_ratios,
    control_a_random_switch, control_c_costs, crisis_window_results,
    load_tx_train, metrics,
)

BEAR_GRID = (0.25, 0.35, 0.45)


def run_one(train_df, bear_exposure: float) -> dict:
    exposed = build_exposure(train_df, ma_window=MA_WINDOW, bear_exposure=bear_exposure)
    d = apply_overlay(exposed)
    base_m = metrics(d["baseline_equity"], d["raw_return"])
    over_m = metrics(d["overlay_equity"], d["overlay_return"])
    over_m_gross = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])
    up_cap, down_cap = capture_ratios(d["raw_return"], d["overlay_return"])
    mdd_reduction_pct = (1 - over_m["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
    mdd_reduction_gross_pct = (1 - over_m_gross["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")

    crisis_rows = crisis_window_results(d)
    n_available = sum(1 for r in crisis_rows if r["improved"] is not None)
    n_improved = sum(1 for r in crisis_rows if r["improved"])

    ctrl_a = control_a_random_switch(d)

    d_lag = apply_overlay(exposed, extra_lag_days=5)
    over_m_lag = metrics(d_lag["overlay_equity"], d_lag["overlay_return"])
    mdd_reduction_lag_pct = (1 - over_m_lag["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")

    ctrl_c = control_c_costs(d)

    pass_mdd = mdd_reduction_pct >= 35
    pass_upcap = up_cap >= 75
    pass_a = ctrl_a["pass_gt_90"]
    lag_direction_consistent = mdd_reduction_lag_pct > 0

    return {
        "bear_exposure": bear_exposure, "ma_window": MA_WINDOW,
        "base_mdd_pct": base_m["mdd_pct"], "base_cagr_pct": base_m["cagr_pct"],
        "overlay_mdd_pct_net": over_m["mdd_pct"], "overlay_mdd_pct_gross": over_m_gross["mdd_pct"],
        "overlay_cagr_pct_net": over_m["cagr_pct"], "overlay_sortino_net": over_m["sortino"],
        "mdd_reduction_pct_net": mdd_reduction_pct, "mdd_reduction_pct_gross": mdd_reduction_gross_pct,
        "up_capture_pct": up_cap, "down_capture_pct": down_cap,
        "crisis_windows_improved": n_improved, "crisis_windows_available": n_available,
        "control_a_percentile": ctrl_a["percentile"],
        "control_b_mdd_reduction_lag_pct": mdd_reduction_lag_pct,
        "control_b_direction_consistent": lag_direction_consistent,
        "control_c_switches_per_year": ctrl_c["switches_per_year"],
        "control_c_cost_pct_per_year": ctrl_c["cost_pct_per_year"],
        "pass_mdd_threshold": pass_mdd, "pass_upcap_threshold": pass_upcap,
        "pass_control_a": pass_a,
    }


def main() -> None:
    train_df = load_tx_train()
    print(f"TRAIN期範圍: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}天\n")

    results = [run_one(train_df, b) for b in BEAR_GRID]

    print("=" * 90)
    print(f"{'bear_exposure':>13} {'MDD縮小淨%':>10} {'MDD縮小毛%':>10} {'上檔捕捉%':>9} "
          f"{'危機改善':>8} {'控制a百分位':>10} {'控制b方向':>9} {'年切換次':>8}")
    for r in results:
        print(f"{r['bear_exposure']:>13.2f} {r['mdd_reduction_pct_net']:>10.1f} "
              f"{r['mdd_reduction_pct_gross']:>10.1f} {r['up_capture_pct']:>9.1f} "
              f"{r['crisis_windows_improved']:>3d}/{r['crisis_windows_available']:<4d} "
              f"{r['control_a_percentile']:>10.1f} "
              f"{'一致' if r['control_b_direction_consistent'] else '翻轉':>9} "
              f"{r['control_c_switches_per_year']:>8.1f}")
    print("=" * 90)

    n_pass_mdd = sum(1 for r in results if r["pass_mdd_threshold"])
    n_pass_upcap = sum(1 for r in results if r["pass_upcap_threshold"])
    n_pass_both = sum(1 for r in results if r["pass_mdd_threshold"] and r["pass_upcap_threshold"])

    print(f"\nMDD縮小≥35%門檻通過格數: {n_pass_mdd}/3")
    print(f"上檔捕捉≥75%門檻通過格數: {n_pass_upcap}/3")
    print(f"兩項門檻都通過格數: {n_pass_both}/3")

    if n_pass_both == 3:
        verdict = "PASS_ALL_THREE（三格都過，效果穩健，非單點運氣）"
    elif n_pass_both == 0:
        verdict = "FAIL_ALL_THREE（三格都沒過，換曝險水位救不回這個訊號）"
    else:
        verdict = "FAIL_PARAMETER_CLIFF（只有部分格通過，判定為參數懸崖，依協定第15節整體判FAIL）"
    print(f"\n最終判定: {verdict}")

    out = {"bear_grid": list(BEAR_GRID), "ma_window": MA_WINDOW, "results": results,
           "n_pass_mdd_threshold": n_pass_mdd, "n_pass_upcap_threshold": n_pass_upcap,
           "n_pass_both": n_pass_both, "verdict": verdict}
    with open("regime_fut_bear_grid_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n輸出已寫入 research/regime_fut_bear_grid_result.json")


if __name__ == "__main__":
    main()
