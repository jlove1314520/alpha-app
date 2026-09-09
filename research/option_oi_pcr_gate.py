"""`HYPOTHESIS_QUEUE.md` #69 台指選擇權買賣權比（Put/Call Ratio）逆向情緒
訊號 第1關cheap gate。

經濟理由：行為財務文獻記載選擇權市場的Put/Call Ratio（買賣權未平倉量或
成交量比值）是常用的市場情緒逆向指標——當Put/Call比異常偏高，代表市場
參與者（尤其散戶/避險需求）過度悲觀，若此類參與者傾向在極端情緒時判斷
錯誤（over-reaction），則高比值後續應predict指數反彈（逆向指標）。跟
`#31`(`option_pcr_gate.py`，用**成交量volume**口徑)是同一份原始資料
（FinMind `TaiwanOptionDaily`），但這裡改用**未平倉量open_interest**口徑
——成交量反映當日新增部位流量，未平倉量反映**部位存量**（累積至今仍未
平倉的方向性下注/避險部位規模），兩者理論意涵不同，不是同一假設換皮。
完整經濟理由/事前綁定定義見`HYPOTHESIS_QUEUE.md` #69條目。

**跟`#64`（期貨基差）的區別**：#64測的是台指期貨基差（現貨-期貨價差，
carry/持有成本訊號），本假設測的是選擇權未平倉量的多空比例分布（衍生性
商品參與者情緒訊號），資料維度與經濟意涵完全不同。若第1關過關，deep_dive
需檢查跟`#31`(pcr成交量版)的相關係數，若>0.7需依「同家族因子只能算一個
獨立發現」鐵律處理（兩者本來就同源自TaiwanOptionDaily，需特別留意）。

**時序對齊邏輯（避免未來函數，完全比照`#31`)**：用「第t日收盤後才完整
可得」的未平倉量Put/Call比率，預測「第t+1日」台股報酬（次一交易日）。

**trading_session口徑決定（完全比照`#31`的既有結論，零重新摸索）**：
只用`trading_session`==`position`（日盤）資料——`夜盤`資料從2017年年中
才開始出現，若含入會讓訊號在TRAIN期前段（2015-2016）跟後段計算口徑不
一致，形成人為的結構斷點。`#69`資料可行性查證已確認`open_interest`欄位
只在`position`（日盤）session才有值（`after_market`夜盤全數為零，跟
`FUT_STATE_ARCHIVE.md`記錄的`TaiwanFuturesDaily`結論一致）——所以這裡
的`position`過濾**同時是方法論選擇也是資料結構要求**，兩個理由疊加。

**事前綁定方向（跟`#31`不同，`#69`明確寫死不給彈性）**：本假設定義文字
明確寫定Put/Call比與後續報酬呈**正向**IC（比值越高代表悲觀情緒濃，若
逆向理論成立，後續報酬應該越高）。cheap gate除了「train/val同號」，
**還要求同號的那個號必須是正號**才算方向假設成立——不像`#31`（文獻方向
本身有分歧，不預先綁定正負號）或`#67`（雙向皆測、何者顯著決定方向），
本假設比照`#66`稅損收割的處理方式，不給方向事後彈性。

2026-09-10 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#69第1關
起跑。資料來源：`research/data/raw/TaiwanOptionDaily__TXO__*.parquet`
既有快取（`#31`留下，2015-01-01~2024-12-31全期間齊全），本次執行**零
新增API呼叫**。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from finmind_client import load_dev
from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260910
OPTION_ID = "TXO"
OPTION_START = "2015-01-01"


def build_oi_pcr_series() -> pd.DataFrame:
    """回傳 columns: date(Timestamp), put_oi, call_oi, oi_pcr。只用
    `trading_session`==`position`（日盤）未平倉量，理由見docstring方法論
    決定段落。逐年分批抓取（沿用`#31`已發現的必要調整，避免跨10年單次
    呼叫觸發FinMind 502）。"""
    frames = []
    start_year = int(OPTION_START[:4])
    end_year = int(VAL_END[:4])
    for yr in range(start_year, end_year + 1):
        yr_start = f"{yr}-01-01"
        yr_end = f"{yr}-12-31"
        chunk = load_dev("TaiwanOptionDaily", OPTION_ID, yr_start, end_date=yr_end, date_col="date")
        if not chunk.empty:
            frames.append(chunk)
    if not frames:
        raise RuntimeError(f"TaiwanOptionDaily({OPTION_ID})逐年抓取後仍全數空資料，第1關無法起跑")
    opt = pd.concat(frames, ignore_index=True)
    opt = opt[opt["trading_session"] == "position"].copy()
    opt["date"] = pd.to_datetime(opt["date"])
    opt["open_interest"] = pd.to_numeric(opt["open_interest"], errors="coerce")
    opt = opt.dropna(subset=["open_interest"])

    grouped = opt.groupby(["date", "call_put"])["open_interest"].sum().unstack(fill_value=0.0)
    for col in ("put", "call"):
        if col not in grouped.columns:
            grouped[col] = 0.0
    grouped = grouped.reset_index().rename(columns={"put": "put_oi", "call": "call_oi"})
    # call_oi==0的日子(理論上不該發生，但防呆)丟棄，避免除以零
    grouped = grouped[grouped["call_oi"] > 0].copy()
    grouped["oi_pcr"] = grouped["put_oi"] / grouped["call_oi"]
    return grouped[["date", "put_oi", "call_oi", "oi_pcr"]].sort_values("date").reset_index(drop=True)


def build_aligned_series() -> pd.DataFrame:
    """對每個台股交易日t+1，配對「t日（t+1前一個交易日）」的未平倉量
    Put/Call比率跟台股t+1日報酬。回傳 columns: signal_date, tw_date,
    oi_pcr, tw_ret。"""
    pcr_df = build_oi_pcr_series()
    tw = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").reset_index(drop=True)
    tw["ret"] = tw["close"].pct_change()

    merged = pcr_df.rename(columns={"date": "signal_date"})
    tw_dates = tw["date"].to_numpy()
    tw_rets = tw["ret"].to_numpy()

    rows = []
    for _, r in merged.iterrows():
        sig_date = np.datetime64(r["signal_date"])
        idx = np.searchsorted(tw_dates, sig_date, side="right")
        if idx >= len(tw_dates):
            continue
        target_ret = tw_rets[idx]
        if pd.isna(target_ret):
            continue
        rows.append({
            "signal_date": r["signal_date"],
            "tw_date": pd.Timestamp(tw_dates[idx]),
            "oi_pcr": float(r["oi_pcr"]),
            "tw_ret": float(target_ret),
        })
    out = pd.DataFrame(rows)
    return out


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["tw_date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["tw_date"] > pd.Timestamp(TRAIN_END)) & (df["tw_date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(pcr: np.ndarray, tw_ret: np.ndarray, n: int, seed: int) -> dict:
    real_pearson, real_p = stats.pearsonr(pcr, tw_ret)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(pcr)
        shuffled[i] = stats.pearsonr(perm, tw_ret)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson),
        "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    pcr = df["oi_pcr"].to_numpy()
    tw_ret = df["tw_ret"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(pcr, tw_ret)
    spearman, spearman_p = stats.spearmanr(pcr, tw_ret)
    shuf = _shuffle_percentile(pcr, tw_ret, N_SHUFFLE, SHUFFLE_SEED)
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
    print(f"訊號日範圍: {aligned['signal_date'].min()} ~ {aligned['signal_date'].max()}")
    print(f"目標台股交易日範圍: {aligned['tw_date'].min()} ~ {aligned['tw_date'].max()}")
    print(f"OI-PCR描述統計: mean={aligned['oi_pcr'].mean():.4f} median={aligned['oi_pcr'].median():.4f} "
          f"std={aligned['oi_pcr'].std():.4f} min={aligned['oi_pcr'].min():.4f} max={aligned['oi_pcr'].max():.4f}")
    # sanity: 確認tw_date確實嚴格晚於signal_date（無未來函數）
    gap = (aligned["tw_date"] - aligned["signal_date"]).dt.days
    print(f"訊號日到目標台股交易日的日曆天數差: min={gap.min()} max={gap.max()} median={gap.median()}")
    assert gap.min() >= 1, "發現tw_date沒有嚴格晚於signal_date，時序對齊有bug"

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    both_positive = train_result["pearson"] > 0 and val_result["pearson"] > 0
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0

    print("\n=== 第1關cheap gate判準（本假設事前綁定方向為正，比#31更嚴格）===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. 事前綁定方向為正、兩期皆須為正號: {both_positive}")
    print(f"  4. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")

    verdict = "CHEAP_PASS" if (same_sign and both_positive and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/option_oi_pcr_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict}


if __name__ == "__main__":
    main()
