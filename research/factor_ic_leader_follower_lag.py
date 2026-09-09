"""`HYPOTHESIS_QUEUE.md` #65 產業龍頭股跨期領先-落後動能
(Intra-Industry Leader-Follower Lead-Lag Momentum) 第1關 cheap IC gate。

經濟理由：Hou (2007, *Review of Financial Studies*)——同產業內大型/高關注度
股票（龍頭）的報酬會領先預測同產業小型/低關注度股票（族群成員）未來報酬，
機制是資訊擴散速度不對稱（有限注意力導致小型股對產業層級消息反應遲緩），
不是估值/品質/籌碼特徵。跟`#11`（產業內相對強度sector-neutral relative
strength，已FAIL）的關鍵差異：那是**同一時間點的橫斷面排序**（無跨期
lag結構），這裡是**跨期**（t期龍頭報酬預測t+1期族群成員報酬），有明確
因果時序方向。完整經濟理由/排除清單/已知限制見`HYPOTHESIS_QUEUE.md`#65。

**具體設計（事前綁定，未看任何數字前寫死）**：
- 龍頭認定：每個產業分組內，trailing 20交易日平均成交金額（`Trading_money`）
  最大者為龍頭，其餘為族群成員。
- 訊號：龍頭在t期（trailing 5交易日，即`ret5`欄位在as_of當天的值）的報酬。
  這個訊號**廣播給同組每一個族群成員**（不含龍頭自己）。
- 預測目標：族群成員在t+1期（次5交易日，as_of到fwd的報酬）的橫斷面報酬。
- 事前綁定方向：**正相關**（龍頭領漲，族群跟漲；龍頭領跌，族群跟跌）——
  不因結果換方向（比照`#42`/`#43`鐵律）。
- MIN_GROUP_SIZE=5：沿用假設定義本身寫的「產業成員數<5則整個產業排除」
  門檻，運作在**這次抽樣的300檔樣本**內部分組（跟`#11`同樣的簡化：可能
  誤把樣本內恰好抽到的最大成交金額股當「龍頭」，而非該產業全市場真正龍頭
  ——這是cheap gate sanity目的下可接受的簡化，deep_dive才需要處理）。

**資料來源，零新增API呼叫**：完全複用`factor_ic.py::load_sample_with_factors()`
既有快取（300檔樣本，跟其餘20幾個因子共用同一份快取）。`Trading_money`欄位
在`adjusted_price_series()`兩條路徑（yfinance/FinMind）皆已存在——yfinance
路徑由`yf_price_client.py`用`close*volume`合成（見該檔案docstring），FinMind
路徑是原始欄位——所以這裡只需要在既有`d`（每檔股票的DataFrame）上多加兩欄
（`ret5`、`turnover_avg20`），不觸發任何新的網路請求。

**跟`factor_ic.py`標準框架的差異**：標準框架每個橫斷面快照用固定20交易日
horizon（`build_snapshots()`預設`horizon=FORWARD_HORIZON=20`），這裡改用
`horizon=LAG_HORIZON=5`（假設定義要求trailing 5天訊號+次5天預測目標），
直接把既有`build_snapshots(calendar, start, end, horizon=5)`參數化重用，
不修改`factor_ic.py`本身。cross-section的建構邏輯改成「每組廣播龍頭訊號給
族群成員」而非「每股獨立因子值排序」，其餘（train/val切分、隨機洗牌null、
Bonferroni門檻、same_sign判準）完全比照`factor_ic_sector_neutral_rel_strength.py`
（#11）同一套框架。

2026-09-09 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#65第1關起跑。
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

TURNOVER_WINDOW = 20  # trailing days for leader identification (mean Trading_money)
LAG_HORIZON = 5  # trading days, both for leader's trailing signal window and follower's forward window
MIN_GROUP_SIZE = 5  # per #65 hypothesis definition: "產業成員數<5則整個產業排除"
EXCLUDE_INDUSTRY_KEYWORDS = ("ETF", "基金")


def build_industry_map() -> dict:
    u = build_universe()
    u = u.dropna(subset=["industry_category"])
    return dict(zip(u["stock_id"], u["industry_category"]))


def _prep_leader_columns(data: dict[str, pd.DataFrame]) -> None:
    """In-place: add ret5 (trailing LAG_HORIZON-day return) and turnover_avg20
    (trailing TURNOVER_WINDOW-day mean Trading_money) to every stock's df.
    Zero new API calls -- Trading_money is already present (see module docstring).
    """
    for d in data.values():
        d["ret5"] = d["adj_close"] / d["adj_close"].shift(LAG_HORIZON) - 1
        d["turnover_avg20"] = d["Trading_money"].rolling(TURNOVER_WINDOW, min_periods=TURNOVER_WINDOW).mean()


def leader_follower_cross_section(
    snapshot: tuple[str, str], data: dict[str, pd.DataFrame], ind_map: dict
) -> tuple[np.ndarray, np.ndarray, int, list[int]]:
    """回傳(龍頭訊號廣播值, 族群成員前瞻報酬, 可用組數, 各組成員數列表)。"""
    as_of, fwd = snapshot
    groups = defaultdict(list)  # ind -> list of (sid, turnover_asof, leader_ret5_asof, follower_fwd_ret)
    for sid, d in data.items():
        ind = ind_map.get(sid)
        if ind is None or any(k in ind for k in EXCLUDE_INDUSTRY_KEYWORDS):
            continue
        idx = d.index[d["date"] == as_of]
        fidx = d.index[d["date"] == fwd]
        if len(idx) == 0 or len(fidx) == 0:
            continue
        idx0 = idx[0]
        turnover = d.loc[idx0, "turnover_avg20"]
        ret5 = d.loc[idx0, "ret5"]
        p0 = d.loc[idx0, "adj_close"]
        p1 = d.loc[fidx[0], "adj_close"]
        if pd.isna(turnover) or pd.isna(ret5) or pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        groups[ind].append((sid, float(turnover), float(ret5), float(p1 / p0 - 1)))

    leader_signals, follower_returns, group_sizes = [], [], []
    n_groups_used = 0
    for members in groups.values():
        if len(members) < MIN_GROUP_SIZE:
            continue
        leader = max(members, key=lambda m: m[1])  # 產業內(樣本內)trailing 20日均成交金額最大者
        followers = [m for m in members if m[0] != leader[0]]
        if not followers:
            continue
        n_groups_used += 1
        group_sizes.append(len(members))
        for _sid, _turnover, _ret5, fwd_ret in followers:
            leader_signals.append(leader[2])  # 龍頭自己的trailing ret5，廣播給每個族群成員
            follower_returns.append(fwd_ret)
    return np.array(leader_signals), np.array(follower_returns), n_groups_used, group_sizes


def evaluate_leader_follower_lag(
    data: dict, snapshots: list[tuple[str, str]], ind_map: dict, bonferroni_n: int = 1
):
    train_ics, val_ics = [], []
    cross_sections = []
    diag_groups_used, diag_group_sizes, diag_n_followers = [], [], []

    for as_of, fwd in snapshots:
        sig, ret, n_groups_used, gsizes = leader_follower_cross_section((as_of, fwd), data, ind_map)
        diag_groups_used.append(n_groups_used)
        diag_group_sizes.extend(gsizes)
        diag_n_followers.append(len(sig))
        if len(sig) < 10:  # 同factor_ic.py的最低橫斷面樣本數門檻
            continue
        ic, _ = spearmanr(sig, ret)
        if np.isnan(ic):
            continue
        if as_of <= holdout.TRAIN_END:
            train_ics.append(ic)
        elif as_of <= holdout.VAL_END:
            val_ics.append(ic)
            cross_sections.append((sig, ret))

    train_mean = float(np.mean(train_ics)) if train_ics else float("nan")
    train_ir = float(np.mean(train_ics) / np.std(train_ics)) if len(train_ics) > 1 and np.std(train_ics) > 0 else float("nan")
    val_mean = float(np.mean(val_ics)) if val_ics else float("nan")
    val_ir = float(np.mean(val_ics) / np.std(val_ics)) if len(val_ics) > 1 and np.std(val_ics) > 0 else float("nan")
    val_hit_rate = float(np.mean([np.sign(x) == np.sign(val_mean) for x in val_ics])) if val_ics and val_mean != 0 else float("nan")

    rng = random.Random(SHUFFLE_SEED)
    null_means = []
    for _ in range(N_SHUFFLES):
        shuffled_ics = []
        for sig, ret in cross_sections:
            perm = sig.copy()
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
    # 事前綁定方向：正相關（龍頭領漲，族群跟漲）——不因結果換方向。
    if np.isnan(val_mean) or val_mean <= 0 or abs(val_mean) < 0.02:
        passes = False
        reasons.append(f"val_mean_ic not positive/large enough per pre-registered direction ({val_mean:.4f})")
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
        "median_followers_per_snapshot": float(np.median(diag_n_followers)) if diag_n_followers else float("nan"),
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
    label = ("產業龍頭股跨期領先-落後動能 Intra-Industry Leader-Follower Lead-Lag "
              "(HYPOTHESIS_QUEUE.md#65新假設, standalone bonferroni_n=1)")
    print(f"\n=== {label} ===")
    print(f"Sample: {len(sample_ids)} names, snapshot_start={SNAPSHOT_START}, "
          f"lag_horizon={LAG_HORIZON}, MIN_GROUP_SIZE={MIN_GROUP_SIZE}")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in factor_ic_leader_follower_lag")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    _prep_leader_columns(data)

    ind_map = build_industry_map()
    n_with_industry = sum(1 for sid in data if ind_map.get(sid) and not any(
        k in ind_map[sid] for k in EXCLUDE_INDUSTRY_KEYWORDS
    ))
    print(f"  {n_with_industry}/{len(data)} names have a non-ETF industry_category")

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END, horizon=LAG_HORIZON)
    print(f"  {len(snapshots)} non-overlapping {LAG_HORIZON}-trading-day snapshots, "
          f"{SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_leader_follower_lag(data, snapshots, ind_map, bonferroni_n=1)
    print(f"\ndiagnostics: {r['diag']}")
    print(f"  train: mean_ic={r['train_mean_ic']:+.4f} IR={r['train_ic_ir']:+.3f} (n={r['n_dates_train']} dates)")
    print(f"  val:   mean_ic={r['val_mean_ic']:+.4f} IR={r['val_ic_ir']:+.3f} hit_rate={r['val_hit_rate']:.2f} (n={r['n_dates_val']} dates)")
    print(f"  null percentile: {r['null_percentile']:.1f} (need >={r['required_percentile']:.1f})  same_sign: {r['same_sign']}")
    print(f"  PASSES: {r['passes']}" + (f"  reasons: {r['reasons']}" if not r['passes'] else ""))
    return r


if __name__ == "__main__":
    main()
