"""`HYPOTHESIS_QUEUE.md` #29 等權重再平衡溢酬 Diversification Return /
Equal-Weight Rebalancing Premium 第2關 隨機控制組。

**為什麼不能直接套用`factor_ic.py`既有的洗牌null（沿用sanity留下的判斷）**：
既有IC類假設的null是「打散因子值跟未來報酬的配對」——前提是假設本身在測
「某個排序依據能不能挑出比較會漲的股票」。這條假設完全沒有排序/選股動作
（樣本裡每一檔股票拿到一樣的權重），打散因子值這個動作對它沒有意義。

**這條假設專屬的控制組設計（事前綁定，寫在這裡之後才跑，不事後移動門柱）**：
Booth & Fama (1992) diversification return的理論主張是——只要成分股報酬
有波動度、彼此相關係數<1，定期拉回等權重這個機械動作本身就會產生正的
溢酬，**跟挑中哪些特定股票無關**。如果sanity算出來的正溢酬只是「剛好這
159檔通過涵蓋度篩選的組合」這個特定股票池構成的運氣（呼應`BACKLOG.md`
偽影六家族第③種「縮小候選池」型偽影精神），換一批隨機抽出的子集應該就
測不到同樣穩健的效果；如果是真正的結構性機制，換誰進來都該穩健出現。

**具體做法**：固定sanity版本的再平衡規則（`REBAL_FREQ=21`交易日、相位
offset=0，不改），對sanity版本159檔panel做**無放回bootstrap**，每次抽
`SUBSET_SIZE=80`檔（約全池的一半，夠小以確保子集組成真的不同、夠大以
不讓單一極端股票主導整體分散效果），重跑`simulate()`計算TRAIN/VAL兩期
的再平衡溢酬(rebalanced total_return - buyhold total_return)，共
`N_DRAWS=100`次獨立抽樣（`MASTER_SEED=20260904`，每次抽樣用
`MASTER_SEED+draw_idx`保證可重現）。

**事前綁定的判定標準（PASS/FAIL依這裡寫的，不看到數字才回頭調）**：
1. **hit_rate（TRAIN與VAL同時為正溢酬的抽樣比例）>=80%**——多數隨機
   組成都該重現正向效果，不能只有恰好那159檔特別幸運。
2. **原始159檔全池的溢酬（sanity算出的TRAIN+24.81pp/VAL+31.72pp）落在
   bootstrap分布的10th~90th百分位之間**——不是極端離群值需要特定幸運組合
   才能達到。
3. **bootstrap分布的中位數溢酬明顯>0**（TRAIN與VAL皆然）——分布本身不是
   以0為中心、只是偶爾靠雜訊翹到正的。
三項全過才算通過第2關（`CHEAP_PASS`），任一項未過依協定判**FAIL**（不用
再等第3關以後，因為這代表效果本身就不穩健，不是「表現普通但方向對」）。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#29第2關
接續sanity（`equal_weight_rebalance_sanity.py`，已PASS非最終判定）執行。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from equal_weight_rebalance_sanity import (
    REBAL_FREQ,
    WINDOW_END,
    WINDOW_START,
    build_panel,
    load_prices,
    simulate,
    summarize,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import holdout

SUBSET_SIZE = 80
N_DRAWS = 100
MASTER_SEED = 20260904


def premium_for_columns(panel: pd.DataFrame, cols: list[str]) -> dict:
    """對panel的一個子集(cols)跑simulate，回傳TRAIN/VAL兩期的再平衡溢酬。"""
    sub_panel = panel[cols]
    sim = simulate(sub_panel, REBAL_FREQ)
    train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
    out = {}
    for label, mask in (("train", train_mask), ("val", val_mask)):
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        rb = summarize(sub["rebal_ret"])
        out[f"{label}_premium"] = rb["total_return"] - bh["total_return"]
    return out


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟sanity版本共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"全池panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"跟sanity版本應完全一致（159檔，作為交叉確認）")

    if panel.shape[1] < SUBSET_SIZE + 10:
        print(f"CONTROL FAIL: 全池({panel.shape[1]}檔)不夠抽{SUBSET_SIZE}檔子集，判結構性不可靠，不繼續")
        return

    full_pool_result = premium_for_columns(panel, list(panel.columns))
    print(f"\n全池({panel.shape[1]}檔)基準溢酬：TRAIN={full_pool_result['train_premium']:+.2%}  "
          f"VAL={full_pool_result['val_premium']:+.2%}"
          f"（應與sanity腳本結果一致，作為交叉確認：sanity記錄TRAIN+24.81pp/VAL+31.72pp）")

    all_cols = list(panel.columns)
    records = []
    for draw_idx in range(N_DRAWS):
        rng = np.random.RandomState(MASTER_SEED + draw_idx)
        cols = list(rng.choice(all_cols, size=SUBSET_SIZE, replace=False))
        result = premium_for_columns(panel, cols)
        records.append(result)
        if (draw_idx + 1) % 20 == 0:
            print(f"  進度：{draw_idx + 1}/{N_DRAWS} draws完成")

    df = pd.DataFrame(records)
    train_premiums = df["train_premium"]
    val_premiums = df["val_premium"]

    hit_rate = float(((train_premiums > 0) & (val_premiums > 0)).mean())
    train_pctl = float((train_premiums < full_pool_result["train_premium"]).mean() * 100)
    val_pctl = float((val_premiums < full_pool_result["val_premium"]).mean() * 100)
    train_median = float(train_premiums.median())
    val_median = float(val_premiums.median())

    print(f"\n=== 第2關隨機控制組結果（N={N_DRAWS} draws, SUBSET_SIZE={SUBSET_SIZE}） ===")
    print(f"TRAIN溢酬分布：median={train_median:+.2%}  mean={train_premiums.mean():+.2%}  "
          f"std={train_premiums.std():.2%}  min={train_premiums.min():+.2%}  max={train_premiums.max():+.2%}")
    print(f"VAL溢酬分布：  median={val_median:+.2%}  mean={val_premiums.mean():+.2%}  "
          f"std={val_premiums.std():.2%}  min={val_premiums.min():+.2%}  max={val_premiums.max():+.2%}")
    print(f"\n判準1：hit_rate(TRAIN且VAL同時為正) = {hit_rate:.1%}  （門檻>=80%）"
          f"  {'PASS' if hit_rate >= 0.80 else 'FAIL'}")
    print(f"判準2：全池結果在bootstrap分布的百分位 —— TRAIN={train_pctl:.1f}%ile  VAL={val_pctl:.1f}%ile"
          f"  （門檻10~90之間）"
          f"  {'PASS' if 10.0 <= train_pctl <= 90.0 and 10.0 <= val_pctl <= 90.0 else 'FAIL'}")
    print(f"判準3：中位數溢酬明顯>0 —— TRAIN median={train_median:+.2%}  VAL median={val_median:+.2%}"
          f"  {'PASS' if train_median > 0 and val_median > 0 else 'FAIL'}")

    all_pass = (
        hit_rate >= 0.80
        and 10.0 <= train_pctl <= 90.0
        and 10.0 <= val_pctl <= 90.0
        and train_median > 0
        and val_median > 0
    )
    print(f"\n=== 第2關綜合判定：{'CHEAP_PASS' if all_pass else 'FAIL'} ===")

    out_path = Path(__file__).parent / "data" / "equal_weight_rebalance_control_v1_draws.csv"
    df.to_csv(out_path, index=False)
    print(f"\n{N_DRAWS}次抽樣明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")


if __name__ == "__main__":
    main()
