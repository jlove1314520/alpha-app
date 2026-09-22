"""`HYPOTHESIS_QUEUE.md` #76 美股VIX期限結構（VIX9D/VIX比值）當台股大盤
regime降曝險訊號 第1關cheap gate。

經濟理由：VIX期限結構倒掛（近端VIX9D高於中期VIX，代表短期恐慌情緒急升、
高於中期預期）長期被文獻記錄為市場壓力前兆；台股與美股波動率市場高度
連動（尤其危機期間）。跟本佇列已測過的#31（選擇權PCR）/#32（台幣匯率）/
#33（公債殖利率曲線）/#34（銅金比）同一種「index-level時序相關性」測試
精神，不是`factor_ic.py`的cross-sectional選股IC——測的是「VIX9D/VIX比值」
這一條時間序列跟「TAIEX後續M個交易日報酬」這一條時間序列之間的相關性。

**訊號口徑決定（事前綁定，第1關前決定）**：用**比值水位本身**
（level = VIX9D收盤/VIX收盤），不是N日變動率——理由跟#34銅金比同一套
邏輯：這是一個狀態性的期限結構訊號（比值>1.0代表倒掛），是水位訊號不是
速度訊號，訊號口徑要對應機制定義本身。

**目標窗口（事前綁定，第1關前決定，非跑完看結果才選）**：M=20交易日
（預測視窗），與本專案既有regime類窗口（`regime_overlay.py`20日波動度窗、
`fx_twd_gate.py`/`fred_yield_curve_gate.py`/`copper_gold_ratio_gate.py`
同量級）同一個量級。目標 = TAIEX[t+M]/TAIEX[t] - 1（訊號日t之後M個交易日
的台股報酬，訊號在t日已完全確定，預測未來，無未來函數）。

**事前綁定方向**：比值越高（倒掛越深，短期恐慌升溫）→ 台股後續報酬越低
（負相關）——若第1關方向跟預期相反要誠實記錄，不能事後改預期方向配合
結果。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19/#31/#32/#33/#34完全同一套框架）**：TRAIN=
[universe起點,TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有`validation/
holdout.py`邊界），皆用Pearson相關係數（主要）+ Spearman（穩健性檢查），
N_SHUFFLE=500次洗牌null（打散訊號時序、保留TAIEX報酬時序）。

**資料源**：`^VIX9D`/`^VIX`兩條指數序列跟TAIEX（^TWII）皆用
`yf_price_client.py::fetch_yf_index()`既有基礎設施（已在
`vix_term_structure_probe.py`資料可行性查證中確認：VIX9D起點
2011-01-03、VIX起點1990-01-02，兩者交集起點2011-01-03，早於TRAIN_END
2020-12-31，通過七之三第10關），不新增資料源模組、不需要新API金鑰。
`fetch_yf_index()`已內建`VAL_END`截斷，holdout天然安全。

2026-09-22 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#76第1關
起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260922
VIX9D_TICKER = "^VIX9D"
VIX_TICKER = "^VIX"
TAIEX_TICKER = "^TWII"
DATA_START = "2011-01-01"  # 受VIX9D起點限制（2011-01-03）
M_TARGET_DAYS = 20  # TAIEX後續M日報酬預測視窗


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t+M存在），配對VIX9D/VIX比值水位(訊號)跟
    TAIEX M日後報酬(目標)。回傳 columns: date, vix_term_ratio, tw_fwd_ret_m。
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

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        ratio[["date", "vix_term_ratio"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date", how="inner",
    )
    merged = merged.dropna(subset=["vix_term_ratio", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    signal = df["vix_term_ratio"].to_numpy()
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
    print(f"VIX9D/VIX比值(水位)描述統計: mean={aligned['vix_term_ratio'].mean():.4f} "
          f"median={aligned['vix_term_ratio'].median():.4f} "
          f"std={aligned['vix_term_ratio'].std():.4f} "
          f"min={aligned['vix_term_ratio'].min():.4f} max={aligned['vix_term_ratio'].max():.4f}")
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
    matches_expected_direction = val_result["pearson"] < 0  # 事前綁定：比值越高→TAIEX後續報酬越低(負相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(負相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/vix_term_structure_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
