"""TW marathon 2026-08-26 (round after #95): cheap IC gate for `f_amihud_illiq`
(Amihud 2002 illiquidity: 20-trading-day mean of |daily return| / dollar
volume). This is the first TW test of the "流動性" family listed in
MARATHON_PROTOCOL.md section 3 ("流動性：Amihud illiquidity") -- a
mechanism completely distinct from every factor tested so far (value/
quality/momentum/reversal/institutional-flow), not a variant of an
existing family.

Standalone single-factor test (bonferroni_n=1): one new hypothesis tested
alone this round, not a batch, per MARATHON_PROTOCOL.md section 2's
per-track independent family framing.

Pure price+volume factor, zero PIT dependency (same class as f_low_vol/
f_short_reversal_1m), reuses the existing 100-name cached sample
(SAMPLE_SEED=20260822) -- no new FinMind/yfinance calls needed beyond what
factor_ic.py's original batch already fetched.

Direction: NOT sign-flipped (unlike f_low_vol/f_short_reversal_1m). The
illiquidity premium literature predicts higher illiquidity -> higher
expected future return, i.e. a positive IC is the "factor works" direction
here, not negative.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_amihud_illiq"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="Amihud illiquidity (f_amihud_illiq), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
