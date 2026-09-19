"""regime.替代A 連續型曝險調節——單次TRAIN判定（驗證帽輪次）。

規格：`REGIME_OVERLAY_PROTOCOL.md`第16節（2026-09-19鎖定，看到任何報酬/MDD數字前
已commit）。本檔案只執行鎖定規格，不調整任何門檻：
  淨MDD縮小>=35% 且 上檔捕捉>=75% -> PASS，否則 FAIL（連續+二元形式一起結案）。
訊號＝TAIEX收盤 vs 200MA的連續距離，曝險 E=clip(1-k*risk_z, 0.5, 1.0)，k=0.5。
基底＝TAIEX價格指數買進持有TRAIN期（未含股利，基底與overlay同口徑）。
holdout全程不碰（load_dev + cap_to_train + assert_no_holdout_leakage）。
"""
from __future__ import annotations
import json
import sys
import numpy as np
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
import regime_overlay_trend_filter_gate as g
from regime_alt_a_cost_precheck import continuous_exposure

MA_MAIN, K_MAIN = 200, 0.5
GRID_MA = (140, 200, 260)
GRID_K = (0.35, 0.5, 0.65)
OUT_JSON = "regime_alt_a_train_verdict_result.json"


def with_continuous(market: pd.DataFrame, ma: int, k: float) -> pd.DataFrame:
    d = market.sort_values("date").reset_index(drop=True).copy()
    d["exposure"] = continuous_exposure(d["close"], ma, k)
    return d


def with_binary(market: pd.DataFrame, ma_window: int = 200) -> pd.DataFrame:
    return g.build_exposure(market, ma_window=ma_window, bear_exposure=0.5)


def evaluate(d_exposed: pd.DataFrame, cost_scale: float = 1.0) -> dict:
    """套用overlay（成本照g的慣例），回傳判定用指標。cost_scale只用於單向成本敏感度。"""
    dd = d_exposed.dropna(subset=["exposure"]).copy()
    if cost_scale != 1.0:
        orig = g.COST_PER_UNIT_EXPOSURE_CHANGE
        g.COST_PER_UNIT_EXPOSURE_CHANGE = orig * cost_scale
        try:
            o = g.apply_overlay(dd)
        finally:
            g.COST_PER_UNIT_EXPOSURE_CHANGE = orig
    else:
        o = g.apply_overlay(dd)
    base = g.metrics(o["baseline_equity"], o["raw_return"])
    net = g.metrics(o["overlay_equity"], o["overlay_return"])
    gross = g.metrics(o["overlay_equity_gross"], o["overlay_return_gross"])
    up, down = g.capture_ratios(o["raw_return"], o["overlay_return"])
    red_net = (1 - net["mdd_pct"] / base["mdd_pct"]) * 100
    red_gross = (1 - gross["mdd_pct"] / base["mdd_pct"]) * 100
    yrs = len(o) / 245.0
    turn = float(o["exposure_lagged"].diff().abs().sum() / yrs)
    return {"o": o, "base": base, "net": net, "gross": gross, "up": up, "down": down,
            "red_net": red_net, "red_gross": red_gross, "turn": turn,
            "cost_pct_yr": float(o["switch_cost"].sum() * 100 / yrs),
            "avg_exp": float(o["exposure_lagged"].mean()),
            "n": len(o), "start": str(o["date"].iloc[0]), "end": str(o["date"].iloc[-1]),
            "days_changed": int((o["exposure_lagged"].diff().abs() > 1e-9).sum())}


def fmt(m: dict) -> str:
    return (f"CAGR={m['cagr_pct']:+.2f}% Sharpe={m['sharpe']:.2f} Sortino={m['sortino']:.2f} "
            f"MDD={m['mdd_pct']:.2f}% Calmar={m['calmar']:.2f}")


def main():
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_alt_a_train_verdict")
    market = holdout.cap_to_train(prepare_market_data(raw)).sort_values("date").reset_index(drop=True)
    print(f"TRAIN {market['date'].min()} ~ {market['date'].max()} n={len(market)}")

    res = {}
    # ---------- 主規格 ----------
    cont = with_continuous(market, MA_MAIN, K_MAIN)
    E = evaluate(cont)
    # 二元版：原始樣本（#243同口徑）與「對齊連續版樣本」兩種
    Bfull = evaluate(with_binary(market, 200))
    cont_start = cont.dropna(subset=["exposure"])["date"].iloc[0]
    bin_aligned = with_binary(market, 200)
    bin_aligned = bin_aligned[bin_aligned["date"] >= cont_start]
    Baligned = evaluate(bin_aligned)

    print("\n=== 主規格（MA200,k=0.5）並排 ===")
    print(f"連續版樣本: {E['start']}~{E['end']} n={E['n']}（連續版warm-up=MA200+sd252，樣本比二元版短）")
    print(f"  基底(連續版樣本): {fmt(E['base'])}")
    print(f"  連續淨: {fmt(E['net'])}")
    print(f"  連續毛: MDD={E['gross']['mdd_pct']:.2f}% 縮小(毛)={E['red_gross']:.1f}%")
    print(f"  ★淨MDD縮小={E['red_net']:.1f}% (門檻>=35) 上檔捕捉={E['up']:.1f}% (門檻>=75) 下檔捕捉={E['down']:.1f}%")
    print(f"  年化Σ|Δ曝險|={E['turn']:.2f} 年化成本拖累={E['cost_pct_yr']:.2f}% 平均曝險={E['avg_exp']:.3f} 曝險變動日數={E['days_changed']}")
    print(f"二元版(原樣本 {Bfull['start']}~ n={Bfull['n']}): 淨MDD縮小={Bfull['red_net']:.1f}% 毛={Bfull['red_gross']:.1f}% "
          f"上檔={Bfull['up']:.1f}% 下檔={Bfull['down']:.1f}% CAGR={Bfull['net']['cagr_pct']:+.2f}% 成本={Bfull['cost_pct_yr']:.2f}%/yr Σ|Δ|={Bfull['turn']:.2f} 平均曝險={Bfull['avg_exp']:.3f}")
    print(f"二元版(對齊連續樣本 n={Baligned['n']}): 基底{fmt(Baligned['base'])}")
    print(f"   淨MDD縮小={Baligned['red_net']:.1f}% 毛={Baligned['red_gross']:.1f}% 上檔={Baligned['up']:.1f}% 下檔={Baligned['down']:.1f}% "
          f"CAGR={Baligned['net']['cagr_pct']:+.2f}% Sharpe={Baligned['net']['sharpe']:.2f} Sortino={Baligned['net']['sortino']:.2f} Calmar={Baligned['net']['calmar']:.2f} "
          f"成本={Baligned['cost_pct_yr']:.2f}%/yr Σ|Δ|={Baligned['turn']:.2f}")

    # 單向成本敏感度（只回報）
    E_half = evaluate(cont, cost_scale=0.5)
    print(f"[僅回報]單向成本(x0.5): 連續淨MDD縮小={E_half['red_net']:.1f}% 上檔={E_half['up']:.1f}%")

    # 危機視窗
    print("\n--- 危機視窗（連續 vs 二元(對齊樣本)）---")
    crisis = []
    cw_c = g.crisis_window_results(E["o"])
    cw_b = g.crisis_window_results(Baligned["o"])
    for rc, rb in zip(cw_c, cw_b):
        if rc["improved"] is None:
            print(f"  {rc['window']}: 連續版樣本內無資料（warm-up未結束）")
            crisis.append({"window": rc["window"], "n": 0})
            continue
        print(f"  {rc['window']} n={rc['n']}: 基底{rc['baseline_mdd_pct']:.2f}% 連續{rc['overlay_mdd_pct']:.2f}%"
              f"({'改善' if rc['improved'] else '未改善'}) 二元{rb['overlay_mdd_pct']:.2f}%({'改善' if rb['improved'] else '未改善'})")
        crisis.append({"window": rc["window"], "n": rc["n"], "base": rc["baseline_mdd_pct"],
                       "cont": rc["overlay_mdd_pct"], "cont_improved": rc["improved"],
                       "bin": rb["overlay_mdd_pct"], "bin_improved": rb["improved"]})

    # ---------- 控制組 ----------
    print("\n--- 控制組(a) 排列法 n=300 ---")
    ca = g.control_a_random_switch(E["o"])
    print(f"  真實MDD改善={ca['real_mdd_improve_pct']:.2f}pp 隨機平均={ca['random_mean_improve_pct']:.2f}pp 百分位={ca['percentile']:.1f} (>90: {'PASS' if ca['pass_gt_90'] else 'FAIL'})")
    print("--- 控制組(b) 延遲5日 ---")
    d5 = g.apply_overlay(cont.dropna(subset=["exposure"]), extra_lag_days=5)
    m5 = g.metrics(d5["overlay_equity"], d5["overlay_return"])
    b5 = g.metrics(d5["baseline_equity"], d5["raw_return"])
    red5 = (1 - m5["mdd_pct"] / b5["mdd_pct"]) * 100
    print(f"  延遲後淨MDD縮小={red5:.1f}%（延遲前 {E['red_net']:.1f}%）")

    # ---------- (d) 9格高原 ----------
    print("\n--- 控制組(d) 9格高原（MDD淨縮小>=35 且 上檔>=75 才算格通過）---")
    grid = []
    for ma in GRID_MA:
        for k in GRID_K:
            ev = evaluate(with_continuous(market, ma, k))
            ok = ev["red_net"] >= 35 and ev["up"] >= 75
            print(f"  MA={ma} k={k}: 淨MDD縮小={ev['red_net']:.1f}% 上檔={ev['up']:.1f}% 成本={ev['cost_pct_yr']:.2f}%/yr "
                  f"n={ev['n']} {'通過' if ok else '未過'}")
            grid.append({"ma": ma, "k": k, "red_net": ev["red_net"], "red_gross": ev["red_gross"], "up": ev["up"],
                         "down": ev["down"], "cost_pct_yr": ev["cost_pct_yr"], "n": ev["n"], "pass": bool(ok),
                         "cagr": ev["net"]["cagr_pct"], "mdd": ev["net"]["mdd_pct"], "base_mdd": ev["base"]["mdd_pct"]})
    n_pass = sum(x["pass"] for x in grid)
    print(f"  {n_pass}/9格通過（高原判準>=7/9）")

    # ---------- 判定 ----------
    c1 = E["red_net"] >= 35
    c2 = E["up"] >= 75
    verdict = "PASS" if (c1 and c2) else "FAIL"
    print("\n=== 判定（鎖定順序，第16節）===")
    print(f"  淨MDD縮小 {E['red_net']:.1f}% ≥35: {c1}；上檔捕捉 {E['up']:.1f}% ≥75: {c2} -> {verdict}")
    if verdict == "FAIL":
        print("  連續形式與二元形式一起結案，不再嘗試第三種曝險調節函數形式。")
    else:
        print(f"  {'強通過(上檔>85)' if E['up'] > 85 else '通過(75<=上檔<=85)'}，進深度驗證；控制組(a)={ca['percentile']:.1f}、高原{n_pass}/9")

    out = {"verdict": verdict, "main": {k: (v if not isinstance(v, (pd.DataFrame, dict)) else None)
                                         for k, v in E.items() if k not in ("o", "base", "net", "gross")},
           "main_base": E["base"], "main_net": E["net"], "main_gross": E["gross"],
           "binary_full": {k: v for k, v in Bfull.items() if k not in ("o", "base", "net", "gross")},
           "binary_aligned": {k: v for k, v in Baligned.items() if k not in ("o", "base", "net", "gross")},
           "binary_aligned_net": Baligned["net"], "control_a": ca, "control_b_red": red5,
           "grid": grid, "grid_pass": n_pass, "crisis": crisis,
           "half_cost": {"red_net": E_half["red_net"], "up": E_half["up"]}}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n結果已寫入 {OUT_JSON}")


if __name__ == "__main__":
    main()
