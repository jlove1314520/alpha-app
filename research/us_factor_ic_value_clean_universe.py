"""US-track cheap-gate IC re-test for `f_us_value_bm` on the CLEAN stratified
universe (`data/us_stratified_universe_sample.csv`, built by
`us_stratified_universe_sample.py` round-376/381) instead of
`us_portfolio_pilot_real_data.cached_ticker_ids()`.

**Why this script exists**: `us_factor_ic_value.py` (#128, FAIL) and the
low-vol factor (#115, FAIL) were both tested against `cached_ticker_ids()`
-- an ad-hoc pool that grew organically over ~380 marathon rounds by
whichever tickers a prior round happened to fetch (popular/large-cap names
fetched first and more often; `US_MARATHON_STATE.md` round-374's
leave-top10-out REFUTED the narrower "handful of stars" theory but the
broader "universe is generally popularity-skewed, not just a few outliers"
question was left for this exact re-run). The stratified sample instead
draws a pre-registered random tercile-by-market-cap sample (100
large/100 mid/100 small, seeds fixed in `us_stratified_universe_sample.py`)
independent of any prior round's fetch history.

**Everything else is identical to `us_factor_ic_value.py`** -- same
`build_snapshots()`/`evaluate_factor()` cheap-gate machinery, same
snapshot window, same drop-reason taxonomy, same bonferroni_n=1 (still a
standalone re-test, not a new multiple-comparison family member). Only the
input ticker list changes. This is a controlled swap-one-variable
re-test, not a redesign.

**New SEC EDGAR cost**: 234 of the 248 usable stratified tickers have no
cached companyfacts payload yet (checked before writing this script) --
this round's real new-API cost, all against SEC EDGAR (FinMind untouched).
At ~0.3s throttle + fetch/parse time per new CIK this is expected to run
several minutes, hence submitted via `run_detached.py` per protocol
section 0b rather than run inline.
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
from validation import holdout

SNAPSHOT_START = "2015-01-01"
SEC_THROTTLE_SEC = 0.3
UNIVERSE_CSV = Path(__file__).parent / "data" / "us_stratified_universe_sample.csv"


def load_clean_universe_tickers() -> list[str]:
    df = pd.read_csv(UNIVERSE_CSV)
    usable = df[df["usable"] == True]["stock_id"].tolist()  # noqa: E712
    return usable


def load_value_sample() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    tickers = load_clean_universe_tickers()
    print(f"{len(tickers)} tickers in clean stratified universe (usable==True)")

    cik_map = get_cik_map()
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
            time.sleep(SEC_THROTTLE_SEC)

        if bvps.empty:
            drop_reasons[ticker] = "no StockholdersEquity/shares 10-K/10-Q datapoints (book_value_per_share_pit empty)"
            continue

        px = us_price_series(ticker)
        if px.empty:
            drop_reasons[ticker] = "price series unexpectedly empty despite clean-universe membership"
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
    print("=== US track cheap-gate IC re-test: f_us_value_bm on CLEAN stratified universe ===")
    print(f"Snapshot window {SNAPSHOT_START}..{holdout.VAL_END}")

    data, drop_reasons = load_value_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
    if drop_reasons:
        from collections import Counter
        reason_kinds = Counter(r.split(" (")[0].split(" --")[0] for r in drop_reasons.values())
        print("Drop reasons:")
        for kind, count in reason_kinds.most_common():
            print(f"  {count}x {kind}")

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below evaluate_factor()'s minimum "
              f"cross-section size of 10.")
        return None

    aapl_px = us_price_series("AAPL")
    if aapl_px.empty:
        print("\nABORT: AAPL price history unavailable even as a calendar-only load.")
        return None
    calendar = sorted(aapl_px["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_factor("f_us_value_bm", data, snapshots, bonferroni_n=1)
    print(f"\ntrain: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
    print(f"val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
    print(f"null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
    print(f"PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))
    print(f"\n=== SUMMARY (clean-universe sample n={len(data)}) ===")
    print(f"  f_us_value_bm: {'CHEAP_PASS' if r.passes else 'FAIL'}  "
          f"train_ic={r.train_mean_ic:+.4f}  val_ic={r.val_mean_ic:+.4f}  "
          f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return r


if __name__ == "__main__":
    main()
