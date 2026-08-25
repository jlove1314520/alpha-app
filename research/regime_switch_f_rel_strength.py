"""TW marathon: regime-switching STRATEGY backtest for `f_rel_strength`
(#5), per LEADS.md's `f_rel_strength_regime_switch` next-step ("用大盤位階
當開關建一個規則型策略，跑完整關卡才能給真正判定") and MARATHON_PROTOCOL.md
section 1b.

Why this candidate, why now: `regime_conditions.py` (2026-08-26 interactive
session) found f_rel_strength's train/val direction reversal is fully and
cleanly explained by market trend (TAIEX vs MA200) -- IC positive in bull,
negative in bear, with the same sign pattern across 3 other conditions too.
That was a factor-level (cross-sectional IC) finding, NOT a strategy-level
backtest. This script builds the actual rule-based strategy LEADS.md
proposed and runs it through the standard deep-dive gates so it can get a
real PASS/FAIL/EXPERIMENTAL verdict instead of staying PENDING.

**Rule (the conservative "關閉" variant, not "反向")**: at each rebalance
date, look up the market trend regime PIT-safe (TAIEX close vs its own
rolling MA200 as of that date, `strategies/weinstein_stage2.py::prepare_market_data`'s
existing `gate` column -- not a new definition). If bull (gate=True): go
long the top decile of f_rel_strength, short the bottom decile (same
decile-long-short construction as f_value_pb/f_quality_roe_stability's
deep dives). If bear (gate=False): hold NO position (flat) -- deliberately
NOT reversing the legs. Reversing was the other option LEADS.md mentioned,
but it assumes the bear-regime IC's sign and magnitude are stable enough to
trade against, which regime_conditions.py never tested (it only established
sign, not whether the negative IC survives its own cost/turnover drag as a
standalone short-the-momentum-losers strategy). Flat is the lower-risk,
fewer-assumptions choice for a first pass; testing "reverse in bear" is left
as an explicit follow-up if this flat version looks promising.

Engine: reuses `long_short_backtest.py`'s cost model
(`validation/costs.py`) and diagnostics (`annualized_return`,
`sortino_ratio`, `capm_beta`) via the `lsb` import, same as
`deep_dive_f_value_pb.py`, but the day-by-day walk itself is a NEW function
(`run_regime_switch`) rather than `lsb.run_long_short`, because that
function's rebalance logic silently KEEPS the previous legs when leg_fn
returns empty lists (`if new_longs and new_shorts:` guard) -- correct for
"skip this rebalance, no new picks available" but wrong here, where an
empty leg_fn result means "the regime says get out", which must actually
flatten the position (and charge the unwind cost), not silently continue
holding the last bull-regime picks through a bear regime.

Sample: same cached 100-name sample as every other TW deep-dive this
marathon (`factor_ic.SAMPLE_SEED`/`SAMPLE_SIZE`), ZERO new FinMind calls.
Matched random control: regime-gated the same way (random legs during bull
windows, flat during bear windows) so the comparison isolates "does
f_rel_strength's specific ranking beat random stock-picking within the same
bull-only trading windows", not "does trading only in bull markets beat
trading always" (that second question is a different, uninteresting one --
of course avoiding bear markets helps directionally, but that's market
timing, not this factor's cross-sectional skill).
"""
from __future__ import annotations

import random
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import costs as costmod
from validation import holdout

TARGET_FACTOR = "f_rel_strength"
START_DATE = "2010-01-01"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # same cadence as factor_ic.py's forward-return horizon and the other TW deep-dives
N_RANDOM_DRAWS = 100  # same resolution as the f_value_pb/f_quality_roe_stability deep-dives
RANDOM_CONTROL_SEED = 20260826
COST_MULTIPLIERS = [1, 2, 3]

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": ("2021-01-01", holdout.VAL_END),
}


def _gate_lookup(market_df: pd.DataFrame) -> dict[str, bool]:
    return dict(zip(market_df["date"], market_df["gate"]))


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


def _decile_legs_factor(as_of: str, data: dict, factor_col: str) -> tuple[list[str], list[str]]:
    ids, vals = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    # f_rel_strength: higher = stronger relative outperformance vs market -> long leg (matches
    # regime_conditions.py's bull-regime finding of positive IC on the raw factor value).
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)
    k = max(1, round(n * DECILE_FRACTION))
    return [sid for sid, _ in order[:k]], [sid for sid, _ in order[-k:]]


def _random_legs_factor(as_of: str, data: dict, rng: random.Random, factor_col: str) -> tuple[list[str], list[str]]:
    ids, _ = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    k = max(1, round(n * DECILE_FRACTION))
    if n < 2 * k:
        return [], []
    picks = rng.sample(ids, 2 * k)
    return picks[:k], picks[k:]


def _regime_gated_legs(as_of: str, data: dict, gate: dict[str, bool], base_leg_fn) -> tuple[list[str], list[str]]:
    if not gate.get(as_of, False):
        return [], []  # bear regime -> flat, regardless of what base_leg_fn would have picked
    return base_leg_fn(as_of, data)


def run_regime_switch(
    data: dict[str, pd.DataFrame], market_df: pd.DataFrame, gate: dict[str, bool],
    start: str, end: str, rebalance_days: int, slippage_bps: float, leg_fn,
) -> pd.DataFrame:
    """Same daily-compounding walk as lsb.run_long_short, but explicitly
    flattens the position (charging unwind cost) when leg_fn returns empty
    legs at a rebalance date, instead of silently keeping the previous
    legs -- see module docstring for why lsb.run_long_short can't be reused
    as-is for a regime-gated strategy."""
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    calendar = sorted(d for d in market_df["date"] if start <= d <= end)
    if not calendar:
        raise ValueError("empty calendar for the given date range")

    longs, shorts = [], []
    rows, equity = [], 1.0
    n_bull_rebalances, n_bear_rebalances = 0, 0
    for i, day in enumerate(calendar):
        if i % rebalance_days == 0:
            new_longs, new_shorts = leg_fn(day, data)
            was_in_position = bool(longs and shorts)
            now_in_position = bool(new_longs and new_shorts)
            if now_in_position:
                n_bull_rebalances += 1
            else:
                n_bear_rebalances += 1
            if was_in_position or now_in_position:
                # Charge turnover cost whenever the position CHANGES (enter, exit, or re-pick),
                # not only when both old and new legs are non-empty (that was lsb.run_long_short's
                # implicit assumption, which never has to handle "go to flat").
                turnover_long = 1.0 if not longs or not new_longs else len(set(new_longs) ^ set(longs)) / (2 * max(len(new_longs), 1))
                turnover_short = 1.0 if not shorts or not new_shorts else len(set(new_shorts) ^ set(shorts)) / (2 * max(len(new_shorts), 1))
                holding_days = rebalance_days
                if new_longs:
                    long_cost = turnover_long * costmod.round_trip_cost_pct(slippage_bps=slippage_bps)
                else:
                    long_cost = 1.0 * costmod.round_trip_cost_pct(slippage_bps=slippage_bps) if longs else 0.0
                if new_shorts:
                    short_cost = turnover_short * costmod.short_round_trip_cost_pct(holding_days, slippage_bps=slippage_bps)
                else:
                    short_cost = 1.0 * costmod.short_round_trip_cost_pct(holding_days, slippage_bps=slippage_bps) if shorts else 0.0
                equity *= (1 - long_cost) * (1 - short_cost)
            longs, shorts = new_longs, new_shorts
        if i == 0:
            rows.append({"date": day, "spread_return": 0.0, "equity": equity})
            continue
        prev_day = calendar[i - 1]

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
                    if abs(r) > lsb.MAX_PLAUSIBLE_DAILY_RETURN:
                        continue
                    rets.append(r)
            return float(np.mean(rets)) if rets else 0.0

        spread = (leg_return(longs) - leg_return(shorts)) if (longs and shorts) else 0.0
        equity *= (1 + spread)
        rows.append({"date": day, "spread_return": spread, "equity": equity})

    result = pd.DataFrame(rows)
    result.attrs["n_bull_rebalances"] = n_bull_rebalances
    result.attrs["n_bear_rebalances"] = n_bear_rebalances
    return result


def run_one(data, market_df, gate, start, end, slippage_bps):
    real_leg_fn = lambda as_of, d: _regime_gated_legs(as_of, d, gate, lambda a, dd: _decile_legs_factor(a, dd, TARGET_FACTOR))
    result = run_regime_switch(data, market_df, gate, start, end, REBALANCE_DAYS, slippage_bps, real_leg_fn)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100
    n_bull, n_bear = result.attrs["n_bull_rebalances"], result.attrs["n_bear_rebalances"]

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = lambda as_of, d, _rng=rng: _regime_gated_legs(as_of, d, gate, lambda a, dd: _random_legs_factor(a, dd, _rng, TARGET_FACTOR))
        rr = run_regime_switch(data, market_df, gate, start, end, REBALANCE_DAYS, slippage_bps, rand_leg_fn)
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
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
        "n_bull_rebalances": n_bull,
        "n_bear_rebalances": n_bear,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in regime_switch_f_rel_strength")
    market_df = prepare_market_data(market_raw)
    gate = _gate_lookup(market_df)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused, ZERO new FinMind calls expected)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    n_with_factor = sum(1 for d in data.values() if TARGET_FACTOR in d.columns and d[TARGET_FACTOR].notna().any())
    print(f"  {n_with_factor}/{len(data)} names have at least one non-NaN {TARGET_FACTOR} value")

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, market_df, gate, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  bull rebalances (in-position windows): {r['n_bull_rebalances']}  bear (flat) rebalances: {r['n_bear_rebalances']}")
            print(f"  random control ({N_RANDOM_DRAWS} draws, same regime gate): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    print("\n=== SUMMARY ===")
    print("CAVEAT: bear-regime rule tested here is FLAT (no position), not reverse-the-legs -- see module docstring.")
    print("CAVEAT: PIT status for f_rel_strength (price-only, no fundamentals) is the standard adjust.py-verified level, "
          "same as the other momentum/price factors -- no additional caveat beyond that.")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/regime_switch_f_rel_strength.csv", index=False)
    print("\nsaved data/regime_switch_f_rel_strength.csv")
    return all_results


if __name__ == "__main__":
    main()
