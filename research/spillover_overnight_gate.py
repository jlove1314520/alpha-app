"""`HYPOTHESIS_QUEUE.md` #19 跨市場美股隔夜報酬外溢效應（Cross-Market
Overnight Spillover）第1關cheap gate。

經濟理由：美股收盤（美東下午4點，約台灣時間隔日清晨4-5點）早於台股開盤
（台灣時間上午9點），美股當日報酬對台股次一交易日開盤具有結構性的資訊
領先（台股開盤前，美股已經反映了這段時間發生的全球性消息），不是巧合
相關。見`HYPOTHESIS_QUEUE.md`#19完整經濟理由段落。

跟本佇列已測過的18條假設不同：這是**指數層級（index-level）時序相關性**
測試，不是cross-sectional選股排序——沒有「多檔股票的橫斷面IC」可算，
測的是「美股隔夜報酬」這一條時間序列跟「台股次日報酬」這一條時間序列之間
的（時序位移）相關性，本質上更接近`vol_targeting_v1.py`/`regime_overlay.py`
（index-level、非選股）的檢驗方式，不是`factor_ic.py`的cross-sectional
IC框架。

**時序對齊邏輯（避免未來函數，這是本輪重點）**：對每個台股交易日t，找
「最近一個、日曆日期嚴格早於t的美股交易日」d_us，用(d_us收盤/d_us前一個
美股交易日收盤 - 1)當作「美股隔夜報酬」訊號，這個訊號在台股t日開盤前
已經確定發生（不論台美假日是否對齊，只看日曆日期先後，不假設兩邊交易
日曆完全同步）。目標變數是台股t日的close-to-close報酬（tw_close[t]/
tw_close[t-1]-1），因為訊號在t日開盤前就已知，可以合法預測整個t日（含
開盤跳空+盤中）的報酬。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null）**：TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END,
VAL_END]（`validation/holdout.py`既有邊界），皆用Pearson相關係數（主要）
+ Spearman（穩健性檢查），N=500次洗牌null（打散訊號時序、保留台股報酬
時序，比照本佇列既有隨機控制組精神）。

2026-09-03 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#19第1關
起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260903


def _daily_returns(ticker: str) -> pd.DataFrame:
    """回傳 date(Timestamp,已排序) + close + ret(當日對前一交易日收盤報酬)。"""
    df = fetch_yf_index(ticker=ticker, start_date="2010-01-01")
    df = df.dropna(subset=["close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    return df[["date", "close", "ret"]]


def build_aligned_series() -> pd.DataFrame:
    """對每個台股交易日t，配對「日曆日期嚴格早於t的最近一個美股交易日」的
    隔夜報酬，跟台股t日報酬。回傳 columns: tw_date, us_signal_date, us_ret,
    tw_ret。
    """
    us = _daily_returns("^GSPC")
    tw = _daily_returns("^TWII")

    us_dates = us["date"].to_numpy()
    us_rets = us["ret"].to_numpy()

    rows = []
    for _, trow in tw.iterrows():
        t_date = trow["date"]
        if pd.isna(trow["ret"]):
            continue
        # 找日曆日期嚴格早於t_date的最近一個美股交易日索引
        idx = np.searchsorted(us_dates, np.datetime64(t_date), side="left") - 1
        if idx < 0:
            continue
        us_signal_date = us_dates[idx]
        us_signal_ret = us_rets[idx]
        if pd.isna(us_signal_ret):
            continue
        rows.append({
            "tw_date": t_date,
            "us_signal_date": pd.Timestamp(us_signal_date),
            "us_ret": float(us_signal_ret),
            "tw_ret": float(trow["ret"]),
        })
    out = pd.DataFrame(rows)
    return out


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["tw_date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["tw_date"] > pd.Timestamp(TRAIN_END)) & (df["tw_date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(us_ret: np.ndarray, tw_ret: np.ndarray, n: int, seed: int) -> dict:
    real_pearson, real_p = stats.pearsonr(us_ret, tw_ret)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(us_ret)
        shuffled[i] = stats.pearsonr(perm, tw_ret)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson),
        "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    us_ret = df["us_ret"].to_numpy()
    tw_ret = df["tw_ret"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(us_ret, tw_ret)
    spearman, spearman_p = stats.spearmanr(us_ret, tw_ret)
    shuf = _shuffle_percentile(us_ret, tw_ret, N_SHUFFLE, SHUFFLE_SEED)
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
    print(f"日期範圍: {aligned['tw_date'].min()} ~ {aligned['tw_date'].max()}")
    # sanity: 確認us_signal_date確實早於tw_date（無未來函數）、時間差合理（1~4天，含週末/假日）
    gap_days = (aligned["tw_date"] - aligned["us_signal_date"]).dt.days
    print(f"美股訊號日到台股交易日的日曆天數差: min={gap_days.min()} max={gap_days.max()} "
          f"median={gap_days.median()}")
    assert gap_days.min() >= 1, "發現us_signal_date沒有嚴格早於tw_date，時序對齊有bug"

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/spillover_overnight_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict}


if __name__ == "__main__":
    main()
