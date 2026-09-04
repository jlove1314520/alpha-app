"""`HYPOTHESIS_QUEUE.md` #34 銅金比（Copper/Gold Ratio）當全球成長/風險偏好
regime訊號 第1關cheap gate。

經濟理由：銅（工業金屬，需求跟全球製造業/營建/電子業景氣連動，市場長期
視其為全球實體經濟活動的領先指標，故有「Dr. Copper博士銅」之稱）對黃金
（傳統避險資產，需求跟風險趨避/停滯性通膨預期連動）的比值，是總經圈廣泛
引用的「風險偏好vs風險趨避」量化指標。跟本佇列已測過的#19（美股報酬外溢）/
#31（選擇權PCR）/#32（台幣匯率）/#33（公債殖利率曲線）不同——那四條全部
來自「金融市場參與者的部位或預期」，這條測的是「實體經濟供需」本身反映在
商品期貨價格上的訊號，資訊來源類別第一次不同。台灣是高度依賴電子/半導體
出口的小型開放經濟體，全球製造業景氣（銅需求主要驅動力）走強時，台灣出口
訂單與台股企業獲利預期理論上應同步受益。完整經濟理由見`HYPOTHESIS_QUEUE.md`
#34條目。

跟`fx_twd_gate.py`（#32）/`fred_yield_curve_gate.py`（#33）同一種指數層級
（index-level）時序相關性測試精神，不是`factor_ic.py`的cross-sectional
選股IC——測的是「銅金比水位」這一條時間序列跟「TAIEX後續M個交易日報酬」
這一條時間序列之間的相關性。

**訊號口徑決定（事前綁定，第1關前決定）**：用**比值水位本身**（level =
銅期貨收盤價/黃金期貨收盤價），不是N日變動率——理由：這是一個狀態性的
風險偏好水位訊號（銅金比高代表當下實體需求相對避險需求強），不是速度
訊號，訊號口徑要對應機制定義本身，不能機械套用#32/#33的變動率公式（那兩條
測的是「資金流向/利率預期的變化速度」，跟這條「當下實體需求水位」機制
不同）。

**目標窗口（事前綁定，第1關前決定，非跑完看結果才選）**：M=20交易日
（預測視窗），與本專案既有regime類窗口（`regime_overlay.py`20日波動度窗、
`fx_twd_gate.py`/`fred_yield_curve_gate.py`同量級）同一個量級。目標 =
TAIEX[t+M]/TAIEX[t] - 1（訊號日t之後M個交易日的台股報酬，訊號在t日已完全
確定，預測未來，無未來函數）。

**事前綁定方向**：預期銅金比走高（實體需求相對避險需求強，風險偏好升溫）
對應TAIEX後續報酬轉強（正相關）——若第1關方向跟預期相反要誠實記錄，不能
事後改預期方向配合結果。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19/#31/#32/#33完全同一套框架）**：TRAIN=[universe起點,
TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有`validation/holdout.py`邊界），
皆用Pearson相關係數（主要）+ Spearman（穩健性檢查），N_SHUFFLE=500次洗牌
null（打散訊號時序、保留TAIEX報酬時序）。

**資料源**：兩條商品期貨序列（HG=F銅期貨、GC=F黃金期貨）跟TAIEX（^TWII）
皆用`yf_price_client.py::fetch_yf_index()`既有基礎設施（已在本輪資料可行性
查證中確認：2015-01-02~2026-06-29完整涵蓋、無NaN、無>14天缺口），不新增
資料源模組、不需要新API金鑰。`fetch_yf_index()`已內建`VAL_END`截斷，holdout
天然安全。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#34第1關起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260905
COPPER_TICKER = "HG=F"
GOLD_TICKER = "GC=F"
TAIEX_TICKER = "^TWII"
DATA_START = "2015-01-01"
M_TARGET_DAYS = 20  # TAIEX後續M日報酬預測視窗


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t+M存在），配對銅金比水位(訊號)跟TAIEX
    M日後報酬(目標)。回傳 columns: date, copper_gold_ratio, tw_fwd_ret_m。
    """
    copper = fetch_yf_index(ticker=COPPER_TICKER, start_date=DATA_START)
    gold = fetch_yf_index(ticker=GOLD_TICKER, start_date=DATA_START)
    for name, df in (("copper", copper), ("gold", gold)):
        if df.empty:
            raise RuntimeError(f"{name}({COPPER_TICKER if name=='copper' else GOLD_TICKER})"
                                f"抓取後為空資料，第1關無法起跑")

    copper = copper.dropna(subset=["close"]).copy()
    copper["date"] = pd.to_datetime(copper["date"])
    copper = copper.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    gold = gold.dropna(subset=["close"]).copy()
    gold["date"] = pd.to_datetime(gold["date"])
    gold = gold.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    ratio = pd.merge(
        copper[["date", "close"]].rename(columns={"close": "copper_close"}),
        gold[["date", "close"]].rename(columns={"close": "gold_close"}),
        on="date", how="inner",
    )
    ratio = ratio[ratio["gold_close"] > 0].copy()
    ratio["copper_gold_ratio"] = ratio["copper_close"] / ratio["gold_close"]

    tw = fetch_yf_index(ticker=TAIEX_TICKER, start_date=DATA_START)
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        ratio[["date", "copper_gold_ratio"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date", how="inner",
    )
    merged = merged.dropna(subset=["copper_gold_ratio", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    return {
        "pearson": float(real_pearson),
        "pearson_p": float(real_p),
        "null_median_abs": float(np.median(np.abs(shuffled))),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, label: str) -> dict:
    signal = df["copper_gold_ratio"].to_numpy()
    target = df["tw_fwd_ret_m"].to_numpy()
    n = len(df)
    pearson, pearson_p = stats.pearsonr(signal, target)
    spearman, spearman_p = stats.spearmanr(signal, target)
    shuf = _shuffle_percentile(signal, target, N_SHUFFLE, SHUFFLE_SEED)
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
    print(f"日期範圍: {aligned['date'].min()} ~ {aligned['date'].max()}")
    print(f"銅金比(水位)描述統計: mean={aligned['copper_gold_ratio'].mean():.4f} "
          f"median={aligned['copper_gold_ratio'].median():.4f} "
          f"std={aligned['copper_gold_ratio'].std():.4f} "
          f"min={aligned['copper_gold_ratio'].min():.4f} max={aligned['copper_gold_ratio'].max():.4f}")
    print(f"TAIEX後M({M_TARGET_DAYS})日報酬描述統計: mean={aligned['tw_fwd_ret_m'].mean():.4f} "
          f"median={aligned['tw_fwd_ret_m'].median():.4f} std={aligned['tw_fwd_ret_m'].std():.4f}")

    train, val = _split(aligned)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    if len(train) < 30 or len(val) < 30:
        print("\n樣本數過少（<30），資料可能不完整，判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample", "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate(val, f"VAL ({TRAIN_END} ~ {VAL_END})")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] > 0  # 事前綁定：銅金比走高對應TAIEX轉強(正相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(正相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/copper_gold_ratio_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
