"""`PENDING_QUEUE.md` 常備.2 VIX期限結構（VIX9D/VIX比值）**N日變動率版**
當台股大盤regime降曝險訊號 第1關cheap gate。

背景：`vix_term_structure_gate.py`（#76）測過「比值水位」版，train/val正負號
相反判FAIL；`STRATEGY_GRAVEYARD.md` #76段落明列「未測比值變動率（速度而非
水位）」為未測變體。本檔案補這個變體，不重跑水位版。

**訊號口徑決定（事前綁定，第1關前決定）**：VIX9D/VIX比值的N日變動率
（fx_change_n = ratio[t]/ratio[t-N] - 1），N=20——沿用`fx_twd_gate.py`
（#32）既有N日變動率窗口慣例，不另挑一個新窗口製造多重比較。跟水位版
（`vix_term_structure_gate.py`）共用同一組VIX9D/VIX/TAIEX資料抓取邏輯與
M=20目標窗口，只有訊號本身從水位換成N日變動率，是唯一改變的自由度。

**目標窗口**：M=20交易日，同水位版、同`fx_twd_gate.py`慣例。

**事前綁定方向**：比值N日內快速上升（短期恐慌相對中期加速升溫，倒掛
加深的速度）→ 台股後續報酬越低（負相關），跟水位版方向假說一致，只是
訊號從「有多深」換成「多快加深」。

**判定標準**：比照#76/#32/#33/#34同一套cheap gate三項判準（幅度非零/
train-val同號/贏過洗牌null N=500），TRAIN/VAL邊界用既有`validation/
holdout.py`。

**資料源**：`^VIX9D`/`^VIX`/`^TWII`皆用`yf_price_client.py::
fetch_yf_index()`，同#76已查證的資料可行性（VIX9D起點2011-01-03早於
TRAIN_END），不新增資料源模組。

2026-09-23 DevQueue自走cycle 20260923-121601，`PENDING_QUEUE.md`常備.2。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
VIX9D_TICKER = "^VIX9D"
VIX_TICKER = "^VIX"
TAIEX_TICKER = "^TWII"
DATA_START = "2011-01-01"  # 受VIX9D起點限制（2011-01-03）
N_SIGNAL_DAYS = 20  # 比值N日變動率信號視窗，沿用fx_twd_gate.py慣例
M_TARGET_DAYS = 20  # TAIEX後續M日報酬預測視窗


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t-N存在且t+M存在），配對VIX9D/VIX比值N日
    變動率(訊號)跟TAIEX M日後報酬(目標)。回傳 columns: date, vix_term_roc, tw_fwd_ret_m。
    """
    vix9d = fetch_yf_index(ticker=VIX9D_TICKER, start_date=DATA_START)
    vix = fetch_yf_index(ticker=VIX_TICKER, start_date=DATA_START)
    for name, df, ticker in (("VIX9D", vix9d, VIX9D_TICKER), ("VIX", vix, VIX_TICKER)):
        if df.empty:
            raise RuntimeError(f"{name}({ticker})抓取後為空資料，第1關無法起跑")

    vix9d = vix9d.dropna(subset=["close"]).copy()
    vix9d["date"] = pd.to_datetime(vix9d["date"])
    vix9d = vix9d.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    vix = vix.dropna(subset=["close"]).copy()
    vix["date"] = pd.to_datetime(vix["date"])
    vix = vix.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ratio = pd.merge(
        vix9d[["date", "close"]].rename(columns={"close": "vix9d_close"}),
        vix[["date", "close"]].rename(columns={"close": "vix_close"}),
        on="date", how="inner",
    )
    ratio = ratio[ratio["vix_close"] > 0].copy()
    ratio["vix_term_ratio"] = ratio["vix9d_close"] / ratio["vix_close"]
    ratio["vix_term_roc"] = ratio["vix_term_ratio"] / ratio["vix_term_ratio"].shift(N_SIGNAL_DAYS) - 1.0

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        ratio[["date", "vix_term_roc"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date", how="inner",
    )
    merged = merged.dropna(subset=["vix_term_roc", "tw_fwd_ret_m"]).reset_index(drop=True)
    return merged


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_pearson, real_p = stats.pearsonr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i] = stats.pearsonr(perm, target)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson),
        "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["vix_term_roc"].to_numpy()
    target = df["tw_fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Pearson r={pearson:+.4f} (p={pearson_p:.4f})")
    print(f"  Spearman rho={spearman:+.4f} (p={spearman_p:.4f})")
    print(f"  洗牌null(N={N_SHUFFLE}): median|r|={shuf['null_median_abs']:.4f}  "
          f"真實|r|percentile={shuf['percentile']:.1f}")
    return {
        "label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
        "spearman": spearman, "spearman_p": spearman_p,
        "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"],
    }


def main():
    aligned = build_aligned_series()
    print(f"對齊後總配對數: {len(aligned)}")
    print(f"日期範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"VIX9D/VIX比值N({N_SIGNAL_DAYS})日變動率描述統計: mean={aligned['vix_term_roc'].mean():.4f} "
          f"median={aligned['vix_term_roc'].median():.4f} "
          f"std={aligned['vix_term_roc'].std():.4f} "
          f"min={aligned['vix_term_roc'].min():.4f} max={aligned['vix_term_roc'].max():.4f}")
    print(f"TAIEX後M({M_TARGET_DAYS})日報酬描述統計: mean={aligned['tw_fwd_ret_m'].mean():.4f} "
          f"median={aligned['tw_fwd_ret_m'].median():.4f} std={aligned['tw_fwd_ret_m'].std():.4f}")

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] < 0  # 事前綁定：比值加深速度越快→TAIEX後續報酬越低(負相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(負相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/vix_term_structure_roc_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
