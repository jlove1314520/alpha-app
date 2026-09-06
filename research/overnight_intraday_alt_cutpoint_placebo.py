"""`HYPOTHESIS_QUEUE.md` #49 日內／隔夜報酬結構分解，第2關placebo檢定。

**為什麼不是套用既有「打亂訊號時序」模板**（`HYPOTHESIS_QUEUE_PROTOCOL.md`
第1節警告過的地雷）：這條假設沒有「訊號預測目標」的結構——overnight跟
intraday是同一個總報酬的加性分解（`overnight+intraday=total`是恆等式），
打亂配對順序不會改變邊際總和，套用舊模板只會得到無意義的100%通過。

**為什麼不是原本設想的「隨機時刻切分」（需要分鐘/tick資料）**：本輪已
用三個獨立來源查證，確認TRAIN期(2015-2020)無法取得TAIEX盤中分鐘級價格
序列：
1. yfinance實測——1分K只保留近8天、5分K/60分K最長回溯約60天/730天，
   完全不覆蓋TRAIN期（見`MARATHON_LOG.md`本輪心跳的實測輸出）。
2. FinMind——`C:\\alpha\\CLAUDE.md`「已知地雷」章節已記錄「FinMind免費層
   不提供盤中1分K」，跟本輪查證一致。
3. TWSE官方——`MI_5MINS`端點雖支援任意歷史日期查詢（實測2015-01-05
   有回應），但欄位是「累積委託買賣筆數/數量/成交金額」等**交易活動
   統計**，不是TAIEX指數點位本身，無法用來重建盤中價格路徑。

三個來源都不可行，依快殺標準「資料不可及」，**這個特定的第2關操作化
方式（隨機時刻切分）判定不可行**——但這不代表整個#49假設判死，因為
其他關卡（成本敏感度/leave-one-out/逐年一致性/OOS）都只需要既有的
日線OHLC，不受這個限制。

**這次改用的替代設計**：`open`不是日內唯一有紀錄的價格點——`high`/`low`
也是當天**真實成交過**的價位，只是不知道確切發生時刻。用這兩者當「替代
切分點」，建構跟`open`切分同樣形式的恆等分解：

    log(high_t/close_{t-1}) + log(close_t/high_t) == log(close_t/close_{t-1})
    log(low_t /close_{t-1}) + log(close_t/low_t)  == log(close_t/close_{t-1})

這是telescoping恆等式，對任何介於close_{t-1}與close_t之間、當天真實
出現過的價格都成立，不需要憑空捏造合成資料。**核心比較問題**：如果
「open」的切分結果（同號、兩期皆顯著、貢獻占比大幅偏離50%）只是「任何
突出的日內價位都會產生類似的偏態」，那用high/low切分應該也會看到類似
乾淨的模式；如果open的模式明顯比high/low更乾淨、更一致，才支持「開盤
（集合競價撮合）這個特定時間點具有特殊經濟意義」這個假設核心主張，而
非「任意找一個極端價位都能製造出偏態」的偽影。

**誠實局限**：這不是嚴格意義的隨機對照組（high/low不是隨機抽樣的價位，
它們本身就跟當天的intraday波動有系統性關聯，可能天生就會產生偏態）。
這是一個**比較式diagnostic**，用來判斷open的訊號模式是否具有相對
特異性，不是一個能單獨產生PASS/FAIL的機率檢定。最終是否視為通過第2關，
取決於這個比較結果加上下一輪對此設計的覆核判斷。

2026-09-07 hypothesis_queue排程新增。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

SIG_LEVEL = 0.05
CONTRIB_DEVIATION_THRESHOLD = 20.0  # |occupancy - 50| must exceed this (>70% or <30%)


def build_multi_cutpoint_series(ticker: str = "^TWII", start_date: str = "2010-01-01") -> pd.DataFrame:
    """回傳 date + open/high/low/close + 三組切分（open/high/low）的
    leg1(收盤到切分點)/leg2(切分點到收盤) simple return，並驗證三組恆等式
    皆逐日成立。
    """
    df = fetch_yf_index(ticker=ticker, start_date=start_date)
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["prev_close"] = df["close"].shift(1)
    df = df.dropna(subset=["prev_close"]).reset_index(drop=True)
    df["total_ret"] = df["close"] / df["prev_close"] - 1.0

    for cutpoint in ("open", "high", "low"):
        df[f"leg1_{cutpoint}"] = df[cutpoint] / df["prev_close"] - 1.0
        df[f"leg2_{cutpoint}"] = df["close"] / df[cutpoint] - 1.0
        # sanity: telescoping恆等式逐日成立
        reconstructed = (1.0 + df[f"leg1_{cutpoint}"]) * (1.0 + df[f"leg2_{cutpoint}"]) - 1.0
        max_err = float((reconstructed - df["total_ret"]).abs().max())
        assert max_err < 1e-9, (
            f"{cutpoint}切分恆等式檢查失敗，最大誤差={max_err}——分解有bug"
        )

    return df


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _leg_stats(returns: pd.Series) -> dict:
    n = len(returns)
    mean = float(returns.mean())
    t_stat, p_val = stats.ttest_1samp(returns, popmean=0.0)
    log_sum = float(np.log1p(returns).sum())
    return {"n": n, "mean": mean, "t_stat": float(t_stat), "p_value": float(p_val), "log_sum": log_sum}


def evaluate_cutpoint(df: pd.DataFrame, cutpoint: str, label: str) -> dict:
    leg1 = df[f"leg1_{cutpoint}"]
    leg2 = df[f"leg2_{cutpoint}"]

    leg1_stats = _leg_stats(leg1)
    leg2_stats = _leg_stats(leg2)
    total_log_sum = leg1_stats["log_sum"] + leg2_stats["log_sum"]

    if abs(total_log_sum) < 1e-9:
        leg1_occ = float("nan")
        leg2_occ = float("nan")
    else:
        leg1_occ = 100.0 * leg1_stats["log_sum"] / total_log_sum
        leg2_occ = 100.0 * leg2_stats["log_sum"] / total_log_sum

    same_sign = (leg1_stats["mean"] > 0) if True else None  # 記錄用，跨期比較在main()做
    print(f"    [{cutpoint}] leg1(close_prev->{cutpoint}): mean={leg1_stats['mean']:+.6f} "
          f"t={leg1_stats['t_stat']:+.3f} p={leg1_stats['p_value']:.4f} occ={leg1_occ:+.1f}%")
    print(f"    [{cutpoint}] leg2({cutpoint}->close):      mean={leg2_stats['mean']:+.6f} "
          f"t={leg2_stats['t_stat']:+.3f} p={leg2_stats['p_value']:.4f} occ={leg2_occ:+.1f}%")

    return {
        "cutpoint": cutpoint, "label": label,
        "leg1": leg1_stats, "leg2": leg2_stats,
        "leg1_occ": leg1_occ, "leg2_occ": leg2_occ,
    }


def _leg1_pass(train_r: dict, val_r: dict) -> bool:
    """套用#49第1關同一套事前綁定判準：同號+兩期皆顯著+兩期occ皆偏離50%±20。"""
    same_sign = (train_r["leg1"]["mean"] > 0) == (val_r["leg1"]["mean"] > 0)
    both_sig = train_r["leg1"]["p_value"] < SIG_LEVEL and val_r["leg1"]["p_value"] < SIG_LEVEL
    both_dev = (
        abs(train_r["leg1_occ"] - 50.0) > CONTRIB_DEVIATION_THRESHOLD
        and abs(val_r["leg1_occ"] - 50.0) > CONTRIB_DEVIATION_THRESHOLD
    )
    return same_sign and both_sig and both_dev


def main():
    df = build_multi_cutpoint_series()
    print(f"對齊後總交易日數: {len(df)}")
    print(f"日期範圍: {df['date'].min().date()} ~ {df['date'].max().date()}")
    print("三組切分（open/high/low）恆等式sanity檢查皆通過（誤差<1e-9）。\n")

    train_df, val_df = _split(df)
    print(f"TRAIN(<= {TRAIN_END}): n={len(train_df)}  VAL({TRAIN_END}~{VAL_END}): n={len(val_df)}\n")

    verdicts = {}
    for cutpoint in ("open", "high", "low"):
        print(f"=== 切分點: {cutpoint} ===")
        print("  TRAIN:")
        train_r = evaluate_cutpoint(train_df, cutpoint, f"TRAIN_{cutpoint}")
        print("  VAL:")
        val_r = evaluate_cutpoint(val_df, cutpoint, f"VAL_{cutpoint}")
        leg1_pass = _leg1_pass(train_r, val_r)
        verdicts[cutpoint] = leg1_pass
        print(f"  [{cutpoint}] leg1(close_prev->{cutpoint})套用#49事前綁定判準："
              f"{'通過' if leg1_pass else '未通過'}\n")

    print("=== 第2關比較結論 ===")
    print(f"  open切分leg1(overnight)通過事前綁定判準: {verdicts['open']}")
    print(f"  high切分leg1通過同一套判準:              {verdicts['high']}")
    print(f"  low切分leg1通過同一套判準:               {verdicts['low']}")

    if verdicts["open"] and not verdicts["high"] and not verdicts["low"]:
        comparison = "open特異：只有open切分通過，high/low皆未通過——支持開盤具有特殊經濟意義，不是任意極端價位都會製造偏態"
    elif verdicts["open"] and (verdicts["high"] or verdicts["low"]):
        comparison = "open不具特異性：high或low切分也通過同一套判準——open的偏態可能只是「任何突出日內價位」的共同現象，不特別支持開盤本身的機制"
    else:
        comparison = "open本身在這個比較下未通過（需交叉核對第1關結果是否一致）"
    print(f"  判讀: {comparison}")

    df.to_csv("data/overnight_intraday_alt_cutpoint.csv", index=False)

    return {"verdicts": verdicts, "comparison": comparison}


if __name__ == "__main__":
    main()
