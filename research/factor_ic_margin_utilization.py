"""`HYPOTHESIS_QUEUE.md` #30 個股融資使用率（Margin Financing Utilization
Ratio）的第1關cheap IC gate。

經濟理由：融資使用率（MarginPurchaseTodayBalance/MarginPurchaseLimit）越高，
代表越多散戶用槓桿持有該股票，股價下跌時維持率不足觸發券商追繳/斷頭賣壓，
是流動性驅動（forced liquidation）而非資訊驅動的賣壓（Brunnermeier & Pedersen
2009 margin spiral機制）。跟前29條假設在機制分類上是第五類正交維度，完整
四類回顧見`HYPOTHESIS_QUEUE.md` #30條目「經濟理由」段落。

**事前綁定方向為負**：融資使用率越高，預期未來報酬越差（IC應為負）——
`f_margin_utilization`因子值保留原始比例、不取負號（跟`f_amihud_illiq`同樣
「原始方向即預期方向」慣例）。這裡預先寫明：cheap gate若跑出train/val同號
但方向為正，即視為方向假設證偽，不因為符合`evaluate_factor()`的「同號」
判準就宣稱通過，仍要在deep_dive小節誠實記錄方向不如預期。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架。Standalone
single-factor test (bonferroni_n=1)。SAMPLE_SIZE已在`factor_ic.py`校準為
300（2026-09-04 `CALIBRATION_PROBE.md`乙結論，非本次改動）。

2026-09-04 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#30第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_margin_utilization"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label=(
            "個股融資使用率 (f_margin_utilization, MarginPurchaseTodayBalance/"
            "MarginPurchaseLimit), HYPOTHESIS_QUEUE.md#30新假設, "
            "事前綁定方向為負, standalone (bonferroni_n=1)"
        ),
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
