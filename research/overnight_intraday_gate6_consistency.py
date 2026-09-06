"""`HYPOTHESIS_QUEUE.md` #49 日內／隔夜報酬結構分解 第6關逐年一致性檢驗。

背景：`HYPOTHESIS_QUEUE_PROTOCOL.md`（本輪）裁示 gate2 placebo 連續兩輪
（隨機時刻切分死於資料不可及；極值切分對照死於選擇偏誤）都卡在方法論
死胡同，建議改道直接跳去做 gate6 逐年一致性檢驗（只需要既有日線 OHLC，
不需要建構任何 placebo/null model），若 gate6 過關再回頭補課 gate2，
若沒過就直接依快殺標準結案。本腳本就是這個「改道」。

只檢驗 gate1 已經 CHEAP_PASS 的那一段——overnight（收盤到隔天開盤）。
intraday 段在 gate1 就沒過（VAL 期不顯著），不需要浪費預算再測一次。

**事前綁定的通過門檻**（比照本佇列 #29/#34 同一把尺：TRAIN 期 6 年
5/6=83.3% 門檻）：本條 TRAIN 期實際涵蓋的年數不是 6 年（gate1 用
`build_decomposed_series()` 預設從 2010-01-01 起算，TRAIN=2010~2020 共
11 個完整/部分年度），套用同一比例門檻——TRAIN 與 VAL 各自獨立要求
「overnight 段年度平均報酬為正（跟 gate1 判定的整體方向一致）」的年數
占比 >= 83.3%（四捨五入取整數年份門檻），兩個窗口都要過，任一窗口沒過
就整體判 FAIL，不能只看其中一個窗口漂亮就放行（同 #29 標準：TRAIN 6年
只要 4/6=66.7% 沒過 83.3% 就判死，不因為其他關卡漂亮而放寬）。

2026-09-07 由 `HYPOTHESIS_QUEUE_PROTOCOL.md` 自動排程新增。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from overnight_intraday_decomposition_gate import build_decomposed_series, _split

CONSISTENCY_THRESHOLD = 5.0 / 6.0  # 83.3%，沿用#29/#34同一把尺


def _year_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """逐年計算overnight段的log貢獻(複利)與簡單平均，回傳每年一列。"""
    work = df.copy()
    work["year"] = work["date"].dt.year
    rows = []
    for year, g in work.groupby("year"):
        log_sum = float(np.log1p(g["overnight_ret"]).sum())
        compounded = float(np.exp(log_sum) - 1.0)
        mean = float(g["overnight_ret"].mean())
        rows.append({
            "year": int(year), "n_days": len(g), "mean_overnight_ret": mean,
            "compounded_overnight_ret": compounded,
        })
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def _consistency_check(year_df: pd.DataFrame, overall_direction_positive: bool, label: str) -> dict:
    n_years = len(year_df)
    if overall_direction_positive:
        same_sign_years = int((year_df["mean_overnight_ret"] > 0).sum())
    else:
        same_sign_years = int((year_df["mean_overnight_ret"] < 0).sum())
    ratio = same_sign_years / n_years if n_years else float("nan")
    required_years = math.ceil(CONSISTENCY_THRESHOLD * n_years)
    passed = same_sign_years >= required_years
    print(f"\n--- {label} 逐年拆解（overnight段，共{n_years}年）---")
    for _, row in year_df.iterrows():
        sign_match = (row["mean_overnight_ret"] > 0) == overall_direction_positive
        mark = "[同號]" if sign_match else "[異號]"
        print(f"  {int(row['year'])}: 年度複利={row['compounded_overnight_ret']:+.2%}  "
              f"日均={row['mean_overnight_ret']:+.6f}  n_days={int(row['n_days'])}  {mark}")
    print(f"  同號年數 = {same_sign_years}/{n_years} = {ratio:.1%}  "
          f"門檻 >= {CONSISTENCY_THRESHOLD:.1%}（需 >= {required_years}/{n_years}年）  "
          f"判準通過={passed}")
    return {
        "label": label, "n_years": n_years, "same_sign_years": same_sign_years,
        "ratio": ratio, "required_years": required_years, "passed": passed,
    }


def main():
    df = build_decomposed_series()
    train_df, val_df = _split(df)

    print(f"TRAIN: n={len(train_df)}日  日期範圍={train_df['date'].min().date()}~{train_df['date'].max().date()}")
    print(f"VAL:   n={len(val_df)}日  日期範圍={val_df['date'].min().date()}~{val_df['date'].max().date()}")

    # gate1已判定overnight段整體方向為正（TRAIN/VAL兩期mean皆為正、同號）
    overall_direction_positive = True

    train_years = _year_breakdown(train_df)
    val_years = _year_breakdown(val_df)

    train_result = _consistency_check(train_years, overall_direction_positive, "TRAIN")
    val_result = _consistency_check(val_years, overall_direction_positive, "VAL")

    verdict = "GATE6_PASS" if (train_result["passed"] and val_result["passed"]) else "FAIL"
    print(f"\n=== 第6關逐年一致性最終判定 ===")
    print(f"TRAIN通過={train_result['passed']}  VAL通過={val_result['passed']}")
    print(f"判定: {verdict}")

    train_years.to_csv("data/overnight_gate6_train_years.csv", index=False)
    val_years.to_csv("data/overnight_gate6_val_years.csv", index=False)

    return {"train": train_result, "val": val_result, "verdict": verdict,
            "train_years": train_years, "val_years": val_years}


if __name__ == "__main__":
    main()
