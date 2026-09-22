"""`HYPOTHESIS_QUEUE.md` #78 美國高收益債ETF/公債ETF價格比值（HYG/IEF）
代理信用利差當TAIEX regime降曝險訊號 第1關cheap gate。

經濟理由：跟#77（FRED `BAMLH0A0HYM2` OAS學術口徑）同一個經濟機制（信用
市場對違約風險的集體定價），但#77已於2026-09-22判定「資料不可及」——
該序列2026-04起免費歷史深度被截斷至僅3年，無法涵蓋TRAIN期。這裡換一個
資料觀察窗：`HYG`（iShares iBoxx高收益公司債ETF）與`IEF`（iShares
7-10年期公債ETF）皆為yfinance可得的真實市場成交價，非授權受限的衍生
指數資料，資料可行性已於本輪`hy_etf_ratio_probe.py`確認（HYG起點
2007-04-11、IEF起點2002-07-30，皆早於TRAIN_END=2020-12-31）。完整
經濟理由見`HYPOTHESIS_QUEUE.md` #78條目。

跟`copper_gold_ratio_gate.py`（#34）/`fx_twd_gate.py`（#32）/
`fred_yield_curve_gate.py`（#33）同一種指數層級（index-level）時序
相關性測試精神，不是`factor_ic.py`的cross-sectional選股IC——測的是
「HYG/IEF比值水位」這一條時間序列跟「TAIEX後續M個交易日報酬」這一條
時間序列之間的相關性。

**訊號口徑（事前綁定，第1關前決定）**：用**比值水位本身**（level =
HYG收盤價/IEF收盤價），不用變動率——理由同#77/#34：水位代表當下信用
風險定價狀態，非速度訊號。

**目標窗口（事前綁定）**：M=20交易日，與本佇列regime類窗口同一量級。
目標 = TAIEX[t+M]/TAIEX[t] - 1（訊號日t之後M個交易日的台股報酬，訊號
在t日已完全確定，預測未來，無未來函數）。

**事前綁定方向（`HYPOTHESIS_QUEUE.md` #78條目原文推導，務必對齊）**：
比值高 = 高收益債相對公債走強 = 信用風險定價低（風險偏好升溫）；比值
低 = 高收益債相對走弱 = 信用風險定價高（對應#77的利差走闊）。#77事前
綁定「利差走闊→後續報酬轉弱」，換算成本條的比值語言即「比值低→後續
報酬轉弱」，也就是**比值水位與TAIEX後續報酬應為正相關**（比值高伴隨
報酬轉強，比值低伴隨報酬轉弱，同向變動）。matches_expected_direction
判準為 VAL期Pearson r > 0。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19/#31/#32/#33/#34/#76/#77完全同一套框架）**：
TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有
`validation/holdout.py`邊界），皆用Pearson相關係數（主要）+ Spearman
（穩健性檢查），N_SHUFFLE=500次洗牌null（打散訊號時序、保留TAIEX報酬
時序）。

**資料源**：HYG、IEF、TAIEX（^TWII）皆用`yf_price_client.py::
fetch_yf_index()`既有基礎設施（不限於指數，任意yfinance ticker皆可用，
函式內部只是把ticker原樣傳給yfinance），不新增資料源模組、不需要新API
金鑰。`fetch_yf_index()`已內建`VAL_END`截斷，holdout天然安全。

2026-09-22 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#78第1關
起跑（承接本輪稍早`hy_etf_ratio_probe.py`資料可行性PASS）。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

N_SHUFFLE = 500
SHUFFLE_SEED = 20260922
HYG_TICKER = "HYG"
IEF_TICKER = "IEF"
TAIEX_TICKER = "^TWII"
DATA_START = "2007-01-01"  # HYG實際起點2007-04-11為限制腿，稍早於此以求對齊完整
M_TARGET_DAYS = 20  # TAIEX後續M日報酬預測視窗


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t+M存在），配對HYG/IEF比值水位(訊號)跟
    TAIEX M日後報酬(目標)。回傳 columns: date, hyg_ief_ratio, tw_fwd_ret_m。
    """
    hyg = fetch_yf_index(ticker=HYG_TICKER, start_date=DATA_START)
    ief = fetch_yf_index(ticker=IEF_TICKER, start_date=DATA_START)
    for name, df, tk in (("HYG", hyg, HYG_TICKER), ("IEF", ief, IEF_TICKER)):
        if df.empty:
            raise RuntimeError(f"{name}({tk})抓取後為空資料，第1關無法起跑")

    hyg = hyg.dropna(subset=["close"]).copy()
    hyg["date"] = pd.to_datetime(hyg["date"])
    hyg = hyg.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ief = ief.dropna(subset=["close"]).copy()
    ief["date"] = pd.to_datetime(ief["date"])
    ief = ief.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ratio = pd.merge(
        hyg[["date", "close"]].rename(columns={"close": "hyg_close"}),
        ief[["date", "close"]].rename(columns={"close": "ief_close"}),
        on="date", how="inner",
    )
    ratio = ratio[ratio["ief_close"] > 0].copy()
    ratio["hyg_ief_ratio"] = ratio["hyg_close"] / ratio["ief_close"]

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        ratio[["date", "hyg_ief_ratio"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date", how="inner",
    )
    merged = merged.dropna(subset=["hyg_ief_ratio", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    signal = df["hyg_ief_ratio"].to_numpy()
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
    print(f"HYG/IEF比值(水位)描述統計: mean={aligned['hyg_ief_ratio'].mean():.4f} "
          f"median={aligned['hyg_ief_ratio'].median():.4f} "
          f"std={aligned['hyg_ief_ratio'].std():.4f} "
          f"min={aligned['hyg_ief_ratio'].min():.4f} max={aligned['hyg_ief_ratio'].max():.4f}")
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
    matches_expected_direction = val_result["pearson"] > 0  # 事前綁定：比值高對應TAIEX轉強(正相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(正相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/hy_etf_ratio_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
