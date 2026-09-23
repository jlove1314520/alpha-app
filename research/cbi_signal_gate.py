"""`HYPOTHESIS_QUEUE.md` #81 台灣景氣對策信號（國發會景氣燈號）當TAIEX
regime降曝險訊號第1關cheap gate。

經濟理由：景氣對策信號是官方九項構成項目複合而成的景氣循環定位指標，
分數越高（越偏紅燈／景氣過熱端）依「過熱後續常接轉折」的反轉邏輯，
事前綁定預期TAIEX後續報酬應負相關；分數越低（越偏藍燈／景氣落底）應
正相關。跟本佇列已測過的10個regime/timing類訊號（#31~#34/#76~#80）
同一種index-level時序相關性測試精神，非cross-sectional選股IC。

**公布延遲查證更正（本輪修正，事前綁定前完成，未看任何報酬）**：
`HYPOTHESIS_QUEUE.md` #81原SPEC文字寫「每月27日左右公布上上個月資料」
（暗示T+2個月延遲）——經WebSearch三方查證（國發會官方頁面
`ndc.gov.tw/nc_335_2236`、Smart自學網、StockFeel股感三個獨立來源一致）
確認實際規則是**公布上個月資料**（T+1個月延遲，每月27~30日公布，僅
1月資料例外延到3月初公布）。原SPEC文字為誤植，本輪已在
`HYPOTHESIS_QUEUE.md`對應段落標註更正，不得沿用原文字的兩個月延遲
假設。操作化：`PUBLISH_LAG_DAYS=30`（自該月最後一天起算30天後才視為
市場已知），跟#80(DGBAS失業率)同一個保守估計值，且30天恰好近似
「27~30日」實際公布窗口與1月例外延到3月初的邊界（1/31+30=3/2）。

**訊號口徑**：月頻「景氣對策信號綜合分數」（0~45分，水準值非變動率），
來源`data_cache/ndc/景氣指標與燈號.csv`（國發會官方免認證zip，
`data.gov.tw/dataset/6099`，2026-09-23 #81首輪已下載並commit）。
早期月份（198201~198312）該欄位為"-"（尚未編製），需篩除。

**目標窗口**：M=20交易日，TAIEX[t+M]/TAIEX[t]-1，跟#76~#80同量級。

**事前綁定方向**：景氣對策信號綜合分數與TAIEX後續M=20交易日報酬應
**負相關**（分數越高/景氣過熱→後續報酬轉弱）。

**判定標準**：比照#19/#31~#34/#76~#80同一套cheap gate三項判準（幅度
非零/train-val同號/VAL贏過洗牌null percentile>=90），Pearson為主，
Spearman為穩健性檢查，N_SHUFFLE=500（月頻訊號merge到日頻TAIEX，沿用
#80同一慣例）。

2026-09-23 由`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節自動排程接續，佇列#81
「下一輪待辦」執行。
"""
from __future__ import annotations

import glob
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
TAIEX_TICKER = "^TWII"
DATA_START = "1982-01-01"
M_TARGET_DAYS = 20
PUBLISH_LAG_DAYS = 30

_CBI_NAME_PREFIX_UTF8 = "景氣指標".encode("utf-8")


def _find_main_csv() -> str:
    for path in glob.glob("data_cache/ndc/*.csv"):
        base = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if base.encode("utf-8", errors="ignore").startswith(_CBI_NAME_PREFIX_UTF8):
            return path
    raise FileNotFoundError("找不到景氣指標與燈號.csv，第1關無法起跑")


def fetch_cbi_score() -> pd.DataFrame:
    """讀取國發會景氣指標與燈號CSV，回傳 columns: month_end, score(float)。
    篩除score為"-"（尚未編製）的早期列。
    """
    path = _find_main_csv()
    df = pd.read_csv(path, encoding="utf-8-sig", encoding_errors="strict")
    df.columns = [str(c) for c in df.columns]
    score_col = df.columns[-2]  # 景氣對策信號綜合分數（倒數第二欄，倒數第一欄是燈號文字）
    date_col = df.columns[0]

    df = df[[date_col, score_col]].copy()
    df.columns = ["yyyymm", "score_raw"]
    df["score"] = pd.to_numeric(df["score_raw"], errors="coerce")
    df = df.dropna(subset=["score"]).copy()
    df["yyyymm"] = df["yyyymm"].astype(int)
    df["year"] = df["yyyymm"] // 100
    df["month"] = df["yyyymm"] % 100
    df["month_end"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str) + "-01") \
        + pd.offsets.MonthEnd(0)
    return df[["month_end", "score"]].sort_values("month_end").reset_index(drop=True)


def build_aligned_series() -> pd.DataFrame:
    cbi = fetch_cbi_score()
    cbi["available_date"] = cbi["month_end"] + timedelta(days=PUBLISH_LAG_DAYS)
    cbi = cbi[["available_date", "score"]].sort_values("available_date").reset_index(drop=True)

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    if tw.empty:
        raise RuntimeError("TAIEX(^TWII)抓取後為空資料，第1關無法起跑")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge_asof(
        tw[["date", "tw_fwd_ret_m"]],
        cbi.rename(columns={"available_date": "date", "score": "cbi_score"}),
        on="date", direction="backward",
    )
    merged = merged.dropna(subset=["cbi_score", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    return {"pearson": float(real_pearson), "pearson_p": float(real_p),
            "null_median_abs": float(np.median(np.abs(shuffled))), "percentile": pctl}


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["cbi_score"].to_numpy()
    target = df["tw_fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Pearson r={pearson:+.4f} (p={pearson_p:.4f})")
    print(f"  Spearman rho={spearman:+.4f} (p={spearman_p:.4f})")
    print(f"  Shuffle null(N={N_SHUFFLE}): median|r|={shuf['null_median_abs']:.4f}  "
          f"real|r|percentile={shuf['percentile']:.1f}")
    return {"label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
            "spearman": spearman, "spearman_p": spearman_p,
            "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"]}


def main():
    aligned = build_aligned_series()
    print(f"aligned total pairs: {len(aligned)}")
    print(f"date range: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"cbi_score stats: mean={aligned['cbi_score'].mean():.4f} "
          f"median={aligned['cbi_score'].median():.4f} std={aligned['cbi_score'].std():.4f} "
          f"min={aligned['cbi_score'].min():.4f} max={aligned['cbi_score'].max():.4f}")

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\nsample too small (<30), verdict=FAIL (structural insufficient sample)")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] < 0  # pre-registered: higher score -> negative correlation

    print("\n=== gate1 cheap gate 3 criteria ===")
    print(f"  1. nontrivial (|r|>0.01 both periods): {nontrivial}")
    print(f"  2. train/val same sign: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL beats shuffle null (percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  (note, not a criterion) VAL matches pre-registered direction (negative): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\nverdict: {verdict}")

    aligned.to_csv("data/cbi_signal_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
