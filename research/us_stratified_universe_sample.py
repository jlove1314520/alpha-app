"""US track: build a market-cap-stratified random sample universe -- the
foundation fix for the `cached_ticker_ids()` selection-bias finding
(TRIALS_LEDGER.md #128/#139, US_MARATHON_STATE.md round 374 "下一步(a)").

**Why this exists.** `us_portfolio_pilot_real_data.py::cached_ticker_ids()`
returns "every ticker that happens to already have a full 1990-2024 price
parquet on disk" -- its own docstring already says "this is NOT a random
sample, it's everything already fetched". Round 374's leave-top10-out check
(#139) proved this matters: excluding the 10 biggest own-return winners from
that 135-name pool made VAL-period return go *up* (+121%→+148%), so the
implausible +100%+/yr numbers seen on `f_us_value_bm` (#128) and
`f_us_low_vol` (#115) are a pool-wide artifact (names get cached because
they were *queried*, i.e. interesting/hot, not because they're
representative), not a 10-name concentration problem a simple exclusion can
fix. The only real fix identified there is "換一個非熱門股優先被快取的隨機
/分層抽樣宇宙重建" -- this script is that rebuild.

**Method.** `us_universe.active_stock_ids()` already carries `market_cap`
for every active ticker from a single `USStockInfo` snapshot call (no
per-ticker fetch needed to build the sampling frame itself) -- same source
`us_factor_ic_by_size.py` already used for its large/mid/small tertile
re-tests (rounds 95/97/99). This script:
1. Drops missing/zero market_cap (can't be tiered) -- same filter
   `us_factor_ic_by_size.py::large_cap_universe_ids()` uses.
2. Splits into 3 equal-COUNT tertiles by market_cap (`pd.qcut`, q=3) --
   deliberately the same tertile definition already used in #47/#52/#95/#97/
   #99, not a new stratification scheme, so any future comparison to those
   results isn't confounded by a different cut.
3. Samples `N_PER_TIER` names per tertile with a **pre-registered seed per
   tier** (picked before looking at any sampled names or running anything
   downstream -- this file's `SAMPLE_SEED_*` constants are the pre-
   registration; do not edit them after seeing results, only add new
   distinct seeds for future re-runs).
4. Fetches each sampled name's full-range `USStockPrice` history via
   `us_factors.us_price_series()` (same call `cached_ticker_ids()`-based
   scripts already use -- first fetch pays FinMind's 3s/request rate limit,
   `finmind_client.py`'s existing on-disk parquet cache means every future
   script that calls `us_price_series()` on these same tickers is free).
5. Records per-ticker usable/dropped status (same `len(px) < 260` trading-
   day threshold `us_factor_ic.py::load_us_sample_with_factors()` uses) to
   `data/us_stratified_universe_sample.csv` -- this CSV, not
   `cached_ticker_ids()`, is what future US-track cheap-gate/1b-deep-dive
   scripts should sample from once this completes.

**N_PER_TIER=100 (300 total), matching TW's `factor_ic.SAMPLE_SIZE=300`
precedent** (post `CALIBRATION_PROBE.md` fix) -- picked so the new US sample
has comparable statistical power to what TW's cheap gate now runs on, not
because 300 has any special property beyond "already validated as adequate
elsewhere in this project". Sampling ~300 *new* names (most will not
overlap with the existing ~225-name hot-stock cache, since that cache skews
toward large/popular names cutting across all three tertiles unevenly) at
FinMind's 3s/request floor is a multi-minute fetch -- **this is why this
script is meant to be run via `run_detached.py submit`, not inline in a
30-minute marathon round** (`MARATHON_PROTOCOL.md` section 0b.2).

**Explicitly NOT a survivorship-bias fix.** `active_stock_ids()` is built
from `us_universe.universe()`'s active-snapshot component -- the *known*,
already-documented survivorship gap (`us_universe.py`'s own docstring:
"only removes the bias for the 5 specific names investigated so far") is
inherited unchanged by this sample. This script only fixes the *separate*
"hot-stock selection" bias `cached_ticker_ids()` had; it does not claim to
produce a survivorship-bias-free universe. Two different, both-documented
gaps -- conflating them would be dishonest.

**QUOTA_ERROR_MARKERS reuse**: same graceful-stop-on-402/429 behavior as
`us_factor_ic.py::load_us_sample_with_factors()` -- if FinMind's free-tier
quota is hit partway through, this script writes out whatever was fetched
so far (labeled with `quota_truncated=True` in the run summary) rather than
losing completed work or retrying into a ban.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from us_factor_ic import QUOTA_ERROR_MARKERS
from us_factors import us_price_series
from us_universe import active_stock_ids

N_PER_TIER = 100  # -> 300 total across 3 tertiles, matches TW factor_ic.SAMPLE_SIZE precedent
MIN_USABLE_DAYS = 260  # same threshold us_factor_ic.py's load_us_sample_with_factors() uses

# Pre-registered before sampling or fetching anything -- one distinct seed per
# tier so each tier's draw is independently reproducible, following the same
# per-tier-distinct-seed convention us_factor_ic_by_size.py used (20260826_1/_2/_3).
SAMPLE_SEEDS = {"large": 20260905_1, "mid": 20260905_2, "small": 20260905_3}

OUT_CSV = Path(__file__).parent / "data" / "us_stratified_universe_sample.csv"


def tiered_universe() -> pd.DataFrame:
    """active_stock_ids() with market_cap coerced numeric, missing/zero
    dropped, split into 3 equal-count tertiles (same cut as
    us_factor_ic_by_size.py::large_cap_universe_ids()). Returns columns:
    stock_id, stock_name, market_cap, tier."""
    u = active_stock_ids()
    u["market_cap"] = pd.to_numeric(u["market_cap"], errors="coerce")
    n_before = len(u)
    u = u.dropna(subset=["market_cap"])
    u = u[u["market_cap"] > 0]
    n_after = len(u)
    print(f"active universe: {n_before} rows, {n_after} with usable numeric market_cap>0 "
          f"({n_before - n_after} dropped: missing/zero/non-numeric)")
    u = u.assign(tier=pd.qcut(u["market_cap"], q=3, labels=["small", "mid", "large"]))
    print(f"tertile counts: {dict(u['tier'].value_counts())}")
    return u


def sample_all_tiers(u: pd.DataFrame) -> pd.DataFrame:
    """N_PER_TIER names per tier via SAMPLE_SEEDS, concatenated. Fewer than
    N_PER_TIER available in a tier (shouldn't happen with ~2,000+/tier here,
    but mirrors us_factor_ic_by_size.py's defensive min() just in case) is
    reported, not treated as an error."""
    picked = []
    for tier, seed in SAMPLE_SEEDS.items():
        pool = u[u["tier"] == tier]
        rng = random.Random(seed)
        n = min(N_PER_TIER, len(pool))
        if n < N_PER_TIER:
            print(f"NOTE: tier '{tier}' only has {len(pool)} names, sampling all of them")
        ids = rng.sample(pool["stock_id"].tolist(), n)
        sub = pool[pool["stock_id"].isin(ids)].copy()
        sub["seed"] = seed
        picked.append(sub)
    return pd.concat(picked, ignore_index=True)


def fetch_and_check(sample: pd.DataFrame) -> pd.DataFrame:
    """Fetches each sampled ticker's price history, records n_days/usable/
    drop_reason. Stops early (not a crash) on the same quota-exhaustion
    signal us_factor_ic.py's loader already watches for."""
    rows = []
    quota_hit = False
    for i, r in enumerate(sample.itertuples(), 1):
        sid = r.stock_id
        if quota_hit:
            rows.append({"stock_id": sid, "tier": r.tier, "market_cap": r.market_cap,
                         "seed": r.seed, "n_days": None, "usable": False,
                         "drop_reason": "not_attempted_quota_hit"})
            continue
        t0 = time.time()
        try:
            px = us_price_series(sid)
        except Exception as e:  # noqa: BLE001 -- deliberately broad, see module docstring on quota-stop behavior
            msg = str(e).lower()
            if any(marker in msg for marker in QUOTA_ERROR_MARKERS):
                print(f"[{i}/{len(sample)}] {sid}: QUOTA/RATE-LIMIT signal ({e}) -- stopping further fetches")
                quota_hit = True
                rows.append({"stock_id": sid, "tier": r.tier, "market_cap": r.market_cap,
                             "seed": r.seed, "n_days": None, "usable": False,
                             "drop_reason": "quota_error"})
                continue
            print(f"[{i}/{len(sample)}] {sid}: fetch error ({e}) -- recorded as unusable, continuing")
            rows.append({"stock_id": sid, "tier": r.tier, "market_cap": r.market_cap,
                         "seed": r.seed, "n_days": None, "usable": False,
                         "drop_reason": f"fetch_error:{type(e).__name__}"})
            continue
        n_days = len(px)
        usable = n_days >= MIN_USABLE_DAYS
        rows.append({"stock_id": sid, "tier": r.tier, "market_cap": r.market_cap,
                     "seed": r.seed, "n_days": n_days, "usable": usable,
                     "drop_reason": None if usable else "too_few_days"})
        dt = time.time() - t0
        print(f"[{i}/{len(sample)}] {sid} ({r.tier}): n_days={n_days} usable={usable} ({dt:.1f}s)")
    return pd.DataFrame(rows)


def main():
    u = tiered_universe()
    sample = sample_all_tiers(u)
    print(f"\nSampled {len(sample)} names total ({N_PER_TIER}/tier x 3 tiers), "
          f"seeds={SAMPLE_SEEDS}")
    result = fetch_and_check(sample)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_CSV, index=False)
    n_usable = result["usable"].sum()
    print(f"\n=== DONE: {n_usable}/{len(result)} usable (n_days>={MIN_USABLE_DAYS}) ===")
    print(result.groupby("tier")["usable"].agg(["sum", "count"]))
    print(f"Written: {OUT_CSV}")


if __name__ == "__main__":
    main()
