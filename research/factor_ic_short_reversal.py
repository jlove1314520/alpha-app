"""TW marathon 2026-08-26: cheap IC gate for `f_short_reversal_1m`
(short-term reversal, 21-trading-day / ~1-month own-stock cumulative return,
sign-flipped). This is the first TW test of the "短期反轉" family listed in
MARATHON_PROTOCOL.md section 3 ("動量變體/短期反轉... 跟中期動能方向常常相
反，這是已知的文獻現象") -- distinct from the existing `f_rel_strength`
(60-day relative-to-market momentum) already in the factor library.

Standalone single-factor test (bonferroni_n=1): this is one new hypothesis
tested alone in this round, not a batch, per MARATHON_PROTOCOL.md section
2's per-track independent family framing.

Pure price factor, zero PIT dependency (same class as f_low_vol), reuses the
existing 100-name cached sample (SAMPLE_SEED=20260822) -- no new FinMind
calls needed beyond what factor_ic.py's original batch already fetched.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_short_reversal_1m"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="short-term reversal (f_short_reversal_1m), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
