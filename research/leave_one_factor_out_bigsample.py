"""第346輪（TW軌）——組合策略層級迭代：leave-one-factor-out。

背景：`portfolio_multifactor_v2`（`A_4pass` = eps_family + revenue_surprise +
low_vol）在300檔安全樣本池上，不論train+val合併IC加權（round327，quarterly VAL
alpha p=0.5314）或train-only嚴格樣本外IC加權（round340，quarterly VAL alpha
p=0.4314），都穩定FAIL（遠未過0.05門檻，非「差一點」的邊緣案例）。round340的
TRAIN-only IC顯示三個成分的訊號強度並不平均：`eps_family` 0.0392／
`revenue_surprise` 0.0505／`low_vol` 0.0350——`low_vol`訊號最弱、`revenue_surprise`
最強。這輪要問：**FAIL是三因子組合的普遍弱勢，還是有特定一個成分在拖累整體？**
若拿掉最弱成分後p值明顯改善（即使仍未過0.05），至少能區分「組合被稀釋」跟
「本質上就沒edge」；若拿掉任何一個成分都沒有實質改善甚至惡化，代表FAIL是
組合層級的系統性弱勢，不是單一因子的問題。

`MARATHON_PROTOCOL.md`第0節裁示明確列出「leave-one-factor-out」是允許的組合
策略層級迭代類型之一。

做法：
1. 沿用round340`train_only_ic_weight_bigsample.py`同一批300檔安全樣本池（
   `safe_pool_ids()`排序後前300檔）＋同一套TRAIN-only mean|IC|權重計算方式，
   零重複造輪子。
2. 三個leave-one-out子組合（各2個成分，equal-weight，因為只剩2個成分時
   train-only IC加權跟等權的相對排序意義不大、且維持跟`FACTOR_VERSIONS`原始
   equal-weight模式同精神），monkeypatch `portfolio_backtest_v2.FACTOR_VERSIONS`
   （不修改該檔案本身，跑完立刻還原）新增3個key，讓`run_one()`原樣重用。
3. 只跑quick scan（1x成本、無隨機控制組），monthly/quarterly × TRAIN/VALIDATION，
   3個子組合 = 12次回測，量級跟round327/340的quick scan相當。
4. 不進TRIALS_LEDGER（這是組合策略內部診斷，不是新因子/新策略候選判定）。

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

FULL_COMPONENTS = ["eps_family", "revenue_surprise", "low_vol"]
TRAIN_ONLY_COMPONENT_COLS = {
    "eps_family": ["f_eps_growth", "f_eps_surprise"],
    "revenue_surprise": ["f_revenue_surprise"],
    "low_vol": ["f_low_vol"],
}
LEAVE_ONE_OUT_VERSIONS = {
    "loo_no_eps_family": ["revenue_surprise", "low_vol"],
    "loo_no_revenue_surprise": ["eps_family", "low_vol"],
    "loo_no_low_vol": ["eps_family", "revenue_surprise"],
}


def main():
    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    print(f"pool total={len(all_ids)}, using first 300: {sample_ids[0]}..{sample_ids[-1]}", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in leave_one_factor_out_bigsample")
    market_df = prepare_market_data(market_raw)
    print("market data ready", flush=True)

    data = load_safe_sample(sample_ids)
    print(f"loaded {len(data)}/{len(sample_ids)} usable names", flush=True)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in leave_one_factor_out_bigsample")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping snapshots, {SNAPSHOT_START}..{holdout.VAL_END}", flush=True)

    # --- 步驟1：TRAIN-only mean |IC|（跟round340完全相同的算法，供對照與紀錄） ---
    print("\n========== 步驟1：TRAIN-only mean |IC|（300檔安全樣本池，同round340） ==========", flush=True)
    raw_train_ic = {}
    for comp, cols in TRAIN_ONLY_COMPONENT_COLS.items():
        for col in cols:
            r = evaluate_factor(col, data, snapshots, bonferroni_n=1)
            raw_train_ic[col] = r.train_mean_ic
            print(f"  {col}: train_mean_ic={r.train_mean_ic:+.4f} (n={r.n_dates_train})", flush=True)
    train_only_weights = {}
    for comp, cols in TRAIN_ONLY_COMPONENT_COLS.items():
        vals = [abs(raw_train_ic[c]) for c in cols if not np.isnan(raw_train_ic[c])]
        train_only_weights[comp] = float(np.mean(vals)) if vals else 0.0
    print("TRAIN_ONLY_IC_WEIGHTS =", train_only_weights, flush=True)
    weakest = min(train_only_weights, key=train_only_weights.get)
    print(f"訓練期IC最弱成分：{weakest}（預期拿掉它對組合影響最小/改善最多）", flush=True)

    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}

    # --- 步驟2：monkeypatch FACTOR_VERSIONS + IC_WEIGHTS，跑3個leave-one-out子組合 ---
    original_versions = dict(pv2.FACTOR_VERSIONS)
    original_weights = dict(pv2.IC_WEIGHTS)
    pv2.FACTOR_VERSIONS = {**original_versions, **LEAVE_ONE_OUT_VERSIONS}
    pv2.IC_WEIGHTS = train_only_weights

    print("\n========== 步驟2：3個leave-one-out子組合 ic_weighted(train-only) quick scan ==========", flush=True)
    results = []
    try:
        for loo_name in LEAVE_ONE_OUT_VERSIONS:
            for cadence_name in ("monthly", "quarterly"):
                for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                                           ("VALIDATION", "2021-01-01", holdout.VAL_END)):
                    r = pv2.run_one(loo_name, "ic_weighted", cadence_name, label, data, market_df,
                                     industry_map, trend_regime, liquidity, start, end,
                                     do_cost_sensitivity=False, do_random_control=False)
                    r["n_stocks"] = len(data)
                    r["dropped_component"] = loo_name.replace("loo_no_", "")
                    results.append(r)
                    print(f"  {loo_name}/{cadence_name}/{label}: 報酬={r['return_pct']:+.2f}%  "
                          f"MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                          f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f})  "
                          f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%", flush=True)
    finally:
        pv2.FACTOR_VERSIONS = original_versions
        pv2.IC_WEIGHTS = original_weights

    df = pd.DataFrame(results)
    df.to_csv("data/leave_one_factor_out_bigsample300.csv", index=False)
    print("\nsaved data/leave_one_factor_out_bigsample300.csv", flush=True)

    print("\n=== 對照：round340完整3因子(train-only IC加權)同樣300檔樣本 ===")
    try:
        base_df = pd.read_csv("data/train_only_ic_weight_bigsample300.csv")
        cols = ["cadence", "label", "alpha_ann_pct", "alpha_pvalue", "return_pct", "mdd_pct", "sortino"]
        print(base_df[cols].to_string(index=False))
    except FileNotFoundError:
        print("（找不到 data/train_only_ic_weight_bigsample300.csv，無法對照）")

    print("\n=== SUMMARY：VALIDATION/quarterly，3個leave-one-out子組合 vs 完整3因子 ===")
    val_q = df[(df["cadence"] == "quarterly") & (df["label"] == "VALIDATION")]
    print(val_q[["dropped_component", "alpha_ann_pct", "alpha_pvalue", "return_pct", "mdd_pct", "sortino"]].to_string(index=False))


if __name__ == "__main__":
    main()
