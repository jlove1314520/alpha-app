"""Cheap-gate testing for time-series futures strategies (TX continuous series).

MARATHON_PROTOCOL.md 1a: for a *strategy* hypothesis, the cheap gate is
"樣本內對隨機控制組" -- in-sample real strategy vs a randomized control,
no train/val split or walk-forward needed yet. This module is the futures
analog of factor_ic.py's shuffle-null test, adapted for a single continuous
price series instead of a stock cross-section.

Control construction: permute the *order* of the daily position array (not
regenerate from scratch) and re-pair it with the same realized return
series. This preserves the real strategy's activity level (fraction of days
long/short/flat, exact position magnitudes used) while destroying whatever
timing edge the signal has -- same spirit as factor_ic.py shuffling which
stock got which factor value while keeping the return pairing intact.

Two hypotheses tested in the first round (FUT_MARATHON_STATE.md 2026-08-24
"下一輪建議工作單位" #1, both suggested as good starting candidates), both
FAILED (TRIALS_LEDGER.md #18/#19, FUT_LEADS.md #1/#2):
  - fut_trend_multi_tf: multi-timeframe trend (10/20/60-day momentum sign
    vote), daily rebalance.
  - fut_donchian_breakout: 20-day Donchian channel breakout, stateful
    (holds previous position when neither channel is broken).

Second round (marathon round 33, following FUT_MARATHON_STATE.md's
suggestion to try "均線系統" or "波動regime過濾" next rather than re-test
the same two failed signals):
  - fut_ma_crossover_20_60: classic dual simple-moving-average crossover
    (SMA20 vs SMA60), a distinct signal family from both momentum-vote and
    channel-breakout (crossover systems trade off SMA smoothing lag against
    Donchian's raw-price responsiveness -- different bias/variance
    tradeoff, not a parameter retune of either prior candidate).
  - fut_vol_regime_trend: the already-failed fut_trend_multi_tf signal,
    but gated to only take positions when 20-day realized volatility is
    below its own trailing median (i.e. only trade the trend signal in
    "calm" regimes, flat otherwise). This is a structural variant per
    MARATHON_PROTOCOL.md's explicit suggestion ("對已測訊號加上明確不同的
    結構性變體...例如只在高波動期間交易"), not a parameter-tuning rescue
    of the failed signal -- it changes *when* the strategy is allowed to
    act, not the signal's internal parameters, and tests the distinct
    "波動regime過濾" hypothesis family from MARATHON_PROTOCOL.md 第3節.

Third round (marathon round 36, following FUT_MARATHON_STATE.md's explicit
post-mortem after four straight FAILs: "不要再對 fut_trend_multi_tf 類趨勢
訊號做regime過濾類變體...改試日內均值回歸...期現價差...三大法人期貨部位/
未平倉量變化...或星期效應/盤別效應"). Two hypotheses from genuinely
different mechanism families, not further variants of price-only trend:
  - fut_oi_price_confirm: chip-based (未平倉量變化), not price-only. Uses
    open_interest (already present in build_continuous_series() output --
    no new data source needed). Classic OI-price relationship reading: a
    price move confirmed by rising open interest (net new capital
    committing to that direction) is read as more informationally credible
    than the same move on falling OI (which looks like short-covering /
    long-liquidation, i.e. existing positions closing rather than new
    conviction entering). Signal: take yesterday's 1-day price direction
    only when today's 5-day open-interest change is positive; flat
    otherwise. This is a *filter on OI*, not a price-momentum signal in
    disguise -- the raw direction input is the noisiest possible one
    (1-day sign, no smoothing), deliberately so the OI filter is doing all
    the discriminating work being tested, not multi-day trend estimation
    which four prior FAILs already ruled unhelpful for this direction
    input.
  - fut_weekday_effect: calendar-based (星期效應), not price/OI-based at
    all. Fixed rule sourced from the classic "weekend effect" literature
    (French 1980: US equity Monday returns average significantly below
    other weekdays, commonly attributed to negative weekend news
    accumulating and being priced in at Monday's open) -- short Monday,
    long Tuesday-Friday. This is a literature-sourced *fixed* rule, not
    fit to this sample (MARATHON_PROTOCOL.md 第3節: 查到的方法一定要重新
    走驗證關卡，不可照抄，但可以當假說來源) -- so there is no in-sample
    day-of-week average computed from this data and used to pick the
    rule; the rule is asserted a priori from outside literature, exactly
    as intended by that protocol clause.

Both use adj_close from continuous_contract.build_continuous_series(),
which FUT_MARATHON_STATE.md (2026-08-24, drift probe finding) confirms is
safe for these short/medium lookback windows (10-60 days is well within the
"short/medium lookback" the drift finding cleared -- nowhere near the
"跨十幾次以上轉倉" long-lookback danger zone flagged for future caution).

This is a CHEAP gate only: in-sample, no walk-forward, no cost sensitivity,
no economic-explanation writeup required yet (MARATHON_PROTOCOL.md 1a vs
1b). A CHEAP_PASS here just queues the hypothesis for deep-dive.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from continuous_contract import build_continuous_series
from validation import holdout

N_SHUFFLES = 200  # cheap-gate resolution (0.5% steps); factor_ic.py uses 1000 for its
# deep-gate-adjacent shuffle test -- this is deliberately coarser since 1a is meant to be
# a fast first filter, not the final statistical word (MARATHON_PROTOCOL.md 1a vs 1b).
SHUFFLE_SEED = 20260824


@dataclass
class CheapGateResult:
    name: str
    n_days: int
    real_terminal_equity: float
    random_median_equity: float
    percentile: float  # where real sits vs the N_SHUFFLES random permutations, 0-100
    passes: bool  # percentile >= 90, this run's single-test bar before Bonferroni;
    # TRIALS_LEDGER.md records the raw percentile so cumulative correction can be
    # applied later regardless of this flag


def _load_series() -> pd.DataFrame:
    series, skipped = build_continuous_series()
    if skipped:
        print(f"  [note] {len(skipped)} rollover events had no clean adjustment ratio "
              f"(continuous_contract.py known gap, see its docstring) -- proceeding, "
              f"raw price used unadjusted for those transitions")
    series = series.sort_values("date").reset_index(drop=True)
    series["ret"] = series["adj_close"].pct_change()
    return series


def _permutation_test(name: str, position: pd.Series, ret: pd.Series) -> CheapGateResult:
    """position[t] is decided using data available through day t (no lookahead
    baked in by the caller); this function itself shifts it by 1 so the
    trade only captures ret[t+1] onward, i.e. position.shift(1) * ret."""
    valid = position.notna() & ret.notna()
    pos = position[valid].reset_index(drop=True)
    r = ret[valid].reset_index(drop=True)

    strat_ret = pos.shift(1).fillna(0.0) * r
    real_equity = float((1.0 + strat_ret).cumprod().iloc[-1])

    rng = np.random.default_rng(SHUFFLE_SEED)
    pos_arr = pos.to_numpy()
    r_arr = r.to_numpy()
    random_terminals = np.empty(N_SHUFFLES)
    for i in range(N_SHUFFLES):
        shuffled_pos = rng.permutation(pos_arr)
        shuffled_strat_ret = np.roll(shuffled_pos, 1)
        shuffled_strat_ret[0] = 0.0
        shuffled_strat_ret = shuffled_strat_ret * r_arr
        random_terminals[i] = np.prod(1.0 + shuffled_strat_ret)

    percentile = float((random_terminals < real_equity).mean() * 100.0)
    return CheapGateResult(
        name=name,
        n_days=len(pos),
        real_terminal_equity=real_equity,
        random_median_equity=float(np.median(random_terminals)),
        percentile=percentile,
        passes=percentile >= 90.0,
    )


def hyp_trend_multi_tf(series: pd.DataFrame) -> CheapGateResult:
    close = series["adj_close"]
    scores = pd.DataFrame({
        f"mom_{n}": close.pct_change(n) for n in (10, 20, 60)
    })
    vote = np.sign(scores).sum(axis=1)  # -3..+3
    position = np.sign(vote)  # -1/0/+1, majority direction across the 3 windows
    return _permutation_test("fut_trend_multi_tf", position, series["ret"])


def hyp_donchian_breakout(series: pd.DataFrame, window: int = 20) -> CheapGateResult:
    close = series["adj_close"]
    upper = close.rolling(window).max().shift(1)  # prior N days, excludes today (no lookahead)
    lower = close.rolling(window).min().shift(1)
    raw_signal = pd.Series(np.nan, index=close.index)
    raw_signal[close > upper] = 1.0
    raw_signal[close < lower] = -1.0
    position = raw_signal.ffill().fillna(0.0)  # stateful: hold previous position
    # between breakouts, classic Donchian behavior
    return _permutation_test(f"fut_donchian_breakout_{window}", position, series["ret"])


def hyp_ma_crossover(series: pd.DataFrame, fast: int = 20, slow: int = 60) -> CheapGateResult:
    close = series["adj_close"]
    sma_fast = close.rolling(fast).mean()
    sma_slow = close.rolling(slow).mean()
    position = np.sign(sma_fast - sma_slow)  # -1/0/+1, no shift needed here since
    # _permutation_test itself shifts position by 1 day before pairing with returns
    return _permutation_test(f"fut_ma_crossover_{fast}_{slow}", position, series["ret"])


def hyp_vol_regime_trend(series: pd.DataFrame, vol_window: int = 20) -> CheapGateResult:
    close = series["adj_close"]
    ret = series["ret"]
    scores = pd.DataFrame({
        f"mom_{n}": close.pct_change(n) for n in (10, 20, 60)
    })
    vote = np.sign(scores).sum(axis=1)
    raw_trend_position = np.sign(vote)

    realized_vol = ret.rolling(vol_window).std().shift(1)  # trailing, no lookahead
    trailing_median_vol = realized_vol.expanding(min_periods=vol_window * 2).median()
    # "calm regime" = today's trailing realized vol is below its own expanding
    # median-to-date -- avoids any full-sample lookahead in the regime threshold
    calm_regime = realized_vol < trailing_median_vol

    position = raw_trend_position.where(calm_regime, 0.0)
    return _permutation_test("fut_vol_regime_trend", position, ret)


def hyp_oi_price_confirm(series: pd.DataFrame, oi_window: int = 5) -> CheapGateResult:
    close = series["adj_close"]
    raw_direction = np.sign(close.diff(1))  # noisiest possible price input (1-day),
    # deliberate: the OI filter below is what's being tested, not multi-day trend
    # estimation (four prior FAILs already covered that family)
    oi_rising = series["open_interest"].diff(oi_window) > 0
    position = raw_direction.where(oi_rising, 0.0)
    return _permutation_test(f"fut_oi_price_confirm_{oi_window}d", position, series["ret"])


def hyp_weekday_effect(series: pd.DataFrame) -> CheapGateResult:
    weekday = pd.to_datetime(series["date"]).dt.dayofweek  # Monday=0
    position = pd.Series(np.where(weekday == 0, -1.0, 1.0), index=series.index)
    return _permutation_test("fut_weekday_effect", position, series["ret"])


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"

    series = _load_series()
    print(f"loaded continuous series: {len(series)} rows, "
          f"{series['date'].min().date()} .. {series['date'].max().date()}")

    results = [
        hyp_oi_price_confirm(series, oi_window=5),
        hyp_weekday_effect(series),
    ]

    for r in results:
        print(f"\n=== {r.name} ===")
        print(f"  n_days={r.n_days}")
        print(f"  real_terminal_equity={r.real_terminal_equity:.4f} "
              f"(i.e. {(r.real_terminal_equity - 1) * 100:+.1f}% cumulative, no costs)")
        print(f"  random_median_equity={r.random_median_equity:.4f} "
              f"(n={N_SHUFFLES} permutations)")
        print(f"  percentile={r.percentile:.1f}  -> {'CHEAP_PASS' if r.passes else 'FAIL'} "
              f"(bar: >=90.0, single-test, pre-Bonferroni)")


if __name__ == "__main__":
    main()
