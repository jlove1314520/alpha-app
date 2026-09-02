"""`HYPOTHESIS_QUEUE.md` #20 純毛利率因子（Gross Profitability，Novy-Marx
2013）：`f_gross_profitability`（GrossProfit / TotalAssets，比率越高排名
越靠前）的第1關cheap IC gate。

經濟理由：核心業務真正的獲利能力（毛利，不受財務槓桿/業外損益污染）相對
公司資產規模，市場對這個訊號的定價效率不足，超額報酬被認為是行為性（低估
持續）而非承擔額外系統性風險的補償。跟已FAIL的`f_gross_margin_stability`
（`TRIALS_LEDGER.md`#67，測毛利率隨時間的「穩定性」）不是同一個構造——這條
測的是毛利率相對總資產的「水位」，Novy-Marx原始論文真正的訊號定義，本專案
至今沒有直接測過這個版本。見`HYPOTHESIS_QUEUE.md`#20。

實作見`factors.py::_gross_profitability()`/`prepare_factors()`「(x) 純
毛利率因子」段落docstring：GrossProfit（`quarterly_pit`損益表）/ TotalAssets
（`balance_sheet_pit`資產負債表），兩者用同一組+45天延遲假設合併，PIT安全。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_residual_momentum/f_52w_high_prox等既有測試同一套機制）。Standalone
single-factor test (bonferroni_n=1)。

2026-09-03 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#20第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_gross_profitability"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="純毛利率因子 (f_gross_profitability, GrossProfit/TotalAssets), HYPOTHESIS_QUEUE.md#20新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
