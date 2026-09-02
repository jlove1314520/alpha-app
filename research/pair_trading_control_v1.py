"""`HYPOTHESIS_QUEUE.md` #16 同產業配對交易 / 統計套利 第2關 隨機控制組（N=100）。

**這輪要證明什麼**：`pair_trading_sanity.py`（第1關）已經確認方向性sanity過
關（相關係數篩選後的12條配對，事件層級median converged_frac=0.855、mean|z|
reduction=+0.820，方向不是反的），但這不足以下判定——`CONSTITUTION.md`第2節
明講「任何新機制若本質是...③縮小候選池...幾乎必然靠運氣在樣本內通過、被
隨機控制組拆穿」，這條假設的核心機制正是「用相關係數把89個同產業配對縮小到
12個」，屬於這個偽影家族的高風險型態——**必須證明相關係數篩選本身有加值，
不是任意從同產業配對池裡挑12個都會有類似的均值回歸表現**（畢竟rolling
z-score本身的統計定義，就會讓幾乎任何兩條序列的價差在極端值後有一定機率
回落到均值附近，這不代表兩檔股票真的存在經濟上的均值回歸關係）。

**方法**：真實組＝相關係數>=0.70篩選後的12條配對，把它們個別的zscore事件
（`pair_trading_sanity.raw_entries()`）全部pool成一份事件池，算pooled
converged_frac跟pooled mean|z| reduction。控制組＝「同樣動作（一樣的產業內
配對母體、一樣的zscore規則、一樣抽12條），只是不用相關係數篩選、改成隨機
從89條可配對的同產業配對裡抽12條」，抽N_DRAWS=100次（`HYPOTHESIS_QUEUE.md`
GATE_SEQUENCE第2關「隨機控制組(>=100draws)」的下限），每次一樣pool成事件池
算同兩個指標，累積成null分布，計算真實組指標在null分布裡的百分位
（percentile=100×(null分布小於真實值的比例)，跟`deep_dive_fut_basis_carry.py`
既有percentile計算方式一致）。

2026-09-02 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，接續同一輪#16第1關
sanity之後的第2關。
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from pair_trading_sanity import (
    CORR_THRESHOLD,
    MIN_OVERLAP_DAYS,
    build_industry_groups,
    load_prices,
    pair_diagnostics,
    raw_entries,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids

N_DRAWS = 100
CONTROL_SEED = 20260902  # 沿用vol_targeting_v1.py同一天期日期當seed的慣例


def pooled_metrics(entries: list[dict]) -> dict:
    if not entries:
        return {"n_entries": 0, "converged_frac": float("nan"), "mean_abs_reduction": float("nan")}
    converged = [abs(e["exit_z"]) < abs(e["entry_z"]) for e in entries]
    reductions = [abs(e["entry_z"]) - abs(e["exit_z"]) for e in entries]
    return {
        "n_entries": len(entries),
        "converged_frac": float(np.mean(converged)),
        "mean_abs_reduction": float(np.mean(reductions)),
    }


def main():
    label = "同產業配對交易 Pair Trading (HYPOTHESIS_QUEUE.md#16, 第2關隨機控制組N=100)"
    print(f"\n=== {label} ===")

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    groups = build_industry_groups(list(prices.keys()))

    all_pairs = []
    for ind, ids in groups.items():
        for a, b in itertools.combinations(sorted(ids), 2):
            all_pairs.append((a, b))

    # 一次算好所有可配對的診斷資訊(相關係數+對齊後的log價格序列)並快取，
    # 之後每次隨機抽樣只需查表，避免N=100次draw重複算價格對齊/相關係數。
    pair_cache: dict[tuple[str, str], dict] = {}
    for a, b in all_pairs:
        diag = pair_diagnostics(prices[a], prices[b])
        if diag is not None:
            pair_cache[(a, b)] = diag

    pool_all = list(pair_cache.keys())
    real_pairs = [k for k, d in pair_cache.items() if d["log_price_corr"] >= CORR_THRESHOLD]
    n_real = len(real_pairs)
    print(f"  candidate pool: {len(pool_all)} pairable same-industry pairs, "
          f"{n_real} pass correlation filter (>= {CORR_THRESHOLD})")

    if n_real == 0 or len(pool_all) < n_real:
        print("  快殺判定：無真實配對或母體不足以支撐同規模隨機抽樣，本輪無法計算percentile。")
        return {"status": "insufficient_pairs"}

    # 每條配對的zscore事件只跟該配對本身有關(跟被抽到哪個draw無關)，記憶化避免重算。
    entries_cache: dict[tuple[str, str], list[dict]] = {}

    def entries_for(key: tuple[str, str]) -> list[dict]:
        if key not in entries_cache:
            d = pair_cache[key]
            entries_cache[key] = raw_entries(d["log_a"], d["log_b"])
        return entries_cache[key]

    def pooled_for(pair_keys: list[tuple[str, str]]) -> dict:
        entries: list[dict] = []
        for k in pair_keys:
            entries.extend(entries_for(k))
        return pooled_metrics(entries)

    real_metrics = pooled_for(real_pairs)
    print(f"  real (corr-filtered) pooled: n_entries={real_metrics['n_entries']}, "
          f"converged_frac={real_metrics['converged_frac']:.4f}, "
          f"mean_abs_reduction={real_metrics['mean_abs_reduction']:+.4f}")

    rng = np.random.default_rng(CONTROL_SEED)
    draws = []
    for _ in range(N_DRAWS):
        idx = rng.choice(len(pool_all), size=n_real, replace=False)
        sampled = [pool_all[i] for i in idx]
        draws.append(pooled_for(sampled))

    converged_null = np.array([d["converged_frac"] for d in draws])
    reduction_null = np.array([d["mean_abs_reduction"] for d in draws])

    pctl_converged = float((converged_null < real_metrics["converged_frac"]).mean() * 100.0)
    pctl_reduction = float((reduction_null < real_metrics["mean_abs_reduction"]).mean() * 100.0)

    print(f"\n  null (random {n_real}-pair draws, N={N_DRAWS}, seed={CONTROL_SEED}):")
    print(f"    converged_frac: median={np.median(converged_null):.4f}, "
          f"p10={np.percentile(converged_null, 10):.4f}, p90={np.percentile(converged_null, 90):.4f}")
    print(f"    mean_abs_reduction: median={np.median(reduction_null):+.4f}, "
          f"p10={np.percentile(reduction_null, 10):+.4f}, p90={np.percentile(reduction_null, 90):+.4f}")
    print(f"\n  REAL vs NULL percentile: converged_frac={pctl_converged:.1f}, "
          f"mean_abs_reduction={pctl_reduction:.1f}  (門檻90.0)")

    df = pd.DataFrame(draws)
    out_path = Path(__file__).parent / "data" / "pair_trading_control_v1_draws.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\n  null draws written to {out_path}")

    return {
        "n_real_pairs": n_real,
        "n_pool_pairs": len(pool_all),
        "real_converged_frac": real_metrics["converged_frac"],
        "real_mean_abs_reduction": real_metrics["mean_abs_reduction"],
        "pctl_converged_frac": pctl_converged,
        "pctl_mean_abs_reduction": pctl_reduction,
    }


if __name__ == "__main__":
    main()
