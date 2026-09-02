"""`HYPOTHESIS_QUEUE.md` #18 短期反轉（1週，Jegadeesh 1990，流動性溢酬）：
`f_short_term_reversal_1w`（過去5個交易日累積報酬取負號，跌越多分數越高，
排名靠前）的第1關cheap IC gate。

經濟理由：短期反轉是流動性提供者（market maker/流動性交易者）承接短期
價格壓力後要求的溢酬——短期內被過度賣壓的股票，流動性提供者買入承接後
很快推回真實價值附近，產生反轉；這是流動性溢酬機制，不是資訊面機制，跟
本佇列已測過的所有假設（動量/財報意外/籌碼/beta類）經濟機制完全不同
類別。見`HYPOTHESIS_QUEUE.md`#18。

**跟已FAIL的`f_short_reversal_1m`刻意做出區隔**（21交易日/~1個月窗口，
`TRIALS_LEDGER.md`#46，train mean_ic=+0.0496正/val mean_ic=-0.0054接近
零轉負，null percentile=23.1遠未過90.0門檻）——那筆FAIL紀錄的原文明寫
「可能因為80檔樣本規模不足以捕捉短期反轉這種通常需要更細（週頻/日頻
分層）資料才穩定顯現的效應」「若之後樣本擴大或改用更短窗口（1週）可
再測」，這裡就是遵照那個建議、真正測試5個交易日(1週)窗口，不是同一個
已死機制換皮重測。

實作見`factors.py::prepare_factors()`「(w) 短期反轉（1週）」段落docstring：
-(當前收盤價/5個交易日前收盤價-1)，純價格資料天然point-in-time，零額外
API呼叫。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_52w_high_prox/f_residual_momentum等既有測試同一套機制）。Standalone
single-factor test (bonferroni_n=1)。

2026-09-02 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#18第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_short_term_reversal_1w"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="短期反轉1週 (f_short_term_reversal_1w, -(5日累積報酬)), HYPOTHESIS_QUEUE.md#18新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
