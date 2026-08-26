"""多因子組合策略回測 v2 — 依 `PORTFOLIO_STRATEGY_SPEC.md` 規格實作（2026-08-26 晚，
使用者「停止磨單因子，去做組合策略」硬性指示）。

跟 `portfolio_backtest.py`（v1）的差異，全部依照 SPEC 逐條對應：
  - 持股 10→20 檔；換股頻率 週頻→月頻(21交易日)+季頻(63交易日)雙版本。
  - 情境條件式加權改用**大盤位階**（第83輪`f_rel_strength_regime_switch`同一個
    bull/bear開關，`strategies/weinstein_stage2.py`的`gate`欄位），不是v1的波動度。
  - 資格池新增流動性門檻（20日均成交金額後10%分位數排除）。
  - 新增隨機選股對照組(a)、買進持有大盤對照組(b)（v1只有alpha/beta回歸，沒有這兩個）。
  - 兩個因子版本：A(4已通過因子去重後3成分)、B(+f_value_pe共4成分)。
  - `backtest/engine.py`新增`rebalance_every_n_days`（純加法擴充，見該檔案2026-08-26
    條目），這裡靠它做到月/季頻，不需要另外寫一個獨立的日走引擎。

樣本、holdout紀律、評判順序完全依`PORTFOLIO_STRATEGY_SPEC.md`，不在這裡重複解釋。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy import stats

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map, _zscore_within_group
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 20
REBALANCE_CADENCES = {"monthly": 21, "quarterly": 63}
COST_MULTIPLIERS = (1, 2, 3)
LIQUIDITY_FLOOR_PERCENTILE = 10  # 資格池排除20日均成交金額後10%分位數的股票

FACTOR_VERSIONS = {
    "A_4pass": ["eps_family", "revenue_surprise", "low_vol"],
    "B_plus_value_pe": ["eps_family", "revenue_surprise", "low_vol", "value_pe"],
}

# 靜態IC加權：factor_ic.py對80檔驗證樣本算出的驗證期(val) mean IC絕對值（跟v1/
# REGIME_CONDITIONS.md同一批數字，2026-08-26複算）。
IC_WEIGHTS = {
    "eps_family": (0.0773 + 0.0804) / 2,
    "revenue_surprise": 0.0397,
    "low_vol": 0.0967,
    "value_pe": 0.0533,
}

# 情境條件式：大盤位階(bull/bear，第83輪同一個gate開關)下，各成分的分群IC絕對值
# （REGIME_CONDITIONS.md「(a)大盤位階」小節 + 這輪為f_value_pe補算的同維度數字）。
REGIME_IC_WEIGHTS_TREND = {
    "bull_above_ma": {
        "eps_family": (0.0676 + 0.0653) / 2, "revenue_surprise": 0.0418,
        "low_vol": 0.1197, "value_pe": 0.0508,
    },
    "bear_below_ma": {
        "eps_family": (0.0410 + 0.0581) / 2, "revenue_surprise": 0.0528,
        "low_vol": 0.0452, "value_pe": 0.1302,
    },
}


def _trend_regime_series(market_df: pd.DataFrame) -> pd.Series:
    """date -> 'bull_above_ma'/'bear_below_ma'，直接沿用`prepare_market_data()`已經算好
    的`gate`欄位（跟第83輪`regime_switch_f_rel_strength.py`同一個定義），不是重新發明。"""
    d = market_df.sort_values("date").reset_index(drop=True)
    label = np.where(d["gate"], "bull_above_ma", "bear_below_ma")
    return pd.Series(label, index=d["date"])


def _raw_components(row: pd.Series) -> dict[str, float | None]:
    eps_vals = [row.get("f_eps_growth"), row.get("f_eps_surprise")]
    eps_vals = [v for v in eps_vals if pd.notna(v)]
    eps_family = float(np.mean(eps_vals)) if eps_vals else None
    out = {"eps_family": eps_family}
    for comp, col in (("revenue_surprise", "f_revenue_surprise"), ("low_vol", "f_low_vol"), ("value_pe", "f_value_pe")):
        v = row.get(col)
        out[comp] = float(v) if pd.notna(v) else None
    return out


def _liquidity_proxy_series(d: pd.DataFrame) -> pd.Series:
    """20日均成交金額，PIT-safe（只用當下及之前的資料，rolling不看未來）。跟
    factors.py f_inst_flow用的流動性正規化同一個底層欄位(`Trading_money`)。"""
    dd = d.sort_values("date").reset_index(drop=True)
    tm20 = dd["Trading_money"].rolling(20, min_periods=20).mean()
    return pd.Series(tm20.values, index=dd["date"])


def compute_composite_at_date(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str],
    components: list[str], weight_mode: str, trend_regime: pd.Series,
    liquidity: dict[str, pd.Series],
) -> pd.DataFrame:
    """回傳 columns: stock_id, industry, composite, n_components, liquidity_proxy。"""
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        raw = _raw_components(d.loc[idx[0]])
        liq = liquidity[sid].get(as_of) if sid in liquidity and as_of in liquidity[sid].index else None
        rows.append({"stock_id": sid, "industry": industry_map.get(sid, "UNKNOWN"),
                     "liquidity_proxy": liq, **raw})
    if not rows:
        return pd.DataFrame(columns=["stock_id", "industry", "composite", "n_components", "liquidity_proxy"])
    cs = pd.DataFrame(rows).set_index("stock_id")

    if weight_mode == "regime_weighted":
        regime = trend_regime.loc[as_of] if as_of in trend_regime.index else "bull_above_ma"
        weights = REGIME_IC_WEIGHTS_TREND[regime]
    elif weight_mode == "ic_weighted":
        weights = IC_WEIGHTS
    elif weight_mode == "equal":
        weights = {c: 1.0 for c in components}
    else:
        raise ValueError(f"unknown weight_mode: {weight_mode}")

    weighted_sum = pd.Series(0.0, index=cs.index)
    weight_total = pd.Series(0.0, index=cs.index)
    n_components = pd.Series(0, index=cs.index)
    for comp in components:
        z_col = f"z_{comp}"
        cs[z_col] = _zscore_within_group(cs[comp], cs["industry"])
        valid = cs[z_col].notna()
        w = weights[comp]
        weighted_sum[valid] += cs.loc[valid, z_col] * w
        weight_total[valid] += w
        n_components[valid] += 1

    cs["composite"] = np.where(weight_total > 0, weighted_sum / weight_total, np.nan)
    cs["n_components"] = n_components
    return cs.reset_index()[["stock_id", "industry", "composite", "n_components", "liquidity_proxy"]]


def _eligible(cs: pd.DataFrame) -> pd.DataFrame:
    from score import MIN_COMPONENTS_FOR_RANKING
    pool = cs[cs["n_components"] >= MIN_COMPONENTS_FOR_RANKING].copy()
    liq = pool["liquidity_proxy"].dropna()
    if len(liq) >= 10:  # 分位數樣本太小沒有意義，門檻沿用factor_ic.py慣例的量級
        floor = np.percentile(liq, LIQUIDITY_FLOOR_PERCENTILE)
        pool = pool[pool["liquidity_proxy"].isna() | (pool["liquidity_proxy"] >= floor)]
    return pool.sort_values("composite", ascending=False)


def make_signal_fn(industry_map, components, weight_mode, trend_regime, liquidity):
    def signal_fn(price_data, as_of, market_df):
        cs = _eligible(compute_composite_at_date(as_of, price_data, industry_map, components, weight_mode, trend_regime, liquidity))
        top = cs.head(TOP_N)
        return dict(zip(top["stock_id"], top["composite"]))
    return signal_fn


def make_random_signal_fn(industry_map, components, trend_regime, liquidity, seed):
    """配對式隨機對照組(a)：同一套資格池(含流動性門檻)、同樣持股數/換股頻率，
    只是排名用隨機而非綜合分——用等權當score值（實際排序無意義，只借用
    make_signal_fn同一套top-N選取機制）。"""
    rng = random.Random(seed)

    def signal_fn(price_data, as_of, market_df):
        cs = _eligible(compute_composite_at_date(as_of, price_data, industry_map, components, "equal", trend_regime, liquidity))
        pool = cs["stock_id"].tolist()
        picks = pool if len(pool) <= TOP_N else rng.sample(pool, TOP_N)
        return {sid: 1.0 for sid in picks}
    return signal_fn


def buy_and_hold_index_pct(market_df: pd.DataFrame, start: str, end: str) -> float:
    """對照組(b)：買進持有加權指數(TAIEX)，零成本、不換股。"""
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    if len(window) < 2:
        return float("nan")
    p0, p1 = window.iloc[0]["close"], window.iloc[-1]["close"]
    return float(p1 / p0 - 1) * 100


def alpha_significance(equity_curve: pd.DataFrame, market_df: pd.DataFrame) -> dict:
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"alpha_ann_pct": float("nan"), "beta": float("nan"), "alpha_pvalue": float("nan"),
                "alpha_significant": False, "n_days": len(merged)}
    reg = stats.linregress(merged["mkt_return"], merged["net_return"])
    alpha_ann_pct = ((1 + reg.intercept) ** 252 - 1) * 100
    pvalue = (2 * stats.t.sf(abs(reg.intercept / reg.intercept_stderr), len(merged) - 2)
              if reg.intercept_stderr else float("nan"))
    return {
        "alpha_ann_pct": float(alpha_ann_pct), "beta": float(reg.slope),
        "alpha_pvalue": float(pvalue) if pvalue == pvalue else float("nan"),
        "alpha_significant": bool(reg.intercept > 0 and pvalue == pvalue and pvalue < 0.05),
        "n_days": len(merged),
    }


def sharpe_ratio(equity_curve: pd.DataFrame) -> float:
    eq = equity_curve["equity"]
    if len(eq) < 2:
        return float("nan")
    r = eq.pct_change().dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(252))


def run_one(factor_version, weight_mode, cadence_name, label, data, market_df, industry_map,
            trend_regime, liquidity, start, end, do_cost_sensitivity=True,
            do_random_control=True, n_random=15) -> dict:
    """`do_cost_sensitivity`/`do_random_control` 讓呼叫端分兩階段跑：先用預設True/True
    跑一次完整版拿到headline數字所需要的所有東西；如果要先用False/False掃過整個
    網格看大方向（每次重抽都要重跑一次完整多年回測，全部組合都跑很貴），
    再針對重要的組合單獨補上完整版——`main()`實際用的正是這個兩階段設計，見那邊
    的說明。"""
    components = FACTOR_VERSIONS[factor_version]
    n_days = REBALANCE_CADENCES[cadence_name]
    signal_fn = make_signal_fn(industry_map, components, weight_mode, trend_regime, liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=n_days, book_name=f"portfolio_v2_{factor_version}_{weight_mode}_{cadence_name}")
    result = run_backtest(signal_fn, data, market_df, cfg)
    holdout.assert_no_holdout_leakage(result.trades, date_col="date",
                                       context=f"portfolio_v2 {factor_version}/{weight_mode}/{cadence_name}")

    alpha = alpha_significance(result.equity_curve, market_df)
    sharpe = sharpe_ratio(result.equity_curve)
    bh_pct = buy_and_hold_index_pct(market_df, start, end)

    cost_returns = {1: result.total_return_pct}
    if do_cost_sensitivity:
        for mult in (2, 3):
            c = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                               rebalance_every_n_days=n_days, book_name=cfg.book_name, cost_multiplier=mult)
            r = run_backtest(signal_fn, data, market_df, c)
            cost_returns[mult] = r.total_return_pct
    else:
        cost_returns[2] = cost_returns[3] = float("nan")

    # 對照組(a)：配對式隨機選股，同資格池/持股數/換股頻率
    random_finals = []
    if do_random_control:
        for i in range(n_random):
            rfn = make_random_signal_fn(industry_map, components, trend_regime, liquidity, seed=20260826 + i)
            rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                                  rebalance_every_n_days=n_days, book_name=f"{cfg.book_name}_random")
            rr = run_backtest(rfn, data, market_df, rcfg)
            random_finals.append(rr.final_equity)
    real_final = result.final_equity
    random_percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals])) if random_finals else float("nan")

    return {
        "factor_version": factor_version, "weight_mode": weight_mode, "cadence": cadence_name,
        "label": label, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "sharpe": sharpe, "n_trades": result.n_trades,
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "cost_1x": cost_returns[1], "cost_2x": cost_returns[2], "cost_3x": cost_returns[3],
        "buy_and_hold_index_pct": bh_pct,
        "random_control_median_pct": (float(np.median(random_finals)) / cfg.initial_capital - 1) * 100 if random_finals else float("nan"),
        "random_control_percentile": random_percentile,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in portfolio_backtest_v2")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in portfolio_backtest_v2")

    industry_map = load_industry_map()
    trend_regime = _trend_regime_series(market_df)
    liquidity = {sid: _liquidity_proxy_series(d) for sid, d in data.items()}

    # 兩階段設計（實測單一組合含成本敏感度+30次隨機控制組跑超過2分鐘，2*3*2*2=24種
    # 組合全部這樣跑不可行）：
    #   階段1（便宜）：全部24種組合(2因子版本x3加權x2頻率x2期間)只跑1x成本、不跑隨機
    #   控制組，快速掃出報酬/MDD/Sortino/alpha這些「主結果」，找出方向。
    #   階段2（完整）：只針對VALIDATION期（決策真正在意的樣本外表現，TRAIN期只用來看
    #   跨期一致性，不需要重複跑一次昂貴的隨機控制組）補上成本敏感度+隨機控制組
    #   （抽樣數降到15，時間預算有限，誠實揭露）。
    print("\n========== 階段1：全網格快速掃描（1x成本、無隨機控制組）==========")
    quick_results = []
    for factor_version in FACTOR_VERSIONS:
        for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
            for cadence_name in REBALANCE_CADENCES:
                for label, start, end in (
                    ("TRAIN", "2015-01-01", holdout.TRAIN_END),
                    ("VALIDATION", "2021-01-01", holdout.VAL_END),
                ):
                    r = run_one(factor_version, weight_mode, cadence_name, label, data, market_df,
                                industry_map, trend_regime, liquidity, start, end,
                                do_cost_sensitivity=False, do_random_control=False)
                    quick_results.append(r)
                    print(f"  {factor_version}/{weight_mode}/{cadence_name}/{label}: "
                          f"報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                          f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.3f})  "
                          f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%")

    quick_df = pd.DataFrame(quick_results)
    quick_df.to_csv("data/portfolio_backtest_v2_quick_scan.csv", index=False)
    print("\n已存 data/portfolio_backtest_v2_quick_scan.csv（階段1全部24種組合）")

    print("\n========== 階段2：VALIDATION期補完整成本敏感度+隨機控制組（15次重抽）==========")
    full_results = []
    for factor_version in FACTOR_VERSIONS:
        for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
            for cadence_name in REBALANCE_CADENCES:
                r = run_one(factor_version, weight_mode, cadence_name, "VALIDATION", data, market_df,
                            industry_map, trend_regime, liquidity, "2021-01-01", holdout.VAL_END,
                            do_cost_sensitivity=True, do_random_control=True, n_random=15)
                full_results.append(r)
                print(f"\n--- {factor_version} / {weight_mode} / {cadence_name} / VALIDATION（完整版）---")
                print(f"  報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                      f"Sharpe={r['sharpe']:.3f}  trades={r['n_trades']}")
                print(f"  alpha(年化)={r['alpha_ann_pct']:+.2f}%  beta={r['beta']:+.3f}  "
                      f"p={r['alpha_pvalue']:.4f}  顯著為正={r['alpha_significant']}")
                print(f"  買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%  "
                      f"隨機對照組中位數={r['random_control_median_pct']:+.2f}%  percentile={r['random_control_percentile']:.1f}")
                print(f"  成本1x/2x/3x: {r['cost_1x']:+.2f}% / {r['cost_2x']:+.2f}% / {r['cost_3x']:+.2f}%")

    df = pd.DataFrame(full_results)
    df.to_csv("data/portfolio_backtest_v2_results.csv", index=False)
    print("\n=== SUMMARY（階段2，VALIDATION完整版，存 data/portfolio_backtest_v2_results.csv）===")
    print(df[["factor_version", "weight_mode", "cadence", "return_pct", "mdd_pct", "sortino", "sharpe",
              "alpha_ann_pct", "alpha_pvalue", "alpha_significant", "buy_and_hold_index_pct",
              "random_control_percentile", "cost_3x"]].to_string(index=False))
    return quick_df, df


if __name__ == "__main__":
    main()
