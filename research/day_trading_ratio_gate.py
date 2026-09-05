"""`HYPOTHESIS_QUEUE.md` #37 全市場現股當沖比重當市場過熱regime訊號
第1關cheap gate（2026-09-06）。

經濟理由：現股當沖集中反映短線投機客/散戶交易熱度，Barber, Lee, Liu,
Odean（2009，用台灣資料）已證實台灣當沖客整體是系統性虧損的noise
trader，當沖活動異常飆高常見於市場見頂前夕（追高殺低、投機亢奮）。
完整經濟理由見`HYPOTHESIS_QUEUE.md` #37條目。

**訊號定義**：全市場當沖比重 = day_trade_volume（TWTASU「當沖賣出成交
數量+資券互抵成交數量」，見`twse_day_trading_client.py`docstring方法論
假設）/ total_volume（FMTQIK全市場成交股數，見
`twse_market_volume_client.py`）。訊號本身是該日比重相對trailing 60個
交易日（含當日，window內自身歷史）的百分位排名（0~1，越高代表越異常
偏高）。

**目標變數**：訊號日之後（不含當日）N=20個交易日TAIEX累積報酬。

**時序對齊**：訊號用t日收盤後才完整可得的資料（TWTASU/FMTQIK皆是當日
盤後公布），預測t日之後的未來窗口，不用來解釋t日當天，無未來函數。

**事前綁定方向**：負（`HYPOTHESIS_QUEUE.md` #37「事前綁定方向為負」）
——比重相對自身歷史越異常偏高，代表投機越過熱，預期後續N日報酬越差。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號
且方向為負/贏過洗牌null，跟`option_pcr_gate.py`/`margin_debt_growth_gate.py`
同一套框架）**：TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]
（既有`validation/holdout.py`邊界），Spearman相關係數，N=200次時序洗牌
null（打散訊號時序、保留TAIEX報酬時序）。

2026-09-06 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，TWTASU/FMTQIK
回補完成（2609/2609，100%）後第1關起跑。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

DT_DIR = Path(__file__).parent / "data" / "raw_twse_day_trading"
MV_DIR = Path(__file__).parent / "data" / "raw_twse_market_volume"

TRAIL_WINDOW = 60
FORWARD_HORIZON = 20
N_SHUFFLE = 200
SHUFFLE_SEED = 20260906
MIN_ABS_CORR = 0.02
EXPECTED_SIGN = -1  # 事前綁定：比重異常偏高 -> 未來報酬應偏差（負相關）


def _load_day_trading_volume() -> pd.DataFrame:
    files = sorted(DT_DIR.glob("TWTASU_*.parquet"))
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["day_trade_sell_volume"])
    df["date"] = pd.to_datetime(df["date"])
    df["day_trade_volume"] = (
        df["day_trade_sell_volume"].fillna(0.0) + df["margin_offset_volume"].fillna(0.0)
    )
    return df[["date", "day_trade_volume"]].sort_values("date").reset_index(drop=True)


def _load_market_volume() -> pd.DataFrame:
    files = sorted(MV_DIR.glob("FMTQIK_*.parquet"))
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["total_volume"])
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "total_volume"]].sort_values("date").reset_index(drop=True)


def _rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """對每個位置i（i>=window-1），回傳values[i]在values[i-window+1:i+1]
    這個窗口內的百分位排名（0~1，1=窗口內最大值）。窗口不足回傳NaN。"""
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        w = values[i - window + 1: i + 1]
        out[i] = float((w <= values[i]).sum() - 1) / (window - 1)
    return out


def build_signal_series() -> pd.DataFrame:
    dt = _load_day_trading_volume()
    mv = _load_market_volume()
    merged = pd.merge(dt, mv, on="date", how="inner")
    merged = merged[merged["total_volume"] > 0].copy()
    merged["ratio"] = merged["day_trade_volume"] / merged["total_volume"]
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["ratio_pctile"] = _rolling_percentile_rank(merged["ratio"].to_numpy(), TRAIL_WINDOW)
    return merged.dropna(subset=["ratio_pctile"])


def build_aligned_series() -> pd.DataFrame:
    sig = build_signal_series()
    taiex = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
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
        rows.append({
            "date": r["date"], "ratio": float(r["ratio"]),
            "ratio_pctile": float(r["ratio_pctile"]), "fwd_ret": float(fwd_ret),
        })
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
        "real_corr": float(real_corr), "real_p": float(real_p),
        "null_median": float(np.median(shuffled)), "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["ratio_pctile"].to_numpy()
    target = df["fwd_ret"].to_numpy()
    n = len(df)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Spearman(ratio_pctile, fwd_ret_{FORWARD_HORIZON}d) = {shuf['real_corr']:+.4f} (p={shuf['real_p']:.4f})")
    print(f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.4f}  "
          f"真實corr percentile(單邊，越低代表越顯著負相關)={shuf['percentile']:.1f}")
    return {"label": label, "n": n, "corr": shuf["real_corr"], "p": shuf["real_p"],
            "null_median": shuf["null_median"], "null_percentile": shuf["percentile"]}


def main():
    print("=== #37 全市場現股當沖比重 regime 訊號 第1關cheap gate ===")
    aligned = build_aligned_series()
    print(f"對齊後總配對數: {len(aligned)}")
    print(f"訊號日範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"當沖比重描述統計: mean={aligned['ratio'].mean():.4%} median={aligned['ratio'].median():.4%} "
          f"std={aligned['ratio'].std():.4%} min={aligned['ratio'].min():.4%} max={aligned['ratio'].max():.4%}")

    if len(aligned) < 60:
        print("\n樣本數過少（<60），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "n": len(aligned)}

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30任一期），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample_split",
                "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    train_sign_ok = (train_result["corr"] < 0) == (EXPECTED_SIGN < 0)
    val_sign_ok = (val_result["corr"] < 0) == (EXPECTED_SIGN < 0)
    same_sign_as_expected = train_sign_ok and val_sign_ok
    nontrivial = abs(train_result["corr"]) > MIN_ABS_CORR and abs(val_result["corr"]) > MIN_ABS_CORR
    beats_null = val_result["null_percentile"] <= 10.0  # 單邊：越低代表越顯著負於null

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
    print(f"  2. train/val皆符合事前綁定負相關方向: {same_sign_as_expected} "
          f"(TRAIN corr={train_result['corr']:+.4f}, VAL corr={val_result['corr']:+.4f})")
    print(f"  3. VAL贏過洗牌null(單邊percentile<=10.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")

    verdict = "CHEAP_PASS" if (nontrivial and same_sign_as_expected and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv(Path(__file__).parent / "data" / "day_trading_ratio_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "n_total": len(aligned), "train_n": len(train), "val_n": len(val)}


if __name__ == "__main__":
    main()
