"""馬拉松第356輪（TW軌）——組合策略層級迭代：`loo_no_low_vol`候選的獨立樣本外驗證。

背景：round353已對round346/round118找到的`loo_no_low_vol`子版本（`portfolio_multifactor_v2`
拿掉`low_vol`，剩`eps_family`+`revenue_surprise`，train-only IC加權）補齊了
`TRIALS_LEDGER.md`#118明文列出的兩個深挖前提：成本敏感度1x/2x/3x、隨機控制組N=100。
結果（`data/deep_dive_loo_no_low_vol_validation.csv`）：monthly cadence VALIDATION
alpha+12.26%（p=0.0489，名目<0.05）、percentile=100.0（完勝100次配對式隨機控制組）；
quarterly cadence alpha+11.72%（p=0.1162，不顯著）。

但#118明確列出**第三個**尚未補齊的前提：「一個真正獨立於這次探索的樣本外驗證（例如換
一批不同的300檔樣本...）」——round346/353全程都用同一批`safe_pool_ids()[:300]`，
這個p=0.0489本身還帶著「先看3個leave-one-out子版本挑最佳者」的選擇偏誤（round346/353
自己的文件已多次明文承認）。這輪把第三個前提補上：換一批**完全沒被round346/353的
因子選擇/子版本挑選過程碰過**的300檔（`safe_pool_ids()[300:600]`，池子總量1142檔，
足夠切出一個不重疊的子樣本），在這批新樣本上**重新計算train-only IC權重**（不是沿用
round353在舊樣本上算出的權重數字——樣本換了，權重理應重新估計，這才是誠實的樣本外
測試，不是把舊樣本的參數套到新樣本上做「參數固定、只換測試集」的半吊子驗證），
再跑同一套完整深挖關卡（monthly+quarterly、1x/2x/3x成本、N=100隨機控制組）。

**判讀原則（寫在執行前，避免看到結果才回頭解釋）**：
- 若新樣本上monthly cadence也顯示alpha為正且p<0.10、percentile明顯贏隨機控制組
  →支持這不是舊樣本的偶然巧合，可以考慮升級為候選（仍需FDR校正，不能只看名目p）。
- 若新樣本上monthly alpha轉負、或p值遠高於0.05、或percentile明顯不到90
  →選擇偏誤假說得到支持，這個子版本應該維持FAIL/降級，不能因為在舊樣本上好看
  就繼續信任。
- 兩期（monthly/quarterly）若在新樣本上出現正負號不一致，比照本專案一貫的
  「train/val正負號不一致=FAIL」判準處理。

零新增API呼叫（全部讀取本機快取：yfinance價格快取+FinMind財報/月營收快取），
完全重用`deep_dive_loo_no_low_vol.py`（round353）跟`leave_one_factor_out_bigsample.py`
（round346）已驗證過的資料載入/monkeypatch機制，不修改既有檔案。
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
}
LOO_NO_LOW_VOL_VERSION = {"loo_no_low_vol": ["eps_family", "revenue_surprise"]}


def main():
    t0 = time.time()
    all_ids = safe_pool_ids()
    # 刻意跳過前300檔（round346/353已用過），取[300:600]這個完全獨立的切片
    sample_ids = all_ids[300:600]
    print(f"pool total={len(all_ids)}, using independent slice [300:600]: "
          f"{sample_ids[0]}..{sample_ids[-1]}", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_loo_no_low_vol_independent_sample")
    market_df = prepare_market_data(market_raw)
    print("market data ready", flush=True)

    data = load_safe_sample(sample_ids)
    print(f"loaded {len(data)}/{len(sample_ids)} usable names", flush=True)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date",
                                           context=f"data[{sid}] in deep_dive_loo_no_low_vol_independent_sample")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping snapshots, {SNAPSHOT_START}..{holdout.VAL_END}", flush=True)

    # 在新樣本上重新計算TRAIN-only mean|IC|（不沿用round353舊樣本的權重數字）
    print("\n========== TRAIN-only mean |IC|（獨立樣本[300:600]重新估計） ==========", flush=True)
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
    print("TRAIN_ONLY_IC_WEIGHTS（新樣本重估） =", train_only_weights, flush=True)

    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}

    original_versions = dict(pv2.FACTOR_VERSIONS)
    original_weights = dict(pv2.IC_WEIGHTS)
    pv2.FACTOR_VERSIONS = {**original_versions, **LOO_NO_LOW_VOL_VERSION}
    pv2.IC_WEIGHTS = train_only_weights

    print("\n========== 獨立樣本驗證：loo_no_low_vol / ic_weighted(train-only重估) / "
          "VALIDATION，monthly+quarterly，完整版（1x/2x/3x成本 + N=100隨機控制組） ==========",
          flush=True)
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
    df.to_csv("data/deep_dive_loo_no_low_vol_independent_sample.csv", index=False)
    print(f"\nsaved data/deep_dive_loo_no_low_vol_independent_sample.csv"
          f"（總耗時{time.time()-t0:.1f}秒）", flush=True)


if __name__ == "__main__":
    main()
