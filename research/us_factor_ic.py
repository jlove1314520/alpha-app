"""US-track cheap-gate IC test -- f_us_low_vol (round 82, FAIL on deep-dive,
see US_LEADS.md #1), f_us_momentum_12m (round 88, FAIL on cheap gate, see
US_LEADS.md #2), and f_us_reversal_1m (2026-08-26 marathon round, third
factor, this round's 1a test).

**Why this exists:** per US_MARATHON_STATE.md's "下一步" (round 79's writeup),
`us_factors.py` had a first factor (`f_us_low_vol`) but no IC-test pipeline to
run it against -- round 79 was infra only (protocol section 1c), round 82 was
the first actual protocol-1a cheap gate for the US track. This module is
generic over `US_FACTOR_COLUMNS` (loops the whole list, see `main()`), so
adding `f_us_momentum_12m` to that list in `us_factors.py` and rerunning this
script unchanged is this round's 1a test -- no fork needed.

**Reuses `evaluate_factor()`/`build_snapshots()` from `factor_ic.py` as-is**
(imported, not copy-pasted) -- both functions are already generic over any
`{sid: DataFrame}` dict with `date`/`adj_close`/<factor_col> columns and a
trading-day calendar list, which is exactly what `us_factors.py`'s
`us_price_series()` + `prepare_us_factors()` output already looks like. No
US-specific fork of the IC math itself; only the sample-loading and calendar
construction are US-specific (see below for why those two pieces can't be
shared with the TW version).

**Sample loading (`load_us_sample_with_factors`)**: mirrors TW's
`load_sample_with_factors()` in spirit, but built directly from
`us_factors.us_price_series()`/`prepare_us_factors()` (not
`adjust.py`/`factors.py`, which are TW-only and pull from a TAIEX-anchored
market_df this track doesn't have). Same `len(px) < 260` guard (need >=~1yr
of trading days before the 60-day rolling window ever produces a non-NaN
value at all).

**Calendar**: TW's `factor_ic.py` uses TAIEX's own date column as the trading
calendar (a market-wide index all TW stocks in the sample can be reindexed
against). This track has no equivalent broad-market series computed yet, so
this uses AAPL's own date column as a calendar proxy instead -- AAPL has
continuous 1990-2024 NYSE/Nasdaq-session coverage in the existing cache
(see us_factors.py's smoke test), which is a reasonable stand-in for "which
days did US equity markets trade" for this first pass. Flagged here as a
simplification: a name with an actual trading halt on a day AAPL traded
would just be silently absent from that day's cross-section (same failure
mode `_cross_section()` already handles via its `len(idx)==0` skip), not a
crash, so this is a coverage-quality caveat, not a correctness bug.

**Sample size / API-quota discipline**: per MARATHON_PROTOCOL.md section 1a
("只用小樣本快篩...不要為了一個可能沒用的假說去衝新的 API 額度"), this
first pass targets a modest random sample and stops early (not endless
retries) the moment a fetch raises what looks like a 402/quota-exhausted
error -- see `load_us_sample_with_factors()`'s loop. Whatever sample size
was actually reached by the time that happens is what gets tested; this
script does not treat "the intended sample size wasn't reached" as a reason
to abort the whole run, only as a caveat to report alongside the result (a
smaller-than-intended sample produces a wider, less certain result --  that
is a legitimate finding to record, not a failure to hide).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from factor_ic import build_snapshots, evaluate_factor
from us_factors import US_FACTOR_COLUMNS, prepare_us_factors, us_price_series
from us_universe import universe as build_us_universe
from validation import holdout

SAMPLE_SIZE = 40
SAMPLE_SEED = 20260826  # today's date as seed, distinct from TW's factor_ic.SAMPLE_SEED (20260822)
                         # on purpose -- no reason these two tracks' samples need the same seed,
                         # and reusing the exact same literal risked looking like an (unintentional)
                         # claim of cross-track comparability this round never validated.
START_DATE = "1990-01-01"  # matches us_factors.py's smoke-test start_date; USStockPrice
                            # already returns split/dividend-adjusted Adj_Close from IPO,
                            # no reason to narrow this the way TW's factor_ic.py does (TW
                            # narrows to 2010-01-01, a TW-specific choice unrelated to this track)
SNAPSHOT_START = "2015-01-01"  # same snapshot window TW's factor_ic.py uses, kept identical on
                                 # purpose so a later side-by-side TW-vs-US comparison isn't
                                 # confounded by a different window choice
QUOTA_ERROR_MARKERS = ("402", "429", "ip banned", "ip_banned")  # substrings _fetch()'s
    # RuntimeError text would contain for a quota/rate-limit rejection specifically, as opposed
    # to some other 4xx (e.g. a genuinely bad ticker). **2026-08-26 round finding**: this
    # started as just ("402", "429") but this round's actual live failure mode was HTTP 403
    # with body {"msg":"ip banned","status":403,"retry_after":<seconds>} -- a harder block than
    # plain rate-limiting (a temporary IP-level ban, not just "you've used your quota"), and the
    # original marker list didn't catch it, so the very first call's error fell through to the
    # generic "price ERROR, dropping" branch instead of stopping the loop -- the script then
    # burned all 40 sample slots hitting the same ban 40 times before exiting empty-handed
    # (see US_LOG.md this round's entry). Added "403"-adjacent text markers here so a future
    # run recognizes this exact failure shape on the very first hit and stops immediately.


def sample_us_universe_ids(sample_size: int, seed: int = SAMPLE_SEED) -> list[str]:
    u = build_us_universe()
    rng = random.Random(seed)
    return rng.sample(list(u["stock_id"]), sample_size)


def load_us_sample_with_factors(sample_ids: list[str]) -> tuple[dict[str, pd.DataFrame], bool, str | None]:
    """Returns (data, quota_hit, quota_hit_ticker). `quota_hit` is True if the
    loop stopped early because a fetch looked like a 402/429 -- see module
    docstring. Everything successfully loaded before that point is still
    returned in `data`, not discarded.
    """
    out: dict[str, pd.DataFrame] = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = us_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- same tolerance as factor_ic.py's TW version
            msg = str(e)
            if any(marker in msg for marker in QUOTA_ERROR_MARKERS):
                print(f"  [{i+1}/{len(sample_ids)}] {sid}: looks like a quota/rate-limit error "
                      f"({msg[:200]}) -- stopping the sample-load loop here, per protocol section 4")
                return out, True, sid
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({msg[:200]}), dropping")
            continue
        if px.empty:
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: EMPTY (delisted-and-gone or no data), dropping")
            continue
        if len(px) < 260:
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: only {len(px)} rows (<260), dropping")
            continue
        d = prepare_us_factors(px)
        out[sid] = d
        print(f"  [{i+1}/{len(sample_ids)}] {sid}: OK ({len(d)} rows, {d['date'].min()}..{d['date'].max()})")
    return out, False, None


def main():
    sample_ids = sample_us_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== US track cheap-gate IC test ===")
    print(f"Sample target: {len(sample_ids)} names (seed={SAMPLE_SEED}), snapshot window "
          f"{SNAPSHOT_START}..{holdout.VAL_END}")

    data, quota_hit, quota_hit_ticker = load_us_sample_with_factors(sample_ids)
    print(f"\n{len(data)}/{len(sample_ids)} usable names loaded"
          + (f" (stopped early at {quota_hit_ticker} -- quota/rate-limit)" if quota_hit else ""))

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the evaluate_factor() minimum "
              f"cross-section size of 10 -- cannot run a meaningful IC test with this sample. "
              f"Not writing a CHEAP_PASS/FAIL verdict, this is an infra/data-availability finding, "
              f"not a factor result.")
        return None

    calendar_ref = data.get("AAPL")
    if calendar_ref is None or calendar_ref.empty:
        # AAPL wasn't in this random sample (or its cache came back empty for
        # some reason) -- load it directly as the calendar source only,
        # separate from whether it's also in the tested cross-sections.
        aapl_px = us_price_series("AAPL", START_DATE)
        if aapl_px.empty:
            print("\nABORT: AAPL price history unavailable even as a calendar-only load -- "
                  "cannot build a trading calendar for this run.")
            return None
        calendar = sorted(aapl_px["date"].tolist())
    else:
        calendar = sorted(calendar_ref["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    # Only test factors that don't already have a recorded verdict. f_us_low_vol
    # went through cheap gate (round 82, CHEAP_PASS) + deep-dive (FAIL, see
    # US_LEADS.md #1 / TRIALS_LEDGER.md #41); f_us_momentum_12m went through cheap
    # gate (round 88, FAIL, same_sign train/val mismatch, see US_LEADS.md #2 /
    # TRIALS_LEDGER.md #42) -- rerunning either here would burn API quota
    # re-fetching prices with zero new information (both verdicts are already
    # final), and would incorrectly conflate this round's single-new-factor
    # bonferroni_n=1 batch with a multi-factor batch it isn't. Only
    # f_us_reversal_1m is new this round (2026-08-26, third factor).
    ALREADY_VERDICTED = {"f_us_low_vol", "f_us_momentum_12m"}
    columns_to_test = [c for c in US_FACTOR_COLUMNS if c not in ALREADY_VERDICTED]

    results = []
    for col in columns_to_test:
        print(f"\nEvaluating {col}...")
        r = evaluate_factor(col, data, snapshots, bonferroni_n=1)  # bonferroni_n=1: genuinely
        # standalone single-new-factor test this round (columns_to_test has exactly one entry
        # -- f_us_momentum_12m) -- per factor_ic.py's own docstring, only pass a real count
        # for an actual multi-factor batch of *new, unverdicted* factors
        results.append(r)
        print(f"  train: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
        print(f"  val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
        print(f"  null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
        print(f"  PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))

    print(f"\n=== SUMMARY (sample n={len(data)}"
          + (", quota-truncated" if quota_hit else "") + ") ===")
    for r in results:
        print(f"  {r.factor}: {'CHEAP_PASS' if r.passes else 'FAIL'}  val_ic={r.val_mean_ic:+.4f}  "
              f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return results


if __name__ == "__main__":
    main()
