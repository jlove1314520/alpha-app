"""`PENDING_QUEUE.md` 常備.3 VIX絕對水位本身（不取VIX9D/VIX比值）
當台股大盤regime降曝險訊號 第1關cheap gate。

背景：`vix_term_structure_gate.py`（#76）測的是VIX9D/VIX**比值**（期限
結構），`STRATEGY_GRAVEYARD.md` #76段落明列「未測VIX絕對水位本身（不取
比值）」為未測變體——這是不同的經濟機制：期限結構測的是「短期恐慌相對
中期恐慌的落差」，絕對水位測的是「恐慌情緒的整體強度」，文獻上兩者常被
分開討論（VIX水位本身是最常見的市場壓力代理指標）。本檔案補這個變體。

**訊號口徑決定（事前綁定，第1關前決定）**：VIX（^VIX）收盤**水位**本身
（不取比值、不取變動率）——這是狀態性訊號（水位越高代表當下恐慌程度
越高），比照`copper_gold_ratio_gate.py`/`fred_yield_curve_gate.py`對
「狀態性訊號用水位不用變動率」的既有判斷邏輯。

**目標窗口**：M=20交易日，同#76/#32/#33/#34既有regime類窗口慣例。

**事前綁定方向**：VIX水位越高（美股恐慌情緒越強）→ 台股後續報酬越低
（負相關）——美股波動率與台股連動、危機期間同步共振是既有機制假說。

**判定標準**：比照#76/#32/#33/#34同一套cheap gate三項判準（幅度非零/
train-val同號/贏過洗牌null N=500），TRAIN/VAL邊界用既有`validation/
holdout.py`。

**資料源**：`^VIX`/`^TWII`皆用`yf_price_client.py::fetch_yf_index()`，
VIX起點1990-01-02遠早於TRAIN_END，資料可行性優於VIX9D（起點2011），
不新增資料源模組。

2026-09-23 DevQueue自走cycle 20260923-121601，`PENDING_QUEUE.md`常備.3。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
VIX_TICKER = "^VIX"
TAIEX_TICKER = "^TWII"
DATA_START = "1990-01-01"  # VIX起點1990-01-02，遠早於TRAIN_END
M_TARGET_DAYS = 20  # TAIEX後續M日報酬預測視窗


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t+M存在），配對VIX收盤水位(訊號)跟TAIEX M日
    後報酬(目標)。回傳 columns: date, vix_level, tw_fwd_ret_m。
    """
    vix = fetch_yf_index(ticker=VIX_TICKER, start_date=DATA_START)
    if vix.empty:
        raise RuntimeError("VIX(^VIX)抓取後為空資料，第1關無法起跑")
    vix = vix.dropna(subset=["close"]).copy()
    vix["date"] = pd.to_datetime(vix["date"])
    vix = vix.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    vix = vix.rename(columns={"close": "vix_level"})

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        vix[["date", "vix_level"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date", how="inner",
    )
    merged = merged.dropna(subset=["vix_level", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    signal = df["vix_level"].to_numpy()
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
    print(f"VIX水位描述統計: mean={aligned['vix_level'].mean():.4f} "
          f"median={aligned['vix_level'].median():.4f} "
          f"std={aligned['vix_level'].std():.4f} "
          f"min={aligned['vix_level'].min():.4f} max={aligned['vix_level'].max():.4f}")
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
    matches_expected_direction = val_result["pearson"] < 0  # 事前綁定：VIX水位越高→TAIEX後續報酬越低(負相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(負相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/vix_level_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
