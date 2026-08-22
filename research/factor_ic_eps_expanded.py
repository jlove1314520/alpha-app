"""Point 3 of the 2026-08-22 Cowork review: re-verify f_eps_growth (the one
factor that passed) on a much larger sample and a longer cross-section
history than the original 6-factor batch test.

**Still not literally universe.py's full 3,196-name universe, disclosed
honestly**: fetching 4 FinMind datasets per name for all 3,196 names is
several thousand more API calls than this run makes, and risks the
free-tier rate limit documented in DATA.md. This run instead uses a much
larger sample (400 names: the original 100 from factor_ic.py's default
SAMPLE_SEED draw, PLUS 300 new names from a second independent draw) and a
longer snapshot history (back to 2008 instead of 2015). This is a
materially more rigorous test than the original 100-name/2015-start run,
not a full-market scan -- both facts stated plainly, not blurred together.

bonferroni_n=1 here (no multiple-comparison correction) is deliberate, not
an oversight: this is a single, pre-specified CONFIRMATORY re-test of one
factor already identified as a candidate, not an exploratory scan across
several factors at once. Correction controls family-wise error across
simultaneous exploratory tests; a lone confirmatory replication of a
specific prior finding doesn't inflate that risk. The original 6-factor
scan (which DOES need correction) was already handled with bonferroni_n=6
in factor_ic.py's own main().
"""
from __future__ import annotations

import random

from factor_ic import SAMPLE_SEED, run_ic_test

EXPANDED_SEED = 20260823  # different from SAMPLE_SEED, draws a disjoint additional batch
EXPANDED_ADDITIONAL = 300
EXPANDED_SNAPSHOT_START = "2008-01-01"


def build_expanded_sample() -> list[str]:
    from factor_ic import sample_universe_ids

    original = sample_universe_ids(100, SAMPLE_SEED)
    from universe import universe as build_universe

    u = build_universe()
    rng = random.Random(EXPANDED_SEED)
    remaining = [sid for sid in u["stock_id"].tolist() if sid not in set(original)]
    additional = rng.sample(remaining, EXPANDED_ADDITIONAL)
    return original + additional


def main():
    sample_ids = build_expanded_sample()
    print(f"Expanded sample: {len(sample_ids)} names "
          f"({100} original + {EXPANDED_ADDITIONAL} new, seed={EXPANDED_SEED})")
    results = run_ic_test(
        ["f_eps_growth"], sample_ids,
        label="f_eps_growth expanded re-verification (400 names, snapshots from 2008)",
        snapshot_start=EXPANDED_SNAPSHOT_START,
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
