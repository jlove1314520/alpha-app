"""HYPOTHESIS_QUEUE.md #27 多因子複合評分 z-score blend baseline第1關cheap IC gate起步：
相關矩陣sanity + baseline複合(GP+f_value_pb+f_revenue_surprise，等權z-score加總)IC測試。

使用者原話baseline：「先跑baseline複合（GP+價值+月營收意外，等權），過cheap gate才打
完整gauntlet」。價值因子選f_value_pb（非f_value_pe）：TRIALS_LEDGER.md#13 CHEAP_PASS
狀態比#14 f_value_pe（累積校正後降級為不確定）更穩固，是本專案目前對這兩個估值因子已有
的既定判定，不是本輪新選擇（見factors.py檔頭PIT揭露：spot-check未發現嚴重look-ahead）。

沿用factor_ic.py既有cross-sectional IC+洗牌null框架做「這個複合分數本身」的cheap gate，
跟本佇列其餘26條單因子第1關同一套機制（train/val同號+|val_ic|>=0.02+贏過1000次洗牌null
percentile>=90.0）。**本輪範圍聲明**：使用者原話額外要求「隨機對照draws>=300、對照組是
隨機選同數量因子亂配權重」這個更嚴格的「贏過隨機組合」控制，跟正交性檢查/leave-one-
factor-out同屬「抗過度擬合控制」，是複合分數若通過這關cheap gate之後的下一步深挖驗證，
本輪先完成「這個複合分數本身是否有真實可辨識的預測力」這一關，不等同宣告「這個特定
組合優於隨機組合」，兩者是不同問題，若本關過了需在下一輪接續。

2026-09-03由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#27第1關起跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, START_DATE, SNAPSHOT_START,
    sample_universe_ids, load_sample_with_factors, build_snapshots, evaluate_factor,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

CANDIDATE_FACTORS = ["f_gross_profitability", "f_value_pb", "f_value_pe", "f_revenue_surprise"]
BASELINE_FACTORS = ["f_gross_profitability", "f_value_pb", "f_revenue_surprise"]
COMPOSITE_COL = "f_composite_zscore_v1"


def correlation_matrix(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for sid, d in data.items():
        cols = [c for c in CANDIDATE_FACTORS if c in d.columns]
        sub = d[["date"] + cols].copy()
        sub["stock_id"] = sid
        frames.append(sub)
    panel = pd.concat(frames, ignore_index=True)
    return panel[CANDIDATE_FACTORS].corr(method="spearman")


def add_composite_zscore(data: dict[str, pd.DataFrame], factors: list[str]) -> None:
    """逐日橫斷面z-score化每個因子後加總；任一組成因子當天缺值就把該股當天複合分數
    設為NaN（不用0填補去偷偷降低缺值股票的懲罰，避免製造隱性的訊號稀釋/膨脹）。"""
    frames = []
    for sid, d in data.items():
        sub = d[["date"] + factors].copy()
        sub["stock_id"] = sid
        frames.append(sub)
    panel = pd.concat(frames, ignore_index=True)

    def zsum(g: pd.DataFrame) -> pd.Series:
        z = pd.DataFrame(index=g.index)
        for f in factors:
            vals = g[f]
            std = vals.std(skipna=True)
            if std and std > 0:
                z[f] = (vals - vals.mean(skipna=True)) / std
            else:
                z[f] = np.nan
        return z.sum(axis=1, skipna=False)

    panel[COMPOSITE_COL] = panel.groupby("date", group_keys=False).apply(zsum)

    for sid, d in data.items():
        merged = d.merge(
            panel.loc[panel["stock_id"] == sid, ["date", COMPOSITE_COL]],
            on="date", how="left",
        )
        d[COMPOSITE_COL] = merged[COMPOSITE_COL].to_numpy()


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print("=== HYPOTHESIS_QUEUE.md#27 多因子複合z-score baseline "
          "(f_gross_profitability + f_value_pb + f_revenue_surprise, 等權) ===")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in composite_zscore_v1")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    print("\n--- 第1步：候選因子相關矩陣 (pooled Spearman, 全期間, 非per-date) ---")
    corr = correlation_matrix(data)
    print(corr.round(3).to_string())
    print("  說明：baseline三因子為 f_gross_profitability / f_value_pb / f_revenue_surprise，"
          "f_value_pe僅列入相關矩陣供對照(未用於baseline複合)。")

    print("\n--- 第2步：baseline複合z-score加總 ---")
    add_composite_zscore(data, BASELINE_FACTORS)
    n_valid = sum(int(d[COMPOSITE_COL].notna().sum()) for d in data.values())
    print(f"  baseline因子: {BASELINE_FACTORS}")
    print(f"  複合欄位非NaN列數(全部股票加總): {n_valid}")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    print("\n--- 第3步：複合因子cheap IC gate (train/val + 1000次洗牌null, standalone bonferroni_n=1) ---")
    r = evaluate_factor(COMPOSITE_COL, data, snapshots, bonferroni_n=1)
    print(f"  train: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
    print(f"  val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
    print(f"  null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
    print(f"  cheap gate PASSES(不含使用者要求的300-draw隨機組合對照，見檔頭範圍聲明): "
          f"{r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))
    return r


if __name__ == "__main__":
    main()
