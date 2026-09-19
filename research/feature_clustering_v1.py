# -*- coding: utf-8 -*-
"""
分群.一（2026-09-19總司令裁示【成本模型更正＋單一商品策略改為特徵分群】三）：
商品特徵分群的可檢驗判準——群間變異數 vs 群內變異數。

用途：對「既有已跑過的策略」的個股層級交易結果，按事前鎖定的可觀測特徵
（20日均成交金額分位／60日波動分位／市值分位／產業大類；法人持股比例
因目前無便宜的PIT快取資料源，本輪略過，見下方文件說明）分組，檢驗組間
績效變異是否顯著大於組內變異。這是「能不能做分群策略」的先決結構檢定，
不是策略本身。

**資料集選擇（設計決策，非總司令原文指定，需在報告誠實揭露）**：
用`weinstein_stage2_v2`（`STRATEGY_GRAVEYARD.md`已記載2026-08-29 FAIL，
「表面總報酬贏買進持有，拆解後主要是beta貢獻」）的VALIDATION期交易記錄
（`data/backtests/weinstein_stage2_v2_unbiased_validation_trades.csv`），
理由：
  1. 這是本專案唯一把「已跑過策略」的個股層級交易明細**存成CSV**的既有
     策略（`portfolio_multifactor_v2`/`power_budget.py`系列只有portfolio
     層級`equity_curve`，沒有落地`trades.csv`），要重跑才能拿到個股級
     資料，而重跑會撞上目前FinMind封鎖冷卻（見`成本.二`/`成本.三`同一輪
     發現）。
  2. 該策略本身alpha顯著性FAIL不影響本檢定的有效性——分群.一問的是「同一
     個策略執行機制下，不同特徵的股票表現是否系統性不同」，不是「這個
     策略賺不賺錢」，兩者是獨立的問題。
  3. VALIDATION期（非TRAIN、非HOLDOUT）符合既有holdout紀律。

**市值分位的PIT警告（誠實揭露，非精確數字）**：本機快取沒有股數/市值
資料集，用`TaiwanStockBalanceSheet`的`CapitalStock`（股本，面額調整前）
除以面額10元 近似股數，乘上進場日收盤價近似市值。用最近一筆
**申報日期在進場日之前至少45天**的股本值（近似財報公告延遲，非精確
查證的法定天數），這是近似值不是精確市值，可能因庫藏股/私募等股本
變動細節而失準，但作為5個分位分組的排序依據，方向性應該還算穩。

**法人持股比例（可選維度，本輪略過）**：`TaiwanStockInstitutionalInvestorsBuySell`
快取的是買賣超金額而非持股比例本身，換算需要額外的股本/流通股數整合，
超出本輪合理範圍，總司令原文本身也標記這項「可選」，本輪誠實跳過，
不偽造數字。

全程使用本機已快取的parquet（`data/raw/`），零筆FinMind即時請求
（目前封鎖冷卻中，剩餘時間見`data/rate_limit_state.json`）。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import finmind_client as fc
from score import load_industry_map

TRADES_CSV = Path(__file__).parent / "data" / "backtests" / "weinstein_stage2_v2_unbiased_validation_trades.csv"
PIT_LAG_DAYS = 45  # 財報公告延遲近似值，見上方docstring


def _cached_price(stock_id: str) -> pd.DataFrame | None:
    for f in sorted(Path(fc.DATA_DIR).glob(f"TaiwanStockPrice__{stock_id}__*.parquet"),
                     key=lambda p: p.stat().st_size, reverse=True):
        df = pd.read_parquet(f)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
    return None


def _cached_balance_sheet(stock_id: str) -> pd.DataFrame | None:
    for f in sorted(Path(fc.DATA_DIR).glob(f"TaiwanStockBalanceSheet__{stock_id}__*.parquet"),
                     key=lambda p: p.stat().st_size, reverse=True):
        df = pd.read_parquet(f)
        if not df.empty:
            return df
    return None


def _capital_stock_asof(bs: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    cap = bs[bs["type"] == "CapitalStock"].copy()
    if cap.empty:
        return None
    cap["date"] = pd.to_datetime(cap["date"])
    cutoff = asof - pd.Timedelta(days=PIT_LAG_DAYS)
    cap = cap[cap["date"] <= cutoff]
    if cap.empty:
        return None
    return float(cap.sort_values("date").iloc[-1]["value"])


def build_trade_level_dataset() -> pd.DataFrame:
    trades = pd.read_csv(TRADES_CSV)
    trades["date"] = pd.to_datetime(trades["date"])
    buys = trades[trades["side"] == "buy"].set_index("trade_id")
    sells = trades[trades["side"] == "sell"].copy()

    rows = []
    industry_map = load_industry_map()
    price_cache: dict[str, pd.DataFrame] = {}
    bs_cache: dict[str, pd.DataFrame] = {}

    for _, sell in sells.iterrows():
        entry_id = sell["entry_trade_id"]
        if pd.isna(entry_id) or entry_id not in buys.index:
            continue
        buy = buys.loc[entry_id]
        stock_id = str(sell["stock_id"])
        entry_date = pd.Timestamp(buy["date"])
        buy_notional = float(buy["price"]) * float(buy["shares"])
        if buy_notional <= 0:
            continue
        trade_return_pct = float(sell["realized_pnl"]) / buy_notional * 100.0

        if stock_id not in price_cache:
            price_cache[stock_id] = _cached_price(stock_id)
        pdf = price_cache[stock_id]
        if pdf is None:
            continue
        hist = pdf[pdf["date"] <= entry_date]
        if len(hist) < 60:
            continue
        liquidity_20d = hist["Trading_money"].tail(20).mean()
        daily_ret = hist["close"].tail(61).pct_change().dropna()
        if len(daily_ret) < 30:
            continue
        vol_60d_ann = float(daily_ret.std() * np.sqrt(252) * 100)
        entry_close = float(hist.iloc[-1]["close"])

        if stock_id not in bs_cache:
            bs_cache[stock_id] = _cached_balance_sheet(stock_id)
        bs = bs_cache[stock_id]
        capital_stock = _capital_stock_asof(bs, entry_date) if bs is not None else None
        market_cap = (capital_stock / 10.0) * entry_close if capital_stock else None

        rows.append({
            "stock_id": stock_id,
            "entry_date": entry_date,
            "trade_return_pct": trade_return_pct,
            "liquidity_20d_money": liquidity_20d,
            "volatility_60d_ann_pct": vol_60d_ann,
            "market_cap_approx": market_cap,
            "industry": industry_map.get(stock_id, "UNKNOWN"),
        })

    return pd.DataFrame(rows)


def _quantile_group(series: pd.Series, n_groups: int = 3) -> pd.Series:
    valid = series.dropna()
    if valid.nunique() < n_groups:
        return pd.Series(["insufficient_data"] * len(series), index=series.index)
    labels = [f"Q{i+1}" for i in range(n_groups)]
    try:
        q = pd.qcut(series.rank(method="first"), n_groups, labels=labels)
    except ValueError:
        return pd.Series(["insufficient_data"] * len(series), index=series.index)
    return q.astype(str)


def between_within_variance_decomposition(df: pd.DataFrame, group_col: str,
                                            value_col: str = "trade_return_pct") -> dict:
    clean = df[[group_col, value_col]].dropna()
    clean = clean[clean[group_col] != "insufficient_data"]
    groups = [g[value_col].values for _, g in clean.groupby(group_col) if len(g) >= 2]
    if len(groups) < 2:
        return {"n_groups": len(groups), "f_stat": float("nan"), "p_value": float("nan"),
                "verdict": "INSUFFICIENT_GROUPS"}
    f_stat, p_value = stats.f_oneway(*groups)
    grand_mean = clean[value_col].mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_within = sum(((g - g.mean()) ** 2).sum() for g in groups)
    ss_total = ss_between + ss_within
    eta_squared = ss_between / ss_total if ss_total > 0 else float("nan")
    return {
        "n_groups": len(groups),
        "group_sizes": [len(g) for g in groups],
        "group_means": {str(k): float(v[value_col].mean()) for k, v in clean.groupby(group_col)
                         if len(v) >= 2},
        "f_stat": float(f_stat),
        "p_value": float(p_value),
        "eta_squared_between_share_of_variance": float(eta_squared),
        "verdict": "GROUP_DIFFERENCE_SIGNIFICANT" if p_value < 0.05 else "NOISE_NOT_STRUCTURE",
    }


def main():
    df = build_trade_level_dataset()
    print(f"可用交易筆數: {len(df)}（母體61檔個股，172筆平倉交易）")
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    df.to_csv(data_dir / "feature_clustering_v1_dataset.csv", index=False)

    df["liquidity_group"] = _quantile_group(df["liquidity_20d_money"], 3)
    df["volatility_group"] = _quantile_group(df["volatility_60d_ann_pct"], 3)
    df["market_cap_group"] = _quantile_group(df["market_cap_approx"], 3)

    results = {}
    for dim, col in [("20日均成交金額分位(3組)", "liquidity_group"),
                      ("60日波動分位(3組)", "volatility_group"),
                      ("市值分位(3組，近似值見docstring)", "market_cap_group"),
                      ("產業大類", "industry")]:
        res = between_within_variance_decomposition(df, col)
        results[dim] = res
        print(f"\n=== {dim} ===")
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))

    n_valid_market_cap = df["market_cap_approx"].notna().sum()
    meta = {
        "n_trades_total": int(len(df)),
        "n_trades_with_market_cap": int(n_valid_market_cap),
        "data_source": "weinstein_stage2_v2_unbiased_validation_trades.csv",
        "dimensions_tested": list(results.keys()),
        "note": "法人持股比例維度本輪略過，見docstring說明",
    }
    out = {"meta": meta, "results": results}
    out_path = Path(__file__).parent / "feature_clustering_v1_results.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n寫入: {out_path}")


if __name__ == "__main__":
    main()
