"""`HYPOTHESIS_QUEUE.md` #25 月轉效應（Turn-of-Month Effect）第1關cheap gate。

經濟理由：Turn-of-month效應（Ariel 1987、Lakonishok & Smidt 1988）——股市
報酬系統性集中在「月底最後一個交易日到月初前N個交易日」這個窄窗口，機構
現金流時點（月薪提撥退休金/定期定額基金申購集中月初、月底windows dressing）
是經濟機制。跟已測過的三種「非選股timing」機制（#10 regime overlay、#15
vol-targeting、#19+spillover overlay）不同——這條用日曆本身的結構性位置，
不依賴任何連續型市場數據。見`HYPOTHESIS_QUEUE.md`#25完整經濟理由段落。

**月轉窗口定義（不用自然日期近似，用實際交易日序列避免國定假日/颱風假
誤判）**：當月最後一個交易日 + 次月前N個交易日，N分別測3跟4（文獻常見
兩種定義，第1關就測兩種，不要事後才多重比較新增變體）。

**判定標準（比照本佇列既有cheap gate三項判準：幅度非零/train-val同號/
贏過洗牌null）**：TRAIN=[起點, TRAIN_END]、VAL=(TRAIN_END, VAL_END]
（`validation/holdout.py`既有邊界）。對每期分別算「窗口內日報酬均值 -
窗口外日報酬均值」，對照組是打散「哪些交易日算窗口」這個布林標籤本身
（保留原始報酬序列時序不變，只重新分配標籤位置，數量不變），N=200次，
percentile用單邊（真實diff贏過多少比例的洗牌diff，因為文獻方向預期是
正——窗口內報酬較高，不是雙邊檢定）。

2026-09-03 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#25第1關
起跑。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 200
SHUFFLE_SEED = 20260903
WINDOW_DEFS = (3, 4)
# 3bp/日的窗口內外報酬差，視為「非零、有實質意義」的門檻（不是統計顯著性
# 門檻，只是排除近乎雜訊等級的極小差異）。
MIN_DIFF_BPS = 0.0003


def _daily_returns(ticker: str = "^TWII") -> pd.DataFrame:
    df = fetch_yf_index(ticker=ticker, start_date="2010-01-01")
    df = df.dropna(subset=["close"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    return df.dropna(subset=["ret"]).reset_index(drop=True)


def label_turn_of_month(dates: pd.Series, n_after: int) -> np.ndarray:
    """回傳布林陣列：True=該交易日屬於「月轉窗口」（當月最後一個交易日+
    次月前n_after個交易日），用實際交易日序列的月份切換點判定，不用自然
    日期近似。第一個月沒有「前一個月的月底」可標記其後續n_after天，最後
    一個月的月底也不會被標記（因為沒有下個月資料），這兩處邊界效應在
    15年資料裡影響可忽略。"""
    dates = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    ym = dates.dt.to_period("M").to_numpy()
    n = len(dates)
    is_window = np.zeros(n, dtype=bool)
    change_idx = np.where(ym[1:] != ym[:-1])[0] + 1
    for start_of_next_month in change_idx:
        month_end_idx = start_of_next_month - 1
        is_window[month_end_idx] = True
        is_window[start_of_next_month:start_of_next_month + n_after] = True
    return is_window


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _real_diff(ret: np.ndarray, is_window: np.ndarray) -> float:
    return float(ret[is_window].mean() - ret[~is_window].mean())


def _shuffle_percentile(ret: np.ndarray, is_window: np.ndarray, n: int, seed: int) -> dict:
    real_diff = _real_diff(ret, is_window)
    rng = np.random.default_rng(seed)
    n_true = int(is_window.sum())
    total = len(ret)
    shuffled = np.empty(n)
    for i in range(n):
        perm_idx = rng.permutation(total)[:n_true]
        perm_window = np.zeros(total, dtype=bool)
        perm_window[perm_idx] = True
        shuffled[i] = _real_diff(ret, perm_window)
    # 單邊：真實diff贏過多少比例的洗牌diff（預期方向為正）
    pctl = 100.0 * float(np.mean(shuffled <= real_diff))
    return {
        "real_diff": real_diff,
        "null_median": float(np.median(shuffled)),
        "null_p90": float(np.percentile(shuffled, 90)),
        "percentile": pctl,
    }


def evaluate(df: pd.DataFrame, n_after: int, label: str) -> dict:
    ret = df["ret"].to_numpy()
    is_window = label_turn_of_month(df["date"], n_after)
    n_window = int(is_window.sum())
    n_total = len(df)
    window_mean = float(ret[is_window].mean())
    nonwindow_mean = float(ret[~is_window].mean())
    shuf = _shuffle_percentile(ret, is_window, N_SHUFFLE, SHUFFLE_SEED)
    print(f"\n--- {label} N={n_after} (n_total={n_total}, n_window={n_window}, "
          f"n_nonwindow={n_total - n_window}) ---")
    print(f"  窗口內日均報酬={window_mean:+.5f}  窗口外日均報酬={nonwindow_mean:+.5f}  "
          f"diff={shuf['real_diff']:+.5f}")
    print(f"  洗牌null(N={N_SHUFFLE}): median={shuf['null_median']:+.5f}  "
          f"p90={shuf['null_p90']:+.5f}  真實diff percentile(單邊)={shuf['percentile']:.1f}")
    return {
        "label": label, "n_after": n_after, "n_total": n_total, "n_window": n_window,
        "window_mean": window_mean, "nonwindow_mean": nonwindow_mean,
        "diff": shuf["real_diff"], "null_median": shuf["null_median"],
        "null_percentile": shuf["percentile"],
    }


def main():
    df = _daily_returns("^TWII")
    print(f"TAIEX日報酬總筆數: {len(df)}  日期範圍: {df['date'].min()} ~ {df['date'].max()}")
    train, val = _split(df)
    print(f"TRAIN(<= {TRAIN_END}): n={len(train)}  VAL({TRAIN_END}~{VAL_END}): n={len(val)}")

    # sanity: 用N=3確認每年窗口天數量級合理（約每月4天*12=48天/年，非0非荒謬值）
    sanity_window = label_turn_of_month(df["date"], 3)
    years_span = (df["date"].max() - df["date"].min()).days / 365.25
    window_per_year = sanity_window.sum() / years_span
    print(f"\nsanity: N=3窗口天數/年 = {window_per_year:.1f}（預期約48天/年附近）")
    assert 30 <= window_per_year <= 60, "月轉窗口天數/年不在合理範圍，判定邏輯可能有bug"

    results = []
    verdicts = {}
    for n_after in WINDOW_DEFS:
        train_result = evaluate(train, n_after, f"TRAIN (<= {TRAIN_END})")
        val_result = evaluate(val, n_after, f"VAL ({TRAIN_END} ~ {VAL_END})")
        results.append(train_result)
        results.append(val_result)

        nontrivial = (abs(train_result["diff"]) > MIN_DIFF_BPS
                      and abs(val_result["diff"]) > MIN_DIFF_BPS)
        same_sign = (train_result["diff"] > 0) == (val_result["diff"] > 0)
        both_positive = train_result["diff"] > 0 and val_result["diff"] > 0
        beats_null = val_result["null_percentile"] >= 90.0

        print(f"\n=== N={n_after} 第1關cheap gate三項判準 ===")
        print(f"  1. 幅度非零 (|diff|>{MIN_DIFF_BPS}兩期): {nontrivial}")
        print(f"  2. train/val同號且方向為正(窗口內>窗口外): {same_sign and both_positive} "
              f"(TRAIN diff={train_result['diff']:+.5f}, VAL diff={val_result['diff']:+.5f})")
        print(f"  3. VAL贏過洗牌null(percentile>=90.0): {beats_null} "
              f"(percentile={val_result['null_percentile']:.1f})")

        verdict = "CHEAP_PASS" if (nontrivial and same_sign and both_positive and beats_null) else "FAIL"
        print(f"  判定(N={n_after}): {verdict}")
        verdicts[n_after] = verdict

    print(f"\n=== 總結 ===")
    for n_after, v in verdicts.items():
        print(f"  N={n_after}: {v}")
    overall = "CHEAP_PASS" if any(v == "CHEAP_PASS" for v in verdicts.values()) else "FAIL"
    print(f"整體判定(任一N版本CHEAP_PASS即算過關，供下一關挑選對應N繼續): {overall}")

    pd.DataFrame(results).to_csv("data/turn_of_month_gate_results.csv", index=False)
    return {"verdicts": verdicts, "overall": overall, "results": results}


if __name__ == "__main__":
    main()
