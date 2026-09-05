"""`TRIALS_LEDGER.md`#140 `margin_debt_level_v1` 第2關深挖之一：trailing窗口
參數穩健性檢查（排除「156週剛好是巧合窗口」的疑慮）。

**背景**：round375（`margin_debt_level_gate.py`）用trailing156週(~3年)百分位
排名，在60d(12w)horizon上得到CHEAP_PASS（TRAIN corr=+0.1170/p=0.0612邊緣、
VAL corr=+0.4567/p<0.0001），但round375自己保留「TRAIN弱、VAL特別強」的
疑慮，且20d/60d兩窗口矛盾也需要排除horizon選擇的多重比較效果。round375
「下一步」明確點名：trailing窗口156週改104/208週是否還過關，排除window
長度巧合——本檔案補做這個檢查。

**事前綁定判準（寫在跑之前，看到結果不得回頭調整）**：
只檢查60d(12w) horizon（20d已經在round375明確FAIL，不重複測，避免對已死
結論做無意義的多重比較）。104週、208週兩個替代trailing窗口，套用跟156週
完全相同的`evaluate_factor`三判準（幅度>0.05兩期、train/val同號為正、VAL
percentile>=90）。**穩健性判定**：
- 兩個替代窗口皆CHEAP_PASS → 支持水位訊號對窗口選擇穩健，疑慮降低。
- 兩個替代窗口皆FAIL → 156週是孤立巧合視窗，`margin_debt_level_v1`
  60d結果應降級為「窗口選擇巧合」，不建議繼續往下一關deep dive。
- 一個過一個不過 → 部分穩健，誠實記錄，仍需更多獨立證據（例如不同的
  TAIEX回撤定義）才能判定，不直接升級也不直接降級。

**資料**：零新增API呼叫，完全重用`margin_debt_level_gate.py`／
`margin_debt_growth_gate.py`既有函式與快取（`backfill_margin_debt_market.py`
662週檔＋既有TAIEX日線快取）。

2026-09-05 馬拉松第377輪（TW軌）新增，接續round375「下一步(a)」。
"""
from __future__ import annotations

import pandas as pd

from margin_debt_growth_gate import MIN_ABS_CORR, _load_taiex_daily
from margin_debt_level_gate import (
    _build_pairs,
    _level_percentile,
    _load_margin_series,
    _split,
    evaluate,
)

HORIZON_DAYS = 60
HORIZON_LABEL = "60d(12w)"
CANDIDATE_TRAILING_WEEKS = (104, 156, 208)


def run_one(margin: pd.DataFrame, taiex: pd.DataFrame, trailing_weeks: int) -> dict:
    margin = margin.copy()
    margin["level_pct"] = _level_percentile(margin["balance"], trailing_weeks)
    n_valid = margin["level_pct"].notna().sum()

    pairs = _build_pairs(margin, taiex, HORIZON_DAYS, "level_pct")
    train, val = _split(pairs)
    print(f"\n########## trailing={trailing_weeks}週 {HORIZON_LABEL} "
          f"暖身後可用={n_valid}/{len(margin)} config_pairs={len(pairs)} "
          f"train_n={len(train)} val_n={len(val)} ##########")

    train_result = evaluate(train, f"TRAIN trailing={trailing_weeks}週")
    val_result = evaluate(val, f"VAL trailing={trailing_weeks}週")

    nontrivial = (abs(train_result["corr"]) > MIN_ABS_CORR
                  and abs(val_result["corr"]) > MIN_ABS_CORR)
    same_sign = (train_result["corr"] > 0) == (val_result["corr"] > 0)
    both_positive = train_result["corr"] > 0 and val_result["corr"] > 0
    beats_null = val_result["null_percentile"] >= 90.0
    verdict = "CHEAP_PASS" if (nontrivial and same_sign and both_positive and beats_null) else "FAIL"

    print(f"  1. 幅度非零(|corr|>{MIN_ABS_CORR}兩期): {nontrivial}")
    print(f"  2. train/val同號且為正: {same_sign and both_positive} "
          f"(TRAIN={train_result['corr']:+.4f}, VAL={val_result['corr']:+.4f})")
    print(f"  3. VAL贏過洗牌null(>=90.0): {beats_null} (percentile={val_result['null_percentile']:.1f})")
    print(f"  判定(trailing={trailing_weeks}週): {verdict}")

    return {
        "trailing_weeks": trailing_weeks,
        "n_valid": int(n_valid),
        "train_n": train_result["n"], "train_corr": train_result["corr"], "train_p": train_result["p"],
        "val_n": val_result["n"], "val_corr": val_result["corr"], "val_p": val_result["p"],
        "val_null_percentile": val_result["null_percentile"],
        "verdict": verdict,
    }


def main():
    print("=== margin_debt_level_v1 trailing窗口參數穩健性檢查（104/156/208週，60d horizon）===")
    margin = _load_margin_series()
    taiex = _load_taiex_daily()
    print(f"融資週檔筆數(is_trading_day=True): {len(margin)}  TAIEX日線筆數: {len(taiex)}")

    rows = [run_one(margin, taiex, w) for w in CANDIDATE_TRAILING_WEEKS]
    df = pd.DataFrame(rows)
    df.to_csv("data/margin_debt_level_window_robustness_results.csv", index=False)

    print("\n=== 總結（104/156/208週，60d horizon）===")
    for r in rows:
        print(f"  trailing={r['trailing_weeks']:>3}週: {r['verdict']:>10}  "
              f"TRAIN corr={r['train_corr']:+.4f}(p={r['train_p']:.4f})  "
              f"VAL corr={r['val_corr']:+.4f}(p={r['val_p']:.4f})  "
              f"VAL_null_pct={r['val_null_percentile']:.1f}")

    alt = [r for r in rows if r["trailing_weeks"] != 156]
    n_alt_pass = sum(1 for r in alt if r["verdict"] == "CHEAP_PASS")
    if n_alt_pass == len(alt):
        robustness = "穩健（兩個替代窗口皆CHEAP_PASS，156週不是孤立巧合視窗）"
    elif n_alt_pass == 0:
        robustness = "不穩健（兩個替代窗口皆FAIL，156週疑似孤立巧合視窗，60d結果應降級）"
    else:
        robustness = "部分穩健（僅一個替代窗口過關，證據不足以升級也不足以降級，需更多獨立檢查）"
    print(f"\n事前綁定判準結論：{robustness}")
    return {"rows": rows, "robustness": robustness}


if __name__ == "__main__":
    main()
