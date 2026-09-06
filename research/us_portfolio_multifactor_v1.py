"""US track's first real Top-N long-only multi-factor portfolio test
(`MARATHON_PROTOCOL.md` 2026-09-03 mandate: main axis is portfolio-level
work, not single-factor mining). This is the first time the US track
actually exercises `us_portfolio_backtest.py`'s Top-N engine (built round
329/333, wired to real data in round333, then left unused for ~80 rounds
while `US_LEADS.md` #20/#21 single-factor deep-diving ran instead).

**Why long-only, not decile long-short like #20/#21's diagnostics**: the
entire round350-412 diagnostic chain on `f_us_value_bm`(#20)/`f_us_low_vol`
(#21) converged on one root cause -- their SHORT leg systematically selects
micro-cap "reverse-split death spiral" stocks (`TRIALS_LEDGER.md` #172/#174/
#177), whose back-adjusted `adj_close` (the only price field FinMind's
`USStockPrice` exposes -- `close`==`adj_close` exactly, confirmed #177) makes
both realistic price-floor filtering and the fixed-representative-price cost
model unreliable. That is a genuine, now-exhausted data/cost-model
limitation of the short side specifically -- round408's leg decomposition
already showed both factors' LONG legs behave sanely in both TRAIN and VAL
(value_bm VAL long ann=+9.78% vs TRAIN +15.42%; low_vol VAL long ann=+4.00%
vs TRAIN +9.12%, both *lower* in VAL, i.e. no long-leg anomaly at all). A
Top-N long-only portfolio sidesteps the diagnosed short-leg problem entirely
by construction, rather than requiring a fifth diagnostic round on the same
short-leg issue -- this is a genuine portfolio-construction pivot per
protocol section 1, not a factor re-test.

**Universe & factor scores**: reuses `deep_dive_us_value_bm_lowvol_combo.py`'s
`build_combo_universe()` (159-name intersection of #20's clean stratified
value_bm sample and #21's low_vol price data, zero new API calls -- 100%
on-disk cache from round383/391/400/404/406) and `_zscore_cross_section()`
(same pre-registered 1/N combo: 0.5*z(value_bm) + 0.5*z(low_vol) per
rebalance date, no fitted weights -- identical method to round406's #20/#21
combo entry, just fed into a Top-N long-only engine instead of a decile
long-short spread).

**Downside-protection framing (`CLAUDE.md` "最高投資原則")**: `USPortfolioConfig`
carries a real 15% hard stop-loss (`stop_loss_pct`, same as
`us_portfolio_pilot_real_data.py`'s convention) and MDD is reported alongside
ann_return/alpha/beta for every period -- this is not evaluated on upside
alone.

**Random control**: same percentile-vs-random-draws pattern as
`deep_dive_f_us_low_vol.py::run_one()` (N=100 draws, `RANDOM_CONTROL_SEED`),
adapted to Top-N long-only: each draw assigns i.i.d. random scores (not real
factor scores) to the SAME eligible cross-section on each rebalance date, run
through the identical `run_us_backtest()` engine/cost model, and the real
strategy's final equity is compared to the empirical distribution of the 100
random-Top-N draws' final equity.

**Heavy work -- must be `run_detached.py`'d**: 100 draws x 2 periods (TRAIN+VAL)
= 200 full day-by-day walks over ~159 names, matching the precedent set by
`deep_dive_portfolio_v2_random_control_n100.py` needing detached execution
for the TW-track equivalent. This module's `__main__` is designed to be
submitted, not run inline in a marathon session.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from deep_dive_f_us_low_vol import _load_market_df
from deep_dive_us_value_bm_lowvol_combo import (
    LOWVOL_COL,
    VALUE_COL,
    build_combo_universe,
    _zscore_cross_section,
)
from portfolio_backtest_v2 import alpha_significance
from us_portfolio_backtest import USPortfolioConfig, run_us_backtest
from validation import holdout

N_RANDOM_DRAWS = 100
RANDOM_CONTROL_SEED = 20260906
MAX_POSITIONS = 15
REBALANCE_DAYS = 63  # quarterly, same convention as deep_dive_us_value_bm_lowvol_combo.py

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def combo_signal_fn(price_data, as_of_date, market_df):
    """Pre-registered 1/N combo: 0.5*z(value_bm) + 0.5*z(low_vol) at as_of_date,
    identical method to round406's `_combo_legs()`, just returned as a raw
    score dict (Top-N engine does its own ranking/selection)."""
    z_value = _zscore_cross_section(as_of_date, price_data, VALUE_COL)
    z_lowvol = _zscore_cross_section(as_of_date, price_data, LOWVOL_COL)
    shared = set(z_value) & set(z_lowvol)
    if len(shared) < 10:
        return {}
    return {sid: 0.5 * z_value[sid] + 0.5 * z_lowvol[sid] for sid in shared}


def random_signal_fn(price_data, as_of_date, market_df, rng: random.Random):
    """Same eligible cross-section as combo_signal_fn (both factors non-NaN
    that date), but i.i.d. random scores instead of real factor values --
    matched-universe random control, same spirit as
    `deep_dive_f_us_low_vol.py::_random_legs()`."""
    z_value = _zscore_cross_section(as_of_date, price_data, VALUE_COL)
    z_lowvol = _zscore_cross_section(as_of_date, price_data, LOWVOL_COL)
    shared = set(z_value) & set(z_lowvol)
    if len(shared) < 10:
        return {}
    return {sid: rng.random() for sid in shared}


def run_period(label, start, end, data, market_df):
    cfg = USPortfolioConfig(
        start_date=start, end_date=end,
        rebalance_every_n_days=REBALANCE_DAYS,
        max_positions=MAX_POSITIONS,
        stop_loss_pct=0.15,
        initial_capital=1_000_000.0,
        book_name=f"us_portfolio_multifactor_v1_{label.lower()}",
    )
    result = run_us_backtest(combo_signal_fn, data, market_df, cfg)
    alpha = alpha_significance(result.equity_curve, market_df)
    real_final = result.final_equity

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)

        def rand_fn(pd_, ad, md, _rng=rng):
            return random_signal_fn(pd_, ad, md, _rng)

        r = run_us_backtest(rand_fn, data, market_df, cfg)
        random_finals.append(r.final_equity)

    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    row = {
        "period": label, "start": start, "end": end,
        "n_trades": result.n_trades,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio,
        "beta": alpha["beta"], "alpha_ann_pct": alpha["alpha_ann_pct"],
        "alpha_pvalue": alpha["alpha_pvalue"], "n_days_alpha": alpha["n_days"],
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "unresolved_at_end": len(result.unresolved_at_end),
    }
    print(f"\n--- {label} ({start}..{end}) ---")
    print(f"trades={row['n_trades']}  total_return={row['total_return_pct']:+.2f}%  "
          f"MDD={row['max_drawdown_pct']:.2f}%  Sortino={row['sortino']:.3f}")
    print(f"beta={row['beta']:+.3f}  alpha_ann={row['alpha_ann_pct']:+.2f}%  "
          f"alpha_p={row['alpha_pvalue']:.4f}  n_days={row['n_days_alpha']}")
    print(f"random_control_median_equity={row['random_control_median_equity']:.4f}  "
          f"percentile={row['random_control_percentile']:.1f}")
    return row


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US portfolio-axis: Top-N long-only multifactor (value_bm x low_vol, 1/N combo) ===")
    data = build_combo_universe()
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the minimum cross-section of 10.")
        return None

    market_df, is_spy = _load_market_df()
    print(f"market benchmark: {'SPY' if is_spy else 'NONE (fetch failed)'}, "
          f"universe n={len(data)}, max_positions={MAX_POSITIONS}, "
          f"rebalance_days={REBALANCE_DAYS}, N_RANDOM_DRAWS={N_RANDOM_DRAWS}")
    if not is_spy or market_df.empty:
        print("ABORT: SPY benchmark unavailable, needed for both calendar and alpha/beta.")
        return None

    rows = [run_period(label, start, end, data, market_df) for label, (start, end) in PERIODS.items()]

    out = pd.DataFrame(rows)
    out.to_csv("data/us_portfolio_multifactor_v1.csv", index=False)
    print("\nsaved data/us_portfolio_multifactor_v1.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    main()
