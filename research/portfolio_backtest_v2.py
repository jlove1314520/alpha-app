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
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()

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

# 2026-09-23總司令裁示【修正alpha量尺＋f52w補完審查＋稽核續跑】尺.一：
# 基準預設改0050含息總報酬，舊版TAIEX價格指數(不含息)保留供重現舊結果。
BENCHMARK_0050_TOTAL_RETURN = "0050_total_return"
BENCHMARK_TAIEX_PRICE_LEGACY = "taiex_price_legacy"
DEFAULT_BENCHMARK = BENCHMARK_0050_TOTAL_RETURN
DIMSON_LAGS = (0, 1, 2)  # Dimson beta的大盤報酬落後期數（含當期）
NEWEY_WEST_MAXLAGS = 5

_0050_TOTAL_RETURN_SERIES: pd.Series | None = None  # module-level cache，避免每次呼叫都重新載入FinMind快取


def _load_0050_total_return_series() -> pd.Series:
    """0050含息總報酬序列(date字串索引，跟market_df同一套日期慣例)，
    快取一次供本模組所有函式共用。沿用`survival_constraint_allocation_
    test.py::load_0050_full_history()`——該函式已用FinMind手動還原權息
    路徑重建0050 2003年至今的完整歷史，且在該檔案的既有測試中驗證過，
    這裡不重新造輪子。"""
    global _0050_TOTAL_RETURN_SERIES
    if _0050_TOTAL_RETURN_SERIES is None:
        from survival_constraint_allocation_test import load_0050_full_history
        df = load_0050_full_history().copy()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        _0050_TOTAL_RETURN_SERIES = df.set_index("date")["adj_close"].sort_index()
    return _0050_TOTAL_RETURN_SERIES

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


def _benchmark_close_series(market_df: pd.DataFrame, benchmark: str) -> pd.Series:
    """回傳基準的收盤(或還原收盤)序列，index=date字串。"""
    if benchmark == BENCHMARK_TAIEX_PRICE_LEGACY:
        return market_df.set_index("date")["close"].sort_index()
    if benchmark == BENCHMARK_0050_TOTAL_RETURN:
        return _load_0050_total_return_series()
    raise ValueError(f"未知的benchmark：{benchmark!r}，合法值："
                      f"{BENCHMARK_0050_TOTAL_RETURN!r}/{BENCHMARK_TAIEX_PRICE_LEGACY!r}")


def buy_and_hold_index_pct(market_df: pd.DataFrame, start: str, end: str,
                            benchmark: str = DEFAULT_BENCHMARK) -> float:
    """對照組(b)：買進持有基準指數，零成本、不換股。

    2026-09-23總司令裁示【修正alpha量尺＋f52w補完審查＋稽核續跑】尺.一：
    預設改0050含息總報酬（`benchmark=BENCHMARK_0050_TOTAL_RETURN`），
    取代舊版TAIEX價格指數——TAIEX是不含息的價格指數，策略端卻是用
    含息adj_close算報酬，兩者不是同一把尺，會系統性高估策略的超額
    報酬，量級約等於「殖利率 x beta」。`benchmark=BENCHMARK_TAIEX_
    PRICE_LEGACY`保留舊行為，只供重現舊結果比較用，不作為新判定依據。
    """
    series = _benchmark_close_series(market_df, benchmark)
    window = series[(series.index >= start) & (series.index <= end)]
    if len(window) < 2:
        return float("nan")
    p0, p1 = window.iloc[0], window.iloc[-1]
    return float(p1 / p0 - 1) * 100


def alpha_significance(equity_curve: pd.DataFrame, market_df: pd.DataFrame,
                        benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """CAPM alpha/beta回歸。

    2026-09-23總司令裁示【修正alpha量尺＋f52w補完審查＋稽核續跑】尺.一：
    - 基準預設0050含息總報酬（見`buy_and_hold_index_pct()`同一次修正），
      `benchmark=BENCHMARK_TAIEX_PRICE_LEGACY`保留舊行為供對照。
    - 標準誤改用Newey-West(HAC, maxlags=5)取代原本假設殘差獨立同分布
      的一般OLS標準誤——策略報酬序列存在自我相關(換股頻率通常低於
      每日、持倉重疊)，一般OLS標準誤在有自我相關時會低估，讓p值看起來
      比實際更顯著。
    - beta改報Dimson beta（大盤報酬同期+落後1/2期三項係數加總），
      修正非同步交易/薄交易個股報酬相對大盤落後入帳造成的OLS beta
      低估；`alpha_ann_pct`/`alpha_pvalue`改用Dimson版本回歸的截距
      計算。同時保留`beta_ols`(=lag0單一迴歸係數)供對照，判斷兩者差距
      大不大。
    - `n_days`不變（Dimson版因為要shift(2)會比OLS版少2筆，取Dimson
      版的樣本數，因為alpha/p值是用它算的）。
    """
    mkt = _benchmark_close_series(market_df, benchmark)
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")

    lag_cols = {f"mkt_lag{lag}": mkt_ret.shift(lag) for lag in DIMSON_LAGS}
    merged = pd.concat([net_ret, pd.DataFrame(lag_cols)], axis=1, join="inner").dropna()
    lag_names = list(lag_cols.keys())
    if len(merged) < 30:
        return {
            "alpha_ann_pct": float("nan"), "beta": float("nan"), "beta_ols": float("nan"),
            "alpha_pvalue": float("nan"), "alpha_significant": False, "n_days": len(merged),
            "benchmark": benchmark,
        }

    import statsmodels.api as sm

    X_dimson = sm.add_constant(merged[lag_names])
    model_dimson = sm.OLS(merged["net_return"], X_dimson).fit(cov_type="HAC", cov_kwds={"maxlags": NEWEY_WEST_MAXLAGS})
    beta_dimson = float(model_dimson.params[lag_names].sum())
    alpha_daily = float(model_dimson.params["const"])
    alpha_pvalue = float(model_dimson.pvalues["const"])
    alpha_ann_pct = ((1 + alpha_daily) ** 252 - 1) * 100

    X_ols = sm.add_constant(merged[["mkt_lag0"]])
    model_ols = sm.OLS(merged["net_return"], X_ols).fit(cov_type="HAC", cov_kwds={"maxlags": NEWEY_WEST_MAXLAGS})
    beta_ols = float(model_ols.params["mkt_lag0"])

    return {
        "alpha_ann_pct": float(alpha_ann_pct), "beta": beta_dimson, "beta_ols": beta_ols,
        "alpha_pvalue": alpha_pvalue if alpha_pvalue == alpha_pvalue else float("nan"),
        "alpha_significant": bool(alpha_daily > 0 and alpha_pvalue == alpha_pvalue and alpha_pvalue < 0.05),
        "n_days": len(merged), "benchmark": benchmark,
    }


def average_invested_pct(result, data: dict) -> float:
    """平均投入比例(持股市值/總權益)，區分低beta是現金拖累還是真的
    低相關（2026-09-23裁示尺.一新增）。`backtest/engine.py`目前的
    `equity_curve`沒有現金欄位，這裡用`result.trades`(買進/賣出交易
    紀錄)在pandas重建每日持倉市值——跟`backtest_engine_soundness_
    test.py::run_s2b()`同一套重建手法，不修改`engine.py`本身（協調.零
    單一寫入者規則：只讀`result.trades`不改`backtest/engine.py`）。"""
    eq = result.equity_curve
    if eq.empty:
        return float("nan")
    trades = result.trades
    buys = trades[trades["side"] == "buy"].sort_values("date")
    sells = trades[trades["side"] == "sell"].sort_values("date")
    buys_by_date = {d: g for d, g in buys.groupby("date")}
    sells_by_date = {d: g for d, g in sells.groupby("date")}

    price_by_sid: dict[str, pd.Series] = {}
    for sid, df in data.items():
        s = df.set_index("date")["adj_close"].astype(float)
        s = s.mask(s <= 0)
        price_by_sid[sid] = s

    holdings: dict[str, float] = {}
    last_price: dict[str, float] = {}
    invested_fracs = []
    for _, row in eq.iterrows():
        d, equity = row["date"], row["equity"]
        if d in buys_by_date:
            for _, r in buys_by_date[d].iterrows():
                holdings[r["stock_id"]] = holdings.get(r["stock_id"], 0.0) + float(r["shares"])
        if d in sells_by_date:
            for _, r in sells_by_date[d].iterrows():
                holdings[r["stock_id"]] = holdings.get(r["stock_id"], 0.0) - float(r["shares"])
        invested = 0.0
        for sid, sh in holdings.items():
            if sh == 0:
                continue
            p = price_by_sid.get(sid, pd.Series(dtype=float)).get(d, np.nan)
            if pd.notna(p):
                last_price[sid] = p
            invested += sh * last_price.get(sid, 0.0)
        if equity and equity == equity:
            invested_fracs.append(invested / equity)
    if not invested_fracs:
        return float("nan")
    return float(np.mean(invested_fracs) * 100)


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
