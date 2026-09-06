"""`HYPOTHESIS_QUEUE.md` #49 日內／隔夜報酬結構分解（Overnight vs Intraday
Return Decomposition）第1關cheap gate。

經濟理由完整版見`HYPOTHESIS_QUEUE.md`#49條目。這不是「訊號預測forward
報酬」的相關性檢定，是「報酬本身在哪個時段被實現」的分解檢定：對TAIEX
(^TWII) 逐日拆解

    overnight_return_t = open_t / close_{t-1} - 1   （收盤到隔天開盤）
    intraday_return_t  = close_t / open_t - 1        （開盤到當天收盤）

用log報酬做加總才是exact恆等式（避免`HYPOTHESIS_QUEUE_PROTOCOL.md`第32行
警告過的「簡單加總聚合口徑bug」）：

    log(1+overnight_t) + log(1+intraday_t) == log(close_t/close_{t-1})

逐日成立，對整個期間加總後，log報酬的貢獻占比就是「該時段對期間累積log
報酬（=累積複利報酬取log）貢獻多少比例」的exact分解，不是近似值。

**事前綁定的通過門檻**（`HYPOTHESIS_QUEUE.md`#49「第1關cheap gate操作化」
段落原文）：至少一段（overnight或intraday）的均值在TRAIN/VAL兩期都顯著
不為零(p<0.05)且同號，且該段對總報酬的log貢獻占比在兩期都明顯偏離50%
（>70%或<30%），才算CHEAP_PASS。

先用TAIEX指數（不需要股利還原，指數本身是price index非total-return
index，沒有除權息污染問題）驗證指數層級現象是否存在——依#49「已知混淆
風險#5」的順序，個股/0050層級留給CHEAP_PASS之後的下一關再做。

2026-09-06 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#49第1關
起跑（前置工程`adjust.py`的open/high/low還原擴充已於上一輪完成，但這條
用TAIEX指數本身、不吃股利還原，用不到那個擴充；那個擴充是為了#49未來
若走到個股層級時備用）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

SIG_LEVEL = 0.05
CONTRIB_DEVIATION_THRESHOLD = 20.0  # |occupancy - 50| must exceed this (>70% or <30%)


def build_decomposed_series(ticker: str = "^TWII", start_date: str = "2010-01-01") -> pd.DataFrame:
    """回傳 date + open + close + overnight_ret + intraday_ret + total_ret
    （皆為simple return），已用log恆等式驗證無誤。
    """
    df = fetch_yf_index(ticker=ticker, start_date=start_date)
    df = df.dropna(subset=["open", "close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["prev_close"] = df["close"].shift(1)
    df = df.dropna(subset=["prev_close"]).reset_index(drop=True)

    df["overnight_ret"] = df["open"] / df["prev_close"] - 1.0
    df["intraday_ret"] = df["close"] / df["open"] - 1.0
    df["total_ret"] = df["close"] / df["prev_close"] - 1.0
    return df[["date", "open", "close", "prev_close", "overnight_ret", "intraday_ret", "total_ret"]]


def _sanity_check_identity(df: pd.DataFrame) -> float:
    """恆等式檢查：(1+overnight)(1+intraday)-1 應等於total_ret，逐日成立。
    回傳最大絕對誤差；理論上應是浮點誤差量級（<1e-9）。
    """
    reconstructed = (1.0 + df["overnight_ret"]) * (1.0 + df["intraday_ret"]) - 1.0
    max_err = float((reconstructed - df["total_ret"]).abs().max())
    assert max_err < 1e-9, f"恆等式檢查失敗，最大誤差={max_err}——overnight/intraday拆解有bug"
    return max_err


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _leg_stats(returns: pd.Series, label: str) -> dict:
    """單一時段（overnight或intraday）的單樣本t檢定 + log報酬加總。"""
    n = len(returns)
    mean = float(returns.mean())
    t_stat, p_val = stats.ttest_1samp(returns, popmean=0.0)
    log_sum = float(np.log1p(returns).sum())  # exact additive log-return contribution
    compounded = float(np.exp(log_sum) - 1.0)  # 該時段單獨累積複利報酬（若每天只做這一段）
    return {
        "label": label, "n": n, "mean": mean, "t_stat": float(t_stat), "p_value": float(p_val),
        "log_sum": log_sum, "compounded_return": compounded,
    }


def evaluate_period(df: pd.DataFrame, label: str) -> dict:
    overnight = df["overnight_ret"]
    intraday = df["intraday_ret"]

    overnight_stats = _leg_stats(overnight, "overnight")
    intraday_stats = _leg_stats(intraday, "intraday")

    # 配對t檢定：overnight跟intraday均值是否有差異（同一天的兩段報酬本質上配對）
    paired_t, paired_p = stats.ttest_rel(overnight, intraday)

    total_log_sum = overnight_stats["log_sum"] + intraday_stats["log_sum"]
    # sanity: total_log_sum應等於log(close_end/close_start)（telescoping恆等式）
    total_ret_direct = float(np.log1p(df["total_ret"]).sum())
    assert abs(total_log_sum - total_ret_direct) < 1e-6, (
        f"log恆等式加總不一致: overnight+intraday={total_log_sum:.6f} vs "
        f"直接加總total_ret={total_ret_direct:.6f}"
    )

    if abs(total_log_sum) < 1e-9:
        overnight_occupancy = float("nan")
        intraday_occupancy = float("nan")
    else:
        overnight_occupancy = 100.0 * overnight_stats["log_sum"] / total_log_sum
        intraday_occupancy = 100.0 * intraday_stats["log_sum"] / total_log_sum

    print(f"\n--- {label} (n={len(df)}) ---")
    print(f"  overnight: mean={overnight_stats['mean']:+.6f} t={overnight_stats['t_stat']:+.3f} "
          f"p={overnight_stats['p_value']:.4f}  複利報酬={overnight_stats['compounded_return']:+.2%}  "
          f"log貢獻占比={overnight_occupancy:+.1f}%")
    print(f"  intraday:  mean={intraday_stats['mean']:+.6f} t={intraday_stats['t_stat']:+.3f} "
          f"p={intraday_stats['p_value']:.4f}  複利報酬={intraday_stats['compounded_return']:+.2%}  "
          f"log貢獻占比={intraday_occupancy:+.1f}%")
    print(f"  配對t檢定(overnight vs intraday差異): t={paired_t:+.3f} p={paired_p:.4f}")
    print(f"  期間總複利報酬(close_end/close_start-1)={np.exp(total_log_sum) - 1:+.2%}")

    return {
        "label": label, "n": len(df),
        "overnight": overnight_stats, "intraday": intraday_stats,
        "overnight_occupancy": overnight_occupancy, "intraday_occupancy": intraday_occupancy,
        "paired_t": float(paired_t), "paired_p": float(paired_p),
        "total_log_sum": total_log_sum,
    }


def main():
    df = build_decomposed_series()
    print(f"對齊後總交易日數: {len(df)}")
    print(f"日期範圍: {df['date'].min().date()} ~ {df['date'].max().date()}")

    max_err = _sanity_check_identity(df)
    print(f"恆等式sanity檢查通過：(1+overnight)(1+intraday)-1 == total_ret，最大絕對誤差={max_err:.2e}")

    train_df, val_df = _split(df)
    print(f"\nTRAIN(<= {TRAIN_END}): n={len(train_df)}  VAL({TRAIN_END}~{VAL_END}): n={len(val_df)}")

    train_result = evaluate_period(train_df, f"TRAIN (<= {TRAIN_END})")
    val_result = evaluate_period(val_df, f"VAL ({TRAIN_END} ~ {VAL_END})")

    print("\n=== 第1關cheap gate事前綁定判準 ===")
    verdict_legs = {}
    for leg in ("overnight", "intraday"):
        train_leg = train_result[leg]
        val_leg = val_result[leg]
        same_sign = (train_leg["mean"] > 0) == (val_leg["mean"] > 0)
        both_significant = train_leg["p_value"] < SIG_LEVEL and val_leg["p_value"] < SIG_LEVEL
        occ_key = f"{leg}_occupancy"
        train_occ = train_result[occ_key]
        val_occ = val_result[occ_key]
        both_deviate = (
            abs(train_occ - 50.0) > CONTRIB_DEVIATION_THRESHOLD
            and abs(val_occ - 50.0) > CONTRIB_DEVIATION_THRESHOLD
        )
        leg_pass = same_sign and both_significant and both_deviate
        verdict_legs[leg] = leg_pass
        print(f"  [{leg}] 同號={same_sign} (TRAIN mean={train_leg['mean']:+.6f}, "
              f"VAL mean={val_leg['mean']:+.6f})")
        print(f"  [{leg}] 兩期皆顯著(p<{SIG_LEVEL})={both_significant} "
              f"(TRAIN p={train_leg['p_value']:.4f}, VAL p={val_leg['p_value']:.4f})")
        print(f"  [{leg}] 兩期log貢獻占比皆偏離50%±{CONTRIB_DEVIATION_THRESHOLD}={both_deviate} "
              f"(TRAIN={train_occ:+.1f}%, VAL={val_occ:+.1f}%)")
        print(f"  [{leg}] 該段判準通過={leg_pass}\n")

    verdict = "CHEAP_PASS" if any(verdict_legs.values()) else "FAIL"
    print(f"判定: {verdict}  (overnight段通過={verdict_legs['overnight']}, "
          f"intraday段通過={verdict_legs['intraday']})")

    df.to_csv("data/overnight_intraday_taiex_decomposed.csv", index=False)

    return {"train": train_result, "val": val_result, "verdict": verdict, "legs": verdict_legs}


if __name__ == "__main__":
    main()
