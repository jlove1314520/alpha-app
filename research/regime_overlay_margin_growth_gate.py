"""regime overlay協定候選4——融資餘額成長率下檔regime，TRAIN期單次判定。

規格已在`REGIME_OVERLAY_PROTOCOL.md`第14節看結果前鎖定（成長窗口12週、
expanding第80百分位以上=過熱→曝險0.50，方向事前綁定）。輸入序列與`#26`
相同(全市場總融資餘額,週頻)，本檔案是把它改成降曝險regime＋成本＋控制組。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from factor_ic import START_DATE
from finmind_client import load_dev
from margin_debt_market_client import load_all_cached
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from regime_overlay_trend_filter_gate import (
    apply_overlay, metrics, capture_ratios, crisis_window_results,
    control_a_random_switch, control_c_costs,
)

GROWTH_WEEKS = 12
PCTILE = 0.80
DEFENSIVE_EXPOSURE = 0.50
MIN_EXPANDING_WEEKS = 52


def load_margin_weekly() -> pd.Series:
    df = load_all_cached()
    df = df[df["is_trading_day"] == True].copy()  # noqa: E712
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["financing_amount_today_balance_kNTD"]).sort_values("date")
    df = df[df["date"] <= pd.Timestamp(holdout.TRAIN_END)]  # 只用TRAIN期
    return df.set_index("date")["financing_amount_today_balance_kNTD"].astype(float)


def hot_flag(bal: pd.Series, weeks: int, pct: float) -> pd.Series:
    growth = bal / bal.shift(weeks) - 1
    thresh = growth.expanding(min_periods=MIN_EXPANDING_WEEKS).quantile(pct)  # PIT-safe
    flag = (growth > thresh).astype(float)
    flag[thresh.isna() | growth.isna()] = np.nan
    return flag


def build_exposure_margin(market_df: pd.DataFrame, bal: pd.Series, weeks: int = GROWTH_WEEKS,
                          pct: float = PCTILE) -> pd.DataFrame:
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    flag = hot_flag(bal, weeks, pct)
    dts = pd.to_datetime(d["date"])
    # 週五收盤後已知的訊號，前向填補到之後的日頻(asof)；apply_overlay再shift(1)次日生效
    sig = flag.dropna()
    idx = sig.index.searchsorted(dts, side="right") - 1
    vals = np.where(idx >= 0, sig.to_numpy()[np.clip(idx, 0, None)], np.nan)
    d["hot"] = vals
    d["exposure"] = np.where(np.isnan(vals), np.nan, np.where(vals > 0.5, DEFENSIVE_EXPOSURE, 1.0))
    return d


def reduction(d):
    bm = metrics(d["baseline_equity"], d["raw_return"])
    om = metrics(d["overlay_equity"], d["overlay_return"])
    gm = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])
    return bm, om, gm, (1 - om["mdd_pct"] / bm["mdd_pct"]) * 100, (1 - gm["mdd_pct"] / bm["mdd_pct"]) * 100


def main():
    print("=" * 70)
    print("regime overlay候選4 融資餘額成長率下檔regime TRAIN期單次判定 (規格見協定第14節)")
    print("=" * 70)
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_overlay_margin_growth_gate")
    train_df = holdout.cap_to_train(prepare_market_data(raw))
    bal = load_margin_weekly()
    print(f"融資週資料: {bal.index.min().date()} ~ {bal.index.max().date()} n={len(bal)}週")

    exposed = build_exposure_margin(train_df, bal)
    first_valid = exposed.loc[exposed["exposure"].notna(), "date"].min()
    d = apply_overlay(exposed)
    print(f"有效判定期: {d['date'].min()} ~ {d['date'].max()} n={len(d)}天 (暖機期{first_valid}起)；"
          f"過熱(半倉)時間占比={float((d['exposure_lagged'] < 1).mean()) * 100:.1f}%")
    bm, om, gm, red, red_g = reduction(d)
    up, down = capture_ratios(d["raw_return"], d["overlay_return"])
    print(f"\n基底: CAGR={bm['cagr_pct']:+.2f}% MDD={bm['mdd_pct']:.2f}% Sortino={bm['sortino']:.2f} Calmar={bm['calmar']:.2f}")
    print(f"融資regime(淨): CAGR={om['cagr_pct']:+.2f}% MDD={om['mdd_pct']:.2f}% Sortino={om['sortino']:.2f} Calmar={om['calmar']:.2f}")
    print(f"融資regime(毛,對照): CAGR={gm['cagr_pct']:+.2f}% MDD={gm['mdd_pct']:.2f}%")
    print(f"MDD縮小(淨)={red:.1f}% (毛{red_g:.1f}%) (門檻>=35%: {'PASS' if red >= 35 else 'FAIL'})")
    print(f"上檔捕捉率={up:.1f}% (門檻>=75%: {'PASS' if up >= 75 else 'FAIL'})  下檔捕捉率={down:.1f}%")

    cc = control_c_costs(d)
    print(f"\n(c) 切換{cc['n_switches']}次 (每年{cc['switches_per_year']:.1f}次) "
          f"累計成本={cc['total_cost_pct_over_period']:.2f}% 年化成本={cc['cost_pct_per_year']:.2f}%")

    print("\n--- 危機視窗(TRAIN可測；2011落在資料起點前，實際只有3個可判) ---")
    n_imp, n_tested = 0, 0
    for r_ in crisis_window_results(d):
        if r_["improved"] is None:
            print(f"  {r_['window']}: 判定期內無資料，跳過")
            continue
        n_tested += 1
        n_imp += int(r_["improved"])
        print(f"  {r_['window']} (n={r_['n']}): 基底{r_['baseline_mdd_pct']:.1f}% overlay{r_['overlay_mdd_pct']:.1f}% "
              f"{'改善' if r_['improved'] else '未改善'}")
    print(f"  改善數 {n_imp}/{n_tested}")

    ca = control_a_random_switch(d)
    print(f"\n(a) 隨機排列n=300: 真實改善={ca['real_mdd_improve_pct']:.2f}pp 隨機平均={ca['random_mean_improve_pct']:.2f}pp "
          f"百分位={ca['percentile']:.1f} ({'PASS' if ca['pass_gt_90'] else 'FAIL'})")

    d5 = apply_overlay(exposed, extra_lag_days=5)
    red5 = reduction(d5)[3]
    print(f"(b) 延遲5日後MDD縮小(淨)={red5:.1f}% (延遲前{red:.1f}%)")

    print("\n(d) 參數高原 成長窗口(週) x 百分位 (MDD縮小%淨, * = >=35%)")
    pcts = (0.60, 0.70, 0.80, 0.90, 0.95)
    print("          pct:  " + "  ".join(f"{p:.2f}" for p in pcts))
    n_pass = 0
    for w in (8, 10, 12, 14, 16):
        row = []
        for p in pcts:
            dd_ = apply_overlay(build_exposure_margin(train_df, bal, w, p))
            rd = reduction(dd_)[3]
            n_pass += int(rd >= 35)
            row.append(f"{rd:6.1f}{'*' if rd >= 35 else ' '}")
        print(f"  win={w:2d}w  " + " ".join(row))
    print(f"  25格中MDD縮小>=35%: {n_pass}/25")

    print("\n結論:")
    print(f"  1.MDD縮小(淨)>=35%: {red:.1f}% (毛{red_g:.1f}%) -> {'PASS' if red >= 35 else 'FAIL'}")
    print(f"  2.上檔捕捉>=75%: {up:.1f}% -> {'PASS' if up >= 75 else 'FAIL'}")
    print(f"  3.危機視窗 {n_imp}/{n_tested}")
    print(f"  4.控制組(a)百分位 {ca['percentile']:.1f}")
    print(f"  5.控制組(b)延遲後MDD縮小 {red5:.1f}%")
    print(f"  6.參數高原 {n_pass}/25")
    print(f"  sharpe={om['sharpe']:.4f} n={len(d)}")


if __name__ == "__main__":
    main()
