"""Deep-dive (MARATHON_PROTOCOL.md 1b) for fut_basis_mean_reversion_60d --
the futures track's third basis-family cheap-gate CHEAP_PASS (round 80,
TRIALS_LEDGER.md #38, FUT_LEADS.md #19).

Round 80 explicitly flagged this candidate as needing the same doubt as
fut_basis_carry (#17): terminal equity 89.24x vs buy-and-hold ~8.79x is an
~82x timing amplification, near-identical in magnitude to the #17 number
that round 75's deep-dive traced to 2000-2002 dot-com-era years dominating
an otherwise-unremarkable sample. FUT_MARATHON_STATE.md explicitly says to
do the train/val split FIRST this time (round 75 did it in listed order but
train/val was already check #1 there too; the instruction here is really
"don't get excited about the whole-sample number before checking val").

Same four checks as deep_dive_fut_basis_carry.py, same order, reusing its
matched-permutation helper logic (period-local dynamic control, not the
static whole-sample control from the cheap-gate stage):
  1. Train/Val split (TRAIN_END/VAL_END from validation/holdout.py).
  2. Leave-one-year-out sensitivity.
  3. Cost sensitivity at 1x/2x/3x (same TX-tax-dominant round-trip
     assumption as #17 -- no dedicated futures cost model exists in this
     repo yet, see deep_dive_fut_basis_carry.py docstring for the rationale).
  4. Beta vs. TAIEX spot returns.

No new FinMind API calls: build_continuous_series() and build_basis_series()
both hit existing full-history parquet caches (same as #17's deep-dive).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import fut_cheap_gate as cg
import fut_basis_series
from validation import holdout
from deep_dive_fut_basis_carry import _matched_permutation_terminal, ROUND_TRIP_COST_BPS_1X, COST_TIERS

WINDOW = 60


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    series = cg._load_series()
    merged = cg._load_basis(series)
    spot = fut_basis_series.build_basis_series()[["date", "spot_close"]]
    merged = merged.merge(spot, on="date", how="inner").sort_values("date").reset_index(drop=True)

    trailing_mean = merged["basis_pct"].rolling(WINDOW).mean().shift(1)
    deviation = merged["basis_pct"] - trailing_mean
    merged["position"] = -np.sign(deviation)
    merged["strat_ret"] = merged["position"].shift(1).fillna(0.0) * merged["ret"]
    merged["year"] = merged["date"].dt.year

    n_warmup_nan = int(merged["position"].isna().sum())
    print(f"loaded {len(merged)} rows, {merged['date'].min().date()} .. {merged['date'].max().date()}")
    print(f"warm-up NaN rows (window={WINDOW}, expected ~{WINDOW}): {n_warmup_nan}")
    print(f"whole-sample real terminal equity (from cheap gate, sanity re-derive here): "
          f"{float((1.0 + merged['strat_ret']).cumprod().iloc[-1]):.4f}")

    # --- 1. Train/Val split with period-local dynamic random control -----
    print("\n=== 1. Train/Val split (TRAIN_END={}, VAL_END={}) ===".format(
        holdout.TRAIN_END, holdout.VAL_END))
    train_mask = merged["date"] <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = (merged["date"] > pd.Timestamp(holdout.TRAIN_END)) & (merged["date"] <= pd.Timestamp(holdout.VAL_END))

    split_results = {}
    for label, mask in [("train", train_mask), ("val", val_mask)]:
        sub = merged[mask].reset_index(drop=True)
        real_eq, rand_med, pctl = _matched_permutation_terminal(
            sub["position"], sub["ret"], seed=cg.SHUFFLE_SEED)
        bh_eq = float((1.0 + sub["ret"]).cumprod().iloc[-1])
        n_flips = int((sub["position"].dropna().diff().abs() > 0).sum())
        split_results[label] = dict(n_days=len(sub), real_eq=real_eq, rand_med=rand_med,
                                     pctl=pctl, bh_eq=bh_eq, n_flips=n_flips,
                                     start=sub["date"].min(), end=sub["date"].max())
        print(f"  [{label}] {sub['date'].min().date()}..{sub['date'].max().date()} "
              f"n={len(sub)} real_eq={real_eq:.4f} ({(real_eq-1)*100:+.1f}%) "
              f"buy&hold_eq={bh_eq:.4f} ({(bh_eq-1)*100:+.1f}%) "
              f"random_median={rand_med:.4f} percentile={pctl:.1f} "
              f"position_flips={n_flips}")

    train_sign_positive = split_results["train"]["real_eq"] > 1.0
    val_sign_positive = split_results["val"]["real_eq"] > 1.0
    print(f"  train/val sign agreement (both net-positive, no cost): "
          f"{'YES' if train_sign_positive == val_sign_positive else 'NO -- SIGN FLIPS ACROSS SPLIT'}")
    val_beats_random_median = split_results["val"]["pctl"] >= 50.0
    print(f"  val period beats random-control median: {'YES' if val_beats_random_median else 'NO'} "
          f"(percentile={split_results['val']['pctl']:.1f})")

    # --- 2. Leave-one-year-out sensitivity --------------------------------
    print("\n=== 2. Leave-one-year-out sensitivity ===")
    valid_full = merged.dropna(subset=["position"]).reset_index(drop=True)
    full_terminal = float((1.0 + valid_full["strat_ret"]).cumprod().iloc[-1])
    years = sorted(valid_full["year"].unique())
    loyo_rows = []
    for y in years:
        kept = valid_full[valid_full["year"] != y]
        kept_terminal = float((1.0 + kept["strat_ret"]).cumprod().iloc[-1])
        year_only = valid_full[valid_full["year"] == y]
        year_ret = float((1.0 + year_only["strat_ret"]).cumprod().iloc[-1]) - 1.0
        loyo_rows.append(dict(year=y, n_days=len(year_only), year_return=year_ret,
                               terminal_excl_year=kept_terminal,
                               ratio_to_full=kept_terminal / full_terminal))
    loyo_df = pd.DataFrame(loyo_rows).sort_values("year_return", ascending=False)
    print(loyo_df.to_string(index=False, formatters={
        "year_return": "{:+.2%}".format,
        "terminal_excl_year": "{:.4f}".format,
        "ratio_to_full": "{:.4f}".format,
    }))
    top3 = loyo_df.head(3)
    top3_contrib_years = top3["year"].tolist()
    excl_top3 = valid_full[~valid_full["year"].isin(top3_contrib_years)]
    excl_top3_terminal = float((1.0 + excl_top3["strat_ret"]).cumprod().iloc[-1])
    print(f"\n  top-3 single-year contributors (by that year's own compounded return): {top3_contrib_years}")
    print(f"  terminal equity excluding those 3 years entirely: {excl_top3_terminal:.4f} "
          f"vs full-sample {full_terminal:.4f} "
          f"(ratio {excl_top3_terminal / full_terminal:.4f})")

    # --- 3. Cost sensitivity 1x/2x/3x --------------------------------------
    print(f"\n=== 3. Cost sensitivity (round-trip 1x = {ROUND_TRIP_COST_BPS_1X}bps, "
          f"approximate TX tax-dominant assumption, see deep_dive_fut_basis_carry.py docstring) ===")
    turnover = valid_full["position"].diff().abs().fillna(0.0)
    for tier_label, mult in COST_TIERS.items():
        per_unit_cost = (ROUND_TRIP_COST_BPS_1X / 2.0 / 10000.0) * mult
        cost_drag = turnover.shift(0) * per_unit_cost
        strat_ret_net = valid_full["strat_ret"] - cost_drag.shift(1).fillna(0.0)
        terminal_net = float((1.0 + strat_ret_net).cumprod().iloc[-1])
        print(f"  [{tier_label}] round_trip_cost={ROUND_TRIP_COST_BPS_1X * mult:.1f}bps "
              f"terminal_equity_net={terminal_net:.4f} ({(terminal_net - 1) * 100:+.1f}%) "
              f"(gross={full_terminal:.4f})")

    # --- 4. Beta vs TAIEX spot --------------------------------------------
    print("\n=== 4. Beta vs. TAIEX spot daily returns ===")
    spot_ret = merged["spot_close"].pct_change()
    valid = merged["strat_ret"].notna() & spot_ret.notna() & merged["position"].notna()
    x = spot_ret[valid].to_numpy()
    y = merged["strat_ret"][valid].to_numpy()
    beta, alpha = np.polyfit(x, y, 1)
    corr = float(np.corrcoef(x, y)[0, 1])
    print(f"  beta={beta:.4f}  alpha(daily)={alpha:.6f}  corr={corr:.4f}  r2={corr**2:.4f}  n={len(x)}")
    print(f"  interpretation: beta near 0 supports 'market-neutral timing edge'; "
          f"beta far from 0 in either direction means this is substantially a "
          f"directional/leveraged bet on TAIEX itself, not a distinct timing edge.")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
