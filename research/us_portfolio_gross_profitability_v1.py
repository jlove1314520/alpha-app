"""US track: Top-N long-only portfolio test for `f_us_gross_profitability`
ALONE (round429/431/433/434's US_MARATHON_STATE.md "下一步" option (2),
first time actually run). Not a new factor -- `f_us_gross_profitability`
already CHEAP_PASSed (`TRIALS_LEDGER.md` #191) and its contamination check
(`deep_dive_f_us_gross_profitability_contamination_check.py`) verdict was
REFUTED (excluded-sample retained_fraction well above the 60% threshold --
see that script's saved CSV), unlike #20/#21 which were CONFIRMED
data-integrity traps. That makes gross_profitability the first US factor
where a genuine `MARATHON_PROTOCOL.md` 2026-09-03 portfolio-level test is
warranted on its own (not bundled into a combo that dilutes it, which is
what happened to #22's value_bm+low_vol equal-weight combo -- FAIL,
`US_LEADS.md` #22).

**Why single-factor, not another combo**: #22 already tested the 2-factor
combo at the portfolio level and it FAILed (percentile 43.0/60.0, both
well under the 90.0 bar). Testing gross_profitability alone isolates
whether that FAIL was combo-dilution (averaging two z-scores muddies each
factor's own ranking) or whether Top-N long-only construction itself
doesn't carry cheap-gate IC through to portfolio alpha for this factor
family. This is the single-factor control for #22's finding, not a new
mining direction.

**Universe & factor score**: reuses `load_quality_sample()` verbatim
(84/248 clean-universe names, `date`/`adj_close`/`f_us_gross_profitability`
columns, zero new API calls -- same on-disk SEC EDGAR companyfacts +
FinMind price cache `deep_dive_f_us_gross_profitability.py` already hit).
Score function is a plain z-score cross-section on the single factor
column (`_zscore_cross_section` imported unchanged from
`deep_dive_us_value_bm_lowvol_combo.py` -- it only needs a `col` name, no
combo-specific coupling).

**Engine / config / random control**: identical to
`us_portfolio_multifactor_v1.py` (Top-N=15, quarterly rebalance, 15% hard
stop-loss, N=100 matched-universe random draws, same seed convention) --
only the signal function and universe loader differ. This keeps the #22
vs this-script comparison apples-to-apples (same engine, same Top-N size,
same rebalance frequency, same random-control methodology), isolating the
factor-choice variable.

**Downside-protection framing (`CLAUDE.md` "最高投資原則")**: same
`USPortfolioConfig` 15% stop-loss and MDD reporting as #22 -- not
evaluated on upside alone.

**Heavy work -- must be `run_detached.py`'d**: 100 draws x 2 periods on an
84-name cross-section. Smaller universe than #22 (159 names) so expected
faster than #22's 19.4 minutes, but still >5 minutes -- per
`MARATHON_PROTOCOL.md` 0b this module's `__main__` is designed to be
submitted, not run inline in a marathon session. (This round only wrote
and smoke-tested the wiring with a tiny local draw count; the full N=100
run is queued for the next round to submit, since this round's
heavy-job-slot is already occupied by the TW-track day-trading-detail
backfill.)
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from deep_dive_f_us_low_vol import _load_market_df
from deep_dive_f_us_gross_profitability import TARGET_FACTOR
from deep_dive_us_value_bm_lowvol_combo import _zscore_cross_section
from portfolio_backtest_v2 import alpha_significance
from us_factor_ic_quality_clean_universe import load_quality_sample
from us_portfolio_backtest import USPortfolioConfig, run_us_backtest
from validation import holdout

N_RANDOM_DRAWS = 100
RANDOM_CONTROL_SEED = 20260908
MAX_POSITIONS = 15
REBALANCE_DAYS = 63  # quarterly, same convention as us_portfolio_multifactor_v1.py

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def gp_signal_fn(price_data, as_of_date, market_df):
    """Single-factor z-score on f_us_gross_profitability at as_of_date.
    Same contract as us_portfolio_multifactor_v1.py's combo_signal_fn, but
    no combo -- raw scores are just the z-scores (Top-N engine ranks them)."""
    z = _zscore_cross_section(as_of_date, price_data, TARGET_FACTOR)
    return dict(z)


def random_signal_fn(price_data, as_of_date, market_df, rng: random.Random):
    """Same eligible cross-section as gp_signal_fn (factor non-NaN that
    date), but i.i.d. random scores -- matched-universe random control."""
    z = _zscore_cross_section(as_of_date, price_data, TARGET_FACTOR)
    if not z:
        return {}
    return {sid: rng.random() for sid in z}


def run_period(label, start, end, data, market_df, n_draws=N_RANDOM_DRAWS):
    cfg = USPortfolioConfig(
        start_date=start, end_date=end,
        rebalance_every_n_days=REBALANCE_DAYS,
        max_positions=MAX_POSITIONS,
        stop_loss_pct=0.15,
        initial_capital=1_000_000.0,
        book_name=f"us_portfolio_gross_profitability_v1_{label.lower()}",
    )
    result = run_us_backtest(gp_signal_fn, data, market_df, cfg)
    alpha = alpha_significance(result.equity_curve, market_df)
    real_final = result.final_equity

    random_finals = []
    for i in range(n_draws):
        rng = random.Random(RANDOM_CONTROL_SEED + i)

        def rand_fn(pd_, ad, md, _rng=rng):
            return random_signal_fn(pd_, ad, md, _rng)

        r = run_us_backtest(rand_fn, data, market_df, cfg)
        random_finals.append(r.final_equity)

    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals])) if random_finals else float("nan")
    row = {
        "period": label, "start": start, "end": end,
        "n_trades": result.n_trades,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio,
        "beta": alpha["beta"], "alpha_ann_pct": alpha["alpha_ann_pct"],
        "alpha_pvalue": alpha["alpha_pvalue"], "n_days_alpha": alpha["n_days"],
        "random_control_median_equity": float(np.median(random_finals)) if random_finals else float("nan"),
        "random_control_percentile": percentile,
        "unresolved_at_end": len(result.unresolved_at_end),
        "n_draws": n_draws,
    }
    print(f"\n--- {label} ({start}..{end}) n_draws={n_draws} ---")
    print(f"trades={row['n_trades']}  total_return={row['total_return_pct']:+.2f}%  "
          f"MDD={row['max_drawdown_pct']:.2f}%  Sortino={row['sortino']:.3f}")
    print(f"beta={row['beta']:+.3f}  alpha_ann={row['alpha_ann_pct']:+.2f}%  "
          f"alpha_p={row['alpha_pvalue']:.4f}  n_days={row['n_days_alpha']}")
    print(f"random_control_median_equity={row['random_control_median_equity']:.4f}  "
          f"percentile={row['random_control_percentile']:.1f}")
    return row


def main(n_draws=N_RANDOM_DRAWS, out_path="data/us_portfolio_gross_profitability_v1.csv"):
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US portfolio-axis: Top-N long-only single-factor (f_us_gross_profitability) ===")
    data, drop_reasons = load_quality_sample()
    print(f"universe: {len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the minimum cross-section of 10.")
        return None

    market_df, is_spy = _load_market_df()
    print(f"market benchmark: {'SPY' if is_spy else 'NONE (fetch failed)'}, "
          f"universe n={len(data)}, max_positions={MAX_POSITIONS}, "
          f"rebalance_days={REBALANCE_DAYS}, n_draws={n_draws}")
    if not is_spy or market_df.empty:
        print("ABORT: SPY benchmark unavailable, needed for both calendar and alpha/beta.")
        return None

    rows = [run_period(label, start, end, data, market_df, n_draws) for label, (start, end) in PERIODS.items()]

    out = pd.DataFrame(rows)
    out.to_csv(out_path, index=False)
    print(f"\nsaved {out_path}")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return rows


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--n-draws", type=int, default=N_RANDOM_DRAWS)
    p.add_argument("--out", default="data/us_portfolio_gross_profitability_v1.csv")
    args = p.parse_args()
    main(n_draws=args.n_draws, out_path=args.out)
