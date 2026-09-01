"""`HYPOTHESIS_QUEUE.md` #4 股票股利率carry：`f_dividend_yield_ttm`
（trailing 12個月現金股利/股價，高殖利率排名靠前）的第1關cheap IC gate。

經濟理由：高股利股票可能反映市場對其成長性/風險的保守定價，也可能反映公司
財務穩健、有持續配息能力，經典價值/收益因子文獻的一支，跟f_value_pb/
f_value_pe（帳面/盈餘估值）是不同的估值角度（現金流分配 vs 資產負債表/
損益表）。期貨端carry已有結論（`TRIALS_LEDGER.md`#35-38），這裡只測股票
股利率這個新角度，見`HYPOTHESIS_QUEUE.md`#4。

PIT安全性見`factors.py::_dividend_yield_ttm_cash()`docstring：ex-date本身
就是生效日，天然PIT-safe，不需要`quarterly_pit`那種延遲假設。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_low_vol/f_eps_surprise等既有PASS因子同一套機制，不是CTA那種單一時間
序列排列測試）。Standalone single-factor test (bonferroni_n=1)。

2026-09-01 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#4第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_dividend_yield_ttm"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="股票股利率carry (f_dividend_yield_ttm, TTM現金股利/股價), HYPOTHESIS_QUEUE.md#4新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
