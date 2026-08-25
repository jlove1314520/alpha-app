"""High-resolution re-check of the two "batch-passed but cumulative-correction-
uncertain" institutional net-position-momentum hypotheses (FUT_MARATHON_STATE.md
round 48's "下一輪建議工作單位" #1, TRIALS_LEDGER.md #25 and #27).

Why this exists (not a parameter-tuning rescue -- MARATHON_PROTOCOL.md 1a
explicitly forbids that for FAILed hypotheses, but these two are not FAILs,
they are CHEAP_PASS-then-downgraded on a resolution problem):

fut_cheap_gate.py's N_SHUFFLES=200 gives percentile steps of 0.5%. The
cumulative Bonferroni thresholds these two hypotheses needed to clear were
99.6 (n=25, TRIALS_LEDGER.md #25, foreign) and 99.63 (n=27, #27, trust) --
both *finer* than the 0.5% measurement resolution the original test could
even produce (nearest achievable values were 99.5 or 100.0). That is a
measurement-precision problem, not evidence the hypotheses are false: the
original test literally could not distinguish "true percentile is 99.55"
from "true percentile is 99.9" at N=200. Re-running the *identical*
methodology (same signal construction, same data, same permutation-test
logic in fut_cheap_gate.py's _permutation_test()) at a finer shuffle count
answers the question the coarse version could not, without touching any
signal parameter.

Precedent for widening resolution specifically (not re-tuning a signal) at
deep-dive time: f_quality_roe_stability's cheap-gate resolution was widened
from 20 to 100 random samples for the same reason (FUT_MARATHON_STATE.md
round 48's suggestion explicitly cites this as the model to follow).

N_SHUFFLES=2000 chosen: gives 0.05% steps, an order of magnitude finer than
the 99.6/99.63 thresholds need to be resolved cleanly, while remaining cheap
(the permutation loop is a pure numpy vectorized op over ~1605 days per
shuffle -- 2000 shuffles is on the order of a few seconds, not a real time
risk to the 30-minute lock window, unlike the original state-file note's
caution which was written before this was actually measured).

This does NOT modify fut_cheap_gate.py's module-level N_SHUFFLES=200 default
(that stays as the standard cheap-gate resolution for all other/future
hypotheses) -- it monkey-patches the imported module's N_SHUFFLES attribute
locally within this script's own process only, then calls the existing
hyp_inst_foreign_net_position_change_5d / hyp_inst_trust_net_position_change_5d
functions unchanged. Both still go through finmind_client.load_dev() via
_load_institutional_net_position(), so the holdout truncation guarantee is
untouched, and both hit the existing local parquet cache (round 39/42/45/48
already fetched this dataset's full history) -- zero new network calls
expected.

Per MARATHON_PROTOCOL.md 2, this counts as two NEW entries in
TRIALS_LEDGER.md (a fresh look at the data with different resolution is
still a look, for multiplicity-accounting purposes), not a silent overwrite
of #25/#27 -- the original coarse-resolution rows stay in the ledger as-is.
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

    results = [
        fcg.hyp_inst_foreign_net_position_change_5d(series),
        fcg.hyp_inst_trust_net_position_change_5d(series),
    ]

    for r in results:
        print(f"\n=== {r.name} (high-res re-check, N_SHUFFLES={HIGH_RES_N_SHUFFLES}) ===")
        print(f"  n_days={r.n_days}")
        print(f"  real_terminal_equity={r.real_terminal_equity:.4f} "
              f"(i.e. {(r.real_terminal_equity - 1) * 100:+.1f}% cumulative, no costs)")
        print(f"  random_median_equity={r.random_median_equity:.4f}")
        print(f"  percentile={r.percentile:.2f}  (single-test bar: >=90.0)")

    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"
    print("\nholdout check (post-run): is_holdout_consumed() == False, confirmed")


if __name__ == "__main__":
    main()
