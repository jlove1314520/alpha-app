"""`HYPOTHESIS_QUEUE.md` #17 52週高點接近度（George & Hwang 2004，錨定不足）：
`f_52w_high_prox`（當前收盤價/過去252個交易日最高價，比率越接近1代表越接近
52週高點，排名靠前）的第1關cheap IC gate。

經濟理由：股價接近52週高點時，投資人對「創新高」這個顯著錨點反應不足
（anchoring/underreaction），導致價格未能立即反映應有的正面資訊，股價越接近
52週高點者後續報酬顯著較高，文獻上發現這個訊號比傳統動量更強、更不容易被
動量因子解釋掉。跟本佇列已FAIL的10條方向性排序假設有本質差異——那些是
「近期報酬/資訊流」驅動的排序，這條是「價格相對於一個顯著心理錨點的距離」
驅動，訊息來源完全不同。見`HYPOTHESIS_QUEUE.md`#17。

實作見`factors.py::prepare_factors()`「(v) 52週高點接近度」段落docstring：
當前收盤價/過去252個交易日(含當日)滾動最高價，純價格資料天然point-in-time。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_residual_momentum/f_dividend_yield_ttm等既有測試同一套機制）。Standalone
single-factor test (bonferroni_n=1)。

2026-09-02 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#17第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_52w_high_prox"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="52週高點接近度 (f_52w_high_prox, 收盤價/252日滾動最高價), HYPOTHESIS_QUEUE.md#17新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
