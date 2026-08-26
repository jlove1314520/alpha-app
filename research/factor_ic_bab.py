"""TW marathon 2026-08-26 (round 101): cheap IC gate for `f_bab` (betting
against beta, Frazzini & Pedersen 2014): 60-trading-day rolling beta vs
TAIEX, sign-flipped (low beta -> higher score). Reuses the exact same
beta_60 computation already done for f_idio_vol in factors.py -- zero new
data, zero new computation beyond that.

This is the THIRD test of the "低風險" (low-risk) family in
MARATHON_PROTOCOL.md section 3 (f_low_vol -- total volatility -- PASSED;
f_idio_vol -- residual volatility -- CHEAP_PASS but downgraded, high
overlap with f_low_vol, round 99). BAB is mechanically distinct from both:
it targets the systematic (beta) component directly, not total or
idiosyncratic volatility, so a priori it is not guaranteed to be as
collinear with f_low_vol as f_idio_vol turned out to be -- worth testing
independently rather than assuming collinearity.

Standalone single-factor test (bonferroni_n=1): first of two hypotheses
tested this round (MARATHON_PROTOCOL.md section 1a permits up to 2-3 per
round); the second is f_asset_growth (factor_ic_asset_growth.py).

Pure price factor (stock + TAIEX daily returns only), zero PIT dependency,
reuses the existing 100-name cached sample (SAMPLE_SEED=20260822) -- no new
FinMind/yfinance calls needed beyond what factor_ic.py's original batch
already fetched.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_bab"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="betting-against-beta (f_bab), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
