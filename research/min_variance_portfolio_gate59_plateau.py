"""`HYPOTHESIS_QUEUE.md` #59 最小變異數投資組合建構 第3關 參數密集高原。

**為什麼要測`COV_WINDOW`而不是`REBAL_FREQ`**：`REBAL_FREQ=21`是`#29`/`#58`/
`#59`三條假設共用的錨點，不是`#59`自己挑選的參數，`#29`第3關已經掃過它的
高原（`equal_weight_rebalance_plateau_v1.py`，17點9/17以上通過）。`#59`
真正獨有、有可能被質疑「事後挑選剛好好看的點」的參數是`COV_WINDOW=60`
（trailing日報酬窗口，用於Ledoit-Wolf共變異數估計）——這是本關要測的高原
軸，`REBAL_FREQ`維持固定21天不掃描。

**事前綁定的判定標準（見`HYPOTHESIS_QUEUE.md` #59條目「GATE_SEQUENCE第3關
事前綁定規格」段落，執行前已寫好，不看到數字才回頭調）**：
1. 一整片門檻：13個網格點中，TRAIN/VAL溢酬同時為正的比例>=70%（>=9/13點）。
2. 非孤立尖峰：通過判準1的點須形成連續區段，最長連續通過區段長度>=4點
   （約30.8%，比照`#29`第3關5/17=29.4%同一個比例級距）。
3. 原60日參數點本身仍要在通過範圍內。
三項全過才算通過第3關，任一項未過依協定判FAIL。

複用`min_variance_portfolio_gate59.py`的`load_prices`/`build_panel`/
`min_variance_weights`/`simulate`/`summarize`，不重寫計算邏輯（跟`equal_
weight_rebalance_plateau_v1.py`複用`equal_weight_rebalance_sanity.py`同一個
精神）。

2026-09-08 hypothesis_queue排程接續，佇列#59第3關接續第2關（已PASS）執行。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from min_variance_portfolio_gate59 import (
    REBAL_FREQ,
    build_panel,
    load_prices,
    simulate,
    summarize,
)
from validation import holdout

GRID = sorted(set(range(20, 141, 10)) | {60})  # 20,30,...,140 + 原60日參數點，共13點
ANCHOR_COV_WINDOW = 60  # 第1/2關已驗證的原始參數點，必須落在高原內
PLATEAU_HIT_RATE_THRESHOLD = 0.70
MIN_CONSECUTIVE_RUN = 4


def premium_for_cov_window(panel: pd.DataFrame, cov_window: int) -> dict:
    sim = simulate(panel, REBAL_FREQ, cov_window)
    train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
    out = {"cov_window": cov_window}
    for label, mask in (("train", train_mask), ("val", val_mask)):
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        mv = summarize(sub["minvar_ret"])
        out[f"{label}_premium"] = mv["total_return"] - bh["total_return"]
    return out


def longest_consecutive_run(flags: list[bool]) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def main():
    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟sanity/第2關共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"應與sanity/第2關159檔一致（交叉確認）")

    if panel.shape[1] < 30:
        print(f"PLATEAU FAIL: panel({panel.shape[1]}檔)過少，判結構性不可靠，不繼續")
        return

    print(f"\nREBAL_FREQ固定={REBAL_FREQ}日（跟#29/#58共用錨點，不掃描），"
          f"COV_WINDOW網格={GRID}（共{len(GRID)}點）")

    records = []
    for i, cw in enumerate(GRID):
        rec = premium_for_cov_window(panel, cw)
        records.append(rec)
        print(f"  [{i+1}/{len(GRID)}] COV_WINDOW={cw:>3}日 完成："
              f"TRAIN溢酬={rec['train_premium']:+.2%}  VAL溢酬={rec['val_premium']:+.2%}")

    df = pd.DataFrame(records)

    both_positive = (df["train_premium"] > 0) & (df["val_premium"] > 0)
    hit_rate = float(both_positive.mean())
    longest_run = longest_consecutive_run(list(both_positive))
    anchor_row = df[df["cov_window"] == ANCHOR_COV_WINDOW].iloc[0]
    anchor_in_plateau = bool(
        anchor_row["train_premium"] > 0 and anchor_row["val_premium"] > 0
    )

    print(f"\n=== 第3關參數密集高原結果（GRID={GRID}） ===")
    for _, row in df.iterrows():
        mark = "PASS" if (row["train_premium"] > 0 and row["val_premium"] > 0) else "    "
        anchor_mark = " <-- 原60日參數點" if int(row["cov_window"]) == ANCHOR_COV_WINDOW else ""
        print(f"  [{mark}] COV_WINDOW={int(row['cov_window']):>3}日  "
              f"TRAIN溢酬={row['train_premium']:+.2%}  VAL溢酬={row['val_premium']:+.2%}{anchor_mark}")

    print(f"\n判準1：一整片門檻 —— {both_positive.sum()}/{len(GRID)}點同時為正 "
          f"= {hit_rate:.1%}（門檻>=70%）  {'PASS' if hit_rate >= PLATEAU_HIT_RATE_THRESHOLD else 'FAIL'}")
    print(f"判準2：最長連續通過區段 = {longest_run}點（門檻>={MIN_CONSECUTIVE_RUN}點，"
          f"非孤立尖峰）  {'PASS' if longest_run >= MIN_CONSECUTIVE_RUN else 'FAIL'}")
    print(f"判準3：原60日參數點本身在高原內 —— TRAIN={anchor_row['train_premium']:+.2%}  "
          f"VAL={anchor_row['val_premium']:+.2%}  {'PASS' if anchor_in_plateau else 'FAIL'}")

    all_pass = (
        hit_rate >= PLATEAU_HIT_RATE_THRESHOLD
        and longest_run >= MIN_CONSECUTIVE_RUN
        and anchor_in_plateau
    )
    print(f"\n=== 第3關綜合判定：{'PASS' if all_pass else 'FAIL'} ===")

    out_path = Path(__file__).parent / "data" / "min_variance_portfolio_gate59_plateau_grid.csv"
    df.to_csv(out_path, index=False)
    print(f"\n網格明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"
    return df, all_pass


if __name__ == "__main__":
    main()
