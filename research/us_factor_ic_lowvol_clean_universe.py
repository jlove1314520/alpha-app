"""US-track cheap-gate IC re-test for `f_us_low_vol` on the CLEAN stratified
universe (`data/us_stratified_universe_sample.csv`), the second of the two
factors `US_MARATHON_STATE.md` round-382 flagged for retest after
`us_factor_ic_value_clean_universe.py` (this round) found `f_us_value_bm`
flips FAIL(#128)->CHEAP_PASS on the clean universe.

**Why this script exists**: `US_LEADS.md` #15 / `TRIALS_LEDGER.md` #115
found `f_us_low_vol` FAIL on `cached_ticker_ids()` (201/225 usable) with the
same implausible VAL-period return magnitude as `f_us_value_bm` (#128) --
`US_MARATHON_STATE.md` round-376 flagged both as needing a clean-universe
retest once the stratified sample existed. This is that retest for the
low-vol factor, mirroring `us_factor_ic_value_clean_universe.py`'s
controlled swap-one-variable design (same cheap-gate machinery, same
snapshot window, only the ticker list changes).

**No new API cost expected**: unlike the value factor (which needed new SEC
EDGAR fetches for 234/248 tickers), `f_us_low_vol` only needs price history,
and round-382's log already showed all 248 clean-universe tickers are also
in `cached_ticker_ids()` (i.e. their price parquet is already cached) --
so this should run in well under a minute, no `run_detached.py` needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from factor_ic import build_snapshots, evaluate_factor
from us_factors import prepare_us_factors, us_price_series
from validation import holdout

SNAPSHOT_START = "2015-01-01"
UNIVERSE_CSV = Path(__file__).parent / "data" / "us_stratified_universe_sample.csv"


def load_clean_universe_tickers() -> list[str]:
    df = pd.read_csv(UNIVERSE_CSV)
    return df[df["usable"] == True]["stock_id"].tolist()  # noqa: E712


def load_lowvol_sample() -> dict[str, pd.DataFrame]:
    tickers = load_clean_universe_tickers()
    print(f"{len(tickers)} tickers in clean stratified universe (usable==True)")

    out: dict[str, pd.DataFrame] = {}
    for i, sid in enumerate(tickers):
        px = us_price_series(sid)
        if px.empty:
            print(f"  [{i+1}/{len(tickers)}] {sid}: EMPTY, dropping")
            continue
        if len(px) < 260:
            print(f"  [{i+1}/{len(tickers)}] {sid}: only {len(px)} rows (<260), dropping")
            continue
        d = prepare_us_factors(px)
        out[sid] = d
        print(f"  [{i+1}/{len(tickers)}] {sid}: OK ({len(d)} rows)")
    return out


def main():
    print("=== US track cheap-gate IC re-test: f_us_low_vol on CLEAN stratified universe ===")
    print(f"Snapshot window {SNAPSHOT_START}..{holdout.VAL_END}")

    data = load_lowvol_sample()
    print(f"\n{len(data)} usable names")

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below evaluate_factor()'s minimum "
              f"cross-section size of 10.")
        return None

    calendar_ref = data.get("AAPL")
    if calendar_ref is not None and not calendar_ref.empty:
        calendar = sorted(calendar_ref["date"].tolist())
    else:
        aapl_px = us_price_series("AAPL")
        if aapl_px.empty:
            print("\nABORT: AAPL price history unavailable even as a calendar-only load.")
            return None
        calendar = sorted(aapl_px["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_factor("f_us_low_vol", data, snapshots, bonferroni_n=1)
    print(f"\ntrain: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
    print(f"val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
    print(f"null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
    print(f"PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))
    print(f"\n=== SUMMARY (clean-universe sample n={len(data)}) ===")
    print(f"  f_us_low_vol: {'CHEAP_PASS' if r.passes else 'FAIL'}  "
          f"train_ic={r.train_mean_ic:+.4f}  val_ic={r.val_mean_ic:+.4f}  "
          f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return r


if __name__ == "__main__":
    main()
