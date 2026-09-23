"""`PENDING_QUEUE.md` 常備.5 美國高收益債ETF/公債ETF價格比值（HYG/IEF）
**其他窗口版（M=5/10/60日，非M=20單一窗口）**當TAIEX regime降曝險訊號
第1關cheap gate。

背景：`hy_etf_ratio_gate.py`（#78）只測過M=20單一預測窗口，train/val
正負號相反判FAIL；`STRATEGY_GRAVEYARD.md` #78段落明列「未測其他窗口
（5/10/60日）」為未測變體。本檔案補這個變體。

**訊號口徑**：沿用#78水位版（HYG/IEF比值水位本身，非變動率），唯一
改變的自由度是預測目標窗口M，事前綁定測{5,10,60}三格，**全部計入N、
不挑最佳格報告**（比照本專案「參數高原」網格慣例，不做post-hoc窗口
挑選）——這是跟#78(M=20)並列的第4個窗口點，等於M∈{5,10,20,60}四格
高原檢視，但本檔案只負責新增的3格，#78已測過的M=20不重跑。

**目標窗口定義**：目標 = TAIEX[t+M]/TAIEX[t] - 1，M∈{5,10,60}交易日，
訊號日t之後M個交易日的台股報酬，無未來函數。

**事前綁定方向**：比值水位與TAIEX後續報酬正相關（同#78推導，比值高=
信用風險偏好升溫=風險偏好升溫→TAIEX轉強）——四個窗口共用同一個方向
假說，不因窗口不同而換方向。

**判定標準**：每格各自套用cheap gate三項判準（幅度非零/train-val同號/
贏過洗牌null N=500）；額外報告「幾格通過」，若0/3過關而#78(M=20)也
FAIL，代表這不是窗口選擇的問題，是HYG/IEF比值機制本身對TAIEX沒有
穩健predictive power。

**資料源**：同#78，`yf_price_client.py::fetch_yf_index()`，不新增
資料源模組。

2026-09-23 DevQueue自走cycle 20260923-121601，`PENDING_QUEUE.md`常備.5。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
HYG_TICKER = "HYG"
IEF_TICKER = "IEF"
TAIEX_TICKER = "^TWII"
DATA_START = "2007-01-01"
M_GRID = (5, 10, 60)  # M=20已由#78測過，這裡不重測


def _load_ratio_and_taiex() -> tuple[pd.DataFrame, pd.DataFrame]:
    hyg = fetch_yf_index(ticker=HYG_TICKER, start_date=DATA_START)
    ief = fetch_yf_index(ticker=IEF_TICKER, start_date=DATA_START)
    for name, df, tk in (("HYG", hyg, HYG_TICKER), ("IEF", ief, IEF_TICKER)):
        if df.empty:
            raise RuntimeError(f"{name}({tk})抓取後為空資料，第1關無法起跑")

    hyg = hyg.dropna(subset=["close"]).copy()
    hyg["date"] = pd.to_datetime(hyg["date"])
    hyg = hyg.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ief = ief.dropna(subset=["close"]).copy()
    ief["date"] = pd.to_datetime(ief["date"])
    ief = ief.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ratio = pd.merge(
        hyg[["date", "close"]].rename(columns={"close": "hyg_close"}),
        ief[["date", "close"]].rename(columns={"close": "ief_close"}),
        on="date", how="inner",
    )
    ratio = ratio[ratio["ief_close"] > 0].copy()
    ratio["hyg_ief_ratio"] = ratio["hyg_close"] / ratio["ief_close"]

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    return ratio[["date", "hyg_ief_ratio"]], tw[["date", "close"]]


def build_aligned_series(ratio: pd.DataFrame, tw: pd.DataFrame, m: int) -> pd.DataFrame:
    t = tw.copy()
    t["tw_fwd_ret_m"] = t["close"].shift(-m) / t["close"] - 1.0
    merged = pd.merge(ratio, t[["date", "tw_fwd_ret_m"]], on="date", how="inner")
    merged = merged.dropna(subset=["hyg_ief_ratio", "tw_fwd_ret_m"]).reset_index(drop=True)
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


def evaluate(df: pd.DataFrame, label: str, seed: int) -> dict:
    signal = df["hyg_ief_ratio"].to_numpy()
    target = df["tw_fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, seed)
    print(f"  {label} (n={n}): Pearson r={pearson:+.4f}(p={pearson_p:.4f}) "
          f"Spearman rho={spearman:+.4f}(p={spearman_p:.4f}) null_percentile={shuf['percentile']:.1f}")
    return {"label": label, "n": n, "pearson": pearson, "pearson_p": pearson_p,
            "spearman": spearman, "spearman_p": spearman_p,
            "null_percentile": shuf["percentile"], "null_median_abs": shuf["null_median_abs"]}


def main():
    ratio, tw = _load_ratio_and_taiex()
    grid = []
    for m in M_GRID:
        print(f"\n=== M={m} 交易日 ===")
        aligned = build_aligned_series(ratio, tw, m)
        train, val = _split(aligned)
        print(f"  TRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")
        if len(train) < 30 or len(val) < 30:
            print("  樣本數過少（<30），判定FAIL（結構性資料不足）")
            grid.append({"m": m, "verdict": "FAIL", "reason": "insufficient_sample"})
            continue
        tr = evaluate(train, f"TRAIN M={m}", SHUFFLE_SEED)
        va = evaluate(val, f"VAL M={m}", SHUFFLE_SEED + m)
        same_sign = (tr["pearson"] > 0) == (va["pearson"] > 0)
        nontrivial = abs(tr["pearson"]) > 0.01 and abs(va["pearson"]) > 0.01
        beats_null = va["null_percentile"] >= 90.0
        matches_expected = va["pearson"] > 0  # 事前綁定：比值高→TAIEX後續報酬高(正相關)，四窗口共用同一方向假說
        verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
        print(f"  判準：幅度非零={nontrivial} train/val同號={same_sign}({tr['pearson']:+.4f}/{va['pearson']:+.4f}) "
              f"VAL贏過null={beats_null}({va['null_percentile']:.1f}) 方向符合預期={matches_expected} -> {verdict}")
        grid.append({"m": m, "train": tr, "val": va, "same_sign": same_sign, "nontrivial": nontrivial,
                     "beats_null": beats_null, "matches_expected_direction": matches_expected, "verdict": verdict})

    n_pass = sum(1 for g in grid if g.get("verdict") == "CHEAP_PASS")
    print(f"\n=== 總結：{n_pass}/{len(M_GRID)}格通過（M=20另見#78，本檔案不重複） ===")
    return {"grid": grid, "n_pass": n_pass, "n_total": len(M_GRID)}


if __name__ == "__main__":
    main()
