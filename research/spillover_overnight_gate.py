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
    """回傳 date(Timestamp,已排序) + open + close + ret(當日對前一交易日收盤報酬)。
    2026-09-23（驗.二第二部分，開盤到收盤重建版）新增`open`欄位：
    `fetch_yf_index()`本來就回傳open，這裡只是額外選取，不改變既有呼叫端
    （既有呼叫端都用`[["date","close"]]`或`[["date","close","ret"]]`子集
    選取，加這欄不影響它們）。"""
    df = fetch_yf_index(ticker=ticker, start_date="2010-01-01")
    df = df.dropna(subset=["close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    return df[["date", "open", "close", "ret"]]


def build_aligned_series_o2c() -> pd.DataFrame:
    """2026-09-23新增（驗.二第二部分，`STRATEGY_GRAVEYARD.md`#346前視偏誤
    更正版）：跟`build_aligned_series()`同一套美股訊號時序對齊邏輯，但目標
    報酬換成台股「t日開盤→t日收盤」（`tw_ret`欄位名沿用不變，只是定義從
    close-to-close換成open-to-close，讓`spillover_overlay_v1.py`既有的
    `build_overlay()`等下游函式可以直接重用，不必另外複製一份），理由見
    `STRATEGY_GRAVEYARD.md`該條目：美股t日訊號在台股t-1收盤後才完全確定，
    但close-to-close報酬含了「台股t-1收盤→t開盤」這段跳空，那段跳空發生
    的同一段時窗正好跟美股當晚交易時段重疊，用收盤到收盤報酬去乘一個
    「訊號公布時已經錯過」的曝險，等於讓回測看到了實際交易時看不到的
    報酬。改用開盤到收盤，訊號在台股當日開盤前就已知，可以合法套用在
    整個交易時段(開盤→收盤)的報酬上，不含那段跳空。

    額外回傳`gap_ret`欄位（台股t-1收盤→t開盤的跳空報酬，非策略報酬的
    一部分，只是診斷用）：用來量化「外溢效應有多少其實是活在跳空裡」——
    如果`gap_ret`對`us_ret`的相關係數遠高於`tw_ret`(o2c)對`us_ret`的
    相關係數，代表原本#346量到的相關性主要來自無法交易的跳空，這裡的
    開盤到收盤版本只是把那部分誠實排除掉，不是「發明」了新的訊號。"""
    us = _daily_returns("^GSPC")
    tw = _daily_returns("^TWII")

    us_dates = us["date"].to_numpy()
    us_rets = us["ret"].to_numpy()

    tw = tw.reset_index(drop=True)
    tw["prev_close"] = tw["close"].shift(1)
    tw["tw_ret_o2c"] = tw["close"] / tw["open"] - 1.0
    tw["gap_ret"] = tw["open"] / tw["prev_close"] - 1.0

    rows = []
    for _, trow in tw.iterrows():
        t_date = trow["date"]
        if pd.isna(trow["tw_ret_o2c"]) or pd.isna(trow["gap_ret"]):
            continue
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
            "tw_ret": float(trow["tw_ret_o2c"]),  # 欄位名沿用tw_ret，供build_overlay()等下游函式直接重用
            "gap_ret": float(trow["gap_ret"]),
        })
    out = pd.DataFrame(rows)
    return out


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


def main_o2c():
    """2026-09-23新增（驗.二第二部分）：#88 cheap gate改用開盤到收盤重跑，
    `evaluate()`本身不管目標報酬是close-to-close還是open-to-close都能重用。
    額外印出「跳空報酬 vs 美股報酬」的相關係數，量化外溢效應有多少活在
    跳空裡（見`build_aligned_series_o2c()`docstring）。"""
    aligned = build_aligned_series_o2c()
    print(f"對齊後總配對數(開盤到收盤版): {len(aligned)}")
    print(f"日期範圍: {aligned['tw_date'].min()} ~ {aligned['tw_date'].max()}")
    gap_days = (aligned["tw_date"] - aligned["us_signal_date"]).dt.days
    assert gap_days.min() >= 1, "發現us_signal_date沒有嚴格早於tw_date，時序對齊有bug"

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    train_result = evaluate(train, f"TRAIN 開盤到收盤 (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL 開盤到收盤 ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"

    print("\n=== 開盤到收盤版 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"\n判定: {verdict}")

    # 跳空診斷：量化「外溢效應有多少活在無法交易的跳空裡」
    gap_r, gap_p = stats.pearsonr(aligned["us_ret"].to_numpy(), aligned["gap_ret"].to_numpy())
    o2c_r_full, _ = stats.pearsonr(aligned["us_ret"].to_numpy(), aligned["tw_ret"].to_numpy())
    print("\n=== 跳空診斷（開盤跳空 vs 美股隔夜報酬）===")
    print(f"  全期 跳空報酬 vs 美股報酬 Pearson r={gap_r:+.4f} (p={gap_p:.4f}, n={len(aligned)})")
    print(f"  全期 開盤到收盤報酬 vs 美股報酬 Pearson r={o2c_r_full:+.4f}（對照）")
    print(f"  跳空相關性佔比（|gap_r|/(|gap_r|+|o2c_r|)）="
          f"{abs(gap_r)/(abs(gap_r)+abs(o2c_r_full))*100:.1f}%" if (abs(gap_r)+abs(o2c_r_full)) > 0 else "  跳空相關性佔比=N/A")

    aligned.to_csv("data/spillover_overnight_aligned_o2c.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "gap_pearson": float(gap_r), "gap_pearson_p": float(gap_p),
            "o2c_pearson_full": float(o2c_r_full)}


if __name__ == "__main__":
    main()
    print("\n\n" + "#" * 70)
    print("# 驗.二第二部分：開盤到收盤重建版")
    print("#" * 70)
    main_o2c()
