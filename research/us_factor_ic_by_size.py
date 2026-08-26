"""US-track cheap-gate IC re-test, size-stratified (marathon round, 2026-08-26).

**Why this exists:** per `US_MARATHON_STATE.md`'s "下一步" after round 91 (all
three price-only factors -- f_us_low_vol/f_us_momentum_12m/f_us_reversal_1m --
FAILed on the *same* unstratified 40-name random sample, 27 usable), the
top-priority next step flagged was: "三個純價格因子...都在同一批27檔隨機小
樣本上失敗...未按產業/規模分層抽樣、無regime控制是共通限制，這可能是樣本問題
而非因子問題本身". This script tests that specific concern: does restricting
the sample to one market-cap tier change any of the three verdicts?

**Scope this round: large-cap tier only.** `us_universe.universe()` already
carries a `market_cap` column (from `USStockInfo`, no extra fetch needed to
get it) -- this script tertile-splits the active universe by that column and
samples from the *top* tertile only. Mid/small tiers are explicitly deferred
to future rounds (protocol section 1: "每一輪只做一件事"; also the honest
reason: sampling three tiers today would ~3x today's API-call budget for one
round, and the whole point of a stratified re-test is to be a *cheap* gate,
not to blow through the same quota ceiling the unstratified version already
hit at 27/40 usable). If a future round wants mid/small, `TIER` below is the
only thing that needs to change.

**Reuses everything possible, forks nothing that doesn't need forking:**
`load_us_sample_with_factors()`, calendar construction via AAPL, and
`build_snapshots()`/`evaluate_factor()` are all imported from
`us_factor_ic.py`/`factor_ic.py` unchanged. The only new logic here is the
market-cap tertile split + sampling from one tier.

**bonferroni_n=3**: same three factors as round 91's unstratified batch,
genuinely tested together this round (all three or none -- see `main()`),
so this uses the same multi-factor-family convention `evaluate_factor()`'s
own docstring describes, not the bonferroni_n=1 single-factor convention
round 91 used (that one was testing exactly one *new* factor against two
already-verdicted ones). These three verdicts are NOT new entries replacing
the round-88/91 unstratified ones -- they are a *different sample*
(large-cap-only vs unstratified), so this is a genuinely new set of trials,
not a re-litigation of the old ones. Both results get kept side by side in
US_LEADS.md/TRIALS_LEDGER.md; whichever generalizes better across future
stratified reruns is what should inform any eventual factor-family
conclusion, not either alone.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from factor_ic import build_snapshots, evaluate_factor
from us_factor_ic import SNAPSHOT_START, START_DATE, load_us_sample_with_factors
from us_factors import US_FACTOR_COLUMNS, us_price_series
from us_universe import universe as build_us_universe
from validation import holdout

TIER = "small"  # "large" | "mid" | "small" -- round 99 switches to "small", the last untested tier (large: round 95, mid: round 97); see module docstring
SAMPLE_SIZE = 30
SAMPLE_SEED = 20260826_3  # distinct from the round-95 large-cap run's seed (20260826_1) and the
                           # round-97 mid-cap run's seed (20260826_2) on purpose -- this is a
                           # different sampling frame (small tertile only), reusing a prior seed
                           # value would not itself be wrong but a distinct seed makes it visually
                           # unambiguous in logs which run produced which random draw


def large_cap_universe_ids() -> pd.Series:
    """Active names only, market_cap coerced numeric, split into 3 equal-count
    tertiles by market_cap (pandas qcut), return the stock_ids in the top
    tertile (largest market cap). Rows with missing/non-numeric market_cap
    are dropped before the split (cannot be tiered), count reported by caller.
    """
    u = build_us_universe()
    active = u[u["status"] == "active"].copy()
    active["market_cap"] = pd.to_numeric(active["market_cap"], errors="coerce")
    n_before = len(active)
    active = active.dropna(subset=["market_cap"])
    active = active[active["market_cap"] > 0]
    n_after = len(active)
    print(f"active universe: {n_before} rows, {n_after} with usable numeric market_cap>0 "
          f"({n_before - n_after} dropped: missing/zero/non-numeric)")
    tier_labels = pd.qcut(active["market_cap"], q=3, labels=["small", "mid", "large"])
    tiered = active.assign(tier=tier_labels)
    counts = tiered["tier"].value_counts()
    print(f"tertile counts: {dict(counts)}")
    return tiered[tiered["tier"] == TIER]["stock_id"]


def sample_tier_ids(sample_size: int, seed: int = SAMPLE_SEED) -> list[str]:
    ids = large_cap_universe_ids().tolist()
    rng = random.Random(seed)
    n = min(sample_size, len(ids))
    if n < sample_size:
        print(f"NOTE: tier '{TIER}' only has {len(ids)} names, sampling all of them "
              f"(requested {sample_size})")
    return rng.sample(ids, n)


def main():
    sample_ids = sample_tier_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"\n=== US track size-stratified cheap-gate IC re-test (tier={TIER}) ===")
    print(f"Sample target: {len(sample_ids)} names (seed={SAMPLE_SEED}), snapshot window "
          f"{SNAPSHOT_START}..{holdout.VAL_END}")

    data, quota_hit, quota_hit_ticker = load_us_sample_with_factors(sample_ids)
    print(f"\n{len(data)}/{len(sample_ids)} usable names loaded"
          + (f" (stopped early at {quota_hit_ticker} -- quota/rate-limit)" if quota_hit else ""))

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below the evaluate_factor() minimum "
              f"cross-section size of 10 -- cannot run a meaningful IC test with this sample.")
        return None

    calendar_ref = data.get("AAPL")
    if calendar_ref is None or calendar_ref.empty:
        aapl_px = us_price_series("AAPL", START_DATE)
        if aapl_px.empty:
            print("\nABORT: AAPL price history unavailable even as a calendar-only load.")
            return None
        calendar = sorted(aapl_px["date"].tolist())
    else:
        calendar = sorted(calendar_ref["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    results = []
    for col in US_FACTOR_COLUMNS:
        print(f"\nEvaluating {col} (tier={TIER})...")
        r = evaluate_factor(col, data, snapshots, bonferroni_n=len(US_FACTOR_COLUMNS))
        results.append(r)
        print(f"  train: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
        print(f"  val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
        print(f"  null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
        print(f"  PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))

    print(f"\n=== SUMMARY (tier={TIER}, sample n={len(data)}"
          + (", quota-truncated" if quota_hit else "") + ") ===")
    for r in results:
        print(f"  {r.factor}: {'CHEAP_PASS' if r.passes else 'FAIL'}  val_ic={r.val_mean_ic:+.4f}  "
              f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return results


if __name__ == "__main__":
    main()
