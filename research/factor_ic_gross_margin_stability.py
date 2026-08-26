"""TW marathon round 105: cheap IC gate for `f_gross_margin_stability`
(Novy-Marx-spirit quality factor variant): quarterly gross margin
(GrossProfit/Revenue), stability score = negative rolling std of the
trailing 8 quarterly gross-margin values (lower volatility scores higher,
same statistical construction as `f_quality_roe_stability` but on the
core-business margin instead of ROE). Reuses `quarterly_pit()` -- the exact
same cache key (TaiwanStockFinancialStatements, same stock_id/start_date)
already fetched for `f_quality_roe_stability`/`f_eps_growth`/etc, so this
introduces zero new FinMind calls.

This is the first test of the "毛利率穩定度（Novy-Marx）" item explicitly
named in MARATHON_PROTOCOL.md section 3's "品質" family (distinct from
`f_quality_roe_stability`, which already covers ROE stability).

Standalone single-factor test (bonferroni_n=1).
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_gross_margin_stability"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="gross margin stability (f_gross_margin_stability, Novy-Marx-spirit quality variant), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
