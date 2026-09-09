"""`HYPOTHESIS_QUEUE.md` #68 券資比（Short-to-Margin Ratio）的第1關cheap IC gate。

經濟理由：融券今日餘額(ShortSaleTodayBalance) / 融資今日餘額
(MarginPurchaseTodayBalance)，捕捉同一檔股票放空籌碼相對做多槓桿籌碼的比值
（多空分歧程度／軋空風險）：券資比偏高代表放空籌碼相對做多槓桿籌碼多，若
股價開始上漲，看空者被迫回補（軋空）會放大且延續漲勢。跟已FAIL的#26（全
市場融資餘額成長率，市場整體槓桿水位）、#30（個股融資使用率，強制平倉/
流動性螺旋）、#36（個股融券使用率，放空水位本身）在機制分類上不同——本
假設測的是「融券相對融資」的比值關係，完整經濟理由見`HYPOTHESIS_QUEUE.md`
#68條目。

**事前綁定方向為正**：券資比越高，預期未來報酬越好（IC應為正）——
`f_short_margin_ratio`因子值保留原始比例、不取負號（跟`f_margin_
utilization`/`f_short_sale_utilization`同樣「原始方向即預期方向」慣例）。
這裡預先寫明：cheap gate若跑出train/val同號但方向為負，即視為方向假設
證偽，不因為符合`evaluate_factor()`的「同號」判準就宣稱通過，仍要在
deep_dive小節誠實記錄方向不如預期。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架。Standalone
single-factor test (bonferroni_n=1)。SAMPLE_SIZE已在`factor_ic.py`校準為
300（2026-09-04 `CALIBRATION_PROBE.md`乙結論，非本次改動）。

2026-09-10 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#68第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_short_margin_ratio"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label=(
            "券資比 (f_short_margin_ratio, ShortSaleTodayBalance/"
            "MarginPurchaseTodayBalance), HYPOTHESIS_QUEUE.md#68新假設, "
            "事前綁定方向為正, standalone (bonferroni_n=1)"
        ),
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
