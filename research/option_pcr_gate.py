"""`HYPOTHESIS_QUEUE.md` #31 台指選擇權Put/Call成交量比率當市場regime/擇時
訊號 第1關cheap gate。

經濟理由：選擇權市場的部位分布反映法人對未來波動/方向的看法，且選擇權
交易者常被認為比現貨市場更知情（Pan & Poteshman 2006）。Put/Call ratio
長期是市場情緒/避險需求的經典逆向指標（極端看跌部位堆積常對應短期底部）。
跟本佇列已測過的30條假設不同——這是第一次引入衍生性商品市場的部位資訊
（而非標的自身的價格/成交量/籌碼）當market regime判定輸入。完整經濟理由
見`HYPOTHESIS_QUEUE.md` #31條目。

跟`spillover_overnight_gate.py`（#19）同一種指數層級（index-level）時序
相關性測試精神，不是`factor_ic.py`的cross-sectional選股IC——測的是「台指
選擇權Put/Call成交量比率」這一條時間序列跟「台股次一交易日報酬」這一條
時間序列之間的（時序位移）相關性。

**時序對齊邏輯（避免未來函數）**：台指選擇權日盤（`trading_session`==
`position`）跟台股現貨同一交易日收盤，兩者收盤時間相近（選擇權日盤
13:45收盤，台股現貨13:30收盤），無法確定選擇權日盤收盤時台股當日收盤價
是否已經反映——保守起見，用「第t日收盤後才完整可得」的Put/Call比率，
預測「第t+1日」台股報酬（次一交易日），不用來預測第t日自己的報酬，
避免任何當日資訊领先疑慮。

**trading_session口徑決定（本輪查證後的方法論決策）**：FinMind
`TaiwanOptionDaily`欄位含`position`（日盤）跟`after_market`（夜盤）兩種
`trading_session`，但夜盤資料從2017年年中才開始出現（2015/2016僅有
`position`），若含入夜盤會讓訊號在TRAIN期前段（2015-2016）跟後段
（2017年後）計算口徑不一致，形成人為的結構斷點——**這裡只用`position`
（日盤）成交量計算Put/Call比率**，全期間（2015-2024）口徑一致，這是
方法論選擇不是bug，寫在這裡供之後deep_dive或重測時參考。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null，跟#19`spillover_overnight_gate.py`完全同一套框架）**：
TRAIN=[universe起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]（既有
`validation/holdout.py`邊界），皆用Pearson相關係數（主要）+ Spearman
（穩健性檢查），N=500次洗牌null（打散訊號時序、保留台股報酬時序）。

**事前綁定方向**：文獻上Put/Call ratio是逆向指標（比率越高、後續報酬
理論上越正，因為過度看跌部位堆積代表悲觀情緒見底）——但這裡不預先假設
方向對錯，跟#30（融資使用率，方向已知理論負號）不同，這條的文獻方向
本身就有分歧（也有研究認為高PC ratio代表法人正確預期下跌、是順向而非
逆向指標），cheap gate只看「train/val同號」，不預先綁定正負號本身。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#31第1關
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
OPTION_ID = "TXO"
OPTION_START = "2015-01-01"


def build_pcr_series() -> pd.DataFrame:
    """回傳 columns: date(Timestamp), put_volume, call_volume, pcr。只用
    `trading_session`==`position`（日盤）成交量，理由見docstring方法論
    決定段落。

    **逐年分批抓取（本輪發現的必要調整）**：一次跨10年（2015~2024）呼叫
    `load_dev`會讓FinMind回應502 Bad Gateway（payload過大伺服器端逾時，
    非本地bug、非額度封鎖類錯誤），改成逐年呼叫`load_dev`（仍是唯一
    sanctioned entry point，只是呼叫多次、每次範圍縮小），沿用其既有
    節流/重試/holdout截斷邏輯，不重新發明。
    """
    frames = []
    start_year = int(OPTION_START[:4])
    from validation.holdout import VAL_END as _val_end
    end_year = int(_val_end[:4])
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
    opt["volume"] = pd.to_numeric(opt["volume"], errors="coerce")
    opt = opt.dropna(subset=["volume"])

    grouped = opt.groupby(["date", "call_put"])["volume"].sum().unstack(fill_value=0.0)
    for col in ("put", "call"):
        if col not in grouped.columns:
            grouped[col] = 0.0
    grouped = grouped.reset_index().rename(columns={"put": "put_volume", "call": "call_volume"})
    # call_volume==0的日子(理論上不該發生，但防呆)丟棄，避免除以零
    grouped = grouped[grouped["call_volume"] > 0].copy()
    grouped["pcr"] = grouped["put_volume"] / grouped["call_volume"]
    return grouped[["date", "put_volume", "call_volume", "pcr"]].sort_values("date").reset_index(drop=True)


def build_aligned_series() -> pd.DataFrame:
    """對每個台股交易日t+1，配對「t日（t+1前一個交易日）」的Put/Call比率
    跟台股t+1日報酬。回傳 columns: signal_date, tw_date, pcr, tw_ret。
    """
    pcr_df = build_pcr_series()
    tw = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = tw.dropna(subset=["close"]).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").reset_index(drop=True)
    tw["ret"] = tw["close"].pct_change()

    merged = pcr_df.rename(columns={"date": "signal_date"})
    merged["tw_date_for_signal"] = merged["signal_date"]  # 選擇權日盤跟台股現貨同一交易日
    # 用shift(-1)取「下一個」有報酬的台股交易日當目標（避免當日資訊領先疑慮）
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
            "pcr": float(r["pcr"]),
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
    pcr = df["pcr"].to_numpy()
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
    print(f"PCR描述統計: mean={aligned['pcr'].mean():.4f} median={aligned['pcr'].median():.4f} "
          f"std={aligned['pcr'].std():.4f} min={aligned['pcr'].min():.4f} max={aligned['pcr'].max():.4f}")
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

    aligned.to_csv("data/option_pcr_aligned.csv", index=False)
    return {"train": train_result, "val": val_result, "verdict": verdict}


if __name__ == "__main__":
    main()
