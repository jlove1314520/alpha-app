"""`HYPOTHESIS_QUEUE.md` #32 美元兌台幣匯率當資金外流/市場壓力regime訊號
第1關cheap gate。

經濟理由：台灣是外資持股占比高（台股外資持股常年3~4成）的小型開放經濟體，
外資大舉撤出台股時，賣股所得台幣需兌換回美元，同時壓低台股（賣壓）跟壓貶
台幣（換匯需求）——兩者是同一個資金外流動作的兩個可觀察面，文獻上新興市場
「股匯雙貶」（EM twin depreciation，risk-off情境下貨幣與股市同步走弱）是有
紀錄的現象。跟本佇列已測過的31條假設不同：這是第一次用「貨幣市場」的價格
當regime判定輸入（前面#19雖跨市場，用的仍是美股「股票市場」報酬），經濟
機制（資金流向）也跟已死的動量崩潰(#2)/槓桿限制(#12)/避險情緒(#31)不同。
完整經濟理由見`HYPOTHESIS_QUEUE.md` #32條目。

跟`option_pcr_gate.py`（#31）/`spillover_overnight_gate.py`（#19）同一種
指數層級（index-level）時序相關性測試精神，不是`factor_ic.py`的
cross-sectional選股IC——測的是「台幣兌美元N日變動率」這一條時間序列跟
「TAIEX後續M個交易日報酬」這一條時間序列之間的相關性。

**匯率欄位口徑決定（本輪方法論選擇，事前綁定，第1關前決定）**：FinMind
`TaiwanExchangeRate`回傳`cash_buy`/`cash_sell`/`spot_buy`/`spot_sell`四個
欄位——現金匯率(cash)價差較大、偏零售，即期匯率(spot)價差較窄、更貼近
銀行間市場真實價格，這裡選**`spot_sell`**（銀行賣出美元給客戶的即期匯率，
數值上升=台幣走貶，符合本假設「貶值方向為正」的定義），不用中價（避免
額外的buy/sell平均計算增加不必要的自由度）。

**訊號/目標窗口（事前綁定，第1關前決定，非跑完看結果才選）**：N=20交易日
（信號視窗）、M=20交易日（預測視窗）——與本專案既有regime類窗口
（`regime_overlay.py`20日波動度窗、`#28`市場廣度20日窗）同一個量級，經濟
理由是資金外流是資金流向的持續性現象，不是單日噪音，用月頻量級窗口比單日
變動更貼近這個機制的時間尺度。訊號 = 台幣匯率[t]/台幣匯率[t-N] - 1（N日
變動率，正值=台幣貶值）；目標 = TAIEX[t+M]/TAIEX[t] - 1（訊號日t之後M個
交易日的台股報酬，訊號在t日已完全確定，預測未來，無未來函數）。

**事前綁定方向**：預期台幣貶值幅度加大（訊號為正）對應TAIEX後續報酬轉弱
（負相關）——若第1關方向跟預期相反要誠實記錄，不能事後改預期方向配合結果
（`cheap gate`本身只看train/val同號，不會因為方向不符預期就自動判FAIL，
但要在心跳/佇列狀態裡如實記錄跟預期是否一致）。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19/#31完全同一套框架）**：TRAIN=[universe起點,
TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有`validation/holdout.py`邊界），
皆用Pearson相關係數（主要）+ Spearman（穩健性檢查），N_SHUFFLE=500次洗牌
null（打散訊號時序、保留TAIEX報酬時序）。

**逐年分批抓取**：比照#31`option_pcr_gate.py`同一個必要調整（一次跨10年
呼叫`load_dev`會遇到FinMind 502），改成逐年呼叫`load_dev("TaiwanExchangeRate",
"USD", ...)`，沿用其既有節流/重試/holdout截斷邏輯，不重新發明。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#32第1關
起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from finmind_client import load_dev
from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260905
FX_DATASET = "TaiwanExchangeRate"
FX_DATA_ID = "USD"
FX_START = "2015-01-01"
RATE_COL = "spot_sell"
N_SIGNAL_DAYS = 20   # 台幣匯率N日變動率信號視窗
M_TARGET_DAYS = 20   # TAIEX後續M日報酬預測視窗


def build_fx_series() -> pd.DataFrame:
    """回傳 columns: date(Timestamp,已排序), rate(spot_sell即期匯率)。

    逐年分批呼叫`load_dev`（理由見docstring方法論決定段落），避免502。
    """
    frames = []
    start_year = int(FX_START[:4])
    end_year = int(VAL_END[:4])
    for yr in range(start_year, end_year + 1):
        yr_start = f"{yr}-01-01"
        yr_end = f"{yr}-12-31"
        chunk = load_dev(FX_DATASET, FX_DATA_ID, yr_start, end_date=yr_end, date_col="date")
        if not chunk.empty:
            frames.append(chunk)
    if not frames:
        raise RuntimeError(f"{FX_DATASET}({FX_DATA_ID})逐年抓取後仍全數空資料，第1關無法起跑")
    fx = pd.concat(frames, ignore_index=True)
    if RATE_COL not in fx.columns:
        raise RuntimeError(f"{FX_DATASET}回傳缺少{RATE_COL!r}欄位，實際欄位: {list(fx.columns)}")
    fx["date"] = pd.to_datetime(fx["date"])
    fx["rate"] = pd.to_numeric(fx[RATE_COL], errors="coerce")
    fx = fx.dropna(subset=["rate"])
    fx = fx[fx["rate"] > 0].copy()
    fx = fx.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return fx[["date", "rate"]]


def build_aligned_series() -> pd.DataFrame:
    """對每個有效訊號日t（需要t-N存在且t+M存在），配對台幣N日變動率(訊號)
    跟TAIEX M日後報酬(目標)。回傳 columns: date, fx_change_n, tw_fwd_ret_m。
    """
    fx = build_fx_series()
    fx["fx_change_n"] = fx["rate"] / fx["rate"].shift(N_SIGNAL_DAYS) - 1.0

    tw = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    tw["tw_fwd_ret_m"] = tw["close"].shift(-M_TARGET_DAYS) / tw["close"] - 1.0

    merged = pd.merge(
        fx[["date", "fx_change_n"]],
        tw[["date", "tw_fwd_ret_m"]],
        on="date",
        how="inner",
    )
    merged = merged.dropna(subset=["fx_change_n", "tw_fwd_ret_m"]).reset_index(drop=True)
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
    signal = df["fx_change_n"].to_numpy()
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
    print(f"匯率N({N_SIGNAL_DAYS})日變動率描述統計: mean={aligned['fx_change_n'].mean():.4f} "
          f"median={aligned['fx_change_n'].median():.4f} std={aligned['fx_change_n'].std():.4f} "
          f"min={aligned['fx_change_n'].min():.4f} max={aligned['fx_change_n'].max():.4f}")
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
    matches_expected_direction = val_result["pearson"] < 0  # 事前綁定：預期台幣貶值對應TAIEX轉弱(負相關)

    print("\n=== 第1關cheap gate三項判準 ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註，非判準本身）VAL方向是否符合事前預期(負相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定: {verdict}")

    aligned.to_csv("data/fx_twd_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
