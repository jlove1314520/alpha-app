"""`HYPOTHESIS_QUEUE.md` #16 同產業配對交易 / 統計套利（Pair Trading /
Statistical Arbitrage）第1關 sanity。

**這輪只做sanity，不做判定**：依`HYPOTHESIS_QUEUE_PROTOCOL.md`「這一輪先把
地基做好」原則——確認能篩出合理數量的候選配對、價差z-score計算邏輯方向
正確（不是反的）、非結構性no-op（z-score不是常數/零），不強求本輪做完
GATE_SEQUENCE後續關卡（隨機控制組/成本敏感度等留給下一輪）。

**方法**：`universe.py`同產業分類（沿用#11`factor_ic_sector_neutral_rel_
strength.py`同一個分類來源，排除ETF/基金）內兩兩配對。對每一對，取兩檔
`adj_close`（`adjust.py::adjusted_price_series`，已經holdout-safe capped
在VAL_END）對齊日期後的對數價格差（log spread），用簡單相關係數先篩掉
「兩檔本來就不相關卻被歸在同產業」的雜訊配對（`HYPOTHESIS_QUEUE.md`#16
條目原文「先用簡單相關係數/價差穩定度篩配對候選，門檻要夠嚴格」），對
通過篩選的配對用滾動窗口（`Z_WINDOW`=120交易日）算log spread的z-score，
統計|z|超過進場閾值（`ENTRY_Z`=2.0）的事件數，並檢查進場後
`CONVERGE_HORIZON`交易日內|z|是否確實傾向縮小（均值回歸方向對不對，不是
反的）——這是這條假設「賭價差收斂」機制最基本的方向性sanity檢查，不是
完整回測。

**執行摩擦誠實揭露**：這裡只用理論多空對稱（不管借券可不可行）測訊號本身
存不存在，`HYPOTHESIS_QUEUE.md`#16條目已載明台股放空受限這個摩擦要留到
portfolio層（第4關以後）才計入。

2026-09-02 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#16第1關
sanity起跑。
"""
from __future__ import annotations

import itertools
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from universe import universe as build_universe
from validation import holdout

EXCLUDE_INDUSTRY_KEYWORDS = ("ETF", "基金")
MIN_OVERLAP_DAYS = 500  # ~2年交易日，滾動z-score窗口(120)+進場後追蹤(20)都要有餘裕
CORR_THRESHOLD = 0.70  # 簡單相關係數篩選門檻——不是最終判準，只是排除明顯不相關的湊對
Z_WINDOW = 120
ENTRY_Z = 2.0
CONVERGE_HORIZON = 20  # 交易日，跟本專案其餘因子/事件研究的forward horizon一致


def build_industry_groups(sample_ids: list[str]) -> dict[str, list[str]]:
    u = build_universe()
    u = u[u["stock_id"].isin(sample_ids)].dropna(subset=["industry_category"])
    groups: dict[str, list[str]] = defaultdict(list)
    for _, row in u.iterrows():
        ind = row["industry_category"]
        if any(k in ind for k in EXCLUDE_INDUSTRY_KEYWORDS):
            continue
        groups[ind].append(row["stock_id"])
    return {ind: ids for ind, ids in groups.items() if len(ids) >= 2}


def load_prices(sample_ids: list[str]) -> dict[str, pd.Series]:
    """回傳 stock_id -> (date-indexed) adj_close Series，capped at VAL_END。"""
    out = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一套容錯
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < MIN_OVERLAP_DAYS:
            continue
        s = px.set_index("date")["adj_close"].dropna()
        s = s[s > 0]
        if len(s) >= MIN_OVERLAP_DAYS:
            out[sid] = s
    return out


def pair_diagnostics(px_a: pd.Series, px_b: pd.Series) -> dict | None:
    common = px_a.index.intersection(px_b.index)
    if len(common) < MIN_OVERLAP_DAYS:
        return None
    a = np.log(px_a.loc[common].sort_index())
    b = np.log(px_b.loc[common].sort_index())
    corr = float(np.corrcoef(a.values, b.values)[0, 1])
    if np.isnan(corr):
        return None
    return {"common_days": len(common), "log_price_corr": corr, "log_a": a, "log_b": b}


def zscore_events(log_a: pd.Series, log_b: pd.Series) -> dict:
    spread = (log_a - log_b).reset_index(drop=True)
    roll_mean = spread.rolling(Z_WINDOW).mean()
    roll_std = spread.rolling(Z_WINDOW).std()
    z = (spread - roll_mean) / roll_std

    entries = []
    n = len(z)
    i = Z_WINDOW
    while i < n:
        zi = z.iloc[i]
        if pd.notna(zi) and abs(zi) >= ENTRY_Z:
            j = min(i + CONVERGE_HORIZON, n - 1)
            if j > i and pd.notna(z.iloc[j]):
                entries.append({"entry_z": float(zi), "exit_z": float(z.iloc[j])})
            i += CONVERGE_HORIZON  # 進場後跳過追蹤窗口，避免同一次偏離重複計入多個事件
        else:
            i += 1

    return {
        "n_entries": len(entries),
        "z_std": float(z.dropna().std()) if z.dropna().shape[0] > 1 else float("nan"),
        "converged_frac": (
            float(np.mean([abs(e["exit_z"]) < abs(e["entry_z"]) for e in entries]))
            if entries else float("nan")
        ),
        "mean_abs_z_reduction": (
            float(np.mean([abs(e["entry_z"]) - abs(e["exit_z"]) for e in entries]))
            if entries else float("nan")
        ),
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    label = "同產業配對交易 Pair Trading / Statistical Arbitrage (HYPOTHESIS_QUEUE.md#16, 第1關sanity)"
    print(f"\n=== {label} ===")
    print(f"Sample: {len(sample_ids)} names, START_DATE={START_DATE}, VAL_END={holdout.VAL_END} (holdout-safe cap)")

    print("Loading prices (cached after first run)...")
    prices = load_prices(sample_ids)
    print(f"  {len(prices)}/{len(sample_ids)} usable names (>= {MIN_OVERLAP_DAYS} trading days)")

    groups = build_industry_groups(list(prices.keys()))
    n_groups = len(groups)
    group_sizes = [len(v) for v in groups.values()]
    print(f"  {n_groups} industry groups with >=2 usable members "
          f"(sizes: median={np.median(group_sizes) if group_sizes else float('nan')}, "
          f"max={max(group_sizes) if group_sizes else 0})")

    all_pairs = []
    for ind, ids in groups.items():
        for a, b in itertools.combinations(sorted(ids), 2):
            all_pairs.append((ind, a, b))
    print(f"  {len(all_pairs)} candidate pairs formed (before correlation filter)")

    pair_stats = []
    for ind, a, b in all_pairs:
        diag = pair_diagnostics(prices[a], prices[b])
        if diag is None:
            continue
        pair_stats.append({"industry": ind, "a": a, "b": b, **diag})

    corrs = [p["log_price_corr"] for p in pair_stats]
    print(f"\n  log-price correlation across all {len(pair_stats)} pairable pairs: "
          f"median={np.median(corrs):.3f}, p25={np.percentile(corrs, 25):.3f}, "
          f"p75={np.percentile(corrs, 75):.3f}" if corrs else "  no pairable pairs")

    passing = [p for p in pair_stats if p["log_price_corr"] >= CORR_THRESHOLD]
    print(f"  {len(passing)}/{len(pair_stats)} pairs pass correlation filter (>= {CORR_THRESHOLD})")

    if not passing:
        print("\n  快殺判定候選：0條配對通過相關係數篩選，可能是樣本量太小"
              "（100檔快取樣本+MIN_OVERLAP_DAYS門檻交集後可用配對太少），"
              "不必然是機制無效，下一輪應先確認是否要放寬取樣或延伸樣本再判死。")
        return {"n_pairs_total": len(all_pairs), "n_pairs_passing": 0}

    results = []
    for p in passing:
        ev = zscore_events(p["log_a"], p["log_b"])
        results.append({**{k: v for k, v in p.items() if k not in ("log_a", "log_b")}, **ev})

    entries_per_pair = [r["n_entries"] for r in results]
    with_entries = [r for r in results if r["n_entries"] > 0]
    converged_fracs = [r["converged_frac"] for r in with_entries if not np.isnan(r["converged_frac"])]
    reductions = [r["mean_abs_z_reduction"] for r in with_entries if not np.isnan(r["mean_abs_z_reduction"])]

    print(f"\n  entries per passing pair: median={np.median(entries_per_pair):.1f}, "
          f"total={sum(entries_per_pair)}, pairs_with_any_entry={len(with_entries)}/{len(results)}")
    if converged_fracs:
        print(f"  direction sanity (entry->+{CONVERGE_HORIZON}d, converged = |exit_z|<|entry_z|): "
              f"pair-level median converged_frac={np.median(converged_fracs):.3f} "
              f"(pooled across pairs, not a formal test -- just checking sign isn't reversed)")
        print(f"  mean |z| reduction over pairs with entries: median={np.median(reductions):+.3f}")
    else:
        print("  no pairs produced any entry event (|z|>=ENTRY_Z) -- z-score likely too tame or window mis-sized")

    df = pd.DataFrame(results).sort_values("n_entries", ascending=False)
    out_path = Path(__file__).parent / "data" / "pair_trading_sanity_results.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\n  results written to {out_path}")

    return {
        "n_pairs_total": len(all_pairs),
        "n_pairs_passing_corr": len(passing),
        "n_pairs_with_entries": len(with_entries),
        "median_entries_per_passing_pair": float(np.median(entries_per_pair)) if entries_per_pair else float("nan"),
        "median_converged_frac": float(np.median(converged_fracs)) if converged_fracs else float("nan"),
    }


if __name__ == "__main__":
    main()
