"""`HYPOTHESIS_QUEUE.md` #42 個股間平均成對相關係數（Average Pairwise
Correlation）當系統性風險regime訊號 第1關cheap gate（2026-09-06）。

經濟理由：Longin & Solnik(1995)記錄過「市場下跌/系統性風險上升時，個股
報酬傾向一起動、相關係數飆高」的現象（CBOE Implied Correlation Index的
設計動機也是量化這個現象）。跟本佇列前面11條已死的timing/regime假設
（#10/#15/#26/#28/#30/#31/#32/#33/#34/#35/#37）不同，那些全部是「單一
外部序列的水位/成長率」，這條看的是整個股票宇宙內部的橫斷面共同運動
結構（個股報酬彼此的平均成對相關係數），是第三種資料建構維度。完整
經濟理由/已知相關背景/資料可行性見`HYPOTHESIS_QUEUE.md` #42條目。

**訊號定義**：對既有300檔快取宇宙（跟`factor_ic.py`同一個seed/樣本數，
複用同一批`adjusted_price_series`快取，零額外資料需求），用trailing
N=60個交易日窗口計算逐日報酬的「平均成對相關係數」（上三角不含對角線的
簡單平均，不是vol加權的隱含相關性），只採用該窗口內完全無缺值的股票
（避免上市未滿一年/下市前資料稀疏造成的標準化污染）。

**計算方法（O(N*W)而非O(N^2*W)，避免逐對計算的高成本）**：用標準化
恆等式——窗口內把每檔股票的報酬做z-score標準化(ddof=1)，則
avg_corr = [sum_s(sum_i z_i,s)^2 - N*(W-1)] / [N*(N-1)*(W-1)]
（推導：sum_i sum_{i≠j} z_i,s*z_j,s，對窗口內每天s加總，除以正規化項；
每檔股票自身sum_s z_i,s^2 = W-1(標準化後的恆等式)，故可用交叉截面總和
的平方一次算出所有股票對的相關係數和，不需要真的算300x300矩陣）。

訊號本身是這個平均相關係數相對自身trailing 60個交易日窗口（含當日）的
百分位排名（0~1，越高代表越異常偏高），跟`day_trading_ratio_gate.py`/
`vrp_gate.py`同一套「原始值→trailing百分位」轉換方式。

**目標變數**：訊號日之後（不含當日）N=20個交易日TAIEX累積報酬。

**時序對齊**：訊號用t日收盤後才完整可得的逐日報酬資料，預測t日之後的
未來窗口，不解釋t日當天，無未來函數。

**事前綁定方向**：負（`HYPOTHESIS_QUEUE.md` #42「相關係數異常升高→未來
報酬預期轉差」）。

**判定標準（跟本佇列既有cheap gate三項判準同一套框架，比照
`day_trading_ratio_gate.py`）**：TRAIN=[universe起點, TRAIN_END]、
VAL=(TRAIN_END, VAL_END]（既有`validation/holdout.py`邊界），Spearman
相關係數，N=200次時序洗牌null（打散訊號時序、保留TAIEX報酬時序）。

2026-09-06由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，本輪從第1關
cheap gate開始，不跳關。
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from universe import universe as build_universe
from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

TRAIL_WINDOW = 60
FORWARD_HORIZON = 20
N_SHUFFLE = 200
SHUFFLE_SEED = 20260906
MIN_ABS_CORR = 0.02
EXPECTED_SIGN = -1  # 事前綁定：平均相關係數異常偏高 -> 未來報酬應偏差（負相關）
SAMPLE_SIZE = 300
SAMPLE_SEED = 20260822  # 跟factor_ic.py同一批300檔宇宙，複用既有價格快取，不重抓
START_DATE = "2010-01-01"
MIN_STOCKS_PER_DATE = 30


def _sample_universe_ids() -> list[str]:
    uni = build_universe()
    ids = sorted(uni["stock_id"].unique().tolist())
    rng = random.Random(SAMPLE_SEED)
    rng.shuffle(ids)
    return ids[:SAMPLE_SIZE]


def _load_return_matrix(stock_ids: list[str]) -> pd.DataFrame:
    """回傳wide DataFrame（index=date，columns=stock_id）of逐日簡單報酬。"""
    series = {}
    for i, sid in enumerate(stock_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一套容錯
            print(f"  [{i + 1}/{len(stock_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < TRAIL_WINDOW + 5:
            continue
        s = px.set_index("date")["adj_close"].sort_index()
        series[sid] = s.pct_change()
    if not series:
        raise RuntimeError("no valid stock return series loaded")
    wide = pd.DataFrame(series)
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def compute_avg_pairwise_corr(
    ret: pd.DataFrame, window: int = TRAIL_WINDOW, min_stocks: int = MIN_STOCKS_PER_DATE
) -> pd.Series:
    """對每個日期t（trailing window結束於t），用z-score恆等式算平均成對
    相關係數，只採用該窗口內完全無缺值的股票，避免逐對O(N^2)計算成本
    （見模組docstring推導）。"""
    dates = ret.index
    values = ret.to_numpy()
    n_dates = values.shape[0]
    out = np.full(n_dates, np.nan)
    valid_mask = ~np.isnan(values)
    for t in range(window - 1, n_dates):
        wslice = values[t - window + 1 : t + 1, :]
        vmask = valid_mask[t - window + 1 : t + 1, :]
        complete_cols = vmask.all(axis=0)
        n_ok = int(complete_cols.sum())
        if n_ok < min_stocks:
            continue
        sub = wslice[:, complete_cols]
        mean = sub.mean(axis=0)
        std = sub.std(axis=0, ddof=1)
        std_safe = np.where(std > 0, std, np.nan)
        z = (sub - mean) / std_safe
        z = np.nan_to_num(z, nan=0.0)
        q = z.sum(axis=1)
        sum_q2 = float(np.sum(q**2))
        denom = n_ok * (n_ok - 1) * (window - 1)
        if denom <= 0:
            continue
        out[t] = (sum_q2 - n_ok * (window - 1)) / denom
    return pd.Series(out, index=dates, name="avg_pairwise_corr")


def _rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """對每個位置i（i>=window-1），回傳values[i]在values[i-window+1:i+1]
    這個窗口內的百分位排名（0~1，1=窗口內最大值）。窗口不足回傳NaN。"""
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        w = values[i - window + 1 : i + 1]
        out[i] = float((w <= values[i]).sum() - 1) / (window - 1)
    return out


def build_signal_series() -> pd.DataFrame:
    print(f"抽樣{SAMPLE_SIZE}檔股票（seed={SAMPLE_SEED}，跟factor_ic.py同一批宇宙）...")
    stock_ids = _sample_universe_ids()
    print("載入逐日報酬（複用既有價格快取）...")
    ret = _load_return_matrix(stock_ids)
    print(f"報酬矩陣: {ret.shape[0]}個交易日 x {ret.shape[1]}檔股票")

    avg_corr = compute_avg_pairwise_corr(ret)
    df = avg_corr.dropna().reset_index()
    df.columns = ["date", "avg_corr"]
    df["avg_corr_pctile"] = _rolling_percentile_rank(df["avg_corr"].to_numpy(), TRAIL_WINDOW)
    return df.dropna(subset=["avg_corr_pctile"])


def build_aligned_series() -> pd.DataFrame:
    sig = build_signal_series()
    taiex = fetch_yf_index(ticker="^TWII", start_date=START_DATE)
    taiex = taiex.dropna(subset=["close"]).copy()
    taiex["date"] = pd.to_datetime(taiex["date"])
    taiex = taiex.sort_values("date").reset_index(drop=True)
    tw_dates = taiex["date"].to_numpy()
    tw_close = taiex["close"].to_numpy()

    rows = []
    for _, r in sig.iterrows():
        sig_date = np.datetime64(r["date"])
        start_idx = int(np.searchsorted(tw_dates, sig_date, side="right"))
        end_idx = start_idx + FORWARD_HORIZON - 1
        if end_idx >= len(tw_dates):
            continue
        fwd_ret = tw_close[end_idx] / tw_close[start_idx] - 1.0
        rows.append(
            {
                "date": r["date"],
                "avg_corr": float(r["avg_corr"]),
                "avg_corr_pctile": float(r["avg_corr_pctile"]),
                "fwd_ret": float(fwd_ret),
            }
        )
    return pd.DataFrame(rows)


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_corr, real_p = spearmanr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i], _ = spearmanr(perm, target)
    # 單邊檢定：事前綁定方向為負，看真實corr有多小（比洗牌null更負的比例）
    pctl = 100.0 * float(np.mean(shuffled >= real_corr))
    return {
        "real_corr": float(real_corr),
        "real_p": float(real_p),
        "null_median": float(np.median(shuffled)),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["avg_corr_pctile"].to_numpy()
    target = df["fwd_ret"].to_numpy()
    n = len(df)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Spearman(avg_corr_pctile, fwd_ret_{FORWARD_HORIZON}d) = {shuf['real_corr']:+.4f} (p={shuf['real_p']:.4f})")
    print(
        f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.4f}  "
        f"真實corr percentile(單邊，越低代表越顯著負相關)={shuf['percentile']:.1f}"
    )
    return {
        "label": label,
        "n": n,
        "corr": shuf["real_corr"],
        "p": shuf["real_p"],
        "null_median": shuf["null_median"],
        "null_percentile": shuf["percentile"],
    }


def main():
    print("=== #42 個股間平均成對相關係數 regime 訊號 第1關cheap gate ===")
    aligned = build_aligned_series()
    print(f"對齊後總配對數: {len(aligned)}")
    if aligned.empty:
        print("\n無有效對齊資料，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "no_aligned_data"}
    print(f"訊號日範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(
        f"平均成對相關係數描述統計: mean={aligned['avg_corr'].mean():.4f} "
        f"median={aligned['avg_corr'].median():.4f} std={aligned['avg_corr'].std():.4f} "
        f"min={aligned['avg_corr'].min():.4f} max={aligned['avg_corr'].max():.4f}"
    )

    if len(aligned) < 60:
        print("\n樣本數過少（<60），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "n": len(aligned)}

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30任一期），判定FAIL（結構性資料不足）")
        return {
            "verdict": "FAIL",
            "reason": "insufficient_sample_split",
            "train_n": len(train),
            "val_n": len(val),
        }

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    train_sign_ok = (train_result["corr"] < 0) == (EXPECTED_SIGN < 0)
    val_sign_ok = (val_result["corr"] < 0) == (EXPECTED_SIGN < 0)
    same_sign_as_expected = train_sign_ok and val_sign_ok
    nontrivial = abs(train_result["corr"]) > MIN_ABS_CORR and abs(val_result["corr"]) > MIN_ABS_CORR
    beats_null = val_result["null_percentile"] <= 10.0  # 單邊：越低代表越顯著負於null

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
    print(
        f"  2. train/val皆符合事前綁定負相關方向: {same_sign_as_expected} "
        f"(TRAIN corr={train_result['corr']:+.4f}, VAL corr={val_result['corr']:+.4f})"
    )
    print(
        f"  3. VAL贏過洗牌null(單邊percentile<=10.0): {beats_null} "
        f"(percentile={val_result['null_percentile']:.1f})"
    )

    verdict = "CHEAP_PASS" if (nontrivial and same_sign_as_expected and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv(Path(__file__).parent / "data" / "avg_pairwise_correlation_aligned.csv", index=False)
    return {
        "train": train_result,
        "val": val_result,
        "verdict": verdict,
        "n_total": len(aligned),
        "train_n": len(train),
        "val_n": len(val),
    }


if __name__ == "__main__":
    main()
