"""TW marathon 2026-08-26 (round 101): cheap IC gate for `f_asset_growth`
(asset growth anomaly, Cooper, Gulen & Schill 2008): TotalAssets YoY growth
(vs 4 quarters prior), sign-flipped (low growth -> higher score) -- the
literature finding is that firms expanding total assets quickly earn LOWER
subsequent returns (over-investment/overextension signal), so low-growth
firms should score higher for a long-oriented factor. Reuses
`balance_sheet_pit()` -- the exact same cache key
(TaiwanStockBalanceSheet, same stock_id/start_date) already fetched for
`f_quality_roe_stability`, so this introduces zero new FinMind calls.

This is the first test of the "資產成長/保守投資" (asset growth / conservative
investment) family in MARATHON_PROTOCOL.md section 3, not yet touched.

Standalone single-factor test (bonferroni_n=1): second of two hypotheses
tested this round (MARATHON_PROTOCOL.md section 1a permits up to 2-3 per
round); the first is f_bab (factor_ic_bab.py).

PIT status: inherits the same "+45-day assumed disclosure lag" treatment
as f_quality_roe_stability (balance_sheet_pit's pit_source='assumed'
column) -- not independently spot-checked against a real disclosure date
the way f_value_pb was (verify_pit_value_pb.py); this factor's PIT
correctness rests entirely on the existing assumed-lag convention already
used elsewhere in factors.py, disclosed here per MARATHON_PROTOCOL.md
section 4's honesty requirement rather than assumed clean.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_asset_growth"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="asset growth anomaly (f_asset_growth), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
