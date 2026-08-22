"""Random control group testing.

CONSTITUTION.md's core anti-overfitting check (the "四大統計偽影陷阱" section,
learned from testing 17 on-window mechanisms on Cybex before spotting the
pattern): a candidate might "work" purely because of a structural
side-effect -- fewer trades, different market exposure, a smaller candidate
pool, swapping out a few top-ranked names -- rather than the signal itself.
The required check: run the exact same MECHANICAL actions (same rebalance
schedule, same position count, same holding-period distribution) on
RANDOMLY CHOSEN members of the universe instead of the signal's picks, many
times, and require the real candidate to beat the resulting random
distribution -- not just beat "buy and hold" or "zero".

This module is strategy-agnostic on purpose: it takes an `evaluate_fn` seam
(a list of stock_ids in, one comparable metric out) rather than knowing
anything about what "picking stocks" means. Milestone 4's Weinstein scanner
plugs into this later; nothing here should need to change when it does.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass
class ControlGroupResult:
    candidate_metric: float
    random_metrics: list[float]
    percentile: float                  # candidate's rank vs the random distribution, 0-100
    n_random: int
    beats_random_at: dict[int, bool]   # e.g. {50: True, 90: True, 95: False}


def run_control_group(
    universe_ids: Sequence[str],
    n_picks: int,
    evaluate_fn: Callable[[list[str]], float],
    candidate_ids: Sequence[str],
    n_random: int = 200,
    seed: int = 20260822,
    thresholds: tuple[int, ...] = (50, 90, 95, 99),
) -> ControlGroupResult:
    """Compare a candidate's picks against `n_random` random picks of the
    same size from the same universe, using `evaluate_fn` for both.

    `seed` is fixed (not defaulted to system randomness) so a control-group
    run is exactly reproducible -- if a result changes between two runs with
    the same inputs, that is itself a bug worth finding, not something to
    average away by not caring about determinism.
    """
    if n_picks <= 0:
        raise ValueError("n_picks must be positive")
    if n_picks > len(universe_ids):
        raise ValueError(f"n_picks ({n_picks}) exceeds universe size ({len(universe_ids)})")

    rng = random.Random(seed)
    candidate_metric = evaluate_fn(list(candidate_ids))

    random_metrics = []
    for _ in range(n_random):
        pick = rng.sample(list(universe_ids), n_picks)
        random_metrics.append(evaluate_fn(pick))

    beats = sum(1 for m in random_metrics if candidate_metric > m)
    percentile = 100.0 * beats / len(random_metrics) if random_metrics else float("nan")
    beats_random_at = {t: percentile >= t for t in thresholds}

    return ControlGroupResult(
        candidate_metric=candidate_metric,
        random_metrics=random_metrics,
        percentile=percentile,
        n_random=n_random,
        beats_random_at=beats_random_at,
    )
