"""US portfolio backtest engine -- first real-data wiring pilot (marathon
round, US track, continues 2026-09-04T05:07 round 329's "下一步" item (b)).

**Why this is the right work unit**: round 329 built `us_portfolio_backtest.
py` (the Top-N engine) but only self-tested it against synthetic data --
its own docstring says "Wiring this to a real US universe sample + real
factor scores ... is the next work unit, left for a future round." Per
`MARATHON_PROTOCOL.md`'s 2026-09-03 directive, the US track's main axis is
now portfolio-strategy-level work, but the US track has **zero** factors
that passed even the standalone cheap gate (`US_LEADS.md` #1-#12: every
price-only factor, across every size tier, is FAIL or CHEAP_PASS-then-FAIL
on deep-dive). There is therefore no legitimate multi-factor combination to
build yet -- attempting one now would violate protocol section 2's FDR
discipline (combining factors that were never individually validated).
**This script is explicitly infrastructure (protocol section 1c), not a new
factor/strategy test** -- it wires the engine to real cached price data and
a real SPY benchmark end-to-end, so the moment a real factor family DOES
pass cheap gate (most likely candidate: SEC-EDGAR-sourced fundamentals,
still unbuilt), the portfolio-level combo work can start immediately without
first debugging plumbing.

**Zero new FinMind API calls.** Every ticker used here is read straight out
of the existing `data/raw/USStockPrice__<TICKER>__1990-01-01__2024-12-31.
parquet` cache built up across prior US-track rounds (138 non-SPY tickers +
SPY itself, all already fetched by earlier `us_factor_ic.py`/
`us_factor_ic_by_size.py`/`deep_dive_f_us_low_vol*.py` runs) -- this script
only globs `research/data/raw/` for that exact filename pattern and calls
`us_price_series()`, which hits `load_dev()`'s parquet cache. This is by far
the largest real-data US sample any script in this project has used (138
vs. the 26-40 random subsamples every prior US factor test used), simply
because it reuses every ticker any prior round happened to fetch rather
than drawing a fresh random subsample.

**Signal function used is `f_us_momentum_12m` -- a KNOWN-FAIL factor
(`US_LEADS.md` #2/#5/#8/#11, every tier).** This is deliberate, not an
oversight: any already-computed column in `US_FACTOR_COLUMNS` would do for
a pure plumbing test, and using the momentum column (already present in
`prepare_us_factors()`'s output, no new code) is the path of least
resistance. **The result below MUST NOT be read as a new candidate
judgment for `f_us_momentum_12m` or logged as a `TRIALS_LEDGER.md` row** --
that factor already has a final FAIL verdict from four independent
cheap-gate tests. This run's only claim is "the engine executes correctly
on 138 real tickers + real SPY calendar without crashing and produces
sane-looking outputs" -- a plumbing check, not a strategy verdict.

**CAPM alpha/beta reused from `portfolio_backtest_v2.py`'s
`alpha_significance()` as-is** (imported, not copy-pasted) -- that function
is already generic over any `equity_curve` (date/equity) + `market_df`
(date/close) pair, which is exactly the shape `run_us_backtest()`'s
`USPortfolioResult.equity_curve` and `deep_dive_f_us_low_vol.py`'s
`_load_market_df()` already produce respectively. No US-specific fork of
the alpha/beta math needed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from deep_dive_f_us_low_vol import _load_market_df
from portfolio_backtest_v2 import alpha_significance
from us_factors import prepare_us_factors, us_price_series
from us_portfolio_backtest import USPortfolioConfig, run_us_backtest
from validation import holdout

CACHE_PATTERN = re.compile(
    r"^USStockPrice__([A-Z0-9.]+)__1990-01-01__2024-12-31\.parquet$"
)
DATA_RAW = Path(__file__).parent / "data" / "raw"


def cached_ticker_ids() -> list[str]:
    """Every ticker with a full-range (1990-01-01..2024-12-31) USStockPrice
    parquet already on disk, excluding SPY (used only as the benchmark, not
    a tradeable universe member here). Sorted for determinism -- this is
    NOT a random sample, it's "everything already fetched", so there is no
    seed to record."""
    ids = []
    for p in DATA_RAW.glob("USStockPrice__*__1990-01-01__2024-12-31.parquet"):
        m = CACHE_PATTERN.match(p.name)
        if m and m.group(1) != "SPY":
            ids.append(m.group(1))
    return sorted(set(ids))


def momentum_12_1_signal_fn(price_data, as_of_date, market_df):
    """Top-N score = `f_us_momentum_12m` column value as of the most recent
    row on/before `as_of_date`. See module docstring: this factor is a
    KNOWN-FAIL cheap-gate result, used here purely as a plumbing-test
    signal, not a candidate."""
    scores = {}
    for sid, df in price_data.items():
        past = df[df["date"] <= as_of_date]
        if past.empty:
            continue
        v = past["f_us_momentum_12m"].iloc[-1]
        if v == v:  # not NaN
            scores[sid] = float(v)
    return scores


def main():
    print("=== us_portfolio_pilot_real_data.py -- real-data engine wiring pilot ===")
    print("NOTE: infra/plumbing test only. f_us_momentum_12m is a known-FAIL factor")
    print("      (US_LEADS.md #2/#5/#8/#11) -- this run's result is NOT a new candidate.\n")

    ids = cached_ticker_ids()
    print(f"cached tickers available (excl. SPY): {len(ids)}")

    market_df, is_spy = _load_market_df()
    if not is_spy or market_df.empty:
        print("SPY benchmark unavailable -- aborting pilot (need it for both the trading")
        print("calendar and alpha/beta; this itself is a valid finding to record).")
        return
    print(f"market benchmark: SPY, {len(market_df)} rows, "
          f"{market_df['date'].min()}..{market_df['date'].max()}")

    price_data = {}
    dropped = []
    for sid in ids:
        px = us_price_series(sid)
        if px.empty or len(px) < 260:
            dropped.append(sid)
            continue
        price_data[sid] = prepare_us_factors(px)
    print(f"usable price_data (>=260 rows, factors computed): {len(price_data)} "
          f"(dropped {len(dropped)}: {dropped[:10]}{'...' if len(dropped) > 10 else ''})")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"is_holdout_consumed() == False: {holdout_ok}")

    periods = [
        ("TRAIN", "2015-01-01", "2020-12-31"),
        ("VAL", "2021-01-01", "2024-12-31"),
    ]
    for label, start, end in periods:
        cfg = USPortfolioConfig(
            start_date=start, end_date=end,
            rebalance_every_n_days=63,  # quarterly, same TW convention as portfolio_backtest_v2.py
            max_positions=15, stop_loss_pct=0.15,
            initial_capital=1_000_000.0,
            book_name=f"us_portfolio_pilot_{label.lower()}",
        )
        result = run_us_backtest(momentum_12_1_signal_fn, price_data, market_df, cfg)
        alpha = alpha_significance(result.equity_curve, market_df)
        print(f"\n--- {label} ({start}..{end}) ---")
        print(f"trades: {result.n_trades}, total_return: {result.total_return_pct:+.2f}%, "
              f"MDD: {result.max_drawdown_pct:.2f}%, Sortino: {result.sortino_ratio:.3f}")
        print(f"beta: {alpha['beta']:.3f}, alpha_ann: {alpha['alpha_ann_pct']:+.2f}%, "
              f"alpha_pvalue: {alpha['alpha_pvalue']:.4f}, n_days: {alpha['n_days']}")
        print(f"unresolved at end: {result.unresolved_at_end}")

    print("\n=== pilot complete -- engine + real SPY calendar + real cached price data ===")
    print("=== all ran end-to-end without crashing. No TRIALS_LEDGER entry (see docstring). ===")


if __name__ == "__main__":
    main()
