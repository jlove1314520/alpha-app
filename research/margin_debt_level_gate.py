"""`HYPOTHESIS_QUEUE.md` #26 全市場融資餘額——「水位」（非成長率）regime 訊號
第1關cheap gate。

**為什麼要測這個、跟已FAIL的`margin_debt_growth_gate.py`差在哪**：
`TRIALS_LEDGER.md`#97（`margin_debt_growth_gate.py`）測的是**成長率**
（20日/60日近似變化率）對後續TAIEX回撤的Spearman相關，結果train/val
方向相反，FAIL。但#97自己的備註明白寫著「不泛化成這個維度完全無效——
只測了成長率構造，**未測用水位（而非成長率）當訊號**」。第373輪
（`TW_MARATHON_STATE.md`）建議衝新API測`MI_MARGN`當regime overlay，
查證後發現MI_MARGN官方全市場數字跟#26是同一份資料、已完整回補
（`backfill_margin_debt_market.py`，662週2012-05~2024-12-31），只是
#97只測過成長率這一種構造——本檔案補上#97明確留下的「水位」缺口，
不是重複#97已測過的東西。

**經濟理由（水位版）**：融資餘額水位本身（相對於自己近期歷史區間的
高低，而非變化速度）代表當下的槓桿擁擠度絕對水準——即使成長率已經
趨緩，若餘額仍停留在歷史高檔，系統性斷頭風險依然存在（成長率轉為
持平或小跌，但存量水位仍高）。這跟成長率是互補而非重複的角度：
成長率捕捉「速度」，水位捕捉「存量」。

**訊號構造（避免look-ahead）**：對每個週觀測點t，用**只包含t之前
（含t）**的trailing 156週（約3年）窗口計算balance[t]在該窗口內的
百分位排名（0~100），不使用t之後的任何資訊。前156週作為窗口暖身期，
不產生訊號（比照`factor_ic.py`等既有因子構造「暖身期不產生訊號」的
慣例）。

**cheap gate設計**：跟`margin_debt_growth_gate.py`同一套框架——訊號
在t觀測到，結果是t之後N個交易日（N=20/60）TAIEX最大回撤幅度絕對值，
Spearman相關（預期為正：水位越高、後續回撤越深），配對式洗牌置換
檢定（N=200，打散配對本身、保留兩邊各自時序）。TRAIN/VAL邊界沿用
`validation/holdout.py`既有常數。

**資料**：零新增API呼叫，完全重用`backfill_margin_debt_market.py`
已完成的662個週檔快取（`research/data/raw_margin_debt_market/`）與
`yf_price_client.fetch_yf_index`既有TAIEX日線快取。

2026-09-05 馬拉松第375輪（TW軌）新增，接續round373「MI_MARGN尚未測」
建議、查證後改為「水位角度尚未測、成長率角度已測FAIL」的精確缺口。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from margin_debt_growth_gate import (
    MIN_ABS_CORR,
    N_SHUFFLE,
    SHUFFLE_SEED,
    WINDOW_DEFS,
    _forward_window_mdd,
    _load_margin_series,
    _load_taiex_daily,
    _shuffle_percentile,
    _split,
)

TRAILING_WEEKS = 156  # ~3年暖身期，避免look-ahead


def _level_percentile(balance: pd.Series, trailing_weeks: int) -> pd.Series:
    """對每個位置i，用balance[max(0,i-trailing_weeks+1):i+1]（含自身、僅過去
    資料）算balance[i]在窗口內的百分位排名。前trailing_weeks-1個位置回傳NaN
    （暖身期不產生訊號）。"""
    out = np.full(len(balance), np.nan)
    values = balance.to_numpy()
    for i in range(trailing_weeks - 1, len(values)):
        window = values[i - trailing_weeks + 1: i + 1]
        out[i] = 100.0 * float(np.mean(window <= values[i]))
    return pd.Series(out, index=balance.index)


def _build_pairs(margin: pd.DataFrame, taiex: pd.DataFrame, horizon_days: int, level_col: str) -> pd.DataFrame:
    rows = []
    for i in range(len(margin)):
        lvl = margin[level_col].iloc[i]
        if pd.isna(lvl):
            continue
        mdd = _forward_window_mdd(taiex, margin["date"].iloc[i], horizon_days)
        if mdd is None:
            continue
        rows.append({"date": margin["date"].iloc[i], "level_pct": float(lvl), "fwd_mdd_abs": abs(mdd)})
    return pd.DataFrame(rows)


def evaluate(df: pd.DataFrame, label: str) -> dict:
    level = df["level_pct"].to_numpy()
    fwd = df["fwd_mdd_abs"].to_numpy()
    n = len(df)
    shuf = _shuffle_percentile(level, fwd, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Spearman(level_pct, |fwd_mdd|) = {shuf['real_corr']:+.4f} (p={shuf['real_p']:.4f})")
    print(f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.4f}  "
          f"真實corr percentile(單邊)={shuf['percentile']:.1f}")
    return {"label": label, "n": n, "corr": shuf["real_corr"], "p": shuf["real_p"],
            "null_median": shuf["null_median"], "null_percentile": shuf["percentile"]}


def main():
    print("=== #26 全市場融資餘額「水位」（非成長率）regime 訊號 第1關cheap gate ===")
    margin = _load_margin_series()
    print(f"融資週檔筆數(is_trading_day=True): {len(margin)}  "
          f"日期範圍: {margin['date'].min().date()} ~ {margin['date'].max().date()}")
    margin["level_pct"] = _level_percentile(margin["balance"], TRAILING_WEEKS)
    n_valid = margin["level_pct"].notna().sum()
    print(f"trailing{TRAILING_WEEKS}週暖身期後可用觀測點: {n_valid}/{len(margin)}"
          f"（首個有效日期: {margin.loc[margin['level_pct'].notna(), 'date'].min().date()}）")

    taiex = _load_taiex_daily()
    print(f"TAIEX日線筆數: {len(taiex)}  日期範圍: {taiex['date'].min().date()} ~ {taiex['date'].max().date()}")

    # sanity: 水位百分位應該在0~100之間均勻分布，不該卡在極端值（構造bug檢查）
    valid_pct = margin["level_pct"].dropna()
    print(f"\nsanity: level_pct全樣本 mean={valid_pct.mean():.1f} std={valid_pct.std():.1f} "
          f"min={valid_pct.min():.1f} max={valid_pct.max():.1f}")
    assert 30 < valid_pct.mean() < 70, "水位百分位均值偏離50太多，可能是構造bug"

    results = []
    verdicts = {}
    for _lag_weeks, horizon_days, label in WINDOW_DEFS:
        pairs = _build_pairs(margin, taiex, horizon_days, "level_pct")
        train, val = _split(pairs)
        print(f"\n########## {label} (horizon={horizon_days}交易日) "
              f"config_pairs={len(pairs)} train_n={len(train)} val_n={len(val)} ##########")

        train_result = evaluate(train, f"TRAIN (<= {pd.Timestamp('2020-12-31').date()}) {label}")
        val_result = evaluate(val, f"VAL {label}")
        results.append({**train_result, "window": label})
        results.append({**val_result, "window": label})

        nontrivial = (abs(train_result["corr"]) > MIN_ABS_CORR
                      and abs(val_result["corr"]) > MIN_ABS_CORR)
        same_sign = (train_result["corr"] > 0) == (val_result["corr"] > 0)
        both_positive = train_result["corr"] > 0 and val_result["corr"] > 0
        beats_null = val_result["null_percentile"] >= 90.0

        print(f"\n=== {label} 第1關cheap gate三項判準 ===")
        print(f"  1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
        print(f"  2. train/val同號且方向為正(水位越高、後續回撤越深): {same_sign and both_positive} "
              f"(TRAIN corr={train_result['corr']:+.4f}, VAL corr={val_result['corr']:+.4f})")
        print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
              f"(percentile={val_result['null_percentile']:.1f})")

        verdict = "CHEAP_PASS" if (nontrivial and same_sign and both_positive and beats_null) else "FAIL"
        print(f"  判定({label}): {verdict}")
        verdicts[label] = verdict

    print("\n=== 總結 ===")
    for label, v in verdicts.items():
        print(f"  {label}: {v}")
    overall = "CHEAP_PASS" if any(v == "CHEAP_PASS" for v in verdicts.values()) else "FAIL"
    print(f"整體判定(任一窗口版本CHEAP_PASS即算過關，供下一關挑選對應窗口繼續): {overall}")

    pd.DataFrame(results).to_csv("data/margin_debt_level_gate_results.csv", index=False)
    return {"verdicts": verdicts, "overall": overall, "results": results}


if __name__ == "__main__":
    main()
