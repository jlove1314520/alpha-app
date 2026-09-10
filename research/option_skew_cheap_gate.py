"""`HYPOTHESIS_QUEUE.md` #70 選擇權波動度偏斜（Volatility Skew）第1關cheap
gate：skew vs 後續報酬相關性檢定。

**本輪範疇**：地基建置(a)(b)(c)(d)已於前幾輪完成（`option_skew_gate.py`
已產出`data/option_skew_series.csv`，2428個交易日100%成功組出skew）。本輪
直接讀那份既有輸出，**零新增API呼叫**，比照`#31`(`option_pcr_gate.py`)/
`#69`(`option_oi_pcr_gate.py`)同款時序相關性框架，完成第1關cheap gate。

**跟`#31`/`#69`的框架差異**：`#31`/`#69`都只測次一交易日（N=1）報酬，本假設
`HYPOTHESIS_QUEUE.md` #70條目「具體假設定義」明確寫「後續N=5、N=20交易日
報酬」（複數horizon），事前決定**兩個horizon都獨立完整跑一次判準，且都必須
過關才算CHEAP_PASS**——這不是憑空加嚴：`C:\\alpha\\alpha-app\\CLAUDE.md`
七之三節新增第7關「相鄰頻率一致性」明文要求「一個頻率好、鄰近頻率翻負即判
雜訊」，N=5跟N=20正是`#70`自己在跑任何數字之前就寫定的兩個相鄰horizon，
用同一把尺檢查比事後只挑一個好看的horizon誠實，此決定在本輪執行前寫入本
docstring，不是看到數字後才追加的條件。

**時序對齊（無未來函數）**：skew在date（signal_date）當天收盤後才完整可得
（`option_skew_gate.py`已用`settlement_price`，這是收盤後才確定的結算價），
預測從signal_date**之後**第1個交易日起算的N=5、N=20交易日累積報酬（即
t+1~t+N，不含t當天，因為t當天skew訊號要收盤才知道，無法在t當天就用它交易）。

**事前綁定方向（複述`#70`條目，不給彈性，比照`#66`/`#69`處理方式）**：
Skew（put_iv−call_iv）與後續報酬呈**負向**IC——skew越陡（下檔避險需求
越濃），後續報酬越差，比照Xing et al. (2010)原始文獻方向。train/val皆須
同號**且方向為負**才算方向假設成立。

**判準（比照`#69`同款四項，兩個horizon各自獨立判定，全數通過才CHEAP_PASS）**：
1. 幅度非零（|Pearson r|>0.01兩期）
2. train/val同號
3. 事前綁定方向為負，兩期皆須為負號
4. VAL贏過洗牌null（N=500，percentile>=90.0）

2026-09-10由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#70第1關cheap
gate。資料來源：`data/option_skew_series.csv`（`option_skew_gate.py`既有
輸出，本輪零重算）、`yf_price_client`既有`^TWII`快取。本次執行**零新增API
呼叫**。`is_holdout_consumed()`開工/收工前皆確認`False`。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END, is_holdout_consumed

N_SHUFFLE = 500
SHUFFLE_SEED = 20260910
HORIZONS = (5, 20)  # 交易日，事前綁定，見docstring理由


def load_skew_series() -> pd.DataFrame:
    df = pd.read_csv("data/option_skew_series.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "skew"]].sort_values("date").reset_index(drop=True)


def build_aligned_series(horizon: int) -> pd.DataFrame:
    """對每個skew訊號日t，配對「t+1到t+horizon（含）」的台股累積報酬（不
    含t當天，避免未來函數）。回傳columns: signal_date, target_start_date,
    target_end_date, skew, fwd_ret。"""
    skew_df = load_skew_series()
    tw = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").reset_index(drop=True)

    tw_dates = tw["date"].to_numpy()
    tw_close = tw["close"].to_numpy()
    n_tw = len(tw_dates)

    rows = []
    for _, r in skew_df.iterrows():
        sig_date = np.datetime64(r["date"])
        # idx_start: 第一個嚴格晚於sig_date的台股交易日索引（t+1）
        idx_start = int(np.searchsorted(tw_dates, sig_date, side="right"))
        idx_end = idx_start + horizon - 1  # 累積到第N個交易日（含）
        if idx_end >= n_tw:
            continue  # 尾端資料不足N天，捨棄（不強湊）
        start_close = tw_close[idx_start - 1] if idx_start > 0 else np.nan
        if idx_start == 0 or pd.isna(start_close):
            continue
        end_close = tw_close[idx_end]
        fwd_ret = float(end_close / start_close - 1.0)
        rows.append({
            "signal_date": r["date"],
            "target_start_date": pd.Timestamp(tw_dates[idx_start]),
            "target_end_date": pd.Timestamp(tw_dates[idx_end]),
            "skew": float(r["skew"]),
            "fwd_ret": fwd_ret,
        })
    return pd.DataFrame(rows)


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["target_end_date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["target_end_date"] > pd.Timestamp(TRAIN_END)) & (df["target_end_date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(skew: np.ndarray, ret: np.ndarray, n: int, seed: int) -> dict:
    real_pearson, real_p = stats.pearsonr(skew, ret)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(skew)
        shuffled[i] = stats.pearsonr(perm, ret)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson), "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))), "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    skew = df["skew"].to_numpy()
    ret = df["fwd_ret"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(skew, ret)
    spearman, spearman_p = stats.spearmanr(skew, ret)
    shuf = _shuffle_percentile(skew, ret, N_SHUFFLE, SHUFFLE_SEED)
    print(f"    {label} (n={n}): Pearson r={pearson:+.4f} (p={pearson_p:.4f})  "
          f"Spearman rho={spearman:+.4f} (p={spearman_p:.4f})  "
          f"洗牌null(N={N_SHUFFLE}) median|r|={shuf['null_median_abs']:.4f}  "
          f"真實|r|percentile={shuf['percentile']:.1f}")
    return {
        "label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
        "spearman": spearman, "spearman_p": spearman_p,
        "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"],
    }


def run_horizon(horizon: int) -> dict:
    print(f"\n=== horizon N={horizon}交易日 ===")
    aligned = build_aligned_series(horizon)
    print(f"  對齊後總配對數: {len(aligned)}")
    if not aligned.empty:
        print(f"  訊號日範圍: {aligned['signal_date'].min().date()} ~ {aligned['signal_date'].max().date()}")
        gap = (aligned["target_start_date"] - aligned["signal_date"]).dt.days
        assert gap.min() >= 1, "發現target_start_date沒有嚴格晚於signal_date，時序對齊有bug"
        span = (aligned["target_end_date"] - aligned["target_start_date"]).dt.days
        print(f"  訊號日到目標起始日的日曆天數差: min={gap.min()} max={gap.max()}")

    train, val = _split(aligned)
    print(f"  TRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("  樣本數過少（<30），判定FAIL（結構性資料不足）")
        return {"horizon": horizon, "verdict": "FAIL", "reason": "insufficient_sample",
                "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN(<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL({TRAIN_END}~{VAL_END})")

    same_sign = (train_result["pearson"] < 0) == (val_result["pearson"] < 0)
    both_negative = train_result["pearson"] < 0 and val_result["pearson"] < 0
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0

    print(f"  判準1.幅度非零(|r|>0.01兩期): {nontrivial}")
    print(f"  判準2.train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  判準3.事前綁定方向為負、兩期皆須為負號: {both_negative}")
    print(f"  判準4.VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")

    horizon_pass = same_sign and both_negative and nontrivial and beats_null
    print(f"  horizon N={horizon}判定: {'CHEAP_PASS' if horizon_pass else 'FAIL'}")

    return {"horizon": horizon, "verdict": "CHEAP_PASS" if horizon_pass else "FAIL",
            "train": train_result, "val": val_result,
            "same_sign": same_sign, "both_negative": both_negative,
            "nontrivial": nontrivial, "beats_null": beats_null}


def main() -> dict:
    print("=== #70選擇權波動度偏斜（Volatility Skew）第1關cheap gate ===")
    print(f"事前綁定：skew與後續N交易日報酬呈負向IC，N in {HORIZONS}，兩個horizon皆須")
    print("獨立通過四項判準才算CHEAP_PASS（複述docstring：比照CLAUDE.md第7關相鄰頻率")
    print("一致性精神，避免只挑好看的單一horizon）")
    assert not is_holdout_consumed(), "holdout已被消耗，本輪異常中止"

    results = [run_horizon(h) for h in HORIZONS]
    all_pass = all(r["verdict"] == "CHEAP_PASS" for r in results)
    overall = "CHEAP_PASS" if all_pass else "FAIL"

    print("\n=== 總結 ===")
    for r in results:
        print(f"  N={r['horizon']}: {r['verdict']}")
    print(f"\n總判定（兩horizon皆須CHEAP_PASS）: {overall}")

    assert not is_holdout_consumed(), "holdout已被消耗，本輪異常中止"
    return {"horizons": results, "verdict": overall}


if __name__ == "__main__":
    result = main()
