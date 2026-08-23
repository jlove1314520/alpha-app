"""Market-neutral long-short evaluation of score.py's composite factor.

Cowork audit, 2026-08-24: the previous long-only top-10 backtest
(run_score_backtest.py, score_topn_v1) proved the factor beats a
mechanically-matched random control (real signal), but that's a different
question from "is this a usable strategy" -- a long-only concentrated
portfolio's absolute return is dominated by market beta, and it lost to a
passive buy&hold of the same names. Comparing a stock-picking factor
against buy&hold conflates the factor's own alpha with general market
direction, and the buy&hold benchmark itself inherited the 80-name
sample's selection bias.

**The orthodox fix, implemented here**: go long the top decile by
composite score, short the bottom decile, equal-weight within each leg.
The long-short SPREAD return isolates the factor's cross-sectional
predictive power from market direction almost by construction (both legs
move with the market; only the spread reflects which stocks the factor
correctly ranked relative to each other). Two things are then measured
directly instead of assumed:
  1. The spread's CAPM beta against TAIEX (regression, not an assumption
     -- market-neutral construction does not guarantee beta==0, e.g. if
     the long leg happens to be structurally higher-beta than the short
     leg, see f_low_vol's presence in the composite).
  2. The spread's annualized return / Sortino net of BOTH legs' real
     costs (long side: validation/costs.py's existing buy/sell legs;
     short side: the new short_round_trip_cost_pct(), including a
     placeholder borrow fee -- see that function's docstring for what
     is and isn't modeled).

The random control here is a matched long-short control (same rebalance
cadence, same decile sizes, random stock picks for both legs instead of
score-based) -- NOT a comparison against buy&hold, which is not a
meaningful yardstick for a market-neutral construction (buy&hold has
large market beta by definition; a long-short strategy is being judged on
whether it has alpha BEYOND beta, not on beating a directional bet).

**Universe**: run against universe.py's full unbiased market (or as large
a slice of it as FinMind's rate limits allow within one session --
disclosed honestly, not silently narrowed), not the 80/100-name sample
used for factor IC testing. This also removes the survivorship/selection
bias that a buy&hold-of-the-sample benchmark would have carried.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factors import prepare_score_factors
from finmind_client import load_dev
from score import compute_scores_at_date, eligible_for_ranking, load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe
from validation import costs as costmod
from validation import holdout

DECILE_FRACTION = 0.10
START_DATE = "2010-01-01"
REBALANCE_CADENCES = {"weekly": 5, "monthly": 21}  # approx trading days between rebalances
COMMISSION_DISCOUNT = 1.0
SLIPPAGE_BPS = costmod.DEFAULT_SLIPPAGE_BPS
MAX_PLAUSIBLE_DAILY_RETURN = 0.20  # TW's real daily circuit breaker is +-10%; this filter uses a buffer
# above that (not a tight 10% cutoff) rather than reject every limit-day move, while still catching the
# much larger artificial jumps caused by unhandled capital-reduction events (adjust.py's known gap) or
# other data anomalies. See leg_return()'s inline comment for the concrete bug this was found fixing.
N_RANDOM_DRAWS = 40  # smaller than the 60 used for the long-only version -- each draw here is a full
# long-short daily walk over the (potentially much larger) universe; disclosed as a smaller budget,
# not a hidden shortcut.
RANDOM_CONTROL_SEED = 20260824


def load_universe_with_factors(
    stock_ids: list[str], market_df: pd.DataFrame, max_names: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Same pattern as factor_ic.py's load_sample_with_factors(), but built
    for a much larger (potentially full-market) name list: skips failures
    per-name without aborting the whole run, and everything routes through
    the same load_dev()/pit.py machinery so nothing here can leak holdout.
    `max_names` caps how many names to attempt (for a bounded test run);
    None means attempt the whole list.
    """
    out = {}
    ids = stock_ids if max_names is None else stock_ids[:max_names]
    n_rate_limited = 0
    for i, sid in enumerate(ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001
            if any(tok in str(e) for tok in ("402", "403", "upper limit", "ip banned")):
                n_rate_limited += 1
            continue
        if px.empty or len(px) < 260:
            continue
        try:
            d = prepare_score_factors(sid, px, START_DATE)  # lean fetch -- only the 4 columns
            # score.py's composite reads, not the full 12-factor set (see factors.py's
            # prepare_score_factors() docstring for why this matters at full-universe scale)
        except Exception as e:  # noqa: BLE001
            if any(tok in str(e) for tok in ("402", "403", "upper limit", "ip banned")):
                n_rate_limited += 1
            continue
        out[sid] = d
        if (i + 1) % 100 == 0:
            print(f"  ... {i+1}/{len(ids)} attempted, {len(out)} usable, {n_rate_limited} rate-limited so far")
    print(f"  done: {len(out)}/{len(ids)} usable ({n_rate_limited} hit rate limits)")
    return out


def _decile_legs(as_of: str, data: dict[str, pd.DataFrame], industry_map: dict) -> tuple[list[str], list[str]]:
    cs = eligible_for_ranking(compute_scores_at_date(as_of, data, industry_map))
    n = len(cs)
    if n < 10:
        return [], []
    k = max(1, int(round(n * DECILE_FRACTION)))
    longs = cs.head(k)["stock_id"].tolist()
    shorts = cs.tail(k)["stock_id"].tolist()
    return longs, shorts


def _random_legs(as_of: str, data: dict[str, pd.DataFrame], industry_map: dict, rng: random.Random) -> tuple[list[str], list[str]]:
    cs = eligible_for_ranking(compute_scores_at_date(as_of, data, industry_map))
    pool = cs["stock_id"].tolist()
    n = len(pool)
    if n < 10:
        return [], []
    k = max(1, int(round(n * DECILE_FRACTION)))
    if n < 2 * k:
        return [], []
    picks = rng.sample(pool, 2 * k)
    return picks[:k], picks[k:]


def run_long_short(
    data: dict[str, pd.DataFrame], market_df: pd.DataFrame, industry_map: dict,
    start: str, end: str, rebalance_days: int, leg_fn=_decile_legs,
) -> pd.DataFrame:
    """Daily-compounding long-short spread return series.
    leg_fn(as_of, data, industry_map) -> (long_ids, short_ids); swap in
    _random_legs (via functools.partial) for the matched random control.
    Returns a DataFrame: date, spread_return (net of costs), equity.
    """
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    calendar = sorted(d for d in market_df["date"] if start <= d <= end)
    if not calendar:
        raise ValueError("empty calendar for the given date range")

    longs, shorts = [], []
    rows = []
    equity = 1.0
    for i, day in enumerate(calendar):
        if i % rebalance_days == 0:
            new_longs, new_shorts = leg_fn(day, data, industry_map)
            if new_longs and new_shorts:
                turnover_long = 1.0 if not longs else len(set(new_longs) ^ set(longs)) / (2 * len(new_longs))
                turnover_short = 1.0 if not shorts else len(set(new_shorts) ^ set(shorts)) / (2 * len(new_shorts))
                holding_days = rebalance_days  # approx trading days until next rebalance
                long_cost = turnover_long * costmod.round_trip_cost_pct(slippage_bps=SLIPPAGE_BPS, commission_discount=COMMISSION_DISCOUNT)
                short_cost = turnover_short * costmod.short_round_trip_cost_pct(holding_days, slippage_bps=SLIPPAGE_BPS, commission_discount=COMMISSION_DISCOUNT)
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
                    if abs(r) > MAX_PLAUSIBLE_DAILY_RETURN:
                        # A real bug found via smoke testing: with only ~8 names/leg (10% of an 80-name
                        # sample), a single bad data point dominates the equal-weight average. TW's actual
                        # daily circuit breaker is +-10%; adjust.py does NOT yet handle capital reductions
                        # (known gap, see STRATEGY_LOG.md), which cause a real one-day price reset far
                        # outside +-10% that has nothing to do with an actual trading gain/loss. Rather than
                        # silently include it and let one stock's data artifact dominate an 8-name average
                        # (observed: >500,000% "returns" from exactly this), drop that stock's observation
                        # for this one day -- treated as missing data, not as a real return.
                        continue
                    rets.append(r)
            return float(np.mean(rets)) if rets else 0.0

        r_long = leg_return(longs)
        r_short = leg_return(shorts)
        spread = r_long - r_short
        equity *= (1 + spread)
        rows.append({"date": day, "spread_return": spread, "equity": equity})

    return pd.DataFrame(rows)


def annualized_return(result: pd.DataFrame) -> float:
    n_days = len(result)
    if n_days < 2:
        return float("nan")
    total_return = result["equity"].iloc[-1] / result["equity"].iloc[0] - 1
    years = n_days / 252.0
    return (1 + total_return) ** (1 / years) - 1 if years > 0 else float("nan")


def sortino_ratio(result: pd.DataFrame) -> float:
    """Same net-of-cost-returns rationale as capm_beta() -- computed from
    equity.pct_change(), not the gross `spread_return` column."""
    rets = result["equity"].pct_change().iloc[1:]
    if len(rets) < 2:
        return float("nan")
    downside = rets[rets < 0]
    downside_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
    if downside_dev == 0:
        return float("nan")
    return float(rets.mean() / downside_dev * np.sqrt(252))


def capm_beta(result: pd.DataFrame, market_df: pd.DataFrame) -> tuple[float, float]:
    """(beta, alpha_annualized) of the spread's daily returns regressed on
    TAIEX's daily returns over the same dates. This is the actual audit of
    "is this market-neutral", not an assumption -- a long-short construction
    is not guaranteed beta==0 just by being long-short.

    Regresses net-of-cost daily returns (equity.pct_change()), NOT the raw
    `spread_return` column -- that column only holds the gross leg spread
    for each day, while rebalance-day cost drag is applied directly to
    `equity` and never written back into `spread_return`. Regressing on the
    gross column would make alpha inconsistent with annualized_return()'s
    net-of-cost total return (found via a smoke-test mismatch: alpha showed
    +20% while the actual net annualized return was +1.35% on the same run).
    """
    mkt = market_df.set_index("date")["close"].sort_index()  # TAIEX is an index, not a stock -- it has no
    # dividends/splits to adjust for, so prepare_market_data() (strategies/weinstein_stage2.py) never adds
    # an adj_close column, only "close". Found via a real KeyError in smoke testing.
    mkt_ret = mkt.pct_change()
    net_ret = result.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return float("nan"), float("nan")
    x = merged["mkt_return"].values
    y = merged["net_return"].values
    beta, alpha_daily = np.polyfit(x, y, 1)
    alpha_annualized = (1 + alpha_daily) ** 252 - 1
    return float(beta), float(alpha_annualized)


def run_period(label: str, data, market_df, industry_map, start: str, end: str, cadence_name: str, rebalance_days: int):
    print(f"\n=== {label} ({cadence_name} rebalance, every {rebalance_days} trading days): {start}..{end} ===")
    result = run_long_short(data, market_df, industry_map, start, end, rebalance_days, leg_fn=_decile_legs)
    ann_ret = annualized_return(result)
    sortino = sortino_ratio(result)
    beta, alpha_ann = capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100
    print(f"  Total spread return (net of costs): {total_ret_pct:+.2f}%  Annualized: {ann_ret*100:+.2f}%  Sortino: {sortino:.3f}")
    print(f"  CAPM beta vs TAIEX: {beta:+.3f}  Annualized alpha: {alpha_ann*100:+.2f}%")

    print(f"  Random long-short control ({N_RANDOM_DRAWS} draws, same cadence/decile size/cost model)...")
    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rr = run_long_short(data, market_df, industry_map, start, end, rebalance_days,
                             leg_fn=lambda as_of, d, im, _rng=rng: _random_legs(as_of, d, im, _rng))
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    print(f"  Real final equity {real_final:.4f} vs random control median {np.median(random_finals):.4f} -- percentile {percentile:.1f}")

    return {
        "label": label, "cadence": cadence_name, "start": start, "end": end,
        "total_return_pct": total_ret_pct, "annualized_return_pct": ann_ret * 100,
        "sortino": sortino, "beta": beta, "annualized_alpha_pct": alpha_ann * 100,
        "random_control_percentile": percentile, "n_dates": len(result),
    }


def main(max_names: int | None = None):
    u = build_universe()
    stock_ids = u["stock_id"].tolist()
    rng = random.Random(20260824)
    rng.shuffle(stock_ids)  # random order so a partial/capped run isn't systematically biased toward
    # any particular part of the universe (e.g. alphabetical/numeric ordering effects)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in long_short_backtest")
    market_df = prepare_market_data(market_raw)

    print(f"Universe: {len(stock_ids)} names total" + (f", attempting first {max_names}" if max_names else ", attempting ALL"))
    data = load_universe_with_factors(stock_ids, market_df, max_names=max_names)

    industry_map = load_industry_map()

    results = []
    for cadence_name, rebalance_days in REBALANCE_CADENCES.items():
        train = run_period(f"TRAIN ({cadence_name})", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END, cadence_name, rebalance_days)
        val = run_period(f"VALIDATION ({cadence_name})", data, market_df, industry_map, "2021-01-01", holdout.VAL_END, cadence_name, rebalance_days)
        results.extend([train, val])

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['label']}: ann_return={r['annualized_return_pct']:+.2f}%  beta={r['beta']:+.3f}  "
              f"alpha={r['annualized_alpha_pct']:+.2f}%  Sortino={r['sortino']:.3f}  "
              f"random_control_pct={r['random_control_percentile']:.1f}")

    pd.DataFrame(results).to_csv("data/long_short_results.csv", index=False)
    print(f"\nUniverse coverage: {len(data)}/{len(stock_ids)} names usable")
    print("saved data/long_short_results.csv")
    return results, len(data), len(stock_ids)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-names", type=int, default=None)
    args = parser.parse_args()
    main(max_names=args.max_names)
