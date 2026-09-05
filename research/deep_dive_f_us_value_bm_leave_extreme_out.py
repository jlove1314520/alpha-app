"""US-track leave-N-out concentration check for `f_us_value_bm` (round 360's
universe-artifact hypothesis, `TRIALS_LEDGER.md` #128 / `US_LEADS.md` #17).

**Why this is this round's work unit (marathon round 363, US track)**:
round 360 found `f_us_value_bm`'s VAL-period (2020-2024) long-short
ann_return (+121%) is implausibly large for a value-premium factor (HML
literature: ~3-5%/yr), and noted it is near-identical in magnitude to the
*unrelated* `f_us_low_vol` factor's VAL result (#15, +111~113%) on the same
`cached_ticker_ids()` superset -- two unrelated factors converging on the
same extreme magnitude on the same pool strongly suggests the pool itself
(not either factor) is the source, via a handful of 2021-2024 mega-winner
names (PLTR/SOFI/NTLA/VST/STEM/SANA/TLN were named in the log) dominating
whichever decile they land in. Round 360 explicitly deferred confirming
this ("US_LEADS.md#17 (c): 先對現有135檔做leave-one-out集中度檢查（輕量版）
驗證假影假說") to a future round rather than doing it in the same pass --
this script is that follow-up, per `MARATHON_PROTOCOL.md` FDR discipline
(section 2, hash-lock pre-bound criteria) and the general "先確認診斷再
決定下一步怎麼修" principle.

**Method -- pre-registered before running (hash-lock discipline)**:
1. Compute each of the 135 usable names' own VAL-period (2020-12-31
   exclusive .. 2024-12-31 inclusive) buy-and-hold total return from
   `adj_close` (first available price after TRAIN_END vs last available
   price by VAL_END).
2. **Exclusion group = top 10 names by that own-return ranking** (a fixed
   *count*, ~7% of 135, decided before inspecting the actual return values
   -- operationalizes "a handful of extreme winners" without letting the
   observed magnitude distribution influence the cutoff, avoiding the
   threshold-picking p-hacking failure mode `MARATHON_PROTOCOL.md` section 2
   warns about).
3. Re-run the exact same VAL-period, 1x-cost, decile long-short backtest
   (reusing `run_one_value()` from `deep_dive_f_us_value_bm.py` verbatim,
   zero forked math) on (a) the full 135-name sample as a reproducibility
   check against round 360's recorded +121.38%, and (b) the 125-name
   sample with the top-10 removed.
4. **Pre-registered verdict criteria** (decided now, before seeing (b)'s
   number):
   - If (b)'s ann_return drops below +30% (still generous vs the 3-5%
     literature benchmark, chosen to allow ample small-sample-noise
     margin while being far below the original +121%): the "handful of
     names" concentration hypothesis is CONFIRMED as (at least) a major
     contributor -- round 360's FAIL verdict on `f_us_value_bm` stands,
     and this becomes supporting evidence that `cached_ticker_ids()` is not
     a safe universe for any VAL-period long-short backtest without either
     a broader/stratified sample or explicit outlier-name exclusion built
     into the sampling itself (not just this one factor).
   - If (b)'s ann_return remains above +60% even after removing the top 10:
     the concentration hypothesis is REFUTED as the *primary* explanation
     -- the implausible magnitude is more broadly distributed across many
     mid-tier winners in the pool, not a handful of named outliers. This
     would point toward a *systematically* biased pool (not just a few
     contaminating rows) and argue for full universe reconstruction over
     targeted exclusion.
   - Between +30% and +60%: partial effect, report as-is, no strong verdict
     either way -- both mechanisms likely contribute.
   This check does not reopen `f_us_value_bm`'s own FAIL verdict either way
   (round 360's FAIL already stands on non-economic-plausibility grounds
   regardless of mechanism); it exists purely to inform whether future
   `cached_ticker_ids()`-based US-track work needs a universe fix before
   any further factor testing on that pool is trustworthy.

**API cost**: zero new calls -- reuses `load_value_sample()` verbatim
(all cache hits per round 360/#17's own confirmation), same guarantee as
`deep_dive_f_us_value_bm.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from deep_dive_f_us_value_bm import run_one_value
from deep_dive_f_us_low_vol import _load_market_df
from us_factor_ic_value import load_value_sample
from validation import holdout
from validation import us_costs as us_costmod

VAL_START, VAL_END = holdout.TRAIN_END, holdout.VAL_END
N_EXCLUDE = 10  # pre-registered fixed count, see module docstring


def own_val_return(df: pd.DataFrame) -> float | None:
    """單檔股票自己在VAL期的買進持有總報酬（不是long-short回測，是這檔股票
    自己的原始漲跌幅）。用來排名「誰是極端贏家」，跟_decile_legs()用的
    f_us_value_bm排序邏輯完全獨立，避免循環論證（不能用「因子分數高不高」
    來定義「贏家」，那樣會把因子本身的訊號跟極端報酬的雜訊混為一談）。"""
    sub = df[(df["date"] > VAL_START) & (df["date"] <= VAL_END)].sort_values("date")
    if len(sub) < 2:
        return None
    p0 = sub["adj_close"].iloc[0]
    p1 = sub["adj_close"].iloc[-1]
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return None
    return float(p1 / p0 - 1)


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== US leave-N-out concentration check: f_us_value_bm (round 360 artifact hypothesis) ===\n")

    data, drop_reasons = load_value_sample()
    print(f"{len(data)} usable names (round 360 recorded 135; reproducibility check below)\n")

    own_returns = {}
    for ticker, df in data.items():
        r = own_val_return(df)
        if r is not None:
            own_returns[ticker] = r

    ranked = sorted(own_returns.items(), key=lambda t: t[1], reverse=True)
    print(f"Own VAL-period (2020-2024) return ranking, top {N_EXCLUDE + 5} of {len(ranked)}:")
    named_suspects = {"PLTR", "SOFI", "NTLA", "VST", "STEM", "SANA", "TLN"}
    for i, (ticker, r) in enumerate(ranked[:N_EXCLUDE + 5]):
        flag = " <-- round 360 named suspect" if ticker in named_suspects else ""
        marker = " [EXCLUDED]" if i < N_EXCLUDE else ""
        print(f"  {i+1:2d}. {ticker:8s} {r*100:+10.1f}%{marker}{flag}")

    exclude_set = {t for t, _ in ranked[:N_EXCLUDE]}
    overlap = exclude_set & named_suspects
    print(f"\nOverlap between excluded top-{N_EXCLUDE} and round 360's named suspects: "
          f"{sorted(overlap)} ({len(overlap)}/{len(named_suspects)} named suspects captured)")

    market_df, is_spy = _load_market_df()
    calendar = sorted(next(iter(data.values()))["date"].tolist())
    for d in data.values():
        calendar = sorted(set(calendar) | set(d["date"].tolist()))

    slip = us_costmod.DEFAULT_SLIPPAGE_BPS * 1  # 1x cost only, this is a confirmatory check not a full re-deep-dive

    print(f"\n=== (a) baseline: full {len(data)}-name sample, VAL {VAL_START}..{VAL_END}, 1x cost ===")
    r_full = run_one_value(data, calendar, market_df, VAL_START, VAL_END, slip)
    print(f"  ann_return={r_full['annualized_return_pct']:+.2f}%  beta={r_full['beta']:+.3f}  "
          f"random_pct={r_full['random_control_percentile']:.1f}")
    print(f"  (round 360 recorded VAL 1x ann_return=+121.38%, this run should reproduce that closely)")

    data_excl = {t: d for t, d in data.items() if t not in exclude_set}
    print(f"\n=== (b) top-{N_EXCLUDE}-excluded: {len(data_excl)}-name sample, VAL {VAL_START}..{VAL_END}, 1x cost ===")
    r_excl = run_one_value(data_excl, calendar, market_df, VAL_START, VAL_END, slip)
    print(f"  ann_return={r_excl['annualized_return_pct']:+.2f}%  beta={r_excl['beta']:+.3f}  "
          f"random_pct={r_excl['random_control_percentile']:.1f}")

    print("\n=== VERDICT (pre-registered thresholds, see module docstring) ===")
    excl_ann = r_excl["annualized_return_pct"]
    if excl_ann < 30:
        verdict = "CONFIRMED -- concentration in top winners is a major contributor"
    elif excl_ann > 60:
        verdict = "REFUTED as primary mechanism -- bias more broadly distributed across pool"
    else:
        verdict = "PARTIAL -- between thresholds, both mechanisms likely contribute"
    print(f"Excluding top-{N_EXCLUDE} own-return winners: ann_return {r_full['annualized_return_pct']:+.2f}% "
          f"-> {excl_ann:+.2f}%")
    print(f"Verdict: {verdict}")

    out = pd.DataFrame([
        {**r_full, "variant": "full_135"},
        {**r_excl, "variant": f"excl_top{N_EXCLUDE}"},
    ])
    out.to_csv("data/deep_dive_f_us_value_bm_leave_extreme_out.csv", index=False)
    print("\nsaved data/deep_dive_f_us_value_bm_leave_extreme_out.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return {"full": r_full, "excl": r_excl, "verdict": verdict, "overlap": sorted(overlap)}


if __name__ == "__main__":
    main()
