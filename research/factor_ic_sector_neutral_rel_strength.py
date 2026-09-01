"""`HYPOTHESIS_QUEUE.md` #11 產業內相對強度 Sector-Neutral Relative Strength
第1關 cheap IC gate（sanity）。

經濟理由：全市場排序的`f_rel_strength`（60日個股報酬-60日大盤報酬，
factors.py既有因子）天然帶有產業輪動的beta——整個產業一起漲跌時，排序
前段班可能只是剛好都在同一個熱門產業，不是真正的個股選股能力。這裡在每個
橫斷面快照裡、限制在同產業分類內比較（減去當期該產業內平均值＝「產業中性化
相對強度」），只留下「個股相對同業的相對強弱」這個更乾淨的訊號。跟#9殘差
動量是互補的兩種中性化角度（#9剝離跨時間的系統性因子曝險，這條剝離橫截面
的產業曝險）。見`HYPOTHESIS_QUEUE.md`#11完整說明。

**為什麼不是加進`factors.py::prepare_factors()`的單股欄位**：這個衍生值
需要「同一天、同產業的其他股票」才能算出（demean），不是可以逐股獨立計算
的時間序列欄位——跟其餘30幾個既有因子（每個都只需要該股自己的價量/財報
歷史）性質不同。所以這裡沿用`factor_ic.py`的判準常數（BASE_ALPHA/N_SHUFFLES/
SHUFFLE_SEED/FORWARD_HORIZON）跟`load_sample_with_factors()`（借用其中已經
算好的原始`f_rel_strength`），但重寫cross-section建構邏輯（多一層產業分組+
demean），不改`factor_ic.py`本身（沿用`dividend_yield_portfolio_v1.py`
「只改自己、不動共用模組」的教訓）。

**產業分類來源**：`universe.py::universe()`的`industry_category`欄位（直接
來自FinMind TaiwanStockInfo，跟`build_company_info.py`同一個原始資料源，
但這裡不套用該腳本的「同日期多分類→留None」歧義處理，因為`universe()`
本身已經是`drop_duplicates(subset="stock_id", keep="last")`只留一筆——
這是比`company_info.json`更粗略的簡化，可能吃到一些歧義代碼的其中一種
分類，但對第1關cheap gate的sanity目的（判斷這個機制方向上有沒有訊號）
足夠，不影響判準邏輯本身；deep_dive階段若要正式構造策略，才需要處理
歧義問題)。ETF/基金類（`industry_category`含"ETF"或"基金"字樣）排除，
因為這條假設測的是「個股」相對同業的相對強弱，不是基金分類。

**MIN_GROUP_SIZE=3**：產業內成員數<3的快照該產業直接濾掉（demean一組
只有1~2檔沒有排序意義）——這是這個機制天然的樣本限制，會在輸出診斷
（每快照平均可用組數/組內平均成員數）裡誠實揭露，不是隱藏掉。

2026-09-02 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#11第1關起跑。
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from factor_ic import (
    BASE_ALPHA,
    N_SHUFFLES,
    SAMPLE_SEED,
    SAMPLE_SIZE,
    SHUFFLE_SEED,
    SNAPSHOT_START,
    START_DATE,
    build_snapshots,
    load_sample_with_factors,
    sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe
from validation import holdout

FACTOR_COL = "f_rel_strength"
MIN_GROUP_SIZE = 3
EXCLUDE_INDUSTRY_KEYWORDS = ("ETF", "基金")


def build_industry_map() -> dict:
    u = build_universe()
    u = u.dropna(subset=["industry_category"])
    return dict(zip(u["stock_id"], u["industry_category"]))


def sector_neutral_cross_section(snapshot, data, ind_map) -> tuple[list[str], np.ndarray, np.ndarray, int, list[int]]:
    """回傳(ids, demeaned相對強度, 前瞻報酬, 可用組數, 各組成員數列表)。"""
    as_of, fwd = snapshot
    rows = []
    for sid, d in data.items():
        ind = ind_map.get(sid)
        if ind is None or any(k in ind for k in EXCLUDE_INDUSTRY_KEYWORDS):
            continue
        idx = d.index[d["date"] == as_of]
        fidx = d.index[d["date"] == fwd]
        if len(idx) == 0 or len(fidx) == 0:
            continue
        fv = d.loc[idx[0], FACTOR_COL]
        p0 = d.loc[idx[0], "adj_close"]
        p1 = d.loc[fidx[0], "adj_close"]
        if pd.isna(fv) or pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        rows.append((sid, ind, float(fv), float(p1 / p0 - 1)))

    groups = defaultdict(list)
    for sid, ind, fv, ret in rows:
        groups[ind].append((sid, fv, ret))

    ids, neutral_vals, returns, group_sizes = [], [], [], []
    for ind, members in groups.items():
        if len(members) < MIN_GROUP_SIZE:
            continue
        group_mean = sum(m[1] for m in members) / len(members)
        group_sizes.append(len(members))
        for sid, fv, ret in members:
            ids.append(sid)
            neutral_vals.append(fv - group_mean)
            returns.append(ret)
    return ids, np.array(neutral_vals), np.array(returns), len(groups), group_sizes


def evaluate_sector_neutral(data: dict, snapshots: list[tuple[str, str]], ind_map: dict, bonferroni_n: int = 1):
    train_ics, val_ics = [], []
    cross_sections = []
    diag_groups_used, diag_group_sizes, diag_n_names = [], [], []

    for as_of, fwd in snapshots:
        ids, nv, ret, n_groups_seen, gsizes = sector_neutral_cross_section((as_of, fwd), data, ind_map)
        diag_groups_used.append(len(gsizes))
        diag_group_sizes.extend(gsizes)
        diag_n_names.append(len(ids))
        if len(nv) < 10:  # 同factor_ic.py的最低橫斷面樣本數門檻
            continue
        ic, _ = spearmanr(nv, ret)
        if np.isnan(ic):
            continue
        if as_of <= holdout.TRAIN_END:
            train_ics.append(ic)
        elif as_of <= holdout.VAL_END:
            val_ics.append(ic)
            cross_sections.append((nv, ret))

    train_mean = float(np.mean(train_ics)) if train_ics else float("nan")
    train_ir = float(np.mean(train_ics) / np.std(train_ics)) if len(train_ics) > 1 and np.std(train_ics) > 0 else float("nan")
    val_mean = float(np.mean(val_ics)) if val_ics else float("nan")
    val_ir = float(np.mean(val_ics) / np.std(val_ics)) if len(val_ics) > 1 and np.std(val_ics) > 0 else float("nan")
    val_hit_rate = float(np.mean([np.sign(x) == np.sign(val_mean) for x in val_ics])) if val_ics and val_mean != 0 else float("nan")

    rng = random.Random(SHUFFLE_SEED)
    null_means = []
    for _ in range(N_SHUFFLES):
        shuffled_ics = []
        for nv, ret in cross_sections:
            perm = nv.copy()
            idx = list(range(len(perm)))
            rng.shuffle(idx)
            perm = perm[idx]
            ic, _ = spearmanr(perm, ret)
            if not np.isnan(ic):
                shuffled_ics.append(ic)
        if shuffled_ics:
            null_means.append(np.mean(shuffled_ics))

    if null_means and not np.isnan(val_mean):
        null_percentile = 100.0 * np.mean([abs(val_mean) > abs(m) for m in null_means])
    else:
        null_percentile = float("nan")

    same_sign = (not np.isnan(train_mean) and not np.isnan(val_mean)
                 and np.sign(train_mean) == np.sign(val_mean) and train_mean != 0)
    required_percentile = 100.0 * (1 - BASE_ALPHA / max(bonferroni_n, 1))

    reasons = []
    passes = True
    if np.isnan(val_mean) or abs(val_mean) < 0.02:
        passes = False
        reasons.append(f"val_mean_ic too small or undefined ({val_mean:.4f})")
    if not same_sign:
        passes = False
        reasons.append(f"train/val sign mismatch (train={train_mean:.4f}, val={val_mean:.4f})")
    if np.isnan(null_percentile) or null_percentile < required_percentile:
        passes = False
        reasons.append(
            f"not distinguishable from random-shuffle null at the Bonferroni-corrected bar "
            f"(percentile={null_percentile:.1f}, required>={required_percentile:.1f} for n={bonferroni_n})"
        )

    diag = {
        "median_groups_used_per_snapshot": float(np.median(diag_groups_used)) if diag_groups_used else float("nan"),
        "median_group_size": float(np.median(diag_group_sizes)) if diag_group_sizes else float("nan"),
        "median_names_per_snapshot": float(np.median(diag_n_names)) if diag_n_names else float("nan"),
        "n_snapshots_total": len(snapshots),
        "n_snapshots_usable": len(train_ics) + len(val_ics),
    }

    return {
        "train_mean_ic": train_mean, "train_ic_ir": train_ir,
        "val_mean_ic": val_mean, "val_ic_ir": val_ir, "val_hit_rate": val_hit_rate,
        "n_dates_train": len(train_ics), "n_dates_val": len(val_ics),
        "null_percentile": null_percentile, "required_percentile": required_percentile,
        "same_sign": same_sign, "passes": passes, "reasons": reasons, "diag": diag,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    label = ("產業內相對強度 Sector-Neutral Relative Strength "
              "(f_rel_strength去產業內均值, HYPOTHESIS_QUEUE.md#11新假設, "
              "standalone bonferroni_n=1)")
    print(f"\n=== {label} ===")
    print(f"Sample: {len(sample_ids)} names, snapshot_start={SNAPSHOT_START}, "
          f"MIN_GROUP_SIZE={MIN_GROUP_SIZE}")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in factor_ic_sector_neutral_rel_strength")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    ind_map = build_industry_map()
    n_with_industry = sum(1 for sid in data if ind_map.get(sid) and not any(
        k in ind_map[sid] for k in EXCLUDE_INDUSTRY_KEYWORDS
    ))
    print(f"  {n_with_industry}/{len(data)} names have a non-ETF industry_category")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping 20-trading-day snapshots, "
          f"{SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_sector_neutral(data, snapshots, ind_map, bonferroni_n=1)
    print(f"\ndiagnostics: {r['diag']}")
    print(f"  train: mean_ic={r['train_mean_ic']:+.4f} IR={r['train_ic_ir']:+.3f} (n={r['n_dates_train']} dates)")
    print(f"  val:   mean_ic={r['val_mean_ic']:+.4f} IR={r['val_ic_ir']:+.3f} hit_rate={r['val_hit_rate']:.2f} (n={r['n_dates_val']} dates)")
    print(f"  null percentile: {r['null_percentile']:.1f} (need >={r['required_percentile']:.1f})  same_sign: {r['same_sign']}")
    print(f"  PASSES: {r['passes']}" + (f"  reasons: {r['reasons']}" if not r['passes'] else ""))
    return r


if __name__ == "__main__":
    main()
