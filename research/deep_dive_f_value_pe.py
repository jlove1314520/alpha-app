# ⛔ 2026-09-07 本檔案的結果不可引用（總司令裁示）
#
# f_value_pe 在正確的全體分母（N=223，Bonferroni 門檻 99.9776 百分位）下
# 只有 96.7 百分位，**未過第一關，不具備進入深挖的資格**。
# 這支腳本與它產出的所有結果，屬於「分母錯誤期間的無效深挖」：
#   - 檔案保留不刪（那是當時真的跑出來的數字，刪掉等於湮滅紀錄）
#   - 但**不得引用**：不得寫進候選清單、不得作為組合成分、
#     不得作為任何新假設的「已知有效因子」前提
# 要重新啟用，必須先讓 f_value_pe 在正確分母下通過第一關。

"""TW marathon round: cost-sensitivity / strategy-level deep-dive for
`f_value_pe` (negative-PER value factor), per `CRITERIA_V2_LOCK.md` line 39:
情境分群檢驗 -> 成本敏感度 -> alpha/beta顯著性, all three gates required before
this CANDIDATE can move to the deep-dive list. The regime-split gate already
passed (`regime_conditions_value_pe.py`, TRIALS_LEDGER.md #166, 8/8 positive
groups, no direction reversal). This script is the second gate.

Method mirrors `deep_dive_f_value_pb.py` (same factor family, same TW
sample-loading pipeline) rather than copying it: decile long-short
(k = round(n*10%)), TRAIN/VAL split, matched random long-short control
(N_RANDOM_DRAWS draws, not a static benchmark), cost sensitivity at
1x/2x/3x DEFAULT_SLIPPAGE_BPS, CAPM beta vs TAIEX. Uses `factor_ic.SAMPLE_SIZE`
(currently 300, post-CALIBRATION_PROBE.md) instead of the old 100-name sample
that `deep_dive_f_value_pb.py` used, for consistency with
`regime_conditions_value_pe.py`'s sample.

PIT caveat (same as `f_value_pb`, repeated on purpose so it isn't silently
dropped): PIT status for `f_value_pe` is "inferred from `f_value_pb`'s single-
stock (2330) spot check" (TaiwanStockPER shares the same disclosure-timing
mechanism as TaiwanStockPBR), NOT independently, directly verified.
"""
from __future__ import annotations

import random
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import long_short_backtest as lsb
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TARGET_FACTOR = "f_value_pe"
START_DATE = "2010-01-01"
DECILE_FRACTION = 0.10
REBALANCE_DAYS = 20  # same cadence as factor_ic.py / regime_conditions_value_pe.py, for comparability
N_RANDOM_DRAWS = 100  # matches deep_dive_f_value_pb.py's resolution
RANDOM_CONTROL_SEED = 20260823  # same seed value as deep_dive_f_value_pb.py, for auditability (not shared randomness --
# rng.sample() draws depend on which ids/dates have non-NaN f_value_pe, not just the seed)
COST_MULTIPLIERS = [1, 2, 3]  # x DEFAULT_SLIPPAGE_BPS, per CONSTITUTION.md's cost-sensitivity requirement

PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VAL": ("2021-01-01", holdout.VAL_END),
}


def _factor_cross_section(as_of: str, data: dict[str, pd.DataFrame], factor_col: str) -> tuple[list[str], list[float]]:
    ids, vals = [], []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        fv = d.loc[idx[0], factor_col]
        if pd.isna(fv):
            continue
        ids.append(sid)
        vals.append(float(fv))
    return ids, vals


def _decile_legs_factor(as_of: str, data: dict, industry_map, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, vals = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    # f_value_pe = -PER, so HIGHER f_value_pe = cheaper (lower PER) = long leg.
    order = sorted(zip(ids, vals), key=lambda t: t[1], reverse=True)
    k = max(1, round(n * DECILE_FRACTION))
    longs = [sid for sid, _ in order[:k]]
    shorts = [sid for sid, _ in order[-k:]]
    return longs, shorts


def _random_legs_factor(as_of: str, data: dict, industry_map, rng: random.Random, factor_col: str = TARGET_FACTOR) -> tuple[list[str], list[str]]:
    ids, _ = _factor_cross_section(as_of, data, factor_col)
    n = len(ids)
    if n < 10:
        return [], []
    k = max(1, round(n * DECILE_FRACTION))
    if n < 2 * k:
        return [], []
    picks = rng.sample(ids, 2 * k)
    return picks[:k], picks[k:]


def run_one(data, market_df, start, end, slippage_bps):
    lsb.SLIPPAGE_BPS = slippage_bps
    leg_fn = partial(_decile_legs_factor, factor_col=TARGET_FACTOR)
    result = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=leg_fn)
    ann_ret = lsb.annualized_return(result)
    sortino = lsb.sortino_ratio(result)
    beta, alpha_ann = lsb.capm_beta(result, market_df)
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rand_leg_fn = partial(_random_legs_factor, rng=rng, factor_col=TARGET_FACTOR)
        rr = lsb.run_long_short(data, market_df, None, start, end, REBALANCE_DAYS, leg_fn=rand_leg_fn)
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "slippage_bps": slippage_bps,
        "total_return_pct": total_ret_pct,
        "annualized_return_pct": ann_ret * 100,
        "sortino": sortino,
        "beta": beta,
        "annualized_alpha_pct": alpha_ann * 100,
        "random_control_median_equity": float(np.median(random_finals)),
        "random_control_percentile": percentile,
        "n_dates": len(result),
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_f_value_pe")
    market_df = prepare_market_data(market_raw)

    print(f"Loading sample ({len(sample_ids)} requested, cached data/raw/ reused via regime_conditions_value_pe.py's prior run, ZERO new FinMind calls expected)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    n_with_factor = sum(1 for d in data.values() if d[TARGET_FACTOR].notna().any())
    print(f"  {n_with_factor}/{len(data)} names have at least one non-NaN {TARGET_FACTOR} value")

    all_results = []
    for period_label, (start, end) in PERIODS.items():
        for mult in COST_MULTIPLIERS:
            slip = lsb.costmod.DEFAULT_SLIPPAGE_BPS * mult
            print(f"\n=== {period_label} {start}..{end}, cost {mult}x (slippage={slip}bps) ===")
            r = run_one(data, market_df, start, end, slip)
            r["period"] = period_label
            r["cost_multiplier"] = mult
            all_results.append(r)
            print(f"  net total_return={r['total_return_pct']:+.2f}%  ann_return={r['annualized_return_pct']:+.2f}%  "
                  f"Sortino={r['sortino']:.3f}  beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%")
            print(f"  random control ({N_RANDOM_DRAWS} draws): median_equity={r['random_control_median_equity']:.4f}  "
                  f"real_percentile={r['random_control_percentile']:.1f}")

    lsb.SLIPPAGE_BPS = lsb.costmod.DEFAULT_SLIPPAGE_BPS

    print("\n=== SUMMARY ===")
    print("CAVEAT (repeat on purpose, do not drop): PIT status for f_value_pe is inferred from f_value_pb's "
          "single-stock (2330) spot check, NOT independently verified. Below numbers inherit that limitation.")
    for r in all_results:
        print(f"  {r['period']} {r['cost_multiplier']}x: ann_return={r['annualized_return_pct']:+.2f}%  "
              f"beta={r['beta']:+.3f}  alpha={r['annualized_alpha_pct']:+.2f}%  "
              f"Sortino={r['sortino']:.3f}  random_pct={r['random_control_percentile']:.1f}")

    out = pd.DataFrame(all_results)
    out.to_csv("data/deep_dive_f_value_pe.csv", index=False)
    print("\nsaved data/deep_dive_f_value_pe.csv")
    return all_results


if __name__ == "__main__":
    main()
