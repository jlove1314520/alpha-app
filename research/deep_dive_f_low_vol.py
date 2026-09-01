"""TW marathon-adjacent round: deep-dive validation for `f_low_vol`
(TW-side low-volatility factor, TRIALS_LEDGER.md #9, PASS at the cheap
IC gate), per `HYPOTHESIS_QUEUE.md` #7 -- "低波動（TW版策略層）".

**Why this exists**: #9's cheap gate only checked cross-sectional Spearman
IC vs a random-shuffle null. That answers "does ranking stocks by trailing
60-day volatility correlate with future returns", not "is this a usable
strategy net of real costs, and is any apparent edge just market beta in
disguise". This script is the TW-side equivalent of `deep_dive_f_us_low_
vol.py` (US track, FAIL, `STRATEGY_GRAVEYARD.md`), and per that FAIL
entry's explicit "泛化" note, this TW deep-dive must pay special attention
to whether CAPM beta drifts across TRAIN/VAL periods -- the US failure
mode was NOT "no edge", it was "VAL period return looked strong but beta
had collapsed to -0.891, i.e. the apparent edge was directional
counter-market exposure, not cross-sectional ranking skill". A TW result
that shows a similar beta swing between periods must be read the same way,
not treated as "the factor got stronger".

**Method, directly reused from `deep_dive_f_quality_roe_stability.py`**
(the established TW single-factor deep-dive template, not reinvented
here): decile long-short (top 10% vs bottom 10% by `f_low_vol`, equal-
weight legs), TRAIN/VAL split (`validation/holdout.py`'s TRAIN_END/
VAL_END), matched random long-short control (same rebalance cadence, same
decile sizes, random picks -- not a static/buy&hold benchmark), cost
sensitivity at 1x/2x/3x `validation/costs.py`'s DEFAULT_SLIPPAGE_BPS, and
CAPM beta/alpha vs TAIEX via `long_short_backtest.capm_beta()` (regression,
not assumed zero just because the construction is long-short).

Same cached 100-name sample (`factor_ic.py`'s SAMPLE_SEED=20260822) as the
#9 cheap gate -- zero new FinMind calls for the underlying price data.
`f_low_vol` is a pure price factor (`-rolling(60).std(daily_ret)`,
`factors.py` LOW_VOL_WINDOW=60) with zero PIT risk, so there is no PIT-
verification prerequisite here the way there was for `f_value_pb`/
`f_quality_roe_stability` before their deep-dives.

**Judgment standard**: same yardstick already applied to `weinstein_
stage2_v2`/`cta_momentum_12m`/`pead_portfolio_v1`/`dividend_yield_
portfolio_v1` -- random-control percentile clearing 90.0 is necessary but
NOT sufficient; alpha significance (t-test p-value on the daily net-of-
cost spread return vs zero) plus the beta reading together are the final
verdict, not the raw total/annualized return number alone.
"""
from __future__ import annotations

import random
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy import stats

import long_short_backtest as lsb
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TARGET_FACTOR = "f_low_vol"
START_DATE = "2010-01-01"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # matches factor_ic.py's FORWARD_HORIZON snapshot cadence, for comparability
N_RANDOM_DRAWS = 100  # same resolution as f_quality_roe_stability's final deep-dive (#17), 1% steps
RANDOM_CONTROL_SEED = 20260902  # new seed, disclosed -- not reused from another factor's draws
COST_MULTIPLIERS = [1, 2, 3]  # x DEFAULT_SLIPPAGE_BPS, per CONSTITUTION.md's cost-sensitivity requirement

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": ("2021-01-01", holdout.VAL_END),
}


def _factor_cross_section(as_of: str, data: dict[str, pd.DataFrame], factor_col: str) -> tuple[list[str], list[float]]:
    ids, vals = [], []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        fv = d.loc[idx[0], factor_col]
        if pd.isna(fv):
            continue
        ids.append(sid)
        vals.append(float(fv))
    return ids, vals


def _decile_legs_factor(as_of: str, data: dict, industry_map, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, vals = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)  # higher f_low_vol (= lower realized vol) = long
    k = max(1, round(n * DECILE_FRACTION))
    longs = [sid for sid, _ in order[:k]]
    shorts = [sid for sid, _ in order[-k:]]
    return longs, shorts


def _random_legs_factor(as_of: str, data: dict, industry_map, rng: random.Random, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, _ = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    k = max(1, round(n * DECILE_FRACTION))
    if n < 2 * k:
        return [], []
    picks = rng.sample(ids, 2 * k)
    return picks[:k], picks[k:]


def _alpha_significance(result: pd.DataFrame) -> tuple[float, float]:
    """One-sample t-test of net-of-cost daily returns against zero.
    Same test used to judge weinstein_stage2_v2/pead_portfolio_v1/
    dividend_yield_portfolio_v1's alpha -- clearing the random-control
    percentile is necessary but not sufficient; this is the final check.
    Returns (mean_daily_return_pct, p_value)."""
    rets = result["equity"].pct_change().iloc[1:].dropna()
    if len(rets) < 30:
        return float("nan"), float("nan")
    t_stat, p_value = stats.ttest_1samp(rets, 0.0)
    return float(rets.mean() * 100), float(p_value)


def run_one(data, market_df, start, end, slippage_bps):
    lsb.SLIPPAGE_BPS = slippage_bps  # module-global read at call time inside run_long_short/costmod calls
    leg_fn = partial(_decile_legs_factor, factor_col=TARGET_FACTOR)
    result = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=leg_fn)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100
    mean_daily_pct, alpha_p = _alpha_significance(result)

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = partial(_random_legs_factor, rng=rng, factor_col=TARGET_FACTOR)
        rr = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=rand_leg_fn)
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100,
        "mean_daily_return_pct": mean_daily_pct,
        "alpha_p_value": alpha_p,
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
    }


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_f_low_vol")
    market_df = prepare_market_data(market_raw)

    print(f"=== TW deep-dive (1b): {TARGET_FACTOR} ===")
    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, same seed as #9 cheap gate)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    n_with_factor = sum(1 for d in data.values() if TARGET_FACTOR in d.columns and d[TARGET_FACTOR].notna().any())
    print(f"  {n_with_factor}/{len(data)} names have at least one non-NaN {TARGET_FACTOR} value")
    if n_with_factor < 10:
        print(f"\nABORT: only {n_with_factor} usable names, below the decile-leg minimum cross-section "
              f"of 10 -- cannot run a meaningful deep-dive with this sample.")
        return None

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = lsb.costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}% "
                  f"(p={r['alpha_p_value']:.4f})")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS  # restore module default before exit

    print("\n=== SUMMARY ===")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}% (p={r['alpha_p_value']:.4f})  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    # Explicit beta-drift check, per the f_us_low_vol FAIL entry's "泛化" note (STRATEGY_GRAVEYARD.md):
    # a VAL-period return improvement accompanied by a large beta swing is NOT evidence of a stronger
    # cross-sectional signal -- it can be directional counter-market exposure in disguise.
    train_beta_1x = next(r["beta"] for r in all_results if r["period"] == "TRAIN" and r["cost_multiplier"] == 1)
    val_beta_1x = next(r["beta"] for r in all_results if r["period"] == "VAL" and r["cost_multiplier"] == 1)
    beta_drift = abs(val_beta_1x - train_beta_1x)
    print(f"\nbeta drift check: TRAIN beta={train_beta_1x:+.3f}  VAL beta={val_beta_1x:+.3f}  "
          f"|drift|={beta_drift:.3f}  "
          f"{'FLAG: large drift, treat any VAL improvement with suspicion (US low-vol failure mode)' if beta_drift > 0.3 else 'within a plausible market-neutral-construction range'}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_low_vol.csv", index=False)
    print("\nsaved data/deep_dive_f_low_vol.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
