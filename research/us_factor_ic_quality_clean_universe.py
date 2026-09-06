"""US-track cheap-gate IC test for the NEW factor `f_us_gross_profitability`
(see `us_factors_quality.py` module docstring for why this is a genuinely
new economic mechanism, not a reskin of #20/#21) on the CLEAN stratified
universe (`data/us_stratified_universe_sample.csv`) -- same universe #20/#21
used, chosen deliberately so this factor's cheap-gate result is directly
comparable to theirs without also changing the sample.

**Everything else is identical to `us_factor_ic_value_clean_universe.py`**
-- same `build_snapshots()`/`evaluate_factor()` cheap-gate machinery, same
snapshot window, same drop-reason taxonomy, same bonferroni_n=1 (first
standalone test of this factor, not a multi-comparison family member yet).
Only the factor module/column changes (`us_factors_quality.add_quality_factor`
/ `f_us_gross_profitability` instead of `us_factors_value.add_value_factor`
/ `f_us_value_bm`).

**Expected SEC EDGAR cost: at or near ZERO new HTTP requests** -- every CIK
already has a cached companyfacts JSON from round383's `f_us_value_bm`
clean-universe run (`get_companyfacts()` caches the WHOLE payload per CIK,
`GrossProfit`/`Assets` are different keys in that SAME cached JSON, see
`us_factors_quality.py` module docstring). Tickers with no cached CIK/companyfacts
at all would still need a fresh fetch, but the clean-universe run already
resolved CIKs for all 248 and fetched companyfacts for the 234 that needed
it, so this round's incremental cost should be near-instant -- run inline,
not `run_detached.py`, unless observed otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import build_snapshots, evaluate_factor
from sec_edgar_client import get_cik_map
from us_factor_ic_value_clean_universe import load_clean_universe_tickers
from us_factors import us_price_series
from us_factors_quality import add_quality_factor, gross_profitability_pit
from validation import holdout

SNAPSHOT_START = "2015-01-01"


def load_quality_sample() -> tuple[dict, dict]:
    tickers = load_clean_universe_tickers()
    print(f"{len(tickers)} tickers in clean stratified universe (usable==True)")

    cik_map = get_cik_map()
    print(f"SEC ticker->CIK map loaded ({len(cik_map)} entries)")

    out = {}
    drop_reasons = {}
    for i, ticker in enumerate(tickers):
        cik = cik_map.get(ticker)
        if cik is None:
            drop_reasons[ticker] = "no resolvable CIK"
            continue

        gp = gross_profitability_pit(ticker, cik_override=cik)
        if gp.empty:
            drop_reasons[ticker] = "no GrossProfit/Assets 10-K datapoints (gross_profitability_pit empty)"
            continue

        px = us_price_series(ticker)
        if px.empty:
            drop_reasons[ticker] = "price series unexpectedly empty despite clean-universe membership"
            continue

        d = add_quality_factor(px, gp)
        n_valid = d["f_us_gross_profitability"].notna().sum()
        if n_valid == 0:
            drop_reasons[ticker] = "f_us_gross_profitability all-NaN (first XBRL disclosure postdates price history start)"
            continue

        out[ticker] = d[["date", "adj_close", "f_us_gross_profitability"]]
        print(f"  [{i+1}/{len(tickers)}] {ticker}: OK ({n_valid}/{len(d)} non-NaN rows)")

    return out, drop_reasons


def main():
    print("=== US track cheap-gate IC test: f_us_gross_profitability on CLEAN stratified universe ===")
    print(f"Snapshot window {SNAPSHOT_START}..{holdout.VAL_END}")

    data, drop_reasons = load_quality_sample()
    print(f"\n{len(data)} usable names (out of {len(data) + len(drop_reasons)} clean-universe candidates)")
    if drop_reasons:
        from collections import Counter
        reason_kinds = Counter(r.split(" (")[0].split(" --")[0] for r in drop_reasons.values())
        print("Drop reasons:")
        for kind, count in reason_kinds.most_common():
            print(f"  {count}x {kind}")

    if len(data) < 10:
        print(f"\nABORT: only {len(data)} usable names, below evaluate_factor()'s minimum cross-section size of 10.")
        return None

    aapl_px = us_price_series("AAPL")
    if aapl_px.empty:
        print("\nABORT: AAPL price history unavailable even as a calendar-only load.")
        return None
    calendar = sorted(aapl_px["date"].tolist())

    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    r = evaluate_factor("f_us_gross_profitability", data, snapshots, bonferroni_n=1)
    print(f"\ntrain: mean_ic={r.train_mean_ic:+.4f} IR={r.train_ic_ir:+.3f} (n={r.n_dates_train} dates)")
    print(f"val:   mean_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit_rate={r.val_hit_rate:.2f} (n={r.n_dates_val} dates)")
    print(f"null percentile: {r.null_percentile:.1f} (need >={r.required_percentile:.1f})  same_sign: {r.same_sign}")
    print(f"PASSES cheap gate: {r.passes}" + (f"  reasons: {r.reasons}" if not r.passes else ""))
    print(f"\n=== SUMMARY (clean-universe sample n={len(data)}) ===")
    print(f"  f_us_gross_profitability: {'CHEAP_PASS' if r.passes else 'FAIL'}  "
          f"train_ic={r.train_mean_ic:+.4f}  val_ic={r.val_mean_ic:+.4f}  "
          f"percentile={r.null_percentile:.1f}/{r.required_percentile:.1f}")
    return r


if __name__ == "__main__":
    main()
