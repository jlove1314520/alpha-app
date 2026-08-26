"""TW marathon 2026-08-26 (round 100): cheap IC gate for `f_accruals`
(earnings-quality accruals, Sloan 1996): balance-sheet-approach accruals
(delta non-cash working capital, YoY, scaled by TotalAssets), sign-flipped
so low accruals score higher -- the literature finding is that firms with
higher accruals (more of reported earnings is non-cash) earn LOWER
subsequent returns (market underestimates the lower persistence of the
accrual component of earnings), so low-accrual firms should score higher
for a long-oriented factor. Reuses `balance_sheet_pit()` -- the exact same
cache key (TaiwanStockBalanceSheet, same stock_id/start_date) already
fetched for `f_quality_roe_stability`/`f_asset_growth`, so this introduces
zero new FinMind calls.

This is the first test of the "accruals 盈餘品質" variant of the "品質"
family in MARATHON_PROTOCOL.md section 3 (f_quality_roe_stability already
covers ROE stability; this is a conceptually distinct quality signal).

Known simplification (disclosed in factors.py's _accruals docstring): this
project has no cash-flow-statement data source, so the classic
"NetIncome - CFO" definition isn't available; uses the balance-sheet
approach instead, omitting the depreciation adjustment term (no
depreciation data source either). Not assumed clean.

Standalone single-factor test (bonferroni_n=1).
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_accruals"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="earnings-quality accruals (f_accruals, Sloan 1996 balance-sheet approach), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
