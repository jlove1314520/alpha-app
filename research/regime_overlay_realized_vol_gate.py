"""regime overlay協定候選3——已實現波動度regime單獨測試，TRAIN期單次判定。

規格已在`REGIME_OVERLAY_PROTOCOL.md`第12節看結果前鎖定（rolling窗口20、
分界=expanding中位數、高波動曝險0.50/低波動1.00），本檔案只回報數字。
重用trend_filter_gate的apply_overlay(成本已內建主路徑)/metrics/控制組(a)。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from regime_overlay_trend_filter_gate import (
    apply_overlay, metrics, capture_ratios, crisis_window_results,
    control_a_random_switch, control_c_costs,
)

WINDOW = 20
QUANTILE = 0.5
HIGH_VOL_EXPOSURE = 0.50
LOW_VOL_EXPOSURE = 1.00


def build_exposure_vol(market_df: pd.DataFrame, window: int = WINDOW, q: float = QUANTILE,
                       high_exp: float = HIGH_VOL_EXPOSURE) -> pd.DataFrame:
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    ret = d["close"].pct_change()
    vol = ret.rolling(window, min_periods=window).std()
    thresh = vol.expanding(min_periods=60).quantile(q)  # PIT-safe：只用當日以前(含)資料
    high = vol > thresh
    d["exposure"] = np.where(high, high_exp, LOW_VOL_EXPOSURE)
    d.loc[thresh.isna() | vol.isna(), "exposure"] = np.nan  # warm-up不判定
    return d


def reduction(d):
    b = metrics(d["baseline_equity"], d["raw_return"])
    o = metrics(d["overlay_equity"], d["overlay_return"])
    g = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])
    red = (1 - o["mdd_pct"] / b["mdd_pct"]) * 100
    red_g = (1 - g["mdd_pct"] / b["mdd_pct"]) * 100
    return b, o, g, red, red_g


def main():
    print("=" * 70)
    print("regime overlay候選3 已實現波動度regime TRAIN期單次判定 (規格見協定第12節)")
    print("=" * 70)
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_overlay_realized_vol_gate")
    train_df = holdout.cap_to_train(prepare_market_data(raw))
    print(f"TRAIN期: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}")

    exposed = build_exposure_vol(train_df)
    d = apply_overlay(exposed)
    b, o, g, red, red_g = reduction(d)
    up, down = capture_ratios(d["raw_return"], d["overlay_return"])
    print(f"\n基底: CAGR={b['cagr_pct']:+.2f}% MDD={b['mdd_pct']:.2f}% Sortino={b['sortino']:.2f} Calmar={b['calmar']:.2f}")
    print(f"波動regime(淨): CAGR={o['cagr_pct']:+.2f}% MDD={o['mdd_pct']:.2f}% Sortino={o['sortino']:.2f} Calmar={o['calmar']:.2f}")
    print(f"波動regime(毛,對照): CAGR={g['cagr_pct']:+.2f}% MDD={g['mdd_pct']:.2f}%")
    print(f"MDD縮小(淨)={red:.1f}% (毛{red_g:.1f}%) (門檻>=35%: {'PASS' if red >= 35 else 'FAIL'})")
    print(f"上檔捕捉率={up:.1f}% (門檻>=75%: {'PASS' if up >= 75 else 'FAIL'})  下檔捕捉率={down:.1f}%")

    cc = control_c_costs(d)
    print(f"\n(c) 切換{cc['n_switches']}次 (每年{cc['switches_per_year']:.1f}次) "
          f"累計成本={cc['total_cost_pct_over_period']:.2f}% 年化成本={cc['cost_pct_per_year']:.2f}%")
    print(f"    成本前置關卡：切換頻率>8.4次/年={'是' if cc['switches_per_year'] > 8.4 else '否'}；"
          f"淨MDD縮小<毛的一半={'是' if red < red_g / 2 else '否'}")
    frac_high = float((d["exposure_lagged"] < 1).mean())
    print(f"    高波動(半倉)時間占比={frac_high * 100:.1f}%")

    print("\n--- 危機視窗(4個TRAIN可測) ---")
    n_imp = 0
    for r_ in crisis_window_results(d):
        if r_["improved"] is None:
            continue
        n_imp += int(r_["improved"])
        print(f"  {r_['window']}: 基底{r_['baseline_mdd_pct']:.1f}% overlay{r_['overlay_mdd_pct']:.1f}% "
              f"{'改善' if r_['improved'] else '未改善'}")
    print(f"  改善數 {n_imp}/4")

    ca = control_a_random_switch(d)
    print(f"\n(a) 隨機排列n=300: 真實改善={ca['real_mdd_improve_pct']:.2f}pp 隨機平均={ca['random_mean_improve_pct']:.2f}pp "
          f"百分位={ca['percentile']:.1f} ({'PASS' if ca['pass_gt_90'] else 'FAIL'})")

    d5 = apply_overlay(exposed, extra_lag_days=5)
    _, _, _, red5, _ = reduction(d5)
    print(f"(b) 延遲5日後MDD縮小(淨)={red5:.1f}% (延遲前{red:.1f}%)")

    print("\n(d) 參數高原 窗口 x 分位數 (MDD縮小%淨, * = >=35%)")
    qs = (0.35, 0.425, 0.5, 0.575, 0.65)
    print("        q:   " + "  ".join(f"{q:.3f}" for q in qs))
    n_pass = 0
    for w in (14, 17, 20, 23, 26):
        row = []
        for q in qs:
            dd_ = apply_overlay(build_exposure_vol(train_df, window=w, q=q))
            _, _, _, rd, _ = reduction(dd_)
            n_pass += int(rd >= 35)
            row.append(f"{rd:6.1f}{'*' if rd >= 35 else ' '}")
        print(f"  win={w:2d}  " + " ".join(row))
    print(f"  25格中MDD縮小>=35%: {n_pass}/25")

    print("\n結論:")
    print(f"  1.MDD縮小(淨)>=35%: {red:.1f}% (毛{red_g:.1f}%) -> {'PASS' if red >= 35 else 'FAIL'}")
    print(f"  2.上檔捕捉>=75%: {up:.1f}% -> {'PASS' if up >= 75 else 'FAIL'}")
    print(f"  3.危機視窗 {n_imp}/4 (換算待總司令裁示)")
    print(f"  4.控制組(a)百分位 {ca['percentile']:.1f}")
    print(f"  5.控制組(b)延遲後MDD縮小 {red5:.1f}%")
    print(f"  6.參數高原 {n_pass}/25")
    print(f"  sharpe={o['sharpe']:.4f} n={len(d)}")


if __name__ == "__main__":
    main()
