"""regime擇時／下檔保護overlay協定——FUT軌配合（`PENDING_QUEUE.md`「二」，
2026-09-04原始裁示：「FUT軌配合：跨商品日報酬池改為測試同一套regime
overlay對期貨曝險的下檔保護，不再做期貨單因子」）。

沿用`REGIME_OVERLAY_PROTOCOL.md`鎖定的門檻（MDD縮小≥35%／上檔捕捉率
≥75%／6視窗≥5改善），套用同一個候選訊號（第一個訊號：200MA趨勢濾網，
binary曝險1.00/0.50）在TX（台指期）連續合約上——不重新訂門檻，只換
標的。基底=TX連續合約買進持有本身（原則跟股票軌一致：「overlay若連
被動部位都保護不了，就保護不了任何東西」，這裡的被動部位換成期貨的
買進持有）。

用TX而非MTX/TE的理由：`FUT_LOG.md`第335輪已查證重疊窗口內TX-MTX日報酬
相關係數0.997、TX-TE 0.955——三者幾乎是同一個大盤beta的三種包裝，
分開測不是三個獨立候選（同家族只算一次，`CLAUDE.md`「同家族因子只能
算一個獨立發現」的期貨版本），選流動性最高、期數最長的TX代表整個
「台指期曝險」。

跟股票軌(`regime_overlay_trend_filter_gate.py`)的關鍵差異：
①成本模型改用期貨慣例（`deep_dive_fut_basis_carry.py`已用過的
ROUND_TRIP_COST_BPS_1X=5.0，期交稅0.002%/邊+手續費/交易所費，稅主導、
無證交稅0.3%——沿用股票的0.3%證交稅成本模型會嚴重高估期貨成本）；
②TX連續合約資料起點2000-01-04，早於股票軌TAIEX資料起點(2010-01-04)，
TRAIN期(<=2020-12-31)實際能涵蓋2008/2011/2015/2018/2020**5個**危機
視窗（只有2022在VAL期不計），比股票軌的4個更接近原始「6視窗」設計。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from continuous_contract import build_continuous_series
from validation import holdout

BULL_EXPOSURE = 1.00
BEAR_EXPOSURE = 0.50
MA_WINDOW = 200

# 期交稅0.002%/邊(雙邊0.004%)+手續費/交易所費(次bp量級,相對稅可忽略)，
# 沿用`deep_dive_fut_basis_carry.py::ROUND_TRIP_COST_BPS_1X`同一個假設與
# 引用理由(該檔案docstring已附完整說明來源，這裡不重複訂一個新數字)。
ROUND_TRIP_COST_BPS_1X = 5.0
COST_PER_UNIT_EXPOSURE_CHANGE = ROUND_TRIP_COST_BPS_1X / 10_000.0

TRAIN_CRISIS_WINDOWS = {
    "2008金融海嘯": ("2008-05-01", "2008-11-30"),
    "2011歐債危機/美債降級": ("2011-07-01", "2011-12-31"),
    "2015中國股災": ("2015-06-01", "2015-09-30"),
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
}
# 2022全年空頭落在VAL期(>holdout.TRAIN_END)，依「門檻TRAIN先訂死」原則
# 不計入TRAIN判斷，跟股票軌REGIME_OVERLAY_PROTOCOL.md第2節同一個理由。

RNG_SEED = 20260915


def load_tx_train() -> pd.DataFrame:
    series, skipped = build_continuous_series(contract="TX", session="position")
    if skipped:
        print(f"警告：TX有{len(skipped)}筆轉倉skipped_events，詳見continuous_contract.py")
    holdout.assert_no_holdout_leakage(series, context="regime_overlay_trend_filter_gate_fut")
    return holdout.cap_to_train(series)


def build_exposure(df: pd.DataFrame, ma_window: int = MA_WINDOW,
                    bear_exposure: float = BEAR_EXPOSURE) -> pd.DataFrame:
    d = df.sort_values("date").reset_index(drop=True).copy()
    ma = d["adj_close"].rolling(ma_window, min_periods=ma_window).mean()
    d["trend_regime"] = np.where(d["adj_close"] > ma, "bull", "bear")
    d.loc[ma.isna(), "trend_regime"] = None
    d["exposure"] = np.where(d["trend_regime"] == "bull", BULL_EXPOSURE,
                              np.where(d["trend_regime"] == "bear", bear_exposure, np.nan))
    return d


def apply_overlay(d: pd.DataFrame, extra_lag_days: int = 0) -> pd.DataFrame:
    d = d.sort_values("date").reset_index(drop=True).copy()
    d["raw_return"] = d["adj_close"].pct_change()
    d["exposure_lagged"] = d["exposure"].shift(1 + extra_lag_days)
    d["overlay_return_gross"] = d["raw_return"] * d["exposure_lagged"]
    exposure_delta = d["exposure_lagged"].diff().abs().fillna(0)
    d["switch_cost"] = exposure_delta * COST_PER_UNIT_EXPOSURE_CHANGE
    d["overlay_return"] = d["overlay_return_gross"] - d["switch_cost"]
    valid = d["raw_return"].notna() & d["overlay_return"].notna()
    d = d[valid].reset_index(drop=True)
    d["baseline_equity"] = (1 + d["raw_return"]).cumprod()
    d["overlay_equity"] = (1 + d["overlay_return"]).cumprod()
    d["overlay_equity_gross"] = (1 + d["overlay_return_gross"]).cumprod()
    return d


def metrics(equity: pd.Series, ret: pd.Series) -> dict:
    n = len(equity)
    if n < 30:
        return {k: float("nan") for k in
                ("cagr_pct", "vol_pct", "sharpe", "sortino", "mdd_pct", "calmar", "worst_12m_pct")} | {"n_days": n}
    total_return = float(equity.iloc[-1] / equity.iloc[0])
    years = n / 252.0
    cagr = total_return ** (1 / years) - 1
    vol = float(ret.std() * np.sqrt(252))
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else float("nan")
    downside = ret[ret < 0]
    sortino = (float(ret.mean() / downside.std() * np.sqrt(252))
               if len(downside) > 1 and downside.std() > 0 else float("nan"))
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    mdd = float(drawdown.min())
    calmar = (cagr / abs(mdd)) if mdd != 0 else float("nan")
    roll_12m = equity.pct_change(252).dropna()
    worst_12m = float(roll_12m.min()) if len(roll_12m) > 0 else float("nan")
    return {"cagr_pct": cagr * 100, "vol_pct": vol * 100, "sharpe": sharpe, "sortino": sortino,
            "mdd_pct": mdd * 100, "calmar": calmar, "worst_12m_pct": worst_12m * 100, "n_days": n}


def capture_ratios(base_ret: pd.Series, over_ret: pd.Series) -> tuple[float, float]:
    up_mask = base_ret > 0
    down_mask = base_ret < 0
    up_capture = (float(over_ret[up_mask].sum() / base_ret[up_mask].sum()) * 100
                  if base_ret[up_mask].sum() != 0 else float("nan"))
    down_capture = (float(over_ret[down_mask].sum() / base_ret[down_mask].sum()) * 100
                    if base_ret[down_mask].sum() != 0 else float("nan"))
    return up_capture, down_capture


def crisis_window_results(d: pd.DataFrame) -> list[dict]:
    rows = []
    for name, (start, end) in TRAIN_CRISIS_WINDOWS.items():
        w = d[(d["date"] >= start) & (d["date"] <= end)]
        if w.empty:
            rows.append({"window": name, "n": 0, "improved": None})
            continue
        base_dd = float((w["baseline_equity"] / w["baseline_equity"].iloc[0] /
                          (w["baseline_equity"] / w["baseline_equity"].iloc[0]).cummax() - 1).min())
        over_dd = float((w["overlay_equity"] / w["overlay_equity"].iloc[0] /
                          (w["overlay_equity"] / w["overlay_equity"].iloc[0]).cummax() - 1).min())
        improved = over_dd > base_dd
        rows.append({"window": name, "n": len(w), "baseline_mdd_pct": base_dd * 100,
                      "overlay_mdd_pct": over_dd * 100, "improved": improved})
    return rows


def control_a_random_switch(d: pd.DataFrame, n_draws: int = 300, seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    raw_ret = d["raw_return"].to_numpy()
    exposures = d["exposure_lagged"].to_numpy()
    base_equity = (1 + raw_ret).cumprod()
    base_mdd = float((base_equity / np.maximum.accumulate(base_equity) - 1).min())
    real_over_mdd = float((d["overlay_equity"] / d["overlay_equity"].cummax() - 1).min())
    real_improve = real_over_mdd - base_mdd
    random_improves = np.empty(n_draws)
    for i in range(n_draws):
        shuffled = rng.permutation(exposures)
        switch_cost = np.abs(np.diff(shuffled, prepend=shuffled[0])) * COST_PER_UNIT_EXPOSURE_CHANGE
        over_ret = raw_ret * shuffled - switch_cost
        over_equity = (1 + over_ret).cumprod()
        over_mdd = float((over_equity / np.maximum.accumulate(over_equity) - 1).min())
        random_improves[i] = over_mdd - base_mdd
    percentile = float((random_improves <= real_improve).mean() * 100)
    return {"n_draws": n_draws, "real_mdd_improve_pct": real_improve * 100,
            "random_mean_improve_pct": float(random_improves.mean() * 100),
            "percentile": percentile, "pass_gt_90": percentile > 90}


def control_c_costs(d: pd.DataFrame) -> dict:
    switch_mask = d["exposure_lagged"].diff().abs() > 1e-9
    n_switches = int(switch_mask.sum())
    total_cost_pct = float(d["switch_cost"].sum() * 100)
    n_years = len(d) / 252.0
    return {"n_switches": n_switches, "switches_per_year": n_switches / n_years,
            "total_cost_pct_over_period": total_cost_pct,
            "cost_pct_per_year": total_cost_pct / n_years}


def control_d_plateau(train_df: pd.DataFrame) -> list[dict]:
    rows = []
    for ma_window in (140, 170, 200, 230, 260):
        for bear_exp in (0.35, 0.425, 0.50, 0.575, 0.65):
            d = build_exposure(train_df, ma_window=ma_window, bear_exposure=bear_exp)
            d = apply_overlay(d)
            base_m = metrics(d["baseline_equity"], d["raw_return"])
            over_m = metrics(d["overlay_equity"], d["overlay_return"])
            mdd_reduction_pct = (1 - over_m["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
            rows.append({"ma_window": ma_window, "bear_exposure": bear_exp,
                          "mdd_reduction_pct": mdd_reduction_pct, "overlay_mdd_pct": over_m["mdd_pct"]})
    return rows


def main():
    print("=" * 70)
    print("regime overlay協定 FUT軌配合(TX連續合約,200MA趨勢濾網) TRAIN期正式測試")
    print("=" * 70)

    train_df = load_tx_train()
    print(f"\nTRAIN期範圍: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}天")

    exposed = build_exposure(train_df)
    d = apply_overlay(exposed)

    base_m = metrics(d["baseline_equity"], d["raw_return"])
    over_m = metrics(d["overlay_equity"], d["overlay_return"])
    over_m_gross = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])
    up_cap, down_cap = capture_ratios(d["raw_return"], d["overlay_return"])
    mdd_reduction_pct = (1 - over_m["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
    mdd_reduction_gross_pct = (1 - over_m_gross["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")

    print("\n--- 主指標(TRAIN全期，主結果已扣切換成本，期貨慣例5bps/次) ---")
    print(f"  基底(TX買進持有): CAGR={base_m['cagr_pct']:+.2f}% 年化波動={base_m['vol_pct']:.2f}% "
          f"Sharpe={base_m['sharpe']:.2f} Sortino={base_m['sortino']:.2f} MDD={base_m['mdd_pct']:.2f}% "
          f"Calmar={base_m['calmar']:.2f} 最差12月={base_m['worst_12m_pct']:.2f}%")
    print(f"  overlay淨(趨勢濾網,扣成本): CAGR={over_m['cagr_pct']:+.2f}% 年化波動={over_m['vol_pct']:.2f}% "
          f"Sharpe={over_m['sharpe']:.2f} Sortino={over_m['sortino']:.2f} MDD={over_m['mdd_pct']:.2f}% "
          f"Calmar={over_m['calmar']:.2f} 最差12月={over_m['worst_12m_pct']:.2f}%")
    print(f"  overlay毛(未扣成本,僅供對照): CAGR={over_m_gross['cagr_pct']:+.2f}% MDD={over_m_gross['mdd_pct']:.2f}%")
    print(f"  MDD縮小幅度(淨): {mdd_reduction_pct:.1f}% (門檻≥35%: {'PASS' if mdd_reduction_pct >= 35 else 'FAIL'})"
          f"　(毛:{mdd_reduction_gross_pct:.1f}%)")
    print(f"  上檔捕捉率(淨): {up_cap:.1f}% (門檻≥75%: {'PASS' if up_cap >= 75 else 'FAIL'})")
    print(f"  下檔捕捉率(淨,只回報不設門檻): {down_cap:.1f}%")

    print("\n--- 危機視窗(TRAIN期可測的5個: 2008/2011/2015/2018/2020,2022在VAL不計) ---")
    crisis_rows = crisis_window_results(d)
    n_improved = 0
    n_available = 0
    for r in crisis_rows:
        if r["improved"] is None:
            print(f"  {r['window']}: 資料為0筆,跳過")
            continue
        n_available += 1
        n_improved += int(r["improved"])
        print(f"  {r['window']} (n={r['n']}): 基底MDD={r['baseline_mdd_pct']:.2f}% "
              f"overlayMDD={r['overlay_mdd_pct']:.2f}% {'改善' if r['improved'] else '未改善'}")
    print(f"  {n_available}個視窗中改善數: {n_improved}/{n_available} "
          f"(原始門檻以6視窗為分母，本軌TRAIN期能測5個，比股票軌4個更接近原始設計；"
          f"2022在VAL不計)")

    print("\n--- 控制組(a) 隨機開關對照(相同在市時間比例,排列法,n=300) ---")
    ctrl_a = control_a_random_switch(d)
    print(f"  真實MDD改善={ctrl_a['real_mdd_improve_pct']:.2f}pp  隨機平均改善={ctrl_a['random_mean_improve_pct']:.2f}pp  "
          f"百分位={ctrl_a['percentile']:.1f} (門檻>90: {'PASS' if ctrl_a['pass_gt_90'] else 'FAIL'})")

    print("\n--- 控制組(b) 訊號延遲1週(5個交易日)再測 ---")
    d_lag = apply_overlay(exposed, extra_lag_days=5)
    over_m_lag = metrics(d_lag["overlay_equity"], d_lag["overlay_return"])
    mdd_reduction_lag_pct = (1 - over_m_lag["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
    print(f"  延遲後overlay MDD={over_m_lag['mdd_pct']:.2f}%  MDD縮小幅度={mdd_reduction_lag_pct:.1f}% "
          f"(延遲前={mdd_reduction_pct:.1f}%；若延遲後保護消失代表前視偏誤)")

    print("\n--- 控制組(c) 交易成本與whipsaw ---")
    ctrl_c = control_c_costs(d)
    print(f"  切換次數={ctrl_c['n_switches']} (每年約{ctrl_c['switches_per_year']:.1f}次)  "
          f"累計成本(全期)={ctrl_c['total_cost_pct_over_period']:.3f}%  年化成本≈{ctrl_c['cost_pct_per_year']:.3f}%")

    print("\n--- 控制組(d) 參數高原(MA窗口×空頭曝險水位,各自±30%網格) ---")
    ctrl_d = control_d_plateau(train_df)
    n_pass_35 = sum(1 for r in ctrl_d if r["mdd_reduction_pct"] >= 35)
    for r in ctrl_d:
        print(f"  ma={r['ma_window']:3d} bear_exp={r['bear_exposure']:.3f}: "
              f"overlayMDD={r['overlay_mdd_pct']:.2f}% MDD縮小={r['mdd_reduction_pct']:.1f}%")
    print(f"  25格中MDD縮小≥35%門檻的格數: {n_pass_35}/25")

    print("\n" + "=" * 70)
    print("結論(依REGIME_OVERLAY_PROTOCOL.md鎖定門檻逐條比對，本檔案只回報，不判死/判活)")
    print("=" * 70)
    print(f"  1. MDD縮小≥35%: {mdd_reduction_pct:.1f}% -> {'PASS' if mdd_reduction_pct >= 35 else 'FAIL'}")
    print(f"  2. 上檔捕捉率≥75%: {up_cap:.1f}% -> {'PASS' if up_cap >= 75 else 'FAIL'}")
    print(f"  3. 危機視窗改善數: {n_improved}/{n_available} (TRAIN期可測全部)")
    print(f"  4. 控制組(a)隨機開關百分位>90: {ctrl_a['percentile']:.1f} -> "
          f"{'PASS' if ctrl_a['pass_gt_90'] else 'FAIL'}")
    print(f"  5. 控制組(b)延遲1週後是否仍縮小MDD: "
          f"{'是(方向一致，非純前視偏誤)' if mdd_reduction_lag_pct > 0 else '否(疑似前視偏誤)'}")
    print(f"  6. 控制組(d)參數高原: {n_pass_35}/25格通過MDD縮小≥35%門檻")


if __name__ == "__main__":
    main()
