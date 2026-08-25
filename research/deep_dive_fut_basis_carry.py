"""Deep-dive (MARATHON_PROTOCOL.md 1b) for fut_basis_carry -- the futures
track's first cheap-gate CHEAP_PASS (round 72, TRIALS_LEDGER.md #35).

The round-72 sanity check ruled out "pure continuous-contract drift
artifact" as the explanation for the 717x terminal equity (buy-and-hold
only reached 8.79x over the same window), but explicitly left one bigger
worry unresolved: an 82x timing amplification over buy-and-hold is
extreme for a daily sign-flip strategy, and could plausibly be an artifact
of a handful of outsized historical event years (2000 dot-com, 2008 GFC,
2024 selloff) dominating the whole-sample number rather than a stable,
repeatable edge. This script is the walk-forward-first response required
by FUT_MARATHON_STATE.md's "下一輪建議工作單位" #1 before any
PASS/EXPERIMENTAL verdict or "why this works" economic writeup is trusted.

Four checks, in the order MARATHON_PROTOCOL.md 1b lists them:
  1. Train/Val split (TRAIN_END/VAL_END from validation/holdout.py) with a
     *dynamic* (period-local) matched-permutation control in each period
     separately -- not the single whole-sample static control already run
     at the cheap-gate stage.
  2. Leave-one-year-out sensitivity, to directly answer "is this a handful
     of extreme years driving everything" with a number, not a guess.
  3. Cost sensitivity at 1x/2x/3x a documented (necessarily approximate,
     TX futures do not have a per-stock-style cost model in this repo yet)
     round-trip cost assumption.
  4. Beta vs. TAIEX spot returns, to check whether the "market-neutral
     timing edge" framing is right or whether this is secretly just a
     leveraged/timed directional bet on the index itself.

No new FinMind API calls: build_continuous_series() and build_basis_series()
both hit existing full-history parquet caches (same as rounds 69/72).
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

# --- Cost model (documented assumption, no existing TX futures cost model
# in this repo to reuse -- validation/costs.py is stock-percentage-of-
# notional and does not apply to a fixed-tax/fixed-commission futures
# contract). TX index futures round-trip cost is dominated by the futures
# transaction tax (期貨交易稅), which for stock index futures is a fixed
# 0.002% of contract value PER SIDE under the Futures Trading Tax Act --
# i.e. ~4bps round-trip on tax alone. Brokerage commission (~NT$20-50/side)
# and exchange fee (~NT$16-20/side) are a few hundredths of a percent of a
# typical ~NT$3.4M TX contract notional (17000pts x NT$200 multiplier),
# i.e. sub-1bp round-trip -- negligible next to the tax. 1x tier below
# (5bps round-trip) is therefore tax-dominant and conservative-rounded up;
# this is an approximation, not a verified live broker fee schedule, and
# is flagged as such rather than presented as a precise number.
ROUND_TRIP_COST_BPS_1X = 5.0
COST_TIERS = {"1x": 1, "2x": 2, "3x": 3}


def _matched_permutation_terminal(pos: pd.Series, ret: pd.Series, seed: int) -> tuple[float, float, float]:
    """Same shuffle-the-position-array-keep-the-return-pairing logic as
    fut_cheap_gate._permutation_test, factored out so it can be called on
    an arbitrary sub-period slice (train-only, val-only) rather than only
    the whole sample -- this is the "配對式隨機控制組（不是靜態版）"
    requirement from MARATHON_PROTOCOL.md 1b: a fresh, period-local random
    control, not reuse of the whole-sample control already computed at the
    cheap-gate stage."""
    valid = pos.notna() & ret.notna()
    p = pos[valid].reset_index(drop=True)
    r = ret[valid].reset_index(drop=True)
    strat_ret = p.shift(1).fillna(0.0) * r
    real_equity = float((1.0 + strat_ret).cumprod().iloc[-1])

    rng = np.random.default_rng(seed)
    p_arr = p.to_numpy()
    r_arr = r.to_numpy()
    randoms = np.empty(cg.N_SHUFFLES)
    for i in range(cg.N_SHUFFLES):
        shuffled = rng.permutation(p_arr)
        shuffled_ret = np.roll(shuffled, 1)
        shuffled_ret[0] = 0.0
        randoms[i] = np.prod(1.0 + shuffled_ret * r_arr)

    percentile = float((randoms < real_equity).mean() * 100.0)
    return real_equity, float(np.median(randoms)), percentile


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    series = cg._load_series()
    merged = cg._load_basis(series)
    spot = fut_basis_series.build_basis_series()[["date", "spot_close"]]
    merged = merged.merge(spot, on="date", how="inner").sort_values("date").reset_index(drop=True)

    merged["position"] = -np.sign(merged["basis_pct"])
    merged["strat_ret"] = merged["position"].shift(1).fillna(0.0) * merged["ret"]
    merged["year"] = merged["date"].dt.year

    print(f"loaded {len(merged)} rows, {merged['date'].min().date()} .. {merged['date'].max().date()}")
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
        n_flips = int((sub["position"].diff().abs() > 0).sum())
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

    # --- 2. Leave-one-year-out sensitivity --------------------------------
    print("\n=== 2. Leave-one-year-out sensitivity ===")
    full_terminal = float((1.0 + merged["strat_ret"]).cumprod().iloc[-1])
    years = sorted(merged["year"].unique())
    loyo_rows = []
    for y in years:
        kept = merged[merged["year"] != y]
        kept_terminal = float((1.0 + kept["strat_ret"]).cumprod().iloc[-1])
        year_only = merged[merged["year"] == y]
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
    excl_top3 = merged[~merged["year"].isin(top3_contrib_years)]
    excl_top3_terminal = float((1.0 + excl_top3["strat_ret"]).cumprod().iloc[-1])
    print(f"\n  top-3 single-year contributors (by that year's own compounded return): {top3_contrib_years}")
    print(f"  terminal equity excluding those 3 years entirely: {excl_top3_terminal:.4f} "
          f"vs full-sample {full_terminal:.4f} "
          f"(ratio {excl_top3_terminal / full_terminal:.4f})")

    # --- 3. Cost sensitivity 1x/2x/3x --------------------------------------
    print(f"\n=== 3. Cost sensitivity (round-trip 1x = {ROUND_TRIP_COST_BPS_1X}bps, "
          f"approximate TX tax-dominant assumption, see module docstring) ===")
    turnover = merged["position"].diff().abs().fillna(0.0)
    for tier_label, mult in COST_TIERS.items():
        per_unit_cost = (ROUND_TRIP_COST_BPS_1X / 2.0 / 10000.0) * mult
        cost_drag = turnover.shift(0) * per_unit_cost  # cost incurred on the day the position changes
        # position changes on day t affect the trade entered for t+1's return
        # (same 1-day shift convention as strat_ret itself), so align cost to
        # the same day index as strat_ret's shift(1) position.
        strat_ret_net = merged["strat_ret"] - cost_drag.shift(1).fillna(0.0)
        terminal_net = float((1.0 + strat_ret_net).cumprod().iloc[-1])
        print(f"  [{tier_label}] round_trip_cost={ROUND_TRIP_COST_BPS_1X * mult:.1f}bps "
              f"terminal_equity_net={terminal_net:.4f} ({(terminal_net - 1) * 100:+.1f}%) "
              f"(gross={full_terminal:.4f})")

    # --- 4. Beta vs TAIEX spot --------------------------------------------
    print("\n=== 4. Beta vs. TAIEX spot daily returns ===")
    spot_ret = merged["spot_close"].pct_change()
    valid = merged["strat_ret"].notna() & spot_ret.notna()
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
