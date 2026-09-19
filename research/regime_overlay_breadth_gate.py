"""regime overlay協定候選1——市場廣度水位regime，TRAIN期單次判定。

規格已在`REGIME_OVERLAY_PROTOCOL.md`第13節看結果前鎖定（MA窗口200、
廣度<0.50→曝險0.50、否則1.00）。宇宙=本機`data/raw`全部4位數代號個股快取，
**存活者偏誤未修正**(今天仍在市的名冊,偽影⑦)，結論須附此但書。
重用trend_filter_gate的apply_overlay(成本主路徑)/metrics/控制組。
"""
from __future__ import annotations

import glob
import re
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

MA_WINDOW = 200
THRESHOLD = 0.50
DEFENSIVE_EXPOSURE = 0.50


def load_close_panel() -> pd.DataFrame:
    fs = sorted(glob.glob("data/raw/TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet"))
    cols = {}
    for f in fs:
        sid = re.search(r"TaiwanStockPrice__(\w+)__", f).group(1)
        if not re.fullmatch(r"\d{4}", sid):
            continue
        df = pd.read_parquet(f)  # 空檔沒有欄位，不能用columns投影
        if df.empty or "close" not in df.columns:
            continue
        df = df[df["close"] > 0].drop_duplicates("date")
        cols[sid] = df.set_index("date")["close"]
    panel = pd.DataFrame(cols).sort_index()
    panel.index = panel.index.astype(str)
    # 先截到TRAIN期再做任何計算(絕不碰VAL/holdout區間)
    capped = holdout.cap_to_train(panel.reset_index().rename(columns={"index": "date"}))
    return capped.set_index("date")


def breadth_series(panel: pd.DataFrame, ma_window: int) -> pd.Series:
    ma = panel.rolling(ma_window, min_periods=ma_window).mean()
    valid = ma.notna() & panel.notna()
    above = (panel > ma) & valid
    return above.sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def build_exposure_breadth(market_df: pd.DataFrame, breadth: pd.Series, threshold: float = THRESHOLD) -> pd.DataFrame:
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    b = d["date"].astype(str).map(breadth)
    d["breadth"] = b
    d["exposure"] = np.where(b < threshold, DEFENSIVE_EXPOSURE, 1.0)
    d.loc[b.isna(), "exposure"] = np.nan
    return d


def reduction(d):
    bm = metrics(d["baseline_equity"], d["raw_return"])
    om = metrics(d["overlay_equity"], d["overlay_return"])
    gm = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])
    return bm, om, gm, (1 - om["mdd_pct"] / bm["mdd_pct"]) * 100, (1 - gm["mdd_pct"] / bm["mdd_pct"]) * 100


def main():
    print("=" * 70)
    print("regime overlay候選1 市場廣度水位 TRAIN期單次判定 (規格見協定第13節)")
    print("=" * 70)
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_overlay_breadth_gate")
    train_df = holdout.cap_to_train(prepare_market_data(raw))
    panel = load_close_panel()
    print(f"TRAIN期: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}；"
          f"廣度宇宙={panel.shape[1]}檔4位數代號(存活者偏誤未修正)，面板{panel.index.min()}~{panel.index.max()}")

    br = {w: breadth_series(panel, w) for w in (140, 170, 200, 230, 260)}
    b200 = br[200].dropna()
    print(f"廣度(200MA)分布: 平均{b200.mean():.3f} 中位{b200.median():.3f} 最小{b200.min():.3f} 最大{b200.max():.3f} "
          f"n={len(b200)}；<0.50占比={float((b200 < 0.5).mean()) * 100:.1f}%")

    exposed = build_exposure_breadth(train_df, br[200])
    d = apply_overlay(exposed)
    bm, om, gm, red, red_g = reduction(d)
    up, down = capture_ratios(d["raw_return"], d["overlay_return"])
    print(f"\n基底: CAGR={bm['cagr_pct']:+.2f}% MDD={bm['mdd_pct']:.2f}% Sortino={bm['sortino']:.2f} Calmar={bm['calmar']:.2f} (n={len(d)})")
    print(f"廣度regime(淨): CAGR={om['cagr_pct']:+.2f}% MDD={om['mdd_pct']:.2f}% Sortino={om['sortino']:.2f} Calmar={om['calmar']:.2f}")
    print(f"廣度regime(毛,對照): CAGR={gm['cagr_pct']:+.2f}% MDD={gm['mdd_pct']:.2f}%")
    print(f"MDD縮小(淨)={red:.1f}% (毛{red_g:.1f}%) (門檻>=35%: {'PASS' if red >= 35 else 'FAIL'})")
    print(f"上檔捕捉率={up:.1f}% (門檻>=75%: {'PASS' if up >= 75 else 'FAIL'})  下檔捕捉率={down:.1f}%")

    cc = control_c_costs(d)
    print(f"\n(c) 切換{cc['n_switches']}次 (每年{cc['switches_per_year']:.1f}次) "
          f"累計成本={cc['total_cost_pct_over_period']:.2f}% 年化成本={cc['cost_pct_per_year']:.2f}%")
    print(f"    成本前置關卡：切換>8.4次/年={'是' if cc['switches_per_year'] > 8.4 else '否'}；"
          f"淨MDD縮小<毛的一半={'是' if red < red_g / 2 else '否'}")
    print(f"    防禦(半倉)時間占比={float((d['exposure_lagged'] < 1).mean()) * 100:.1f}%")

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
    red5 = reduction(d5)[3]
    print(f"(b) 延遲5日後MDD縮小(淨)={red5:.1f}% (延遲前{red:.1f}%)")

    print("\n(d) 參數高原 MA窗口 x 門檻 (MDD縮小%淨, * = >=35%)")
    ths = (0.35, 0.425, 0.5, 0.575, 0.65)
    print("           th:  " + "  ".join(f"{t:.3f}" for t in ths))
    n_pass = 0
    for w in (140, 170, 200, 230, 260):
        row = []
        for t in ths:
            dd_ = apply_overlay(build_exposure_breadth(train_df, br[w], t))
            rd = reduction(dd_)[3]
            n_pass += int(rd >= 35)
            row.append(f"{rd:6.1f}{'*' if rd >= 35 else ' '}")
        print(f"  MA={w:3d}  " + " ".join(row))
    print(f"  25格中MDD縮小>=35%: {n_pass}/25")

    print("\n結論:")
    print(f"  1.MDD縮小(淨)>=35%: {red:.1f}% (毛{red_g:.1f}%) -> {'PASS' if red >= 35 else 'FAIL'}")
    print(f"  2.上檔捕捉>=75%: {up:.1f}% -> {'PASS' if up >= 75 else 'FAIL'}")
    print(f"  3.危機視窗 {n_imp}/4 (換算待總司令裁示)")
    print(f"  4.控制組(a)百分位 {ca['percentile']:.1f}")
    print(f"  5.控制組(b)延遲後MDD縮小 {red5:.1f}%")
    print(f"  6.參數高原 {n_pass}/25")
    print(f"  sharpe={om['sharpe']:.4f} n={len(d)}")


if __name__ == "__main__":
    main()
