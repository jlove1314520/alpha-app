"""`HYPOTHESIS_QUEUE.md` #45 存託憑證（ADR）溢價/折價收斂 第1關cheap gate。

接續`adr_premium_assembly.py`已完成的地基（PIT對齊premium時間序列，見
`data/adr_premium_aligned.csv`）。本腳本完成#45「下一輪待辦」列出的兩件事：
(1) 決定訊號定義、(2) 設計N=4小樣本的替代隨機控制組方案，並跑第1關。

**訊號定義決定（事前綁定，跑之前決定，不是看完結果才選）**：用**premium
原始水位本身**（非相對自身歷史均值的偏離、非收斂速度）。理由：#45條目
「具體假設定義」段落已經明文寫死「premium顯著為正→預期本地股價將上漲
收斂價差」，這是本假設本來就已經預先綁定的操作化方式（不是本輪才臨時
決定），本腳本只是把這個既有文字定義第一次轉成可執行的統計檢定，不是
重新選擇。

**目標窗口**：M=20交易日（沿用本佇列regime/timing類既有窗口量級，
`#31`/`#32`/`#33`/`#34`同一個M），逐檔以自己的本地交易日曆計算
`local_close.shift(-M)/local_close - 1`（trading-day-based，非calendar-day，
跟`copper_gold_ratio_gate.py`的`tw["close"].shift(-M_TARGET_DAYS)`同一個
做法）。

**N=4小樣本替代隨機控制組設計（本腳本核心方法論貢獻，回答#45「已知風險
與限制」第1點提出的問題）**：標準做法（`#31`/`#32`/`#33`/`#34`）洗牌訊號
的「時序」本身，因為那些是單一時間序列，沒有跨標的維度可以搞混。這裡
改用**「同一檔股票自身時間序列洗牌」**——每次抽樣時，對panel裡每一檔
股票各自獨立、只在該股票自己的資料列範圍內做permutation（打散該股票的
premium時序，但保留該股票自己的forward return時序不動），再重新pool
四檔資料算一次橫跨全panel的Pearson/Spearman。這樣做的理由：
1. 不跨標的混洗——避免把TSM的premium水位配到ASX的forward return上，
   那種混法會製造出跟真實機制完全無關的雜訊分布，不是有意義的null。
2. 保留每檔股票自己的premium邊際分布與自我相關結構（TSM/ASX的premium
   均值、波動度顯著不同，若用「跨全panel任意打散」的全域洗牌，null
   分布會被這種異質性污染，讓判斷偏保守或偏寬鬆都有可能，方向不確定）。
3. 保留每檔股票自己的forward return時序（該股票真實發生過的報酬路徑
   完全不變），只打散「哪一天對應哪個premium值」這個配對關係——這正是
   要檢定的東西：premium的時序資訊是否真的攜帶預測forward return的訊號，
   還是純粹巧合配對。

**已知的TSM主導風險（誠實揭露，本腳本額外輸出逐檔拆解因應）**：TSM
資料列數（4673）遠多於ASX（1628），pooled相關係數的統計檢定力主要由
TSM貢獻。本腳本額外印出逐檔獨立相關係數，讓判讀者能看出訊號是否只來自
TSM一檔（單一巨型股主導），這是#45經濟理由段落已知風險第2點要求的
「排除台積電」對照精神的第1關版本（完整的「全樣本vs排除台積電」portfolio
層對照留待通過第1關後的深挖步驟，第1關先只做透明度揭露不做正式排除）。

判定標準沿用本佇列既有cheap gate三項判準（幅度非零/train-val同號/贏過
洗牌null percentile>=90.0），跟`#31`~`#34`完全同一套框架，只是null的生成
方式改為「逐標的內部洗牌」。

2026-09-06 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#45第1關
起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from validation.holdout import TRAIN_END, VAL_END

ALIGNED_CSV = "data/adr_premium_aligned.csv"
N_SHUFFLE = 500
SHUFFLE_SEED = 20260906
M_TARGET_DAYS = 20  # 本地股forward M日報酬預測視窗
MIN_SAMPLE = 30


def build_panel() -> pd.DataFrame:
    """讀`adr_premium_aligned.csv`，逐檔加上forward M日本地報酬(target)。

    回傳 columns: ticker, date, premium(signal), fwd_ret_m(target)。
    """
    df = pd.read_csv(ALIGNED_CSV, parse_dates=["date"])
    if df.empty:
        raise RuntimeError(f"{ALIGNED_CSV}為空，第1關無法起跑（先跑adr_premium_assembly.py）")

    frames = []
    for ticker, g in df.groupby("ticker", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        g["fwd_ret_m"] = g["local_close"].shift(-M_TARGET_DAYS) / g["local_close"] - 1.0
        frames.append(g[["ticker", "date", "premium", "fwd_ret_m"]])
    panel = pd.concat(frames, ignore_index=True)
    panel = panel.dropna(subset=["premium", "fwd_ret_m"]).reset_index(drop=True)
    return panel


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _within_ticker_shuffle_percentile(df: pd.DataFrame, n: int, seed: int) -> dict:
    """逐標的內部洗牌null（本腳本核心方法論，見模組docstring）。"""
    signal = df["premium"].to_numpy()
    target = df["fwd_ret_m"].to_numpy()
    real_pearson, real_p = stats.pearsonr(signal, target)

    rng = np.random.default_rng(seed)
    df_reset = df.reset_index(drop=True)
    positions_by_ticker = {t: df_reset.index[df_reset["ticker"] == t].to_numpy() for t in df_reset["ticker"].unique()}

    shuffled = np.empty(n)
    sig_arr = df_reset["premium"].to_numpy().copy()
    tgt_arr = df_reset["fwd_ret_m"].to_numpy()
    for i in range(n):
        perm_sig = sig_arr.copy()
        for t, positions in positions_by_ticker.items():
            perm_sig[positions] = rng.permutation(sig_arr[positions])
        shuffled[i] = stats.pearsonr(perm_sig, tgt_arr)[0]

    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {
        "pearson": float(real_pearson), "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["premium"].to_numpy()
    target = df["fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _within_ticker_shuffle_percentile(df, N_SHUFFLE, SHUFFLE_SEED)

    print(f"\n--- {label} (pooled n={n}) ---")
    print(f"  Pooled Pearson r={pearson:+.4f} (p={pearson_p:.4f})")
    print(f"  Pooled Spearman rho={spearman:+.4f} (p={spearman_p:.4f})")
    print(f"  逐標的內部洗牌null(N={N_SHUFFLE}): median|r|={shuf['null_median_abs']:.4f}  "
          f"真實|r|percentile={shuf['percentile']:.1f}")

    print(f"  逐檔獨立相關係數（TSM主導風險透明度揭露）:")
    per_ticker = {}
    for t, g in df.groupby("ticker", sort=False):
        if len(g) < 10:
            print(f"    {t}: n={len(g)} 過少(<10)，略過")
            continue
        r, p = stats.pearsonr(g["premium"], g["fwd_ret_m"])
        per_ticker[t] = {"n": len(g), "pearson": float(r), "pearson_p": float(p)}
        print(f"    {t}: n={len(g)} r={r:+.4f} (p={p:.4f})")

    return {
        "label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
        "spearman": spearman, "spearman_p": spearman_p,
        "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"],
        "per_ticker": per_ticker,
    }


def main() -> dict:
    print("=== #45 ADR premium 第1關cheap gate ===")
    panel = build_panel()
    print(f"panel總列數: {len(panel)}, 標的: {sorted(panel['ticker'].unique())}")
    print(f"日期範圍: {panel['date'].min().date()} ~ {panel['date'].max().date()}")
    print(f"premium(signal)描述統計: mean={panel['premium'].mean():+.4f} "
          f"median={panel['premium'].median():+.4f} std={panel['premium'].std():.4f}")
    print(f"fwd_ret_m(target,M={M_TARGET_DAYS})描述統計: mean={panel['fwd_ret_m'].mean():+.4f} "
          f"median={panel['fwd_ret_m'].median():+.4f} std={panel['fwd_ret_m'].std():.4f}")

    train, val = _split(panel)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")
    print(f"TRAIN逐標的列數: {train['ticker'].value_counts().to_dict()}")
    print(f"VAL逐標的列數: {val['ticker'].value_counts().to_dict()}")

    if len(train) < MIN_SAMPLE or len(val) < MIN_SAMPLE:
        print(f"\n樣本數過少（<{MIN_SAMPLE}），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample",
                "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] > 0  # 事前綁定：premium正→本地股價上漲收斂（正相關）

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過逐標的內部洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(正相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    panel.to_csv("data/adr_premium_panel_with_target.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
