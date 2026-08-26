"""主線 2（2026-08-26 使用者裁示）：多因子組合策略回測——**這才是真正的 holdout 候選**，
單一因子不是。未經使用者明確同意，不准呼叫 `unlock_holdout_once()`。

背景：`score.py`/`run_score_backtest.py`（`score_topn_v1`）是「App 顯示用的評分」（見
`score.py` docstring），不是這裡要的策略回測——這支腳本是另外新建、專門測試 4 個已
通過 IC 檢定的因子（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`）
＋ 1 個待複驗候選（`f_value_pe`，2026-08-25 FDR 重新評分後的結果，見 `TRIALS_LEDGER.md`）
組成的**三個加權版本**：

1. **等權** (`equal`)：4 個獨立成分（EPS家族去重後1個+revenue_surprise+low_vol+value_pe）
   各 1/4，跟 `score.py` 同精神但多納入 `f_value_pe`。
2. **IC加權** (`ic_weighted`)：權重 ∝ `factor_ic.py` 算出的驗證期(val) IC 絕對值，
   靜態、不隨時間變動。實測數字（80檔驗證樣本，見下方 `IC_WEIGHTS` 常數的計算依據）：
   eps_family +0.0788、revenue_surprise +0.0397、low_vol +0.0967、value_pe +0.0533。
3. **情境條件式加權** (`regime_weighted`)：權重隨每個換股日當下的「波動度環境」
   （`regime_conditions.py` PIT-safe 的 20日已實現波動度 vs 擴張窗中位數）動態調整，
   ∝ 該因子在當下波動度狀態下的分群IC絕對值（見 `REGIME_CONDITIONS.md`）。**只用波動度
   這一個條件維度**（不是全部四組）——這是刻意的範圍縮減，理由：`REGIME_CONDITIONS.md`
   顯示波動度維度上四個成分的量級差異最大、方向解讀最清楚（`f_low_vol`/`f_value_pe`/
   `f_eps_growth`在低波動下更強，`f_revenue_surprise`相反在高波動下更強），其餘三組
   條件（大盤位階/市值規模/流動性）較適合用在挑選「哪些股票」而非「怎麼加權因子」，
   混進來會讓這裡的邏輯複雜到難以驗證，留待後續。

**完整交易規則（使用者要求，不能只給報酬數字）**：
- 換股頻率：每週五（`backtest/engine.py::BacktestConfig.rebalance_weekday=4`，T日收盤
  訊號→T+1收盤成交，跟這個專案其他回測一致）。
- 持股檔數：10 檔（`max_positions=10`），單一部位上限＝總資產 1/10（引擎原生機制：
  等權分配於這 10 個槽位，不會集中壓單一檔）。
- 進出場規則：綜合分（三種加權版本之一）由高到低排序，取前10名；只換真正進出前10
  名的名字，不強制全部重新等權（引擎原生行為，降低不必要換手）；15% 停損（引擎既有
  的第三層風控，跟 `weinstein_stage2` 系列一致）。
- 全成本：手續費0.1425%×2＋證交稅0.3%（`validation/costs.py`），1x/2x/3x敏感度都測。
- 資格池：`score.eligible_for_ranking()`（`MIN_COMPONENTS_FOR_RANKING=2`，同一產業
  peer z-score）。

**評判順序（使用者裁示，取代單純看報酬率）**：
1. 淨利與 MDD 達標（正報酬、MDD 沒有失控）
2. Sortino ratio
3. 對大盤回歸後 alpha 是否顯著為正（`scipy.stats.linregress`，t檢定 p<0.05）
4. Sharpe ratio（放最後，僅供參考）
"""
from __future__ import annotations

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

TOP_N = 10
COST_MULTIPLIERS = (1, 2, 3)

# 靜態 IC 加權版本的權重來源：factor_ic.py 對 80 檔驗證樣本、2015-01-01..VAL_END
# 算出的驗證期(val) mean IC 絕對值（跟 REGIME_CONDITIONS.md 用同一批快照/樣本）。
# eps_family 是 f_eps_growth(+0.0773)/f_eps_surprise(+0.0804) 的平均——這兩個因子
# 同家族(+0.831相關，factor_correlation.py)去重成一個成分，跟 score.py 同精神。
IC_WEIGHTS = {
    "eps_family": (0.0773 + 0.0804) / 2,
    "revenue_surprise": 0.0397,
    "low_vol": 0.0967,
    "value_pe": 0.0533,
}

# 情境條件式版本：每個成分在「高波動」/「低波動」環境下各自的分群IC絕對值
# （REGIME_CONDITIONS.md，只用波動度這一個條件維度，理由見上面模組docstring）。
REGIME_IC_WEIGHTS = {
    "high_vol": {
        "eps_family": (0.0685 + 0.0746) / 2, "revenue_surprise": 0.0553,
        "low_vol": 0.0567, "value_pe": 0.0576,
    },
    "low_vol": {
        "eps_family": (0.0521 + 0.0491) / 2, "revenue_surprise": 0.0298,
        "low_vol": 0.1632, "value_pe": 0.0844,
    },
}

COMPONENTS = ["eps_family", "revenue_surprise", "low_vol", "value_pe"]


def _vol_regime_series(market_df: pd.DataFrame) -> pd.Series:
    """date -> 'high_vol'/'low_vol', PIT-safe (見 regime_conditions.py 同名邏輯，
    這裡重新算一次是因為需要索引成 date->label 的查表結構，跟那邊回傳格式不同，
    避免額外做一次跨模組的資料轉換)。"""
    d = market_df.sort_values("date").reset_index(drop=True)
    ret = d["close"].pct_change()
    vol20 = ret.rolling(20, min_periods=20).std() * np.sqrt(252)
    expanding_median = vol20.expanding(min_periods=60).median()
    label = np.where(vol20 > expanding_median, "high_vol", "low_vol")
    return pd.Series(label, index=d["date"])


def _raw_components(d: pd.DataFrame) -> dict[str, float | None]:
    """從 prepare_factors() 算好的欄位取出這 4 個成分在當前這一列(某個日期)的原始值。
    d 已經是 as_of 那一天的單列 Series（呼叫端已經 .loc 過），不是整個 DataFrame。"""
    eps_vals = [d.get("f_eps_growth"), d.get("f_eps_surprise")]
    eps_vals = [v for v in eps_vals if pd.notna(v)]
    eps_family = float(np.mean(eps_vals)) if eps_vals else None
    rev = d.get("f_revenue_surprise")
    low_vol = d.get("f_low_vol")
    value_pe = d.get("f_value_pe")
    return {
        "eps_family": eps_family,
        "revenue_surprise": float(rev) if pd.notna(rev) else None,
        "low_vol": float(low_vol) if pd.notna(low_vol) else None,
        "value_pe": float(value_pe) if pd.notna(value_pe) else None,
    }


def compute_composite_at_date(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str],
    weight_mode: str, vol_regime: pd.Series | None = None,
) -> pd.DataFrame:
    """回傳 columns: stock_id, industry, composite, n_components。跟 score.py 同精神
    的同產業 peer z-score，但這裡是獨立實作（4個成分,非3個，且支援3種權重模式），
    不呼叫 score.py 的 compute_scores_at_date()（那個函式的成分/權重是寫死的3個等權，
    改不了，這裡刻意分開避免互相牽動）。
    """
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        raw = _raw_components(d.loc[idx[0]])
        rows.append({"stock_id": sid, "industry": industry_map.get(sid, "UNKNOWN"), **raw})
    if not rows:
        return pd.DataFrame(columns=["stock_id", "industry", "composite", "n_components"])
    cs = pd.DataFrame(rows).set_index("stock_id")

    if weight_mode == "regime_weighted":
        if vol_regime is None or as_of not in vol_regime.index:
            weights = IC_WEIGHTS  # 找不到當天的regime標籤(理論上不該發生)時退回IC加權，不崩潰
        else:
            weights = REGIME_IC_WEIGHTS[vol_regime.loc[as_of]]
    elif weight_mode == "ic_weighted":
        weights = IC_WEIGHTS
    elif weight_mode == "equal":
        weights = {c: 1.0 for c in COMPONENTS}
    else:
        raise ValueError(f"unknown weight_mode: {weight_mode}")

    z_cols = []
    for comp in COMPONENTS:
        z_col = f"z_{comp}"
        # _zscore_within_group() 內建小同儕組(< MIN_PEER_GROUP_SIZE)回退全樣本z-score
        # 的邏輯（score.py 本身的處理），這裡直接重用，不再自己重複實作一次。
        cs[z_col] = _zscore_within_group(cs[comp], cs["industry"])
        z_cols.append((z_col, weights[comp]))

    weighted_sum = pd.Series(0.0, index=cs.index)
    weight_total = pd.Series(0.0, index=cs.index)
    n_components = pd.Series(0, index=cs.index)
    for z_col, w in z_cols:
        valid = cs[z_col].notna()
        weighted_sum[valid] += cs.loc[valid, z_col] * w
        weight_total[valid] += w
        n_components[valid] += 1

    cs["composite"] = np.where(weight_total > 0, weighted_sum / weight_total, np.nan)
    cs["n_components"] = n_components
    return cs.reset_index()[["stock_id", "industry", "composite", "n_components"]]


def _eligible(cs: pd.DataFrame) -> pd.DataFrame:
    from score import MIN_COMPONENTS_FOR_RANKING
    return cs[cs["n_components"] >= MIN_COMPONENTS_FOR_RANKING].sort_values("composite", ascending=False)


def make_signal_fn(industry_map: dict[str, str], weight_mode: str, vol_regime: pd.Series | None):
    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        cs = _eligible(compute_composite_at_date(as_of, price_data, industry_map, weight_mode, vol_regime))
        top = cs.head(TOP_N)
        return dict(zip(top["stock_id"], top["composite"]))
    return signal_fn


def alpha_significance(result_equity: pd.DataFrame, market_df: pd.DataFrame) -> dict:
    """CAPM 迴歸（scipy.stats.linregress，非 np.polyfit）：拿截距(alpha,日頻)、
    beta、跟 alpha 的 t 檢定 p 值——這是使用者要求的「對大盤回歸後alpha顯著為正」
    判準需要的東西，`long_only_vs_market.py::decompose_alpha_beta()` 用 np.polyfit
    沒有算顯著性，這裡另外算一次，不是重複造輪子。
    """
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = result_equity.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"alpha_daily": float("nan"), "alpha_ann_pct": float("nan"), "beta": float("nan"),
                "alpha_pvalue": float("nan"), "alpha_significant": False, "n_days": len(merged)}
    reg = stats.linregress(merged["mkt_return"], merged["net_return"])
    alpha_ann_pct = ((1 + reg.intercept) ** 252 - 1) * 100
    return {
        "alpha_daily": float(reg.intercept), "alpha_ann_pct": float(alpha_ann_pct),
        "beta": float(reg.slope), "alpha_pvalue": float(reg.intercept_stderr and
            2 * stats.t.sf(abs(reg.intercept / reg.intercept_stderr), len(merged) - 2)),
        "alpha_significant": bool(reg.intercept > 0 and reg.intercept_stderr and
            2 * stats.t.sf(abs(reg.intercept / reg.intercept_stderr), len(merged) - 2) < 0.05),
        "n_days": len(merged),
    }


def sharpe_ratio(equity_curve: pd.DataFrame) -> float:
    eq = equity_curve["equity"]
    if len(eq) < 2:
        return float("nan")
    daily_returns = eq.pct_change().dropna()
    if daily_returns.empty or daily_returns.std() == 0:
        return float("nan")
    return float(daily_returns.mean() / daily_returns.std() * np.sqrt(252))


def run_one(weight_mode: str, label: str, data: dict, market_df: pd.DataFrame,
            industry_map: dict, start: str, end: str, vol_regime: pd.Series | None) -> dict:
    print(f"\n--- {label} ({weight_mode}) {start}..{end} ---")
    signal_fn = make_signal_fn(industry_map, weight_mode, vol_regime)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          book_name=f"portfolio_{weight_mode}")
    result = run_backtest(signal_fn, data, market_df, cfg)
    holdout.assert_no_holdout_leakage(result.trades, date_col="date", context=f"portfolio_backtest {weight_mode}")

    alpha = alpha_significance(result.equity_curve, market_df)
    sharpe = sharpe_ratio(result.equity_curve)

    cost_returns = {}
    for mult in COST_MULTIPLIERS:
        c = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                            book_name=f"portfolio_{weight_mode}", cost_multiplier=mult)
        r = run_backtest(signal_fn, data, market_df, c)
        cost_returns[mult] = r.total_return_pct

    print(f"  報酬={result.total_return_pct:+.2f}%  MDD={result.max_drawdown_pct:.2f}%  "
          f"Sortino={result.sortino_ratio:.3f}  Sharpe={sharpe:.3f}  trades={result.n_trades}")
    print(f"  alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta={alpha['beta']:+.3f}  "
          f"p={alpha['alpha_pvalue']:.4f}  顯著為正={alpha['alpha_significant']}")
    print(f"  成本1x/2x/3x: {cost_returns[1]:+.2f}% / {cost_returns[2]:+.2f}% / {cost_returns[3]:+.2f}%")

    return {
        "weight_mode": weight_mode, "label": label, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "sharpe": sharpe, "n_trades": result.n_trades,
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "cost_1x": cost_returns[1], "cost_2x": cost_returns[2], "cost_3x": cost_returns[3],
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in portfolio_backtest")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in portfolio_backtest")

    industry_map = load_industry_map()
    vol_regime = _vol_regime_series(market_df)

    results = []
    for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
        for label, start, end in (
            ("TRAIN", "2015-01-01", holdout.TRAIN_END),
            ("VALIDATION", "2021-01-01", holdout.VAL_END),
        ):
            results.append(run_one(weight_mode, label, data, market_df, industry_map, start, end, vol_regime))

    df = pd.DataFrame(results)
    df.to_csv("data/portfolio_backtest_results.csv", index=False)
    print("\n=== SUMMARY (saved data/portfolio_backtest_results.csv) ===")
    print(df[["weight_mode", "label", "return_pct", "mdd_pct", "sortino", "sharpe",
               "alpha_ann_pct", "alpha_pvalue", "alpha_significant", "cost_3x"]].to_string(index=False))
    return df


if __name__ == "__main__":
    main()
