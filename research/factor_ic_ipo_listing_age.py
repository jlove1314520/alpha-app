# -*- coding: utf-8 -*-
"""`HYPOTHESIS_QUEUE.md` #46 新股上市長期弱勢（IPO Long-Run
Underperformance）：`f_listing_age_days`（距TWSE官方上市日的天數，越大越
上市越久）第1關cheap IC gate。

經濟理由：承銷定價偏樂觀+初期投資人情緒消退的被動衰減過程（Ritter 1991
"The Long-Run Performance of Initial Public Offerings"），跟本佇列已測過
的七種機制（方向性選股排序/timing overlay/portfolio construction/配對
交易均值回歸/強制平倉流動性驅動賣壓/公司行動事件驅動/跨市場套利收斂）都
不同——純粹的「事件時鐘」，不涉及任何人的主動決策。**事前綁定方向為正、
不取負號**：上市越久預期未來報酬越好，見`factors.py::_listing_age_days()`
docstring。

**只覆蓋TWSE現存上市公司**：`f_listing_age_days`用`build_twse_listing_
dates.py`存的官方`上市日期`（1094檔），查不到的股票（TPEx上櫃、已下市、
或本輪`sample_universe_ids()`抽到但未回補）該欄位為NaN，
`factor_ic.py::_cross_section`會自然跳過這些股票在這個因子的橫截面樣本
（不影響它們其他因子），代價是有效樣本數會比其他因子少一些——這是本輪
範圍界定決策的已知、誠實揭露的局限（見`HYPOTHESIS_QUEUE.md`#46），不是
bug。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架。
Standalone single-factor test (bonferroni_n=1)。

2026-09-06 hypothesis_queue排程接續，佇列#46第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_listing_age_days"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="新股上市長期弱勢 (f_listing_age_days, 距TWSE官方上市日天數), "
              "HYPOTHESIS_QUEUE.md#46新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
