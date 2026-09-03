"""`HYPOTHESIS_QUEUE.md` #26 全市場融資餘額成長率 regime 訊號第1關cheap gate。

經濟理由：全市場總融資餘額（散戶信用交易槓桿）快速成長代表市場槓桿/擁擠度
升高，槓桿快速累積的市場對利空反應會被放大（強制斷頭連鎖賣壓）——這是
**regime訊號**，預期方向是「融資餘額成長越快，後續下檔風險（回撤幅度）
越大」，不是預測後續報酬方向本身（見`HYPOTHESIS_QUEUE.md`#26「具體假設
定義」段落最後一句）。跟已測過的三種非選股timing機制（#10 regime overlay
用大盤自身200日均線/波動度、#15 vol-targeting用自身已實現波動度、#19+
spillover用美股隔夜報酬）不同——這條用市場結構性槓桿水位，不是價格序列
的任何變換。

**資料**：`backfill_margin_debt_market.py`已完成的662個週檔全範圍回補
（2012-05-02~2024-12-31，`research/data/raw_margin_debt_market/`，週頻
抽樣、非逐日——docstring已記錄理由）。

**成長率定義（週頻資料下的20日/60日近似）**：本資料是週頻抽樣，`.pct_change(4)`
（間隔4個週觀測 ≈ 20交易日）跟`.pct_change(12)`（≈60交易日）近似原始假設
文字的「20日/60日成長率」，跟`backfill_margin_debt_market.py`docstring
記錄的「週頻近似中期趨勢」理由一致。

**cheap gate設計（信號=融資成長率，結果=後續同長度窗口TAIEX最大回撤幅度）**：
對每個有效成長率觀測點t，用**TAIEX日線**（不是週頻，避免用週頻資料算回撤
低估真實日內回撤）計算從t往後N個交易日（N=20對應4週成長率、N=60對應
12週成長率）窗口內的最大回撤幅度（絕對值，越大代表下檔風險越大）。測試
Spearman相關：融資成長率 vs 後續回撤幅度，預期為正（成長越快、後續回撤
越深）。對照組是打散「成長率觀測值對應到哪個時間點」這個配對本身（保留
兩邊各自的時序不變，只重新配對，N=200次）。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null）**：TRAIN=[起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]
（`validation/holdout.py`既有邊界）。

2026-09-03 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#26回補完成
後第1關起跑。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

MARGIN_DATA_DIR = Path(__file__).parent / "data" / "raw_margin_debt_market"

N_SHUFFLE = 200
SHUFFLE_SEED = 20260903
# (週觀測間隔lag, 對應交易日近似horizon, 標籤)
WINDOW_DEFS = ((4, 20, "20d(4w)"), (12, 60, "60d(12w)"))
MIN_ABS_CORR = 0.05


def _load_margin_series() -> pd.DataFrame:
    files = sorted(MARGIN_DATA_DIR.glob("MARGIN_*.parquet"))
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["is_trading_day"] == True].copy()  # noqa: E712
    df = df.dropna(subset=["financing_amount_today_balance_kNTD"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "financing_amount_today_balance_kNTD"]].rename(
        columns={"financing_amount_today_balance_kNTD": "balance"}
    )


def _load_taiex_daily() -> pd.DataFrame:
    df = fetch_yf_index(ticker="^TWII", start_date="2011-01-01")
    df = df.dropna(subset=["close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "close"]]


def _forward_window_mdd(taiex: pd.DataFrame, start_date: pd.Timestamp, horizon_days: int) -> float | None:
    """從`start_date`之後（不含當天，用下一個交易日開始）算N個交易日窗口
    內的最大回撤幅度（負值，越負代表回撤越深）。窗口不足`horizon_days`
    （太接近資料尾端，即VAL_END附近）回傳None，不勉強用不完整窗口。"""
    idx = int(taiex["date"].searchsorted(start_date, side="right"))
    window = taiex.iloc[idx: idx + horizon_days]
    if len(window) < horizon_days:
        return None
    prices = window["close"].to_numpy()
    running_max = np.maximum.accumulate(prices)
    dd = (prices - running_max) / running_max
    return float(dd.min())


def _build_pairs(margin: pd.DataFrame, taiex: pd.DataFrame, lag_weeks: int, horizon_days: int) -> pd.DataFrame:
    growth = margin["balance"].pct_change(lag_weeks)
    rows = []
    for i, g in enumerate(growth):
        if pd.isna(g):
            continue
        mdd = _forward_window_mdd(taiex, margin["date"].iloc[i], horizon_days)
        if mdd is None:
            continue
        rows.append({"date": margin["date"].iloc[i], "growth": float(g), "fwd_mdd_abs": abs(mdd)})
    return pd.DataFrame(rows)


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _shuffle_percentile(growth: np.ndarray, fwd_mdd_abs: np.ndarray, n: int, seed: int) -> dict:
    real_corr, real_p = spearmanr(growth, fwd_mdd_abs)
    rng = np.random.default_rng(seed)
    n_obs = len(growth)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(n_obs)
        shuffled[i], _ = spearmanr(growth, fwd_mdd_abs[perm])
    pctl = 100.0 * float(np.mean(shuffled <= real_corr))
    return {
        "real_corr": float(real_corr),
        "real_p": float(real_p),
        "null_median": float(np.median(shuffled)),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    growth = df["growth"].to_numpy()
    fwd = df["fwd_mdd_abs"].to_numpy()
    n = len(df)
    shuf = _shuffle_percentile(growth, fwd, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} (n={n}) ---")
    print(f"  Spearman(growth, |fwd_mdd|) = {shuf['real_corr']:+.4f} (p={shuf['real_p']:.4f})")
    print(f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.4f}  "
          f"真實corr percentile(單邊)={shuf['percentile']:.1f}")
    return {"label": label, "n": n, "corr": shuf["real_corr"], "p": shuf["real_p"],
            "null_median": shuf["null_median"], "null_percentile": shuf["percentile"]}


def main():
    print("=== #26 全市場融資餘額成長率 regime 訊號 第1關cheap gate ===")
    margin = _load_margin_series()
    print(f"融資週檔筆數(is_trading_day=True): {len(margin)}  "
          f"日期範圍: {margin['date'].min().date()} ~ {margin['date'].max().date()}")
    taiex = _load_taiex_daily()
    print(f"TAIEX日線筆數: {len(taiex)}  日期範圍: {taiex['date'].min().date()} ~ {taiex['date'].max().date()}")

    # sanity: 已知結構性事實年份附近成長率量級檢查（不做嚴格assert，僅列印供人工核對）
    growth_4w_all = margin["balance"].pct_change(4)
    print(f"\nsanity: growth_4w全樣本 mean={growth_4w_all.mean():+.4f} "
          f"std={growth_4w_all.std():.4f} min={growth_4w_all.min():+.4f} max={growth_4w_all.max():+.4f}")
    assert growth_4w_all.abs().median() < 0.5, "成長率量級異常（中位數超過50%），可能是單位或資料bug"

    results = []
    verdicts = {}
    for lag_weeks, horizon_days, label in WINDOW_DEFS:
        pairs = _build_pairs(margin, taiex, lag_weeks, horizon_days)
        train, val = _split(pairs)
        print(f"\n########## {label} (lag={lag_weeks}週, horizon={horizon_days}交易日) "
              f"config_pairs={len(pairs)} train_n={len(train)} val_n={len(val)} ##########")

        train_result = evaluate(train, f"TRAIN (<= {TRAIN_END}) {label}")
        val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END}) {label}")
        results.append({**train_result, "window": label})
        results.append({**val_result, "window": label})

        nontrivial = (abs(train_result["corr"]) > MIN_ABS_CORR
                      and abs(val_result["corr"]) > MIN_ABS_CORR)
        same_sign = (train_result["corr"] > 0) == (val_result["corr"] > 0)
        both_positive = train_result["corr"] > 0 and val_result["corr"] > 0
        beats_null = val_result["null_percentile"] >= 90.0

        print(f"\n=== {label} 第1關cheap gate三項判準 ===")
        print(f"  1. 幅度非零 (|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
        print(f"  2. train/val同號且方向為正(成長越快、後續回撤越深): {same_sign and both_positive} "
              f"(TRAIN corr={train_result['corr']:+.4f}, VAL corr={val_result['corr']:+.4f})")
        print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
              f"(percentile={val_result['null_percentile']:.1f})")

        verdict = "CHEAP_PASS" if (nontrivial and same_sign and both_positive and beats_null) else "FAIL"
        print(f"  判定({label}): {verdict}")
        verdicts[label] = verdict

    print("\n=== 總結 ===")
    for label, v in verdicts.items():
        print(f"  {label}: {v}")
    overall = "CHEAP_PASS" if any(v == "CHEAP_PASS" for v in verdicts.values()) else "FAIL"
    print(f"整體判定(任一窗口版本CHEAP_PASS即算過關，供下一關挑選對應窗口繼續): {overall}")

    pd.DataFrame(results).to_csv("data/margin_debt_growth_gate_results.csv", index=False)
    return {"verdicts": verdicts, "overall": overall, "results": results}


if __name__ == "__main__":
    main()
