"""US-track cheap-gate IC test for `f_us_value_bm` (book-to-market) --
marathon round following US_MARATHON_STATE.md round-345's explicit "下一步":
"用 us_portfolio_pilot_real_data.cached_ticker_ids() 交集可解析 CIK 的樣本
（預估30-60檔）跑 factor_ic.evaluate_factor() cheap gate 測試". Round 345
built the factor itself (`us_factors_value.py`) and fixed two real bugs in
it (XBRL dimensional-context outlier, split-adjustment mismatch) but
deliberately left the cheap-gate run for this round -- see that round's
writeup for why (budget exhausted after the bug hunt).

**Sample construction, why it differs from `us_factor_ic.py`'s random
draw**: that script draws a fresh random sample from `build_us_universe()`
every run (burns new FinMind API calls per name). This script instead
starts from `us_portfolio_pilot_real_data.cached_ticker_ids()` -- every
ticker that already has a full 1990-01-01..2024-12-31 USStockPrice parquet
on disk from prior rounds (138 names) -- so the PRICE side costs zero new
FinMind calls. The SEC EDGAR side is NOT free: only 3 CIKs
(AAPL/MSFT/PLTR) have a cached companyfacts payload before this round, so
resolving book-to-market for the other ~135 cached tickers means ~135 new
`companyfacts/CIK{cik}.json` fetches (one per CIK, then cached for every
future round) -- this is the round's actual new API cost, all against SEC
EDGAR (not FinMind, so the FinMind hourly quota this track otherwise has
to protect is untouched).

**Not every cached ticker survives to the final sample.** Three
independent filters apply, in order, each one a legitimate "absent, not a
bug" outcome per `sec_edgar_client.py`/`us_fundamentals.py`'s existing
convention:
1. No resolvable CIK at all (ticker not in SEC's current ticker->CIK map --
   e.g. delisted-and-reused tickers, some ETFs/ADRs).
2. CIK resolves but `book_value_per_share_pit()` returns empty (no
   StockholdersEquity 10-K/10-Q datapoints -- covers 20-F foreign private
   issuers per `us_factors_value.py`'s docstring, and any filer whose
   earliest XBRL disclosure postdates this track's DEV/VAL window
   entirely).
3. `add_value_factor()` produces zero non-NaN `f_us_value_bm` rows in the
   snapshot window (merge_asof found no pit_date <= any snapshot date --
   only possible if the filer's very first XBRL disclosure is later than
   2015-01-01, the snapshot window's own start).

Whatever survives all three is this round's actual test sample -- reported
honestly even if the intended ~40-60 target isn't hit (same "smaller
sample is a caveat, not a reason to abort" convention `us_factor_ic.py`
already documents).

**Economic prior, stated up front per protocol section 1b/CLAUDE.md**:
positive IC expected (book-to-market is the textbook Fama-French HML
value premium -- cheap-relative-to-book stocks historically outperform,
plausibly because the market systematically overweights recent growth/
momentum narratives and underweights balance-sheet-anchored value, a
behavioral underreaction-to-value story, not a data-mined pattern -- this
is the FIRST fundamentals-based factor this track has ever tested, after
3 price-only factors (low-vol/momentum/reversal) all failed, so this is
also the first real test of whether the SEC EDGAR PIT plumbing itself can
produce ANY signal, not just this specific factor).

Reuses `build_snapshots()`/`evaluate_factor()` from `factor_ic.py` as-is,
same convention `us_factor_ic.py` already follows -- no fork of the IC math.

Zero calls into FinMind's holdout-gated `load_dev()` path beyond what
`us_price_series()` already safely wraps (every ticker here is a cache
hit, see above) -- `is_holdout_consumed()` is checked before/after this
script runs, same as every other marathon round.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from factor_ic import build_snapshots, evaluate_factor
from sec_edgar_client import get_cik_map
from us_factors import us_price_series
from us_factors_value import add_value_factor, book_value_per_share_pit
from us_portfolio_pilot_real_data import cached_ticker_ids
from validation import holdout

SNAPSHOT_START = "2015-01-01"  # same window every other US-track cheap-gate script uses
SEC_THROTTLE_SEC = 0.3  # polite pacing between new companyfacts fetches, well under SEC's
                         # documented ~10 req/sec fair-use ceiling (see sec_edgar_client.py
                         # module docstring) -- not a hard requirement, just good citizenship
                         # since this round's ~135 new fetches is far more than any prior
                         # SEC-EDGAR-calling round in this project has done in one pass


def load_value_sample() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Returns (data, drop_reasons). `data` maps ticker -> DataFrame with
    date/adj_close/f_us_value_bm columns (evaluate_factor()'s required
    shape). `drop_reasons` maps ticker -> why it didn't make it into
    `data`, for honest reporting (protocol section 4: no silent drops).
    """
    tickers = cached_ticker_ids()
    print(f"{len(tickers)} tickers with cached full-range price series (zero new FinMind calls)")

    cik_map = get_cik_map()  # single cached call (24h TTL), not per-ticker
    print(f"SEC ticker->CIK map loaded ({len(cik_map)} entries)")

    out: dict[str, pd.DataFrame] = {}
    drop_reasons: dict[str, str] = {}
    for i, ticker in enumerate(tickers):
        cik = cik_map.get(ticker)
        if cik is None:
            drop_reasons[ticker] = "no resolvable CIK"
            continue

        cache_path = Path(__file__).parent / "data" / "raw" / f"SEC_companyfacts_{str(cik).zfill(10)}.json"
        was_cached = cache_path.exists()

        bvps = book_value_per_share_pit(ticker, cik_override=cik)
        if not was_cached:
            time.sleep(SEC_THROTTLE_SEC)  # only throttle on an actual new fetch, not a cache hit

        if bvps.empty:
            drop_reasons[ticker] = "no StockholdersEquity/shares 10-K/10-Q datapoints (book_value_per_share_pit empty)"
            continue

        px = us_price_series(ticker)  # cache hit, per cached_ticker_ids()'s own guarantee
        if px.empty:
            drop_reasons[ticker] = "price series unexpectedly empty despite cached_ticker_ids() membership"
            continue

        d = add_value_factor(px, bvps)
        n_valid = d["f_us_value_bm"].notna().sum()
        if n_valid == 0:
            drop_reasons[ticker] = "f_us_value_bm all-NaN (first XBRL disclosure postdates price history start)"
            continue

        out[ticker] = d[["date", "adj_close", "f_us_value_bm"]]
        print(f"  [{i+1}/{len(tickers)}] {ticker}: OK ({n_valid}/{len(d)} non-NaN f_us_value_bm rows"
              + ("" if was_cached else ", new SEC fetch") + ")")

    return out, drop_reasons


def main():
    print("=== US track cheap-gate IC test: f_us_value_bm (book-to-market) ===")
    print(f"Snapshot window {SNAPSHOT_START}..{holdout.VAL_END}")

    data, drop_reasons = load_value_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} cached-price candidates)")
    if drop_reasons:
        from collections import Counter
        reason_kinds = Counter(r.split(" (")[0].split(" --")[0] for r in drop_reasons.values())
        print("Drop reasons:")
        for kind, count in reason_kinds.most_common():
            print(f"  {count}x {kind}")

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below evaluate_factor()'s minimum "
              f"cross-section size of 10 -- cannot run a meaningful IC test with this sample. "
              f"Not writing a CHEAP_PASS/FAIL verdict, this is an infra/data-availability "
              f"finding, not a factor result.")
        return None

    aapl_px = us_price_series("AAPL")
    if aapl_px.empty:
        print("\nABORT: AAPL price history unavailable even as a calendar-only load.")
        return None
    calendar = sorted(aapl_px["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_factor("f_us_value_bm", data, snapshots, bonferroni_n=1)  # bonferroni_n=1:
    # genuinely standalone test -- f_us_value_bm is the only NEW, previously-unverdicted
    # US-track factor this round tests (US_FACTOR_COLUMNS' 3 price factors all already
    # have final verdicts, see US_LEADS.md #1-15), same convention us_factor_ic.py follows
    print(f"\ntrain: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
    print(f"val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
    print(f"null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
    print(f"PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))
    print(f"\n=== SUMMARY (sample n={len(data)}) ===")
    print(f"  f_us_value_bm: {'CHEAP_PASS' if r.passes else 'FAIL'}  "
          f"train_ic={r.train_mean_ic:+.4f}  val_ic={r.val_mean_ic:+.4f}  "
          f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return r


if __name__ == "__main__":
    main()
