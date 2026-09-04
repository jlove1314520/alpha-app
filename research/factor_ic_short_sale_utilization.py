"""`HYPOTHESIS_QUEUE.md` #36 個股融券使用率（Short Sale Utilization Ratio）
的第1關cheap IC gate。

經濟理由：融券使用率（ShortSaleTodayBalance/ShortSaleLimit）越高，代表越多
放空者集中做空該股票——放空需付借券成本、承擔下檔有限上檔理論無限的不對稱
風險，願意承擔者通常握有額外資訊優勢，是資訊驅動（知情悲觀）而非流動性
驅動的訊號（Asquith, Pathak & Ritter 2005；Cohen, Diether & Malloy 2007）。
跟`#30`個股融資使用率（已FAIL，`TRIALS_LEDGER.md`#120）資料源相同但欄位/
投資人族群/機制方向相反，完整區隔說明見`HYPOTHESIS_QUEUE.md` #36條目
「經濟理由」段落。

**事前綁定方向為負**：融券使用率越高，預期未來報酬越差（IC應為負）——
`f_short_sale_utilization`因子值保留原始比例、不取負號（跟`f_margin_
utilization`同樣「原始方向即預期方向」慣例）。這裡預先寫明：cheap gate
若跑出train/val同號但方向為正，即視為方向假設證偽，不因為符合
`evaluate_factor()`的「同號」判準就宣稱通過，仍要在deep_dive小節誠實記錄
方向不如預期。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架。Standalone
single-factor test (bonferroni_n=1)。SAMPLE_SIZE已在`factor_ic.py`校準為
300（2026-09-04 `CALIBRATION_PROBE.md`乙結論，非本次改動）。

2026-09-05 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#36第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_short_sale_utilization"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label=(
            "個股融券使用率 (f_short_sale_utilization, ShortSaleTodayBalance/"
            "ShortSaleLimit), HYPOTHESIS_QUEUE.md#36新假設, "
            "事前綁定方向為負, standalone (bonferroni_n=1)"
        ),
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
