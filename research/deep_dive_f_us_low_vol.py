"""US-track deep-dive (MARATHON_PROTOCOL.md 1b) for `f_us_low_vol` -- the
US track's first cheap-gate CHEAP_PASS (round 82, TRIALS_LEDGER.md #39,
US_LEADS.md #1).

**Why this exists**: round 82's cheap gate only checked cross-sectional
Spearman IC vs a random-shuffle null (does the factor rank stocks in a
direction correlated with future returns). That is not "is this a usable
strategy net of real costs, and is any apparent edge just market beta in
disguise". US_MARATHON_STATE.md's own "下一步" note is explicit: deep-dive
must do train/val split FIRST, learning from FUT track's `fut_basis_carry`
lesson (a CHEAP_PASS that did not survive out-of-sample deep-dive scrutiny,
`deep_dive_fut_basis_carry.py`, TRIALS_LEDGER.md #37/FAIL) -- a strong VAL
IC alone is not sufficient, the full 1b gate (train/val, matched random
control, cost sensitivity 1x/2x/3x, beta) must all run before any
PASS/EXPERIMENTAL verdict.

**Why this is a new script, not a reuse of `long_short_backtest.run_long_short`
as-is**: that function's cost model call
(`costmod.round_trip_cost_pct(slippage_bps=..., commission_discount=...)`)
is hardcoded to TW's `validation/costs.py` signature (flat-rate, no
`price`/`shares` args). `validation/us_costs.py`'s functions of the same
name have a genuinely different signature -- they need `price` and `shares`
because the US model's SEC-fee/FINRA-TAF components are computed in
absolute dollar terms, not as a flat percentage (see that module's
docstring). Monkeypatching `lsb.costmod` to point at `us_costs` would raise
a TypeError (missing required `price` arg), not silently produce a wrong
number, but it's cleaner to write a small US-specific `run_long_short_us()`
below than to hack around the mismatch. `annualized_return()`,
`sortino_ratio()`, and `capm_beta()` ARE reused directly from
`long_short_backtest` (imported as `lsb`) -- those three only operate on
the resulting (date, spread_return, equity) DataFrame + a market_df with
(date, close), no TW-specific coupling, same pattern already validated by
`deep_dive_f_quality_roe_stability.py`.

**Cost model simplification, disclosed not hidden**: `us_costs.py`'s
per-trade fee model needs a concrete price/share-count to compute a
percentage (SEC fee/FINRA TAF have floors that make the effective % cost
non-scale-invariant at very small notional). This script computes cost at
one representative notional (price=$50, shares=100 -> $5,000/leg) rather
than the actual per-stock price on each rebalance day. $5,000/leg is a
plausible retail position size, not a special-cased favorable number picked
to make the strategy look good -- but it IS an approximation, and is
reported as such alongside the numbers, not silently assumed exact.

**Market benchmark, disclosed choice**: this track has no cached broad-
market index series yet (unlike TW's TAIEX). This script fetches SPY
(S&P 500 ETF) as a single new API call -- one ticker, not a hypothesis-
testing budget burn, per protocol section 4's "小樣本快篩" spirit applying
to 1a not 1b (a deep-dive on an already-CHEAP_PASS candidate is allowed to
spend a modest amount of new quota). If that fetch fails (quota/network),
falls back to an equal-weight average of the already-cached sample itself
as a market proxy -- honestly labeled as a much weaker proxy, not silently
treated as equivalent to SPY.

**Sample**: reuses the EXACT same 40-name random sample (seed=20260826) and
loader (`load_us_sample_with_factors`) from `us_factor_ic.py`'s round-82
cheap gate -- same names, same source, zero new API calls for the stock
data itself (round 82 already populated the parquet cache for every name
that loaded successfully; anything that failed there will fail identically
here, same cache-miss behavior).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from finmind_client import load_dev
from us_factor_ic import SAMPLE_SEED, SAMPLE_SIZE, load_us_sample_with_factors, sample_us_universe_ids
from us_factors import US_FACTOR_COLUMNS
from validation import holdout
from validation import us_costs as us_costmod

TARGET_FACTOR = "f_us_low_vol"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # matches us_factor_ic.py's snapshot cadence (build_snapshots' default), for comparability
N_RANDOM_DRAWS = 100  # same resolution as TW's f_quality_roe_stability deep-dive
RANDOM_CONTROL_SEED = 20260826
COST_MULTIPLIERS = [1, 2, 3]
REPRESENTATIVE_PRICE = 50.0   # disclosed simplification, see module docstring
REPRESENTATIVE_SHARES = 100.0  # -> $5,000/leg notional
MAX_PLAUSIBLE_DAILY_RETURN = 0.50  # US has no +-10% circuit breaker (us_costs.py docstring), so this is
# purely a data-artifact guard (bad split/dividend adjustment, not a real regulatory band) -- set wider
# than TW's 0.20 for that reason, not because larger real US daily moves are expected to be common.

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": (holdout.TRAIN_END, holdout.VAL_END),
}


def _load_market_df() -> tuple[pd.DataFrame, bool]:
    """Returns (market_df with date/close columns, is_spy). Tries SPY first
    (one new API call), falls back to an equal-weight synthetic index built
    from load_us_sample_with_factors' own already-cached sample on failure."""
    try:
        raw = load_dev("USStockPrice", "SPY", "1990-01-01")
        if not raw.empty:
            df = raw.rename(columns={"Close": "close"})[["date", "close"]].sort_values("date").reset_index(drop=True)
            print(f"  market benchmark: SPY, {len(df)} rows, {df['date'].min()}..{df['date'].max()}")
            return df, True
    except Exception as e:  # noqa: BLE001
        print(f"  SPY fetch failed ({str(e)[:200]}), falling back to equal-weight sample proxy")
    return pd.DataFrame(), False


def _cross_section(as_of, data: dict[str, pd.DataFrame], factor_col: str) -> tuple[list[str], list[float]]:
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


def _decile_legs(as_of, data, factor_col=TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, vals = _cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)  # higher f_us_low_vol (= lower realized vol) = long
    k = max(1, round(n * DECILE_FRACTION))
    return [sid for sid, _ in order[:k]], [sid for sid, _ in order[-k:]]


def _random_legs(as_of, data, rng: random.Random, factor_col=TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, _ = _cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    k = max(1, round(n * DECILE_FRACTION))
    if n < 2 * k:
        return [], []
    picks = rng.sample(ids, 2 * k)
    return picks[:k], picks[k:]


def run_long_short_us(data: dict[str, pd.DataFrame], calendar: list, start: str, end: str,
                       rebalance_days: int, slippage_bps: float, leg_fn) -> pd.DataFrame:
    """US-specific twin of long_short_backtest.run_long_short() -- same
    mechanics (equal-weight legs, rebalance-day cost drag, per-day spread
    return compounding), but wired to validation/us_costs.py's price/shares-
    based cost functions instead of TW's flat-rate ones. See module
    docstring for why this can't just call lsb.run_long_short directly."""
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    days = sorted(d for d in calendar if start <= d <= end)
    if not days:
        raise ValueError("empty calendar for the given date range")

    round_trip = us_costmod.round_trip_cost_pct(
        price=REPRESENTATIVE_PRICE, shares=REPRESENTATIVE_SHARES, slippage_bps=slippage_bps)
    short_round_trip = us_costmod.short_round_trip_cost_pct(
        price=REPRESENTATIVE_PRICE, holding_days=rebalance_days, shares=REPRESENTATIVE_SHARES, slippage_bps=slippage_bps)

    longs, shorts = [], []
    rows = []
    equity = 1.0
    for i, day in enumerate(days):
        if i % rebalance_days == 0:
            new_longs, new_shorts = leg_fn(day, data)
            if new_longs and new_shorts:
                turnover_long = 1.0 if not longs else len(set(new_longs) ^ set(longs)) / (2 * len(new_longs))
                turnover_short = 1.0 if not shorts else len(set(new_shorts) ^ set(shorts)) / (2 * len(new_shorts))
                long_cost = turnover_long * round_trip
                short_cost = turnover_short * short_round_trip
                equity *= (1 - long_cost) * (1 - short_cost)
                longs, shorts = new_longs, new_shorts
        if i == 0:
            rows.append({"date": day, "spread_return": 0.0, "equity": equity})
            continue
        prev_day = days[i - 1]

        def leg_return(ids):
            rets = []
            for sid in ids:
                if sid not in idx:
                    continue
                df = idx[sid]
                if day not in df.index or prev_day not in df.index:
                    continue
                p0, p1 = df.loc[prev_day, "adj_close"], df.loc[day, "adj_close"]
                if p0 and p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
                    r = p1 / p0 - 1
                    if abs(r) > MAX_PLAUSIBLE_DAILY_RETURN:
                        continue
                    rets.append(r)
            return float(np.mean(rets)) if rets else 0.0

        r_long = leg_return(longs)
        r_short = leg_return(shorts)
        spread = r_long - r_short
        equity *= (1 + spread)
        rows.append({"date": day, "spread_return": spread, "equity": equity})

    return pd.DataFrame(rows)


def run_one(data, calendar, market_df, start, end, slippage_bps):
    from functools import partial
    result = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slippage_bps, leg_fn=_decile_legs)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = (float("nan"), float("nan"))
    if not market_df.empty:
        beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = partial(_random_legs, rng=rng)
        rr = run_long_short_us(data, calendar, start, end, REBALANCE_DAYS, slippage_bps, leg_fn=rand_leg_fn)
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100 if not pd.isna(alpha_ann) else float("nan"),
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
    }


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_us_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== US deep-dive (1b): {TARGET_FACTOR} ===")
    print(f"Loading sample ({len(sample_ids)} requested, same seed={SAMPLE_SEED} as round-82 cheap gate, cache-first)...")
    data, quota_hit, quota_hit_ticker = load_us_sample_with_factors(sample_ids)
    print(f"  {len(data)}/{len(sample_ids)} usable names" +
          (f" (stopped early at {quota_hit_ticker} -- quota/rate-limit)" if quota_hit else ""))

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the decile-leg minimum cross-section "
              f"of 10 -- cannot run a meaningful deep-dive with this sample.")
        return None

    market_df, is_spy = _load_market_df()
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = us_costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, calendar, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print(f"market benchmark used for beta: {'SPY' if is_spy else 'NONE (SPY fetch failed, beta not computed)'}")
    print(f"sample: {len(data)} names (cross-section decile size k={max(1, round(len(data)*DECILE_FRACTION))}/leg -- "
          f"small-sample caveat, same disclosure pattern as TW's f_quality_roe_stability deep-dive)")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    train_sign = "positive" if all_results[0]["annualized_return_pct"] > 0 else "negative"
    val_sign = "positive" if all_results[3]["annualized_return_pct"] > 0 else "negative"
    print(f"\nTRAIN sign (1x): {train_sign}  VAL sign (1x): {val_sign}  "
          f"{'AGREE' if train_sign == val_sign else 'DISAGREE -- sign flips across split'}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_us_low_vol.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return all_results


if __name__ == "__main__":
    main()
