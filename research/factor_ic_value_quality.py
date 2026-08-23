"""TW marathon round 1 (2026-08-23): re-run the cheap IC gate for the three
factors that were implemented but never tested because the 2026-08-22
FinMind rate limit hit before they could run (see TRIALS_LEDGER.md's
"待測" note and TW_MARATHON_STATE.md). The rate limit is confirmed cleared
as of 2026-08-23, so this is the first real statistical test of:

  - f_value_pb        (negative PBR, i.e. cheaper book multiple = higher factor)
  - f_value_pe        (negative PER, excluding loss-making/negative-PER names)
  - f_quality_roe_stability (low quarter-to-quarter ROE variance = higher factor)

Uses the same default 100-name sample (SAMPLE_SEED) and snapshot window as
factor_ic.py's original 6-factor batch, so this reuses the already-cached
parquet files in data/raw/ (see MARATHON_PROTOCOL.md section 1a: cheap gate
should use existing cached sample, not chase new API quota for an untested
hypothesis).

bonferroni_n=3: this is an exploratory batch of 3 new factors tested
together, not a lone confirmatory re-test, so family-wise correction across
these 3 applies (same logic as factor_ic.py's own 6-factor main()).

**f_value_pb/f_value_pe PIT caveat still applies regardless of IC outcome**:
factors.py's own docstring discloses their PIT status as unverified (FinMind
computes PBR/PER from a trailing EPS/book-value figure whose own update
timing relative to disclosure has not been checked). A PASS here is a cheap
IC pass, not a PIT-clean confirmation -- if either passes, TW_LEADS.md must
carry that caveat forward into deep-dive, per MARATHON_PROTOCOL.md section
1b/6's "PIT 狀態未驗證" requirement.
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_value_pb", "f_value_pe", "f_quality_roe_stability"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="value/quality re-test after 2026-08-23 rate-limit clear (Bonferroni n=3)",
        bonferroni_n=3,
    )
    return results


if __name__ == "__main__":
    main()
