"""`HYPOTHESIS_QUEUE.md` #9 殘差動量 Residual Momentum（Blitz/Huij/Martens
2011）：`f_residual_momentum`（trailing 252個交易日CAPM單因子迴歸剝離beta後
的殘差動量，高分位排名靠前）的第1關cheap IC gate。

經濟理由：本專案目前已死的三條假設（Weinstein第二階段、CTA趨勢跟隨、PEAD
策略層）共同死因是「表面報酬漂亮但拆解後是beta曝險、alpha不顯著」——傳統
動量訊號本身常隱含大量市場beta。先用CAPM剝離beta，只對剝離後的殘差報酬做
動量排序，文獻上發現波動更低、動量崩盤現象更輕微，直接對症「都是beta」
這個共同病灶，不是換皮重測已死的動量類假設。見`HYPOTHESIS_QUEUE.md`#9。

實作見`factors.py::prepare_factors()`「(u) 殘差動量」段落docstring：252日
滾動beta（沿用f_bab/f_idio_vol同一套cov/var算法，只換窗口）+「12個月股票
報酬-beta*12個月大盤報酬」近似累積殘差報酬，純價格資料天然point-in-time。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_low_vol/f_dividend_yield_ttm等既有測試同一套機制）。Standalone
single-factor test (bonferroni_n=1)。

2026-09-02 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#9第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_residual_momentum"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="殘差動量 Residual Momentum (f_residual_momentum, 252日CAPM剝離beta後動量), HYPOTHESIS_QUEUE.md#9新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
