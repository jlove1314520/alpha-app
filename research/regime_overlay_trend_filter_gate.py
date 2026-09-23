"""regime擇時／下檔保護overlay協定——第一個訊號（指數200MA趨勢濾網）正式
TRAIN期測試，對照`REGIME_OVERLAY_PROTOCOL.md`鎖定的門檻。

候選：TAIEX收盤>200日均線=多頭(曝險1.00)，反之空頭(曝險0.50)。基底=TAIEX
買進持有(協定第0節：橫截面選股全滅後,overlay套用在被動部位本身就是要正式
判定的候選,不是等未來選股候選的sanity佔位)。只用TRAIN期(<=holdout.TRAIN_END)，
門檻已在協定文件裡看到任何結果之前鎖定,本檔案只回報數字,不回頭調門檻。

四個危機視窗(2011/2015/2018Q4/2020Q1)是TRAIN期資料實際涵蓋的全部——2008
早於資料起點(2010-01-04)完全無資料,2022落在VAL期不可用於TRAIN判斷,兩者
都不是本檔案的選擇,是協定文件第2節記錄的資料覆蓋度落差。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data, MARKET_MA_WINDOW
from validation import holdout
from validation.costs import round_trip_cost_pct

BULL_EXPOSURE = 1.00
BEAR_EXPOSURE = 0.50

TRAIN_CRISIS_WINDOWS = {
    "2011歐債危機/美債降級": ("2011-07-01", "2011-12-31"),
    "2015中國股災": ("2015-06-01", "2015-09-30"),
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
}

RNG_SEED = 20260915  # 這個協定第一次跑的固定種子,不是搜出來的


def build_exposure(market_df: pd.DataFrame, ma_window: int = MARKET_MA_WINDOW,
                    bear_exposure: float = BEAR_EXPOSURE) -> pd.DataFrame:
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    ma = d["close"].rolling(ma_window, min_periods=ma_window).mean()
    d["trend_regime"] = np.where(d["close"] > ma, "bull", "bear")
    d.loc[ma.isna(), "trend_regime"] = None  # warm-up期無法判定,不是刻意判多頭
    d["exposure"] = np.where(d["trend_regime"] == "bull", BULL_EXPOSURE,
                              np.where(d["trend_regime"] == "bear", bear_exposure, np.nan))
    return d


COST_PER_UNIT_EXPOSURE_CHANGE = round_trip_cost_pct(commission_discount=0.18, instrument_type="etf")
# 2026-09-23修.二修正：交易標的是TAIEX代理部位（0050股票型ETF），賣出證交稅率
# 應為0.1%，原本用round_trip_cost_pct()預設daytrade=False（一般股票0.3%）——
# 見PENDING_QUEUE.md修.二完整清單。regime_alt_a_*系列（import這個常數）連帶修正。
# 換一次曝險水位(0->1或1->0視為滿額買賣)的全額摩擦成本，`CONSTITUTION.md`要求
# 任何回測數字上報前都要先過成本模組，這裡不留"gross"版本當最終結果。
# 2026-09-19 成本.二更正：舊版硬寫COMMISSION_RATE*2（即1.0折/無折扣）+稅+滑價，
# 完全沒有折數參數，比總司令實際1.8折的手續費更貴。改用costs.py的
# round_trip_cost_pct(commission_discount=0.18)，0.685%→0.4513%/次切換。
# 本檔案為regime.候選1/2/3/4/5＋FUT版共用的成本常數來源（其餘四支透過
# `from regime_overlay_trend_filter_gate import ... COST_PER_UNIT_EXPOSURE_CHANGE`
# 匯入），改這裡即全部生效，不需逐檔修改。


def apply_overlay(d: pd.DataFrame, extra_lag_days: int = 0, apply_costs: bool = True) -> pd.DataFrame:
    d = d.sort_values("date").reset_index(drop=True).copy()
    d["raw_return"] = d["close"].pct_change()
    d["exposure_lagged"] = d["exposure"].shift(1 + extra_lag_days)
    d["overlay_return_gross"] = d["raw_return"] * d["exposure_lagged"]
    exposure_delta = d["exposure_lagged"].diff().abs().fillna(0)
    d["switch_cost"] = exposure_delta * COST_PER_UNIT_EXPOSURE_CHANGE if apply_costs else 0.0
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
        improved = over_dd > base_dd  # 較不負=改善
        rows.append({"window": name, "n": len(w), "baseline_mdd_pct": base_dd * 100,
                      "overlay_mdd_pct": over_dd * 100, "improved": improved})
    return rows


def control_a_random_switch(d: pd.DataFrame, n_draws: int = 300, seed: int = RNG_SEED) -> dict:
    """排列法:把曝險值的時間順序隨機打亂,保證每個曝險水位的總天數跟真實訊號
    完全相同(同一份"在市時間比例"),只打亂哪一天套用哪個曝險。回傳真實MDD改善
    落在這n_draws次隨機排列的百分位。"""
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
        over_ret = raw_ret * shuffled - switch_cost  # 隨機排列通常換手更頻繁,成本也要扣才公平
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


def control_d_plateau(market_df: pd.DataFrame) -> list[dict]:
    rows = []
    for ma_window in (140, 170, 200, 230, 260):
        for bear_exp in (0.35, 0.425, 0.50, 0.575, 0.65):
            d = build_exposure(market_df, ma_window=ma_window, bear_exposure=bear_exp)
            d = apply_overlay(d)
            base_m = metrics(d["baseline_equity"], d["raw_return"])
            over_m = metrics(d["overlay_equity"], d["overlay_return"])
            mdd_reduction_pct = (1 - over_m["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
            rows.append({"ma_window": ma_window, "bear_exposure": bear_exp,
                          "mdd_reduction_pct": mdd_reduction_pct, "overlay_mdd_pct": over_m["mdd_pct"]})
    return rows


def main():
    print("=" * 70)
    print("regime overlay協定 第一個訊號(200MA趨勢濾網) TRAIN期正式測試")
    print("=" * 70)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="regime_overlay_trend_filter_gate")
    market_df = prepare_market_data(market_raw)
    train_df = holdout.cap_to_train(market_df)
    print(f"\nTRAIN期範圍: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}天")

    exposed = build_exposure(train_df)
    d = apply_overlay(exposed)

    base_m = metrics(d["baseline_equity"], d["raw_return"])
    over_m = metrics(d["overlay_equity"], d["overlay_return"])  # 已扣切換成本(淨值),是主結果
    over_m_gross = metrics(d["overlay_equity_gross"], d["overlay_return_gross"])  # 未扣成本,只供對照
    up_cap, down_cap = capture_ratios(d["raw_return"], d["overlay_return"])
    mdd_reduction_pct = (1 - over_m["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")
    mdd_reduction_gross_pct = (1 - over_m_gross["mdd_pct"] / base_m["mdd_pct"]) * 100 if base_m["mdd_pct"] != 0 else float("nan")

    print("\n--- 主指標(TRAIN全期，主結果已扣切換成本，CONSTITUTION.md要求成本不得後補) ---")
    print(f"  基底(買進持有): CAGR={base_m['cagr_pct']:+.2f}% 年化波動={base_m['vol_pct']:.2f}% "
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

    print("\n--- 危機視窗(TRAIN期可測的4個,2008無資料/2022在VAL不計) ---")
    crisis_rows = crisis_window_results(d)
    n_improved = 0
    for r in crisis_rows:
        if r["improved"] is None:
            print(f"  {r['window']}: 資料為0筆,跳過")
            continue
        n_improved += int(r["improved"])
        print(f"  {r['window']} (n={r['n']}): 基底MDD={r['baseline_mdd_pct']:.2f}% "
              f"overlayMDD={r['overlay_mdd_pct']:.2f}% {'改善' if r['improved'] else '未改善'}")
    print(f"  4個視窗中改善數: {n_improved}/4 (原始比例5/6與快殺門檻<4/6換算到4視窗分母，"
          f"見REGIME_OVERLAY_PROTOCOL.md第3節第5點——本檔案只回報數字，不自行換算判死)")

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
    print(f"  3. 危機視窗改善數: {n_improved}/4 (TRAIN期可測全部，原始門檻以6視窗為分母，"
          f"換算方式待總司令裁示)")
    print(f"  4. 控制組(a)隨機開關百分位>90: {ctrl_a['percentile']:.1f} -> "
          f"{'PASS' if ctrl_a['pass_gt_90'] else 'FAIL'}")
    print(f"  5. 控制組(b)延遲1週後是否仍縮小MDD: "
          f"{'是(方向一致，非純前視偏誤)' if mdd_reduction_lag_pct > 0 else '否(疑似前視偏誤)'}")
    print(f"  6. 控制組(d)參數高原: {n_pass_35}/25格通過MDD縮小≥35%門檻")


if __name__ == "__main__":
    main()
