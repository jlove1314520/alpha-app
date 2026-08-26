"""TW marathon 2026-08-26 (round after #95): cheap IC gate for `f_idio_vol`
(idiosyncratic volatility, Ang, Hodrick, Xing & Zhang 2006 anomaly):
60-trading-day market-model residual volatility (Var(r) = beta^2*Var(rm) +
Var(residual) closed-form decomposition vs TAIEX), sign-flipped like
f_low_vol. This is the second TW test of the "低風險" family in
MARATHON_PROTOCOL.md section 3 (f_low_vol -- total volatility -- was the
first and already PASSED; this factor deliberately isolates the
market-model-residual component instead of total volatility, a distinct
mechanism in the literature even though the two are likely correlated).

Standalone single-factor test (bonferroni_n=1): one new hypothesis tested
alone this round (this is the SECOND hypothesis of this marathon round,
after f_amihud_illiq -- MARATHON_PROTOCOL.md section 1a permits up to 2-3
per round), not a batch, per section 2's per-track independent family
framing.

Pure price factor (stock + TAIEX daily returns only), zero PIT dependency,
reuses the existing 100-name cached sample (SAMPLE_SEED=20260822) -- no new
FinMind/yfinance calls needed beyond what factor_ic.py's original batch
already fetched.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_idio_vol"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="idiosyncratic volatility (f_idio_vol), new hypothesis, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
