"""第340輪（TW軌）——組合策略層級迭代：修補`LEADS.md`「誠實限制(2)」點出的
`portfolio_backtest_v2.IC_WEIGHTS`潛在洩漏問題。

背景：`IC_WEIGHTS`（`portfolio_backtest_v2.py`第47行）是用80檔驗證樣本的**驗證期
(val) mean IC絕對值**當權重常數，然後拿同一批VALIDATION期資料去跑回測、算alpha
顯著性——權重本身已經「看過」VAL期表現，不是乾淨的樣本外設計。這是`MARATHON_
PROTOCOL.md`第0節第2點列的允許迭代之一：「train-only嚴格樣本外」，`TW_MARATHON_
STATE.md`第337輪待辦「回頭評估組合策略層級是否有其他迭代方向」的具體落地。

做法：
1. 用`factor_ic.py::evaluate_factor()`（零修改，直接reuse）在300檔安全樣本池（跟
   round327 `run_bigsample_300.py`同一批sorted前300檔stock_id）上，只取**TRAIN
   期**mean |IC|，重新組出一套`TRAIN_ONLY_IC_WEIGHTS`。
2. **不修改`portfolio_backtest_v2.py`本身**（SPEC鎖定、`IC_WEIGHTS`原值保留給既有
   `ic_weighted`結果對照）——改在本腳本內monkeypatch該模組的`IC_WEIGHTS`屬性，
   跑一組獨立標記為`ic_weighted_train_only`的VALIDATION期回測，跟round327已存的
   `ic_weighted`（train+val合併權重）數字並列比較，不覆蓋、不刪除原記錄。
3. 只跑A_4pass（B版本因PER額度問題仍未涵蓋在安全樣本池，同round327限制）。

零新增API呼叫（全部讀取本機快取：yfinance價格快取＋FinMind財報/月營收快取）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import portfolio_backtest_v2 as pv2
from factor_ic import build_snapshots, evaluate_factor
from finmind_client import load_dev
from portfolio_backtest_v2_bigsample import safe_pool_ids, load_safe_sample
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

START_DATE = "2010-01-01"
SNAPSHOT_START = "2015-01-01"

TRAIN_ONLY_COMPONENT_COLS = {
    "eps_family": ["f_eps_growth", "f_eps_surprise"],
    "revenue_surprise": ["f_revenue_surprise"],
    "low_vol": ["f_low_vol"],
}


def main():
    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    print(f"pool total={len(all_ids)}, using first 300: {sample_ids[0]}..{sample_ids[-1]}", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in train_only_ic_weight_bigsample")
    market_df = prepare_market_data(market_raw)
    print("market data ready", flush=True)

    data = load_safe_sample(sample_ids)
    print(f"loaded {len(data)}/{len(sample_ids)} usable names", flush=True)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in train_only_ic_weight_bigsample")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping snapshots, {SNAPSHOT_START}..{holdout.VAL_END}", flush=True)

    # --- 步驟1：TRAIN期單因子IC（只用TRAIN，完全不看VAL期數字） ---
    print("\n========== 步驟1：TRAIN-only mean |IC|（300檔安全樣本池） ==========", flush=True)
    raw_train_ic = {}
    for comp, cols in TRAIN_ONLY_COMPONENT_COLS.items():
        for col in cols:
            r = evaluate_factor(col, data, snapshots, bonferroni_n=1)
            raw_train_ic[col] = r.train_mean_ic
            print(f"  {col}: train_mean_ic={r.train_mean_ic:+.4f} (n={r.n_dates_train}), "
                  f"val_mean_ic={r.val_mean_ic:+.4f}（僅供對照，不用來組權重）", flush=True)

    train_only_weights = {}
    for comp, cols in TRAIN_ONLY_COMPONENT_COLS.items():
        vals = [abs(raw_train_ic[c]) for c in cols if not np.isnan(raw_train_ic[c])]
        train_only_weights[comp] = float(np.mean(vals)) if vals else 0.0

    print("\nTRAIN_ONLY_IC_WEIGHTS =", train_only_weights, flush=True)
    print("既有(train+val合併)IC_WEIGHTS =",
          {k: v for k, v in pv2.IC_WEIGHTS.items() if k in train_only_weights}, flush=True)

    # --- 步驟2：monkeypatch權重，跑ic_weighted VALIDATION期回測（quick scan，1x成本） ---
    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}

    original_weights = dict(pv2.IC_WEIGHTS)
    pv2.IC_WEIGHTS = train_only_weights
    print("\n========== 步驟2：ic_weighted_train_only（monkeypatch權重）VALIDATION+TRAIN期回測 ==========", flush=True)
    results = []
    try:
        for cadence_name in ("monthly", "quarterly"):
            for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                                       ("VALIDATION", "2021-01-01", holdout.VAL_END)):
                r = pv2.run_one("A_4pass", "ic_weighted", cadence_name, label, data, market_df,
                                 industry_map, trend_regime, liquidity, start, end,
                                 do_cost_sensitivity=False, do_random_control=False)
                r["n_stocks"] = len(data)
                r["weight_mode"] = "ic_weighted_train_only"
                results.append(r)
                print(f"  {cadence_name}/{label}: 報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  "
                      f"Sortino={r['sortino']:.3f}  alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f})  "
                      f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%", flush=True)
    finally:
        pv2.IC_WEIGHTS = original_weights  # 還原，避免污染同process後續任何呼叫

    df = pd.DataFrame(results)
    df.to_csv("data/train_only_ic_weight_bigsample300.csv", index=False)
    print("\nsaved data/train_only_ic_weight_bigsample300.csv", flush=True)

    print("\n=== 對照：round327既有ic_weighted（train+val合併權重）同樣300檔樣本 quarterly/VALIDATION ===")
    try:
        old_df = pd.read_csv("data/portfolio_backtest_v2_bigsample300_quick_scan.csv")
        row = old_df[(old_df["weight_mode"] == "ic_weighted") & (old_df["cadence"] == "quarterly") & (old_df["label"] == "VALIDATION")]
        if not row.empty:
            print(row[["alpha_ann_pct", "alpha_pvalue", "return_pct", "mdd_pct", "sortino"]].to_string(index=False))
        else:
            print("（找不到對照列，round327 csv格式可能有變動）")
    except FileNotFoundError:
        print("（找不到 data/portfolio_backtest_v2_bigsample300_quick_scan.csv，無法對照）")


if __name__ == "__main__":
    main()
