"""#52-US cheap gate, first pilot: Item 2.02 8-K filings vs Post-Earnings-
Announcement Drift (HYPOTHESIS_QUEUE.md #52-US, round452 spec, executed this
round per round452's "下一輪US軌接手" instruction). Small-sample pilot only
(large-tier, N=25) -- spec explicitly says start small before spending the
full-tier API budget.

**Everything here follows the round452 spec verbatim, nothing re-decided
after seeing numbers:**
- PIT anchor = `acceptanceDateTime` (not filingDate/reportDate), converted to
  US/Eastern via zoneinfo (handles EDT/EST automatically -- no manual offset
  table, which is how round452's own manual "UTC-4" example would have been
  wrong for an EST-period filing).
- Reaction day: acceptance <16:00 ET on a trading day -> same day; otherwise
  (>=16:00 ET, or a non-trading day) -> next trading day in that ticker's own
  price calendar.
- Item family: any 8-K whose comma-separated `items` field contains "2.02"
  (multi-item filings included, per spec's explicit "9.01 alongside 2.02 is
  the common case, excluding it would drop most real earnings events").
- r0 = reaction-day return (close/prev_close - 1). r_drift = cumulative
  return from reaction_day+1 through reaction_day+5 (one week), i.e.
  close[+5]/close[+1] - 1. Direction pre-registered as *continuation*
  (PEAD): same_sign(r0, r_drift) is the metric, not reversal.
- No market/industry adjustment (US_MARATHON_STATE.md's known gap, spec
  says raw returns are fine for this stage).
- Holdout: `us_price_series()` -> `load_dev()` is already VAL_END-capped, so
  any reaction day needing price data past 2024-12-31 for r_drift simply
  can't be computed (IndexError guarded, silently out of range -- not a
  holdout leak, holdout was never loaded in the first place).

**One implementation choice NOT in the spec text** (spec only pins r0/r_drift
windows, not the control-sampling exclusion buffer): control days are drawn
from each ticker's own eligible trading-day pool, excluding any day within
+/-10 trading days of *any* real event reaction day for that ticker (avoids
a control draw accidentally landing inside a real drift window and silently
inheriting the same signal). This buffer only affects which days are
*eligible to be picked as noise*, not the sign convention or which events
count as signal -- it cannot manufacture the PASS/FAIL direction, so it does
not count as a post-hoc selection choice under CONSTITUTION's "selection
must be pre-bound" rule, but is disclosed here per that same honesty norm.

Control: `control_group_standard.evaluate_vs_control()`, two independent
random-seed variants (MIN_CONTROL_VARIANTS=2), 100 draws each. Each draw
resamples one control day per real event from that event's own ticker pool
(paired by ticker, same event count as the real set) and computes the same
same-sign proportion metric -- directly comparable to the real proportion.

TRAIN/VAL split by `validation.holdout` (TRAIN_END=2020-12-31,
VAL_END=2024-12-31), matching the pipeline-wide convention (same as
`fut_settlement_event_gate60.py` this same session).
"""
from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from control_group_standard import evaluate_vs_control
from sec_edgar_client import get_cik, get_8k_events
from us_factors import us_price_series
from us_universe import universe as build_us_universe
from validation import holdout

TIER = "large"
SAMPLE_SIZE = 25
SAMPLE_SEED = 20260908_52  # distinct from every prior US-track seed on purpose (round convention)
DRIFT_DAYS = 5
CONTROL_EXCLUSION_BUFFER = 10  # trading days either side of a real event, see module docstring
N_CONTROL_DRAWS = 100
CONTROL_SEEDS = {"seed_a": 20260908_521, "seed_b": 20260908_522}

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def large_tier_ids() -> list[str]:
    u = build_us_universe()
    active = u[u["status"] == "active"].copy()
    active["market_cap"] = pd.to_numeric(active["market_cap"], errors="coerce")
    active = active.dropna(subset=["market_cap"])
    active = active[active["market_cap"] > 0]
    tier_labels = pd.qcut(active["market_cap"], q=3, labels=["small", "mid", "large"])
    tiered = active.assign(tier=tier_labels)
    return tiered[tiered["tier"] == TIER]["stock_id"].tolist()


def sample_ids(n: int, seed: int) -> list[str]:
    ids = large_tier_ids()
    rng = random.Random(seed)
    return rng.sample(ids, min(n, len(ids)))


def reaction_day_index(accept_dt_raw: str, calendar: list[str]) -> int | None:
    """calendar: sorted list of 'YYYY-MM-DD' strings (this ticker's own trading
    days). Returns the index into calendar of the reaction day, or None if
    the acceptance timestamp is unparseable or falls entirely after the
    ticker's last available trading day (no next trading day to assign).
    """
    if not accept_dt_raw:
        return None
    try:
        dt_utc = pd.Timestamp(accept_dt_raw).tz_localize(UTC) if pd.Timestamp(accept_dt_raw).tzinfo is None \
            else pd.Timestamp(accept_dt_raw)
        dt_et = dt_utc.tz_convert(ET)
    except (ValueError, TypeError):
        return None
    anchor = dt_et.strftime("%Y-%m-%d")
    before_close = dt_et.hour < 16
    if before_close and anchor in calendar:
        target = anchor
    else:
        later = [d for d in calendar if d > anchor]
        if not later:
            return None
        target = later[0]
    return calendar.index(target)


@dataclass
class EventRow:
    ticker: str
    reaction_date: str
    period: str  # TRAIN / VAL / OUT_OF_RANGE
    r0: float
    r_drift: float
    same_sign: bool


def period_of(date_str: str) -> str:
    if date_str <= holdout.TRAIN_END:
        return "TRAIN"
    if date_str <= holdout.VAL_END:
        return "VAL"
    return "OUT_OF_RANGE"


def process_ticker(ticker: str) -> tuple[list[EventRow], list[int], list[str], dict]:
    """Returns (event_rows, eligible_control_indices, calendar, skip_reasons)."""
    skips: dict = {}
    cik = get_cik(ticker)
    if cik is None:
        skips["no_cik"] = 1
        return [], [], [], skips
    px = us_price_series(ticker)
    if px.empty or len(px) < 30:
        skips["no_price_history"] = 1
        return [], [], [], skips
    calendar = px["date"].tolist()
    closes = px["adj_close"].tolist()
    n = len(calendar)

    events = get_8k_events(cik, full_history=True)
    item_events = [e for e in events if e.get("items") and "2.02" in e["items"].split(",")]

    rows: list[EventRow] = []
    seen_reaction_idx: set[int] = set()
    skipped_oob = 0
    skipped_tie = 0
    for e in item_events:
        idx = reaction_day_index(e.get("acceptanceDateTime"), calendar)
        if idx is None or idx in seen_reaction_idx:
            continue
        if idx < 1 or idx + DRIFT_DAYS >= n:
            skipped_oob += 1
            continue
        r0 = closes[idx] / closes[idx - 1] - 1.0
        r_drift = closes[idx + DRIFT_DAYS] / closes[idx + 1] - 1.0
        if r0 == 0.0:
            skipped_tie += 1
            continue
        seen_reaction_idx.add(idx)
        rows.append(EventRow(
            ticker=ticker, reaction_date=calendar[idx], period=period_of(calendar[idx]),
            r0=r0, r_drift=r_drift, same_sign=(r0 > 0) == (r_drift > 0),
        ))
    if skipped_oob:
        skips["out_of_range_for_drift_window"] = skipped_oob
    if skipped_tie:
        skips["r0_exactly_zero"] = skipped_tie

    excluded = set()
    for idx in seen_reaction_idx:
        for off in range(-CONTROL_EXCLUSION_BUFFER, CONTROL_EXCLUSION_BUFFER + 1):
            excluded.add(idx + off)
    eligible = [i for i in range(1, n - DRIFT_DAYS) if i not in excluded]
    return rows, eligible, calendar, skips


def draw_control_proportion(events: list[EventRow], pools: dict[str, list[int]],
                             closes_by_ticker: dict[str, list[float]], rng: random.Random) -> float:
    same = 0
    total = 0
    for ev in events:
        pool = pools.get(ev.ticker)
        if not pool:
            continue
        idx = rng.choice(pool)
        closes = closes_by_ticker[ev.ticker]
        r0 = closes[idx] / closes[idx - 1] - 1.0
        r_drift = closes[idx + DRIFT_DAYS] / closes[idx + 1] - 1.0
        if r0 == 0.0:
            continue
        total += 1
        if (r0 > 0) == (r_drift > 0):
            same += 1
    return same / total if total else float("nan")


def main() -> int:
    if holdout.is_holdout_consumed():
        print("ABORT: holdout already consumed, refusing to run")
        return 1

    tickers = sample_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== #52-US cheap gate pilot: Item 2.02 8-K PEAD, tier={TIER}, "
          f"N={len(tickers)} (seed={SAMPLE_SEED}) ===")
    print(f"tickers: {tickers}")

    all_events: list[EventRow] = []
    pools: dict[str, list[int]] = {}
    closes_by_ticker: dict[str, list[float]] = {}
    skip_summary: dict = {}
    usable = 0
    for t in tickers:
        rows, eligible, calendar, skips = process_ticker(t)
        for k, v in skips.items():
            skip_summary[k] = skip_summary.get(k, 0) + v
        if rows or eligible:
            usable += 1
        all_events.extend(rows)
        if eligible:
            px = us_price_series(t)
            pools[t] = eligible
            closes_by_ticker[t] = px["adj_close"].tolist()
        print(f"  {t}: {len(rows)} usable 2.02 events, {len(eligible)} eligible control days"
              + (f", skips={skips}" if skips else ""))

    print(f"\n{usable}/{len(tickers)} tickers usable, {len(all_events)} total 2.02 events")
    print(f"skip reasons across all tickers: {skip_summary}")

    for period in ("TRAIN", "VAL"):
        period_events = [e for e in all_events if e.period == period]
        n_ev = len(period_events)
        print(f"\n--- {period} ({holdout.TRAIN_END if period == 'TRAIN' else holdout.VAL_END} cutoff) ---")
        print(f"n_events={n_ev}")
        if n_ev < 10:
            print(f"SKIP: fewer than 10 usable events in {period}, too small for a meaningful cheap gate")
            continue
        same_sign_n = sum(1 for e in period_events if e.same_sign)
        signal_stat = same_sign_n / n_ev
        print(f"real same-sign(r0,r_drift) proportion = {signal_stat:.4f} ({same_sign_n}/{n_ev})")

        control_draws = {}
        for name, seed in CONTROL_SEEDS.items():
            rng = random.Random(seed)
            draws = [draw_control_proportion(period_events, pools, closes_by_ticker, rng)
                     for _ in range(N_CONTROL_DRAWS)]
            draws = [d for d in draws if d == d]  # drop nan (all-skip draws, should be rare)
            control_draws[name] = draws
            print(f"  control[{name}]: n_draws={len(draws)} mean={sum(draws)/len(draws):.4f} "
                  f"max={max(draws):.4f}")

        verdict = evaluate_vs_control(
            signal_stat=signal_stat,
            control_draws=control_draws,
            selection_spec=(
                f"事前綁定：#52-US round452規格，唯一測項Item 2.02，繼續性方向（PEAD），"
                f"{period}期same-sign(r0,r_drift)比例，tier={TIER} N={SAMPLE_SIZE} seed={SAMPLE_SEED}，"
                "此為該假說第一次也是唯一一次cheap gate執行，無多格選點"
            ),
        )
        print(f"  PASSES cheap gate: {verdict.passed}")
        print(f"  {verdict.reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
