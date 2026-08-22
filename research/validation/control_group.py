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

**2026-08-22 correction (Cowork audit):** the first Milestone-4 run used
`run_control_group()` below with a STATIC equal-weight buy&hold evaluate_fn
as its random control -- i.e. "pick N random names once, hold them the
whole period, no rebalancing." Cowork correctly flagged that this is not
mechanically equivalent to a weekly-rebalancing strategy: it has different
turnover, a different holding-period distribution, and doesn't pay the same
number of round-trip costs. `run_matched_control_group()` (added below)
fixes this: it takes the REAL strategy's actual trade schedule (every
entry_date/exit_date pair from its own trades DataFrame) and, for each
random draw, substitutes a random stock_id into every trade slot while
keeping the exact same entry/exit dates -- so the random control
automatically inherits the real strategy's rebalance frequency, position
count over time, and holding-period distribution, and only randomizes which
stock filled each slot. This is now the sanctioned control-group method for
backtest candidates; `run_control_group()` is kept for other, simpler
static-portfolio comparisons where it remains a legitimate fit.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Sequence

import pandas as pd


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


def extract_trade_schedule(trades: pd.DataFrame) -> list[dict]:
    """From a real backtest's trades DataFrame (matching audit_ledgers'
    TRADES_SCHEMA), extract one {entry_date, exit_date} dict per closed
    round-trip. This is the exact rebalance timing, position count over
    time, and holding-period distribution of the real strategy -- passing
    this to run_matched_control_group() is what makes its random draws
    mechanically equivalent to the real strategy instead of just "N random
    picks held the whole period".
    """
    if trades.empty:
        return []
    buys = trades[trades["side"] == "buy"].set_index("trade_id")
    sells = trades[trades["side"] == "sell"]
    schedule = []
    for _, sell in sells.iterrows():
        entry_id = sell["entry_trade_id"]
        if entry_id not in buys.index:
            continue  # shouldn't happen if audit_ledgers.check_every_close_has_entry passed
        schedule.append({"entry_date": buys.loc[entry_id, "date"], "exit_date": sell["date"]})
    return schedule


def run_matched_control_group(
    trade_schedule: list[dict],
    price_data: dict[str, pd.DataFrame],
    strategy_final_equity: float,
    initial_capital: float,
    slot_allocation: float,
    cost_rates: dict[str, float],
    n_random: int = 200,
    seed: int = 20260822,
    thresholds: tuple[int, ...] = (50, 90, 95, 99),
    date_col: str = "date",
    price_col: str = "adj_close",
) -> ControlGroupResult:
    """The sanctioned control-group method for backtest candidates (see the
    2026-08-22 correction note in this module's docstring).

    For each of `n_random` draws: replay `trade_schedule` exactly (same
    entry/exit dates, same number of trades, same implicit rebalance
    timing), but for every trade slot draw a fresh random stock_id (from
    whichever names in `price_data` have a price row on both that trade's
    entry_date and exit_date) instead of whatever the real strategy
    actually held. Apply the identical position-sizing and cost formulas
    the real backtest engine uses (see cost_rates), sum realized P&L across
    all trades in the draw, and compare the resulting distribution of
    `initial_capital + total_pnl` against `strategy_final_equity`.

    cost_rates: {'buy': <rate>, 'sell': <rate>} as fractions of notional,
    e.g. from backtest.engine's _buy_leg_rate()/_sell_leg_rate() applied to
    the same BacktestConfig used for the real run -- pass those exact
    values in, don't recompute independently, so the control group's costs
    can never silently drift from what the real strategy actually paid.
    """
    rng = random.Random(seed)
    indexed = {sid: df.set_index(date_col) for sid, df in price_data.items()}

    def one_draw() -> float:
        total_pnl = 0.0
        for trade in trade_schedule:
            entry_date, exit_date = trade["entry_date"], trade["exit_date"]
            candidates = [sid for sid, df in indexed.items()
                          if entry_date in df.index and exit_date in df.index]
            if not candidates:
                continue
            sid = rng.choice(candidates)
            entry_price = float(indexed[sid].loc[entry_date, price_col])
            exit_price = float(indexed[sid].loc[exit_date, price_col])
            if entry_price <= 0:
                continue
            shares = int(slot_allocation // (entry_price * (1 + cost_rates["buy"])))
            if shares <= 0:
                continue
            entry_notional = shares * entry_price
            entry_cost = entry_notional * cost_rates["buy"]
            exit_notional = shares * exit_price
            exit_cost = exit_notional * cost_rates["sell"]
            total_pnl += (exit_notional - exit_cost) - (entry_notional + entry_cost)
        return initial_capital + total_pnl

    random_metrics = [one_draw() for _ in range(n_random)]
    beats = sum(1 for m in random_metrics if strategy_final_equity > m)
    percentile = 100.0 * beats / len(random_metrics) if random_metrics else float("nan")
    beats_random_at = {t: percentile >= t for t in thresholds}

    return ControlGroupResult(
        candidate_metric=strategy_final_equity,
        random_metrics=random_metrics,
        percentile=percentile,
        n_random=n_random,
        beats_random_at=beats_random_at,
    )
