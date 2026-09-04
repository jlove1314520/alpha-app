"""馬拉松第353輪（TW軌）——組合策略層級迭代：深挖round346找到的`loo_no_low_vol`候選。

背景：round346（`leave_one_factor_out_bigsample.py`）對`portfolio_multifactor_v2`
做leave-one-factor-out，三個2因子子版本裡，**拿掉`low_vol`**（剩`eps_family`+
`revenue_surprise`，train-only IC加權）是唯一一個「TRAIN+VAL兩期alpha皆正」、且
VALIDATION/monthly名目上p<0.05（p=0.0489）的子版本。但round346只跑了1x成本、
無隨機控制組的quick scan，`TW_LEADS.md`明確記錄「下一步深挖前提：成本敏感度
1x/2x/3x、隨機控制組N≥100，且p<0.05是從3個子版本挑最佳者之後才看到的數字，
隱含多重比較，未經校正前不能視為顯著」——這輪把這些前提補上，取得能真正拿來
判定的完整數字。

做法：
1. 完全重用round346`leave_one_factor_out_bigsample.py`的資料載入/權重計算/
   monkeypatch機制（同一批300檔安全樣本池、同一套TRAIN-only mean|IC|權重），
   不重寫、不改動既有檔案。
2. 只跑`loo_no_low_vol`這一個子版本（round346已經確立這是三者中唯一有潛力的
   一個，另外兩個子版本連名目p值都在0.7以上，深挖沒有意義）。
3. VALIDATION期monthly＋quarterly兩個頻率，都用`run_one(do_cost_sensitivity=True,
   do_random_control=True, n_random=100)`——完整版：1x/2x/3x成本敏感度＋100次
   配對式隨機控制組（沿用`portfolio_backtest_v2.py`既有機制，跟round201/202對
   完整3因子版本用的N=100解析度一致，不是round346的N=15/0天花板假象）。
4. TRAIN期不重複跑完整版（round346已有quick scan數字，這輪聚焦在真正用來
   判定的VALIDATION期補齊深挖關卡，避免一輪塞太多任務）。
5. 這仍是組合策略內部診斷（`portfolio_multifactor_v2`家族的迭代），不是新
   因子/新策略試驗，暫不進`TRIALS_LEDGER.md`——除非這裡的完整數字顯示這個
   2因子子版本本身可能構成一個新的、獨立的候選策略，屆時才另外走完整流程。

**重要：這仍然只是「深挖」單一子版本的一個組合，不是對round346挑出的候選做
多重比較校正的替代品**——round346是從3個子版本裡挑最佳，這輪的p值本身仍然
帶著那個「先看過3個結果再挑1個深挖」的選擇偏誤，不能因為深挖數字好看就視為
乾淨顯著結果，要在解讀時明確揭露這一點。

零新增API呼叫（全部讀取本機快取：yfinance價格快取＋FinMind財報/月營收快取）。
"""
from __future__ import annotations

import sys
import time
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
LOO_NO_LOW_VOL_VERSION = {"loo_no_low_vol": ["eps_family", "revenue_surprise"]}


def main():
    t0 = time.time()
    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    print(f"pool total={len(all_ids)}, using first 300: {sample_ids[0]}..{sample_ids[-1]}", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_loo_no_low_vol")
    market_df = prepare_market_data(market_raw)
    print("market data ready", flush=True)

    data = load_safe_sample(sample_ids)
    print(f"loaded {len(data)}/{len(sample_ids)} usable names", flush=True)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in deep_dive_loo_no_low_vol")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping snapshots, {SNAPSHOT_START}..{holdout.VAL_END}", flush=True)

    # TRAIN-only mean |IC|（跟round340/346完全相同的算法，重算一次確認可重現）
    print("\n========== TRAIN-only mean |IC| ==========", flush=True)
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

    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}

    original_versions = dict(pv2.FACTOR_VERSIONS)
    original_weights = dict(pv2.IC_WEIGHTS)
    pv2.FACTOR_VERSIONS = {**original_versions, **LOO_NO_LOW_VOL_VERSION}
    pv2.IC_WEIGHTS = train_only_weights

    print("\n========== 深挖：loo_no_low_vol / ic_weighted(train-only) / VALIDATION，"
          "monthly+quarterly，完整版（1x/2x/3x成本 + N=100隨機控制組） ==========", flush=True)
    import os
    cadences = os.environ.get("DEEP_DIVE_CADENCES", "monthly,quarterly").split(",")
    results = []
    try:
        for cadence_name in cadences:
            t1 = time.time()
            r = pv2.run_one("loo_no_low_vol", "ic_weighted", cadence_name, "VALIDATION",
                             data, market_df, industry_map, trend_regime, liquidity,
                             "2021-01-01", holdout.VAL_END,
                             do_cost_sensitivity=True, do_random_control=True, n_random=100)
            r["n_stocks"] = len(data)
            results.append(r)
            elapsed = time.time() - t1
            print(f"  {cadence_name}/VALIDATION（耗時{elapsed:.1f}秒）: "
                  f"報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  "
                  f"Sortino={r['sortino']:.3f}  alpha={r['alpha_ann_pct']:+.2f}%"
                  f"(p={r['alpha_pvalue']:.4f})  beta={r['beta']:.3f}  "
                  f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%  "
                  f"成本1x/2x/3x={r['cost_1x']:+.2f}/{r['cost_2x']:+.2f}/{r['cost_3x']:+.2f}%  "
                  f"隨機控制組percentile={r['random_control_percentile']:.1f}"
                  f"（中位數{r['random_control_median_pct']:+.2f}%）", flush=True)
    finally:
        pv2.FACTOR_VERSIONS = original_versions
        pv2.IC_WEIGHTS = original_weights

    df = pd.DataFrame(results)
    df.to_csv("data/deep_dive_loo_no_low_vol_validation.csv", index=False)
    print(f"\nsaved data/deep_dive_loo_no_low_vol_validation.csv（總耗時{time.time()-t0:.1f}秒）", flush=True)


if __name__ == "__main__":
    main()
