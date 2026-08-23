"""Measure cumulative ratio-adjustment drift for the continuous TX series.

MARATHON_PROTOCOL.md 1c / FUT_CONTINUOUS_CONTRACT_DESIGN.md "尚待驗證 #2":
the ratio back-adjustment method (continuous_contract.py) is known-in-theory
to make `adj_close` diverge from the real same-day spot price (`close`, the
front-month contract's actual traded price) as more rollovers compound going
back in time. This script quantifies how large that divergence actually gets
over the full 2000-2024 history, instead of assuming "it's probably fine".

Zero network calls: build_continuous_series() defaults to the exact
(start_date, end_date) key that matches the existing on-disk full-history
parquet cache (see continuous_contract.py / FUT_LOG.md precedent).
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import build_continuous_series

pd.set_option("display.width", 140)


def main() -> None:
    series, skipped = build_continuous_series()
    print(f"series: {len(series)} rows, {series.attrs['n_rollover_events']} rollover events, "
          f"{series.attrs['n_skipped_events']} skipped")

    s = series.copy()
    s["pct_diff"] = (s["adj_close"] / s["close"] - 1.0) * 100.0
    s["ratio_factor"] = s["adj_close"] / s["close"]

    print("\n--- summary stats of pct_diff (adj_close vs same-day raw close), whole sample ---")
    print(s["pct_diff"].describe())

    print("\n--- drift by calendar year (first row of each year) ---")
    s["year"] = s["date"].dt.year
    first_of_year = s.groupby("year").first()[["date", "contract_date", "close", "adj_close", "pct_diff", "ratio_factor"]]
    print(first_of_year.to_string())

    worst = s.loc[s["pct_diff"].abs().idxmax()]
    print("\n--- single worst-drift day ---")
    print(worst[["date", "contract_date", "close", "adj_close", "pct_diff", "ratio_factor"]])

    earliest = s.iloc[0]
    print("\n--- earliest date in sample (max compounding, all 300 rollovers applied) ---")
    print(earliest[["date", "contract_date", "close", "adj_close", "pct_diff", "ratio_factor"]])

    # Monotonicity check: is drift roughly increasing the further back you go
    # (consistent with a systematic contango bias), or does it wander both
    # directions (consistent with rollover ratios being noise around 1 with
    # no persistent sign)? Correlate |pct_diff| against "days back from most
    # recent date".
    s["days_back"] = (s["date"].max() - s["date"]).dt.days
    corr = s["days_back"].corr(s["pct_diff"].abs())
    print(f"\ncorrelation(days_back, |pct_diff|) = {corr:.4f} "
          "(near 1.0 = drift grows ~monotonically the further back you go; "
          "near 0 = drift wanders without a persistent trend)")

    # How many trading days have |pct_diff| beyond a few sanity thresholds.
    for thresh in (1, 5, 10, 20, 50):
        n = (s["pct_diff"].abs() > thresh).sum()
        pct = n / len(s) * 100
        print(f"days with |pct_diff| > {thresh}%: {n} ({pct:.1f}% of sample)")

    # Second question: does this large drift in absolute *level* also mean
    # day-to-day *returns* are distorted, or is it purely a level-rebasing
    # artifact that leaves returns intact (as FUT_CONTINUOUS_CONTRACT_DESIGN.md
    # claims: "轉倉點的報酬率是連續、無跳空的")? Compare adj_close pct-change
    # against raw close pct-change (raw close naturally jumps at rollover
    # since the underlying contract changes) on every day.
    s["adj_ret"] = s["adj_close"].pct_change()
    s["raw_ret"] = s["close"].pct_change()
    s["ret_diff"] = (s["adj_ret"] - s["raw_ret"]).abs()
    is_rollover_day = s["contract_date"] != s["contract_date"].shift(1)
    n_diverge = (s["ret_diff"] > 1e-9).sum()
    n_diverge_on_rollover = (s["ret_diff"] > 1e-9)[is_rollover_day].sum()
    n_diverge_off_rollover = (s["ret_diff"] > 1e-9)[~is_rollover_day].sum()
    print(f"\n--- day-to-day return check: adj_ret vs raw_ret ---")
    print(f"days where adj_ret != raw_ret: {n_diverge} total "
          f"({n_diverge_on_rollover} on a contract-switch day, "
          f"{n_diverge_off_rollover} on a non-switch day)")
    print("(expected: divergence should be confined to contract-switch days only, "
          "confirming the adjustment purely re-bases historical *levels* without "
          "touching returns elsewhere -- if n_diverge_off_rollover > 0 that would "
          "be a bug, not an expected side effect)")

    if skipped:
        print(f"\nSKIPPED EVENTS (no ratio applied, {len(skipped)} total, "
              "these are a separate known gap, not part of this drift measurement):")
        for sk in skipped:
            print(f"  {sk}")


if __name__ == "__main__":
    main()
