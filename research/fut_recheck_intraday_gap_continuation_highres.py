"""High-resolution re-check of `fut_intraday_gap_continuation` (FUT_MARATHON_STATE.md
round 54's "下一輪建議工作單位" #1, TRIALS_LEDGER.md #33).

Why this exists (not a parameter-tuning rescue -- MARATHON_PROTOCOL.md 1a
explicitly forbids that for FAILed hypotheses, but this one is not a FAIL,
it is a weak CHEAP_PASS that fell just short of its correction bar):

fut_cheap_gate.py's default N_SHUFFLES=200 gives percentile steps of 0.5%.
The single-test bar (>=90.0) was cleared at percentile=92.0, but this
batch's own multi-test correction bar (95.0, n=2 same-batch tests) and the
cumulative Bonferroni bar (99.70, n=33 in TRIALS_LEDGER.md) were both not
cleared. At 200 shuffles, 92.0 sits only ~3.6 measurement-steps below the
batch bar -- close enough that it is worth asking whether the true
percentile is meaningfully below 95 or whether 200 shuffles is simply too
coarse to tell. This is the identical methodology precedent set by round 51
(fut_recheck_inst_momentum_highres.py) for the exact same situation
(batch/cumulative-correction-uncertain, not a FAIL): re-run the SAME signal
construction and SAME permutation-test logic at a finer shuffle count,
change nothing else.

N_SHUFFLES=2000 chosen (same as round 51): gives 0.05% steps, an order of
magnitude finer than the 95.0/99.70 thresholds need to be resolved cleanly.
The permutation loop here uses _permutation_test_same_day (paired same-day
signal/return, not the shifted cross-day version fut_recheck_inst_momentum
used) -- still a pure numpy vectorized op over ~6185 days per shuffle, so
2000 shuffles remains cheap (order of a few seconds), not a real time risk
to the 30-minute lock window.

This does NOT modify fut_cheap_gate.py's module-level N_SHUFFLES=200
default (that stays as the standard cheap-gate resolution for all
other/future hypotheses) -- it monkey-patches the imported module's
N_SHUFFLES attribute locally within this script's own process only, then
calls the existing hyp_intraday_gap_continuation function unchanged. It
still goes through build_continuous_series() which round 54 already
confirmed hits the existing local parquet cache, so zero new network calls
expected and the holdout truncation guarantee is untouched.

Per MARATHON_PROTOCOL.md 2, this counts as one NEW entry in
TRIALS_LEDGER.md (a fresh look at the data with different resolution is
still a look, for multiplicity-accounting purposes), not a silent overwrite
of #33 -- the original coarse-resolution row stays in the ledger as-is.
The sibling hypothesis `fut_intraday_gap_reversal` (round 54, percentile=8.0,
clean FAIL, direction wrong) is not re-checked here -- it is not in the
"batch-passed but correction-uncertain" bucket this script targets, and
re-testing a clean FAIL at higher resolution would not change its
conclusion (a FAIL 82 percentile-points below the bar has no realistic path
to crossing it via measurement-precision alone).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fut_cheap_gate as fcg  # noqa: E402
from validation import holdout  # noqa: E402

HIGH_RES_N_SHUFFLES = 2000


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"

    fcg.N_SHUFFLES = HIGH_RES_N_SHUFFLES
    print(f"N_SHUFFLES patched to {fcg.N_SHUFFLES} for this re-check run "
          f"(fut_cheap_gate.py's own default of 200 is untouched on disk)")

    series = fcg._load_series()
    print(f"loaded continuous series: {len(series)} rows, "
          f"{series['date'].min().date()} .. {series['date'].max().date()}")

    r = fcg.hyp_intraday_gap_continuation(series)

    print(f"\n=== {r.name} (high-res re-check, N_SHUFFLES={HIGH_RES_N_SHUFFLES}) ===")
    print(f"  n_days={r.n_days}")
    print(f"  real_terminal_equity={r.real_terminal_equity:.4f} "
          f"(i.e. {(r.real_terminal_equity - 1) * 100:+.1f}% cumulative, no costs)")
    print(f"  random_median_equity={r.random_median_equity:.4f}")
    print(f"  percentile={r.percentile:.2f}  (single-test bar: >=90.0; "
          f"round-54 batch bar: >=95.0; cumulative n=33 bar: >=99.70)")

    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"
    print("\nholdout check (post-run): is_holdout_consumed() == False, confirmed")


if __name__ == "__main__":
    main()
