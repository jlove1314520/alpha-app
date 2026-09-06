"""US-track narrower-null diagnostic for `f_us_low_vol` on the clean
stratified universe -- answers `US_LEADS.md`#21's outstanding "下一步(3)"
item explicitly left open since round392: `_random_legs()` (used by
`deep_dive_f_us_low_vol.py::run_one()` and already REFUTED the "any random
long/short beats costs" hypothesis in `TRIALS_LEDGER.md`#162) draws a
BRAND-NEW random 2k-stock sample every single rebalance day (20 trading
days). That means its long/short legs churn almost 100% turnover every
rebalance, while the REAL factor's legs are serially correlated (a stock
that is low-volatility this month is usually still low-volatility next
month), so the real strategy's turnover is much lower. Higher turnover ->
more `us_costs.py` slippage/commission/short-borrow drag baked into the
random control's equity curve, for reasons that have nothing to do with
stock-picking skill. round392 flagged this as an unresolved confound:
"`_random_legs()`是完全隨機挑股，不是「打亂f_us_low_vol分數本身再照原規則
排序」，兩者統計檢定力可能不同，更精確的窄版本診斷仍待做".

**This script's control ("persistent-random legs")**: assign each stock ID
a single random pseudo-score, drawn ONCE per Monte Carlo draw (not
re-drawn every rebalance day), then apply the exact same rank-and-split
decile logic as the real `_decile_legs()`. This isolates turnover as the
sole free variable: the persistent-random control has the SAME serial-
correlation-driven low turnover as the real strategy (a stock keeps the
same pseudo-rank all period, so it stays in the same leg until it drops
out of the cross-section), but its ranking carries zero information about
real low-volatility characteristics. If turnover/cost-drag were the real
driver, this control should score close to the real strategy. If it still
loses badly, turnover is not the explanation and the earlier `_random_legs`
REFUTED verdict (#162) stands on firmer ground.

**Pre-registered verdict (written BEFORE running, hash-lock discipline)**:
comparing this persistent-random control's `random_control_percentile`
(vs ITS OWN 100 persistent-random draws, i.e. is the real strategy still
beating a turnover-matched null) on VAL 2020-2024, 1x cost only (where the
anomaly is most extreme per `TRIALS_LEDGER.md`#151/#152/#154):
  - CONFIRMED (turnover artifact explains a material part of the anomaly):
    real percentile vs persistent-random null < 90.0 (down from the 100.0
    the real strategy scores against the fresh-random null in #162), i.e.
    turnover-matching alone closes most of the gap.
  - PARTIAL: real percentile 90.0-99.0 against persistent-random null --
    turnover-matching narrows but does not close the gap.
  - REFUTED: real percentile stays >=99.0, i.e. turnover-matching makes no
    material difference -- the anomaly is about WHICH stocks are picked,
    not how often the picks change.
Also reports mean turnover_long/turnover_short for real vs fresh-random
(`_random_legs`) vs persistent-random legs, as the direct evidence for
which mechanism (stock selection vs turnover) is doing the work.

**Zero new API calls**: reuses `load_clean_sample_with_factors()` from
`deep_dive_f_us_low_vol_clean_universe.py` unchanged (248 already-cached
tickers, price-only factor, no SEC EDGAR dependency).
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from deep_dive_f_us_low_vol import (
    MAX_PLAUSIBLE_DAILY_RETURN,
    N_RANDOM_DRAWS,
    RANDOM_CONTROL_SEED,
    REBALANCE_DAYS,
    REPRESENTATIVE_PRICE,
    REPRESENTATIVE_SHARES,
    TARGET_FACTOR,
    _cross_section,
    _decile_legs,
    _load_market_df,
    _random_legs,
)
from deep_dive_f_us_low_vol_clean_universe import load_clean_sample_with_factors
from validation import holdout
from validation import us_costs as us_costmod

DECILE_FRACTION = 0.10
VAL_PERIOD = (holdout.TRAIN_END, holdout.VAL_END)
SLIPPAGE_1X = us_costmod.DEFAULT_SLIPPAGE_BPS


def _persistent_random_legs_factory(rng: random.Random):
    """Returns a leg_fn that ranks by a per-stock pseudo-score drawn ONCE
    (closure-captured dict), not re-drawn per rebalance day -- this is the
    only difference from `_random_legs()`, which draws a fresh sample every
    call. Same rank-and-split mechanics as the real `_decile_legs()`."""
    score_cache: dict[str, float] = {}

    def leg_fn(as_of, data):
        ids, _ = _cross_section(as_of, data, TARGET_FACTOR)
        n = len(ids)
        if n < 10:
            return [], []
        for sid in ids:
            if sid not in score_cache:
                score_cache[sid] = rng.random()
        order = sorted(ids, key=lambda sid: score_cache[sid], reverse=True)
        k = max(1, round(n * DECILE_FRACTION))
        return order[:k], order[-k:]

    return leg_fn


def run_long_short_us_with_turnover(data, calendar, start, end, rebalance_days, slippage_bps, leg_fn):
    """Turnover-instrumented twin of `deep_dive_f_us_low_vol.run_long_short_us`.
    Duplicated (not imported) because that function does not expose turnover
    per rebalance and this script must not modify the frozen, already-tested
    original -- same rationale as that module's own docstring re: not
    monkeypatching engines with different signatures."""
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
    turnovers = []
    equity = 1.0
    for i, day in enumerate(days):
        if i % rebalance_days == 0:
            new_longs, new_shorts = leg_fn(day, data)
            if new_longs and new_shorts:
                turnover_long = 1.0 if not longs else len(set(new_longs) ^ set(longs)) / (2 * len(new_longs))
                turnover_short = 1.0 if not shorts else len(set(new_shorts) ^ set(shorts)) / (2 * len(new_shorts))
                turnovers.append((turnover_long, turnover_short))
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

    result = pd.DataFrame(rows)
    mean_turnover_long = float(np.mean([t[0] for t in turnovers])) if turnovers else float("nan")
    mean_turnover_short = float(np.mean([t[1] for t in turnovers])) if turnovers else float("nan")
    return result, mean_turnover_long, mean_turnover_short


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=N_RANDOM_DRAWS,
                         help="Monte Carlo draws per control (default full N_RANDOM_DRAWS=100). "
                              "Lower values are an honestly-disclosed reduced-resolution run, "
                              "e.g. to fit inside a marathon round while the heavy-job-slot is busy "
                              "elsewhere -- not a silent shortcut.")
    parser.add_argument("--skip-fresh-random", action="store_true",
                         help="Skip recomputing the fresh-random (_random_legs) control -- "
                              "its percentile/median vs this same clean universe/VAL/1x setup "
                              "is already on record (TRIALS_LEDGER.md #162: all-cost-multiplier "
                              "median_equity 0.7828/0.7146/0.6522, i.e. net losses).")
    args = parser.parse_args()
    n_draws = args.n_draws

    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US narrower-null diagnostic: f_us_low_vol persistent-random control ===")
    print("Pre-registered verdict thresholds are in this script's module docstring "
          "(written before running).")
    print(f"n_draws={n_draws} (reduced from default {N_RANDOM_DRAWS} if this round's log says so), "
          f"skip_fresh_random={args.skip_fresh_random}\n")

    data = load_clean_sample_with_factors()
    if len(data) < 10:
        print(f"ABORT: only {len(data)} usable names.")
        return None

    market_df, is_spy = _load_market_df()
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    start, end = VAL_PERIOD
    print(f"VAL period {start}..{end}, 1x cost (slippage={SLIPPAGE_1X}bps), {len(data)} names\n")

    # Real strategy
    real_result, real_to_long, real_to_short = run_long_short_us_with_turnover(
        data, calendar, start, end, REBALANCE_DAYS, SLIPPAGE_1X, leg_fn=_decile_legs)
    real_final = real_result["equity"].iloc[-1]
    real_ann = lsb.annualized_return(real_result)
    real_beta = float("nan")
    if not market_df.empty:
        real_beta, _ = lsb.capm_beta(real_result, market_df)
    print(f"REAL decile strategy: final_equity={real_final:.4f}  ann_return={real_ann*100:+.2f}%  "
          f"beta={real_beta:+.3f}  mean_turnover(long/short)={real_to_long:.3f}/{real_to_short:.3f}")

    # Fresh-random control (same mechanism as #162's _random_legs, recomputed here for turnover stats)
    if args.skip_fresh_random:
        fresh_finals = []
        fresh_to_long = [float("nan")]
        fresh_to_short = [float("nan")]
        fresh_pct = float("nan")
        print("\nFRESH-RANDOM control: SKIPPED this run (--skip-fresh-random). "
              "Reference from TRIALS_LEDGER.md #162 (same clean universe/VAL/1x): "
              "median_equity=0.7828 (net loss), real strategy total_return=+1264.82% -> percentile=100.0.")
    else:
        fresh_finals, fresh_to_long, fresh_to_short = [], [], []
        for i in range(n_draws):
            rng = random.Random(RANDOM_CONTROL_SEED + i)
            from functools import partial
            leg_fn = partial(_random_legs, rng=rng)
            rr, tl, ts = run_long_short_us_with_turnover(data, calendar, start, end, REBALANCE_DAYS, SLIPPAGE_1X, leg_fn=leg_fn)
            fresh_finals.append(rr["equity"].iloc[-1])
            fresh_to_long.append(tl)
            fresh_to_short.append(ts)
        fresh_pct = 100.0 * float(np.mean([real_final > f for f in fresh_finals]))
        print(f"\nFRESH-RANDOM control (N={n_draws}, redraws every rebalance -- #162 mechanism, recomputed):"
              f"\n  median_equity={np.median(fresh_finals):.4f}  real_percentile={fresh_pct:.1f}  "
              f"mean_turnover(long/short)={np.mean(fresh_to_long):.3f}/{np.mean(fresh_to_short):.3f}")

    # Persistent-random control (this script's new diagnostic)
    persist_finals, persist_to_long, persist_to_short = [], [], []
    for i in range(n_draws):
        rng = random.Random(RANDOM_CONTROL_SEED + 10_000 + i)
        leg_fn = _persistent_random_legs_factory(rng)
        rr, tl, ts = run_long_short_us_with_turnover(data, calendar, start, end, REBALANCE_DAYS, SLIPPAGE_1X, leg_fn=leg_fn)
        persist_finals.append(rr["equity"].iloc[-1])
        persist_to_long.append(tl)
        persist_to_short.append(ts)
    persist_pct = 100.0 * float(np.mean([real_final > f for f in persist_finals]))
    print(f"\nPERSISTENT-RANDOM control (N={n_draws}, score fixed per stock all period):"
          f"\n  median_equity={np.median(persist_finals):.4f}  real_percentile={persist_pct:.1f}  "
          f"mean_turnover(long/short)={np.mean(persist_to_long):.3f}/{np.mean(persist_to_short):.3f}")

    if persist_pct < 90.0:
        verdict = "CONFIRMED (turnover-matching materially closes the gap)"
    elif persist_pct < 99.0:
        verdict = "PARTIAL (turnover-matching narrows but does not close the gap)"
    else:
        verdict = "REFUTED (turnover-matching makes no material difference)"
    print(f"\n=== VERDICT: {verdict} ===")
    print(f"real_percentile vs fresh-random={fresh_pct:.1f}  vs persistent-random={persist_pct:.1f}")

    out = pd.DataFrame([{
        "period": "VAL", "cost_multiplier": 1,
        "real_final_equity": real_final, "real_ann_return_pct": real_ann * 100, "real_beta": real_beta,
        "real_mean_turnover_long": real_to_long, "real_mean_turnover_short": real_to_short,
        "fresh_random_median_equity": float(np.median(fresh_finals)), "fresh_random_percentile": fresh_pct,
        "fresh_random_mean_turnover_long": float(np.mean(fresh_to_long)), "fresh_random_mean_turnover_short": float(np.mean(fresh_to_short)),
        "persistent_random_median_equity": float(np.median(persist_finals)), "persistent_random_percentile": persist_pct,
        "persistent_random_mean_turnover_long": float(np.mean(persist_to_long)), "persistent_random_mean_turnover_short": float(np.mean(persist_to_short)),
        "verdict": verdict,
    }])
    out.to_csv("data/deep_dive_f_us_low_vol_persistent_random_control.csv", index=False)
    print("\nsaved data/deep_dive_f_us_low_vol_persistent_random_control.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return out


if __name__ == "__main__":
    main()
