"""HYPOTHESIS_QUEUE.md #27 多因子複合評分 z-score blend baseline的第2步：
使用者原話額外要求的「隨機因子組合控制（>=300 draws，隨機選同數量因子亂配權重）」。

背景：`composite_zscore_v1.py`（前一輪已完成）證明了baseline複合分數
（f_gross_profitability + f_value_pb + f_revenue_surprise，等權z-score加總）
本身有可辨識的橫斷面IC（VAL mean_ic=+0.0826，null percentile=100.0）。但那個
cheap gate只證明了「這個特定複合分數本身不是雜訊」，不等於證明「這三個因子的
特定組合優於任意隨機3因子等權/亂權組合」——後者才是CONSTITUTION.md「每個候選
都要打贏『同樣動作、隨機挑對象』的控制組」鐵律要求的對照組，也是使用者原話
明確要求的下一步。

構造：從`factors.py::prepare_factors()`實際會計算出的全部25個f_*因子（見下方
`FACTOR_POOL`，逐一對照`factors.py`原始碼行518-769確認，非憑印象列舉）中，
每次抽3個（跟baseline因子數量相同，抽出不放回），每個因子配一個從
Uniform(-1,1)抽出的隨機權重（真正「亂配權重」，不是重複baseline的等權1.0，
權重可正可負模擬「不知道方向對不對」的隨機建構者），用跟`add_composite_zscore`
完全相同的逐日橫斷面z-score標準化後加權加總邏輯（只是換成加權版），算出
複合分數，只算VAL期mean IC（跳過對每個draw內部再做1000次洗牌null，300 draws
*1000 shuffles=30萬次spearman運算過於昂貴且非必要——這裡的null本身就是
「300個隨機構造」，不需要每個構造內部再疊一層洗牌檢定）。

判準：跟`factor_ic.py::evaluate_factor()`的null_percentile算法同一個定義
（percentile = 100 * mean(abs(baseline) > abs(random_draw)) across draws），
bonferroni_n=1（standalone單一控制測試，非批次），required_percentile=90.0
（跟本佇列其餘標準gate同一把尺）。

2026-09-03自動排程接續composite_zscore_v1.py「下一輪」。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from composite_zscore_v1 import BASELINE_FACTORS
from factor_ic import (
    BASE_ALPHA, SAMPLE_SEED, SAMPLE_SIZE, START_DATE, SNAPSHOT_START,
    _cross_section, sample_universe_ids, load_sample_with_factors, build_snapshots,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

N_DRAWS = 300
DRAW_K = 3  # 跟baseline因子數量一致
CONTROL_SEED = 20260903
WEIGHT_LOW, WEIGHT_HIGH = -1.0, 1.0

# 完整清單，逐一對照 factors.py::prepare_factors() 原始碼（行518-769）確認，
# 是該函式實際會產出的全部f_*欄位，非部分抽樣，也非憑印象列舉。
FACTOR_POOL = [
    "f_rel_strength", "f_ma_breakout", "f_foreign_streak", "f_inst_flow",
    "f_inst_streak_days", "f_rev_accel", "f_eps_growth", "f_eps_surprise",
    "f_revenue_surprise", "f_low_vol", "f_short_reversal_1m", "f_amihud_illiq",
    "f_idio_vol", "f_bab", "f_residual_momentum", "f_52w_high_prox",
    "f_short_term_reversal_1w", "f_quality_roe_stability", "f_asset_growth",
    "f_accruals", "f_gross_margin_stability", "f_gross_profitability",
    "f_value_pb", "f_value_pe", "f_dividend_yield_ttm",
]

RANDOM_COMPOSITE_COL = "_f_composite_random_draw"
BASELINE_COMPOSITE_COL = "f_composite_zscore_v1"


def weighted_zscore_composite(data: dict[str, pd.DataFrame], weights: dict[str, float]) -> None:
    """跟composite_zscore_v1.add_composite_zscore同一套邏輯，差別只是加權（可為
    負權重）而非等權1.0加總；任一組成因子當天缺值仍讓該股當天複合分數整體設為
    NaN（同一份「不用0填補去偷偷降低缺值股票懲罰」原則，不因為是隨機對照組就
    放寬標準）。"""
    factors = list(weights.keys())
    frames = []
    for sid, d in data.items():
        cols = [c for c in factors if c in d.columns]
        sub = d[["date"] + cols].copy()
        sub["stock_id"] = sid
        frames.append(sub)
    panel = pd.concat(frames, ignore_index=True)

    def wsum(g: pd.DataFrame) -> pd.Series:
        z = pd.DataFrame(index=g.index)
        for f in factors:
            vals = g[f]
            std = vals.std(skipna=True)
            if std and std > 0:
                z[f] = ((vals - vals.mean(skipna=True)) / std) * weights[f]
            else:
                z[f] = np.nan
        return z.sum(axis=1, skipna=False)

    panel[RANDOM_COMPOSITE_COL] = panel.groupby("date", group_keys=False).apply(wsum)

    for sid, d in data.items():
        if RANDOM_COMPOSITE_COL in d.columns:
            # 上一次呼叫（baseline補算或前一個draw）留下的暫存欄位；不先丟掉的話
            # merge時左右兩側同名欄位會被pandas加上_x/_y後綴，導致下面直接用
            # RANDOM_COMPOSITE_COL取值時KeyError（2026-09-03排程接續時實際踩到
            # 這個bug，修好後才能繼續跑300draws，見MARATHON_LOG.md對應條目）。
            d.drop(columns=[RANDOM_COMPOSITE_COL], inplace=True)
        merged = d.merge(
            panel.loc[panel["stock_id"] == sid, ["date", RANDOM_COMPOSITE_COL]],
            on="date", how="left",
        )
        d[RANDOM_COMPOSITE_COL] = merged[RANDOM_COMPOSITE_COL].to_numpy()


def mean_ic_train_val(factor_col: str, data: dict[str, pd.DataFrame], snapshots: list[tuple[str, str]]) -> tuple[float, float, int, int]:
    train_ics, val_ics = [], []
    for as_of, fwd in snapshots:
        ids, fv, ret = _cross_section(factor_col, (as_of, fwd), data)
        if len(fv) < 10:
            continue
        ic, _ = spearmanr(fv, ret)
        if np.isnan(ic):
            continue
        if as_of <= holdout.TRAIN_END:
            train_ics.append(ic)
        elif as_of <= holdout.VAL_END:
            val_ics.append(ic)
    train_mean = float(np.mean(train_ics)) if train_ics else float("nan")
    val_mean = float(np.mean(val_ics)) if val_ics else float("nan")
    return train_mean, val_mean, len(train_ics), len(val_ics)


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print("=== HYPOTHESIS_QUEUE.md#27 composite_zscore_v1 隨機因子組合控制 "
          f"(N_DRAWS={N_DRAWS}, draw_k={DRAW_K}, pool_size={len(FACTOR_POOL)}) ===")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in composite_zscore_v1_random_control")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in composite_zscore_v1_random_control")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    # 確認baseline複合欄位已存在（前一輪composite_zscore_v1.main()跑過的話會有，
    # 若這次是獨立重跑則自己補算，equal weight=1.0跟baseline定義完全一致）
    for sid, d in data.items():
        if BASELINE_COMPOSITE_COL not in d.columns:
            weighted_zscore_composite({sid: d}, {f: 1.0 for f in BASELINE_FACTORS})
            d[BASELINE_COMPOSITE_COL] = d[RANDOM_COMPOSITE_COL]

    baseline_train_ic, baseline_val_ic, n_train, n_val = mean_ic_train_val(BASELINE_COMPOSITE_COL, data, snapshots)
    print(f"\n--- Baseline複合 (等權GP+value_pb+revenue_surprise) ---")
    print(f"  TRAIN mean_ic={baseline_train_ic:+.4f} (n={n_train})  VAL mean_ic={baseline_val_ic:+.4f} (n={n_val})")

    rng = random.Random(CONTROL_SEED)
    draw_records = []
    print(f"\n--- {N_DRAWS} 次隨機因子組合抽樣 (Uniform({WEIGHT_LOW},{WEIGHT_HIGH}) 權重) ---")
    for i in range(N_DRAWS):
        chosen = rng.sample(FACTOR_POOL, DRAW_K)
        weights = {f: rng.uniform(WEIGHT_LOW, WEIGHT_HIGH) for f in chosen}
        weighted_zscore_composite(data, weights)
        train_ic, val_ic, _, _ = mean_ic_train_val(RANDOM_COMPOSITE_COL, data, snapshots)
        draw_records.append({
            "draw": i, "factors": "+".join(chosen),
            "weights": ",".join(f"{weights[f]:+.3f}" for f in chosen),
            "train_ic": train_ic, "val_ic": val_ic,
        })
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{N_DRAWS} draws done")

    draws_df = pd.DataFrame(draw_records)
    val_ics_all = draws_df["val_ic"].dropna().to_numpy()

    percentile = 100.0 * float(np.mean(np.abs(baseline_val_ic) > np.abs(val_ics_all))) if len(val_ics_all) and not np.isnan(baseline_val_ic) else float("nan")
    required_percentile = 100.0 * (1 - BASE_ALPHA / 1)  # bonferroni_n=1, standalone

    print(f"\n--- 結果 ---")
    print(f"  有效draws (val_ic非NaN): {len(val_ics_all)}/{N_DRAWS}")
    print(f"  隨機組合 val_ic 分布: median={np.median(val_ics_all):+.4f} "
          f"p10={np.percentile(val_ics_all,10):+.4f} p90={np.percentile(val_ics_all,90):+.4f} "
          f"max_abs={np.max(np.abs(val_ics_all)):+.4f}")
    print(f"  baseline VAL mean_ic={baseline_val_ic:+.4f}")
    print(f"  percentile (baseline贏過隨機組合的比例): {percentile:.1f} (need >={required_percentile:.1f})")
    passes = (not np.isnan(percentile)) and percentile >= required_percentile
    print(f"  隨機因子組合控制 PASSES: {passes}")

    Path("data").mkdir(exist_ok=True)
    draws_df.to_csv("data/composite_zscore_v1_random_control.csv", index=False)
    print("\n已存 data/composite_zscore_v1_random_control.csv (gitignored)")

    return {
        "baseline_train_ic": baseline_train_ic, "baseline_val_ic": baseline_val_ic,
        "percentile": percentile, "required_percentile": required_percentile, "passes": passes,
        "n_draws": len(val_ics_all),
    }


if __name__ == "__main__":
    main()
