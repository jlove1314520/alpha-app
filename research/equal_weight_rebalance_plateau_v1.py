"""`HYPOTHESIS_QUEUE.md` #29 等權重再平衡溢酬 Diversification Return /
Equal-Weight Rebalancing Premium 第3關 參數密集高原。

**為什麼要做這關**：sanity（第1關PASS）跟隨機控制組（第2關CHEAP_PASS）都只
測了`REBAL_FREQ=21`這一個參數點。`HYPOTHESIS_QUEUE.md`統一關卡第3項要求
「附近一整片參數都要能過，不是剛好三個點湊巧過」——如果只有21天附近極窄
一小段有效、其餘再平衡頻率都轉負或不穩定，代表這個「溢酬」很可能是21天
這個特定選擇的偶然巧合（例如剛好對到某個季節性雜訊），不是Booth & Fama
(1992)理論主張的、對再平衡頻率不敏感的結構性機制。

**具體做法**：固定sanity版本的159檔panel（跟第1/2關同一組資料，事前綁定不
換），對`REBAL_FREQ`跑密集網格（5~80交易日，step=5，共16個點，涵蓋約
週頻到季頻），每個點各算一次TRAIN/VAL兩期的再平衡溢酬（rebalanced -
buyhold total_return），跟第1/2關用同一個`simulate()`/`summarize()`函式，
不重寫計算邏輯。

**事前綁定的判定標準（PASS/FAIL依這裡寫的，不看到數字才回頭調）**：
1. **「一整片」門檻**：16個網格點中，TRAIN與VAL溢酬同時為正的比例
   >=70%（>=11/16點）——不要求100%（極短頻率如5天可能被換手雜訊主導，
   允許邊緣有例外），但要求明顯多數，不是「剛好21天附近3個點過、其餘
   全部失敗」這種孤立尖峰。
2. **非孤立尖峰**：通過門檻1的點必須形成連續區段（不能是東一點西一點
   分散在網格兩端、中間全部斷開）——用「最長連續通過區段長度」
   >=5個網格點（=25交易日跨距）驗證，呼應協定「日曆假高原/孤立尖峰」
   的示警（單點暴衝、鄰居很低＝aliasing，不是真高原）。
3. **原21天參數點本身仍要在通過範圍內**（不能是"其他頻率更好但21天剛好
   最差"這種倒果為因的情況——第1/2關的結論基礎是21天，高原要包含它）。
三項全過才算通過第3關，任一項未過依協定判**FAIL**（代表21天這個結果
是孤立僥倖，不是穩健的參數高原）。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#29第3關
接續第2關（`equal_weight_rebalance_control_v1.py`，已CHEAP_PASS）執行。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from equal_weight_rebalance_sanity import (
    build_panel,
    load_prices,
    simulate,
    summarize,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import holdout

GRID = sorted(set(range(5, 81, 5)) | {21})  # 5,10,...,80交易日+原21天參數點，共17點
ANCHOR_FREQ = 21  # 第1/2關已驗證的原始參數點，必須落在高原內
PLATEAU_HIT_RATE_THRESHOLD = 0.70
MIN_CONSECUTIVE_RUN = 5


def premium_for_freq(panel: pd.DataFrame, rebal_freq: int) -> dict:
    sim = simulate(panel, rebal_freq)
    train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
    out = {"rebal_freq": rebal_freq}
    for label, mask in (("train", train_mask), ("val", val_mask)):
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        rb = summarize(sub["rebal_ret"])
        out[f"{label}_premium"] = rb["total_return"] - bh["total_return"]
    return out


def longest_consecutive_run(flags: list[bool]) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def main():
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

    records = [premium_for_freq(panel, f) for f in GRID]
    df = pd.DataFrame(records)

    both_positive = (df["train_premium"] > 0) & (df["val_premium"] > 0)
    hit_rate = float(both_positive.mean())
    longest_run = longest_consecutive_run(list(both_positive))
    anchor_row = df[df["rebal_freq"] == ANCHOR_FREQ].iloc[0]
    anchor_in_plateau = bool(
        anchor_row["train_premium"] > 0 and anchor_row["val_premium"] > 0
    )

    print(f"\n=== 第3關參數密集高原結果（GRID={GRID}） ===")
    for _, row in df.iterrows():
        mark = "✓" if (row["train_premium"] > 0 and row["val_premium"] > 0) else " "
        anchor_mark = " <-- 原21天參數點" if int(row["rebal_freq"]) == ANCHOR_FREQ else ""
        print(f"  [{mark}] REBAL_FREQ={int(row['rebal_freq']):>3}日  "
              f"TRAIN溢酬={row['train_premium']:+.2%}  VAL溢酬={row['val_premium']:+.2%}{anchor_mark}")

    print(f"\n判準1：一整片門檻 —— {both_positive.sum()}/{len(GRID)}點同時為正 "
          f"= {hit_rate:.1%}（門檻>=70%）  {'PASS' if hit_rate >= PLATEAU_HIT_RATE_THRESHOLD else 'FAIL'}")
    print(f"判準2：最長連續通過區段 = {longest_run}點（門檻>={MIN_CONSECUTIVE_RUN}點，"
          f"非孤立尖峰）  {'PASS' if longest_run >= MIN_CONSECUTIVE_RUN else 'FAIL'}")
    print(f"判準3：原21天參數點本身在高原內 —— TRAIN={anchor_row['train_premium']:+.2%}  "
          f"VAL={anchor_row['val_premium']:+.2%}  {'PASS' if anchor_in_plateau else 'FAIL'}")

    all_pass = (
        hit_rate >= PLATEAU_HIT_RATE_THRESHOLD
        and longest_run >= MIN_CONSECUTIVE_RUN
        and anchor_in_plateau
    )
    print(f"\n=== 第3關綜合判定：{'PASS' if all_pass else 'FAIL'} ===")

    out_path = Path(__file__).parent / "data" / "equal_weight_rebalance_plateau_v1_grid.csv"
    df.to_csv(out_path, index=False)
    print(f"\n網格明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")


if __name__ == "__main__":
    main()
