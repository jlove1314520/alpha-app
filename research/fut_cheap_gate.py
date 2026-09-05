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

Fourth round (marathon round 42, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1 after round 39's infra work confirmed
TaiwanFuturesInstitutionalInvestors is usable): directional institutional
net futures positioning (三大法人期貨部位), distinct from the
non-directional `open_interest` column already tested in
fut_oi_price_confirm (#5, FAILed) -- this dataset carries LONG vs SHORT
balance separately per category (外資/投信/自營商), so a net-long-minus-
net-short signed quantity can be built, which open_interest alone cannot
express. Only 外資 (foreign institutional investors) tested this round --
they carry by far the largest and most liquid TX futures book of the three
categories and are the category most commonly cited in Taiwan retail
trading folklore as the "smart money" whose net positioning is worth
following ("跟著外資期貨部位") -- 投信/自營商 variants are explicitly left
for a later round rather than tested all three at once (MARATHON_PROTOCOL.md
1a: max 2-3 hypotheses per round, and testing one category cleanly first
avoids conflating "does institutional positioning have signal" with "which
category" in a single round).

**Known sample-size caveat (carried over from FUT_MARATHON_STATE.md, do not
re-derive): TaiwanFuturesInstitutionalInvestors only has data from
2018-06-05 onward (confirmed by fut_probe_institutional_positions.py, round
39), not the full 2000-2024 history the price-only hypotheses above used.
The merge in _load_institutional_net_position() is an inner join so this
restriction happens automatically -- these two hypotheses run on ~1605 days,
not ~6185. This is a materially smaller sample than the six prior FAILs, so
the same 90th-percentile bar carries less statistical power here; a FAIL on
this smaller sample is weaker evidence of "no effect" than a FAIL on the
full-history sample, and a PASS should be read with that caveat too.**

  - fut_inst_foreign_net_position_sign: position[t] = sign(foreign
    investors' net open-interest balance on day t), i.e. go long TX when
    foreign investors are net long futures, short when net short. This is
    the *level* (contemporaneous positioning), not a change -- the classic
    "smart money" reading: foreign institutional investors are presumed to
    have superior information/capital relative to retail, so their
    directional book itself (not just its recent change) may forecast
    subsequent price direction (informed-trading hypothesis).
  - fut_inst_foreign_net_position_change_5d: position[t] = sign(5-day
    change in foreign investors' net open-interest balance), i.e. trade in
    the direction institutional positioning has been *moving* over the
    trailing week, regardless of its absolute level. Tests a distinct
    "positioning momentum" mechanism from the level-based hypothesis above
    -- a foreign book that is heavily net-short but *reducing* that short
    (moving toward neutral) is bullish here even though the level-based
    signal above would still read bearish; separates "which sign is
    correct" (level) from "which direction of change is informative"
    (momentum in positioning) as two independently falsifiable readings of
    the same underlying data.

Both use adj_close from continuous_contract.build_continuous_series(),
which FUT_MARATHON_STATE.md (2026-08-24, drift probe finding) confirms is
safe for these short/medium lookback windows (10-60 days is well within the
"short/medium lookback" the drift finding cleared -- nowhere near the
"跨十幾次以上轉倉" long-lookback danger zone flagged for future caution).

Fifth round (marathon round 44, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1: "三大法人期貨部位家族還有兩個類別沒測（投信、自營商）"):
only 投信 (securities investment trust) tested this round, not both --
MARATHON_PROTOCOL.md 1a caps a round at 2-3 hypotheses, and testing one
new category cleanly (sign + change_5d, same two-hypothesis pattern as
round 42's 外資 batch) keeps this round's batch size consistent with the
prior precedent rather than quadrupling it by doing 投信+自營商 together.
自營商 (proprietary dealers) is left for a later round.
  - fut_inst_trust_net_position_sign / _change_5d: same construction as
    the 外資 pair above (_load_institutional_net_position(category="投信")),
    same level-vs-momentum distinction. Economic framing differs from
    外資: 投信 (mutual-fund managers) are a much smaller book than 外資 and
    are sometimes described in Taiwan market commentary as more prone to
    herding/momentum-chasing behavior (following recent price trends into
    their positioning) rather than acting on independent information --
    this is an *alternative*, not confirmatory, hypothesis to 外資's
    "informed trading" framing, i.e. if 投信 positioning has any
    forecasting power at all, the a priori economic story for *why* would
    likely be different (trend-following/crowd behavior vs proprietary
    information), which is exactly why this counts as testing a distinct
    mechanism, not a parameter retune of the 外資 pair.

Sixth round (marathon round 48, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1: "三大法人期貨部位家族最後一個類別沒測（自營商）"):
自營商 (proprietary dealers, i.e. brokerage firms' own trading desks)
tested, completing all three categories (外資/投信/自營商) of this
signal family.
  - fut_inst_dealer_net_position_sign / _change_5d: same construction and
    same level-vs-momentum distinction as the two prior category pairs
    (_load_institutional_net_position(category="自營商")). Economic framing
    differs from both prior categories: 自營商 book activity in Taiwan is
    widely understood to be dominated by hedging flow against options/
    warrant issuance (market-making desks delta-hedging their derivatives
    book, not directional conviction bets), so if this category's net
    positioning has any forecasting power at all, the a priori story would
    most likely be "mechanical hedging flow happens to correlate with
    market stress/direction" rather than either 外資's informed-trading
    story or 投信's herding story -- a third, structurally distinct
    mechanism, not a parameter retune of the other two category pairs.

This is a CHEAP gate only: in-sample, no walk-forward, no cost sensitivity,
no economic-explanation writeup required yet (MARATHON_PROTOCOL.md 1a vs
1b). A CHEAP_PASS here just queues the hypothesis for deep-dive.

Eighth round (marathon round 72, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1 after round 69 finished the basis-family infra --
`fut_basis_series.py`'s build_basis_series() gives a clean 100%-coverage
basis_pct series): first batch of basis (期現價差) hypotheses, a genuinely
new mechanism family (carry/convergence) distinct from every prior family
tested (price-only trend, chip/OI, institutional positioning, calendar,
intraday microstructure). Two hypotheses, level vs. change-momentum, same
two-hypothesis-per-family pattern as institutional positioning (round 42
onward) and intraday gap (round 54):
  - fut_basis_carry: position[t] = -sign(basis_pct[t]), i.e. LONG when
    futures trade at a discount to spot (basis_pct < 0), SHORT when at a
    premium (basis_pct > 0). Economic story: classic futures "roll yield" /
    cost-of-carry convergence -- a futures contract's price converges to
    spot as expiry approaches (holding spot roughly flat), so a discount
    mechanically pulls the futures price UP toward spot over time (positive
    return for a long position), while a premium pulls it DOWN (negative
    return for a long position). This is the standard "buy backwardation,
    sell contango" carry framing from the commodity-futures literature
    (Keynes's normal backwardation theory), applied here to an equity index
    future where the carry driver is expected dividends net of financing
    cost rather than storage cost. round 69's basis distribution finding
    (mean -0.2%, discount 65.7% of days) is consistent with TX historically
    trading at a modest average discount, which this hypothesis interprets
    as a *persistent* carry signal, not noise.
  - fut_basis_change_momentum_5d: position[t] = sign(basis_pct[t] -
    basis_pct[t-5]), i.e. trade in the direction the basis has been MOVING
    over the trailing week, regardless of its absolute level. Distinct
    mechanism from the level/carry hypothesis above: a basis that is deeply
    discounted but *narrowing* (moving toward zero/premium) signals here as
    bullish even though the level-based carry signal above would still read
    bullish too in that specific case, but a basis that is near-zero and
    *widening toward discount* signals bearish here while the level signal
    would be near-neutral -- the two hypotheses diverge whenever the basis
    is moving, which is most of the time. Economic framing: a widening
    discount (or narrowing premium) plausibly reflects deteriorating
    forward-looking sentiment among futures-market participants (who are
    more likely to be leveraged/informed traders than the cash-equity
    crowd) relative to the spot market, i.e. the basis *change* carries
    incremental information the static level does not -- same
    "positioning momentum vs. positioning level" logic already applied to
    the institutional-investors family (round 42's foreign sign vs.
    change_5d pair), transplanted to basis instead of net position.

Seventh round (marathon round 54, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1(a) after the 三大法人期貨部位 family closed out with no
survivors: switch to a genuinely new mechanism family, 日內均值回歸, first
confirming whether the daily bars even support an "intraday" decomposition
at all -- they do: build_continuous_series() already carries
adj_open/adj_max/adj_min/adj_close, so overnight (yesterday's adj_close to
today's adj_open) and intraday (today's adj_open to today's adj_close) can
be split out with zero new data source. Foundation check (done ad hoc
before writing this function, not a separate probe script since it's a
one-line describe() call, not a multi-step investigation like the earlier
地基 probes): 6185 rows, only 1 NaN (the very first day's overnight_gap,
expected -- no prior close to compare against), no non-positive
open/close, overnight_gap std ~0.89%, intraday_ret std ~1.16%, both
economically sane magnitudes for a daily index future.
  - fut_intraday_gap_reversal: position[t] = -sign(overnight_gap[t]),
    i.e. fade the overnight gap -- go short for the day session after a
    gap up at the open, long after a gap down, flat on an exact-zero gap.
    Traded against intraday_ret[t] (same day, NOT shifted -- the gap is
    fully observable at today's open, before the day's own intraday
    return realizes, so no lookahead; this is a deliberately different
    pairing convention from every price/OI/institutional hypothesis above,
    which all decide on day t and trade day t+1's close-to-close return).
    Economic story this is testing: opening-auction overreaction --
    order-imbalance-driven gaps (news, overnight index futures/ADR moves,
    or simply an overnight order backlog clearing at the open) are
    commonly hypothesized to overshoot the "true" new price on thin
    opening liquidity, with intraday trading arbitraging some of that
    overshoot back out by the close (a distinct microstructure story from
    every trend/momentum/carry mechanism tested so far in this file).
    RESULT: FAILED badly (percentile=8.0, i.e. 92% of random permutations
    beat the real reversal strategy) -- this is itself informative, not
    just a null result: it points toward the *opposite* mechanism (gap
    continuation) being worth testing as a separate hypothesis this same
    round, per MARATHON_PROTOCOL.md's 2-3-hypotheses-per-round allowance --
    this is NOT "調參數硬救" the failed reversal signal (no parameter of
    the reversal signal was retuned), it is testing a distinct a priori
    economic story (order-flow persistence / gap continuation, the
    standard alternative to opening-overreaction in the market
    microstructure literature) that happens to be the sign-flip of the
    first signal's *position*, decided BEFORE seeing this round's second
    result, not chosen because it happened to win.
  - fut_intraday_gap_continuation: position[t] = +sign(overnight_gap[t]),
    i.e. trade WITH the gap for the day session -- long after a gap up,
    short after a gap down. Economic story: overnight gaps often reflect
    genuine new information (macro news, overnight US market moves via
    ADRs/index futures that Taiwan's own index cannot trade against until
    its own open) that continues to be digested/priced in through the
    day's session, rather than being pure noise that reverts -- the
    standard "informed overnight order flow" alternative to the
    overreaction story above.

Ninth round (marathon round 80, following FUT_MARATHON_STATE.md's "下一輪
建議工作單位" #1 after round 75's deep-dive found fut_basis_carry FAILed
out-of-sample: the third and last basis mechanism from
MARATHON_PROTOCOL.md 第3節's "期現價差" entry, after level/carry (round 72,
CHEAP_PASS but round-75 deep-dive FAIL) and change-momentum (round 72,
FAIL) -- basis *mean reversion around its own trailing average*, a
genuinely distinct construction from both prior basis hypotheses:
  - fut_basis_mean_reversion_60d: position[t] = -sign(basis_pct[t] -
    trailing_60d_mean(basis_pct)[t]), i.e. LONG when today's basis is more
    discounted than its own trailing 60-day average (betting the basis
    reverts back UP toward its recent norm), SHORT when today's basis is
    more premium-heavy than its own trailing average. This differs from
    fut_basis_carry (which trades the level relative to zero, i.e. always
    long on any discount regardless of how "normal" that discount is) and
    from fut_basis_change_momentum_5d (which trades the direction of the
    most recent 5-day move, not deviation from a longer-run norm).
    Economic story: the basis's long-run average level already reflects
    the structural cost-of-carry driver (expected dividend yield net of
    financing cost, which is fairly stable), so temporary deviations from
    that structural average more plausibly reflect transient supply/
    demand imbalances in the futures market itself (e.g. a wave of
    hedging flow or speculative positioning temporarily pushing the
    futures price away from its fair-value spread to spot) that should
    unwind as that flow normalizes -- a standard mean-reversion-around-a-
    slow-moving-equilibrium story, distinct from both the carry-level and
    carry-momentum framings already tested. The 60-day window mirrors the
    slowest lookback already used elsewhere in this file (the 60-day leg
    of hyp_trend_multi_tf's momentum vote and hyp_vol_regime_trend's
    realized-vol window), not a value searched for on this specific
    series.

Tenth round (marathon round 98, following FUT_MARATHON_STATE.md's "下一輪
建議" #1 after round 93's infra work confirmed build_continuous_series(
session="after_market") is ready and cross-validated -- basis family fully
closed (round 80/86 above), first hypotheses from the genuinely new 盤別效應
(session-effect) family: does the night session's own price discovery
(round 91 confirmed night session T PRECEDES day session T within the same
date label, round 90 confirmed rollover events are exactly synchronized
between the two sessions) forecast the day session's own subsequent
intraday move? Both directions tested this round, paired precedent from
hyp_intraday_gap_reversal/continuation (#14/#15):
  - fut_night_session_momentum / fut_night_session_reversal: position[T] =
    +/-sign(night session T's own open-to-close return), traded against
    day session T's own open-to-close return, same-day pairing (not a
    cross-day shift -- _permutation_test_same_day, same convention as the
    overnight-gap hypotheses). Economic story if momentum wins: night
    session price discovery reflects real new information (overnight news,
    US market/ADR moves that TX itself cannot trade on before the night
    session opens) that day session continues to digest -- the same
    "underreaction at reopen" story already used for
    hyp_intraday_gap_continuation, but here testing the night session's OWN
    realized move rather than the day-to-day open/close gap (a materially
    different, more direct measurement of what happened during the
    overnight window, now that TX actually trades through most of it).
    Economic story if reversal wins instead: night session volume/liquidity
    is thinner than day session (well-documented TX market structure), so
    night session price moves may overshoot on temporary imbalance and mean-
    revert once day session's deeper liquidity reopens price discovery --
    the classic thin-market-overreaction story.

Eleventh round (marathon round 104, following round 98's "下一輪建議" (a),
first of the "two gap constructs" it flagged as untested: this round covers
the day_close(T-1) -> night_open(T) gap (round 98 already tested night
session's own FULL realized return, night_ret; this is a materially
different measurement -- the jump that happens the instant night session
opens, before any of night session's own price discovery occurs). The
second gap construct (night_close(T) -> day_open(T)) is deliberately left
for a future round, same "test 2-3 hypotheses, then stop" discipline as
every prior round in this file. Direct structural analog of
hyp_intraday_gap_reversal/continuation (#14/#15, which used
day_close(T-1) -> day_open(T) predicting day's own intraday_ret) -- same
construction, just substituting the night session as the "session that
opens after the gap" instead of the day session:
  - fut_night_gap_reversal / fut_night_gap_continuation: position[T] =
    -/+sign(night_open(T) / day_close(T-1) - 1), traded against night
    session T's own open-to-close return (night_ret, reusing
    _load_session_pair()'s existing column, not day_ret -- the gap being
    tested here leads INTO night session, so the session whose own move it
    should predict is night session itself, not day session). Same-day
    pairing (_permutation_test_same_day): the gap is realized at
    night_open(T) and the outcome is night_close(T), both carry the same
    date label T (round 63 timing). Economic story if continuation wins:
    the day_close(T-1)->night_open(T) gap is TX's first opportunity to
    react to news that accumulated since day session T-1 closed (a shorter,
    more concentrated news-accumulation window than a full overnight gap
    into the next day session, since night session opens same-day-evening);
    if the initial reaction at night_open is directionally correct but
    incomplete, night session's own subsequent move should continue in the
    same direction as trading continues through the thin overnight session
    -- an underreaction-at-reopen story, structurally the same logic already
    used for hyp_intraday_gap_continuation (#15) and the night-session-
    momentum story (round 98), but applied to a different pair of prices.
    Economic story if reversal wins instead: the gap itself may overshoot
    because night session's opening liquidity is thinner than even night
    session's own steady-state liquidity (the very first print after a
    liquidity gap), making the initial jump a noisy overreaction that
    reverts as more participants join through the rest of the night
    session -- the standard opening-overreaction story.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import finmind_client
from continuous_contract import FULL_HISTORY_START, FULL_HISTORY_END, build_continuous_series
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


def _permutation_test_same_day(name: str, position: pd.Series, ret: pd.Series) -> CheapGateResult:
    """Same spirit as _permutation_test, but for signals decided and traded
    within the SAME day (no cross-day shift) -- e.g. an overnight-gap signal
    observed at today's open, traded against today's own open-to-close
    return. Using _permutation_test here would silently introduce a
    spurious 1-day lag between an already-same-day-paired signal/return,
    which is wrong for this pairing convention, not just a stylistic
    choice -- hence a dedicated function rather than reusing the shifted
    one."""
    valid = position.notna() & ret.notna()
    pos = position[valid].reset_index(drop=True)
    r = ret[valid].reset_index(drop=True)

    strat_ret = pos * r
    real_equity = float((1.0 + strat_ret).cumprod().iloc[-1])

    rng = np.random.default_rng(SHUFFLE_SEED)
    pos_arr = pos.to_numpy()
    r_arr = r.to_numpy()
    random_terminals = np.empty(N_SHUFFLES)
    for i in range(N_SHUFFLES):
        shuffled_pos = rng.permutation(pos_arr)
        random_terminals[i] = np.prod(1.0 + shuffled_pos * r_arr)

    percentile = float((random_terminals < real_equity).mean() * 100.0)
    return CheapGateResult(
        name=name,
        n_days=len(pos),
        real_terminal_equity=real_equity,
        random_median_equity=float(np.median(random_terminals)),
        percentile=percentile,
        passes=percentile >= 90.0,
    )


def hyp_intraday_gap_reversal(series: pd.DataFrame) -> CheapGateResult:
    overnight_gap = series["adj_open"] / series["adj_close"].shift(1) - 1.0
    intraday_ret = series["adj_close"] / series["adj_open"] - 1.0
    position = -np.sign(overnight_gap)  # fade the gap: short after gap-up, long after gap-down
    return _permutation_test_same_day("fut_intraday_gap_reversal", position, intraday_ret)


def hyp_intraday_gap_continuation(series: pd.DataFrame) -> CheapGateResult:
    overnight_gap = series["adj_open"] / series["adj_close"].shift(1) - 1.0
    intraday_ret = series["adj_close"] / series["adj_open"] - 1.0
    position = np.sign(overnight_gap)  # trade with the gap: long after gap-up, short after gap-down
    return _permutation_test_same_day("fut_intraday_gap_continuation", position, intraday_ret)


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


def hyp_oi_price_confirm_graded(series: pd.DataFrame, oi_window: int = 5, vol_window: int = 60) -> CheapGateResult:
    """Round 385's follow-up to FUT_MARATHON_STATE.md round 372's "下一步(b)":
    the binary 0/1 oi filter (hyp_oi_price_confirm, TRIALS_LEDGER #22, FAIL
    at percentile 62.0) discards all information in *how much* OI rose -- a
    huge OI build plausibly carries more "genuine new money confirms this
    move" signal than a barely-positive OI tick, but the binary gate treats
    them identically. This variant replaces the 0/1 gate with a continuous
    conviction weight, scaling the same underlying hypothesis rather than
    changing it (isolating the OI encoding as the only variable, same
    discipline as round 362's combo trials).

    raw_direction (1-day price sign) is deliberately unchanged from the
    binary version -- still the noisiest possible price input, since the OI
    filter is what's being tested here, not price-direction estimation.

    Construction: conviction = clip(oi_chg / trailing_std, 0, 2) / 2, i.e.
    an OI move at or above 2 trailing standard deviations gets full
    conviction (weight 1.0), a barely-positive OI move gets near-zero
    weight, and a falling/flat OI (oi_chg <= 0) gets weight 0 exactly like
    the binary version's oi_rising=False branch -- the two constructions
    agree exactly on the "OI not rising" case and only differ on how the
    "OI rising" case is weighted. trailing_std = oi_chg.rolling(vol_window)
    .std() is a purely trailing (no future data) normalization of that
    day's OI-change magnitude relative to its own recent history -- not a
    forecast, just causal unit-scaling so the clip threshold means the same
    thing across different OI-turnover regimes.

    Pre-registered (hash-locked) pass criterion: percentile >= 90.0, same
    bar as every other hyp_* in this file. If this also lands near the
    binary version's 62.0, that would suggest the OI-confirm family itself
    (not just the binary encoding) lacks edge in this construction, closing
    off round 372's option (b) and leaving only (c) [deprioritize FUT] as a
    live option pending a genuinely new FUT hypothesis family."""
    close = series["adj_close"]
    raw_direction = np.sign(close.diff(1))
    oi_chg = series["open_interest"].diff(oi_window)
    trailing_std = oi_chg.rolling(vol_window).std()
    conviction = (oi_chg / trailing_std).clip(lower=0.0, upper=2.0) / 2.0
    position = raw_direction * conviction
    return _permutation_test(f"fut_oi_price_confirm_graded_{oi_window}d", position, series["ret"])


def hyp_weekday_effect(series: pd.DataFrame) -> CheapGateResult:
    weekday = pd.to_datetime(series["date"]).dt.dayofweek  # Monday=0
    position = pd.Series(np.where(weekday == 0, -1.0, 1.0), index=series.index)
    return _permutation_test("fut_weekday_effect", position, series["ret"])


def _load_institutional_net_position(series: pd.DataFrame, category: str = "外資") -> pd.DataFrame:
    """Inner-join `series` (from build_continuous_series()) with the signed net
    futures position of a single TaiwanFuturesInstitutionalInvestors category.

    net_position = long_open_interest_balance_volume - short_open_interest_balance_volume,
    positive = net long, negative = net short. This is the directional quantity
    that open_interest alone (used in fut_oi_price_confirm, #22, FAIL) cannot
    express -- OI is unsigned, it counts total contracts outstanding regardless
    of which side, whereas the institutional-investors dataset separately
    reports each category's long and short balances.

    Inner join is deliberate, not an oversight: TaiwanFuturesInstitutionalInvestors
    only has data from 2018-06-05 onward (fut_probe_institutional_positions.py,
    round 39), so this naturally restricts the merged sample to ~1605 days --
    the caller must not assume the full 2000-2024 history is available here.
    """
    inst = finmind_client.load_dev(
        dataset="TaiwanFuturesInstitutionalInvestors",
        data_id="TX",
        start_date=FULL_HISTORY_START,
        end_date=FULL_HISTORY_END,
    )
    cat = inst[inst["institutional_investors"] == category].copy()
    cat["date"] = pd.to_datetime(cat["date"])
    cat["net_position"] = (
        cat["long_open_interest_balance_volume"] - cat["short_open_interest_balance_volume"]
    )
    cat = cat[["date", "net_position"]].sort_values("date").reset_index(drop=True)

    merged = series.merge(cat, on="date", how="inner").sort_values("date").reset_index(drop=True)
    return merged


def hyp_inst_foreign_net_position_sign(series: pd.DataFrame) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="外資")
    position = np.sign(merged["net_position"])
    return _permutation_test("fut_inst_foreign_net_position_sign", position, merged["ret"])


def hyp_inst_foreign_net_position_change_5d(series: pd.DataFrame, window: int = 5) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="外資")
    position = np.sign(merged["net_position"].diff(window))
    return _permutation_test(
        f"fut_inst_foreign_net_position_change_{window}d", position, merged["ret"]
    )


def hyp_inst_trust_net_position_sign(series: pd.DataFrame) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="投信")
    position = np.sign(merged["net_position"])
    return _permutation_test("fut_inst_trust_net_position_sign", position, merged["ret"])


def hyp_inst_trust_net_position_change_5d(series: pd.DataFrame, window: int = 5) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="投信")
    position = np.sign(merged["net_position"].diff(window))
    return _permutation_test(
        f"fut_inst_trust_net_position_change_{window}d", position, merged["ret"]
    )


def hyp_inst_dealer_net_position_sign(series: pd.DataFrame) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="自營商")
    position = np.sign(merged["net_position"])
    return _permutation_test("fut_inst_dealer_net_position_sign", position, merged["ret"])


def hyp_inst_dealer_net_position_change_5d(series: pd.DataFrame, window: int = 5) -> CheapGateResult:
    merged = _load_institutional_net_position(series, category="自營商")
    position = np.sign(merged["net_position"].diff(window))
    return _permutation_test(
        f"fut_inst_dealer_net_position_change_{window}d", position, merged["ret"]
    )


def _load_basis(series: pd.DataFrame) -> pd.DataFrame:
    """Inner-join `series` (from build_continuous_series(), already has 'ret')
    with the basis_pct series from fut_basis_series.build_basis_series().

    Round 69 already verified 100% date-calendar coverage between the two
    (6185/6185 rows both sides), so this inner join is not expected to drop
    any rows -- but it is still an inner join, not an assumed-safe direct
    column assignment, in case that full-sample finding does not hold on
    some future re-run with different date bounds.
    """
    import fut_basis_series  # local import: keeps this as an optional dependency,
    # consistent with how _load_institutional_net_position() only imports
    # finmind_client at call time, not module load time

    basis = fut_basis_series.build_basis_series()[["date", "basis_pct"]]
    merged = series.merge(basis, on="date", how="inner").sort_values("date").reset_index(drop=True)
    return merged


def hyp_basis_carry(series: pd.DataFrame) -> CheapGateResult:
    merged = _load_basis(series)
    position = -np.sign(merged["basis_pct"])  # long when discount, short when premium
    return _permutation_test("fut_basis_carry", position, merged["ret"])


def hyp_basis_change_momentum_5d(series: pd.DataFrame, window: int = 5) -> CheapGateResult:
    merged = _load_basis(series)
    position = np.sign(merged["basis_pct"].diff(window))
    return _permutation_test(
        f"fut_basis_change_momentum_{window}d", position, merged["ret"]
    )


def hyp_basis_mean_reversion(series: pd.DataFrame, window: int = 60) -> CheapGateResult:
    merged = _load_basis(series)
    trailing_mean = merged["basis_pct"].rolling(window).mean().shift(1)  # excludes
    # today's own basis_pct value -- the "recent norm" reference must be known
    # before today's deviation from it can be read, same no-lookahead spirit as
    # hyp_vol_regime_trend's trailing_median_vol
    deviation = merged["basis_pct"] - trailing_mean
    position = -np.sign(deviation)  # long when more discounted than recent norm
    # (betting reversion back up), short when more premium-heavy than recent norm
    return _permutation_test(f"fut_basis_mean_reversion_{window}d", position, merged["ret"])


def _load_session_pair(series: pd.DataFrame) -> pd.DataFrame:
    """Inner-join the day-session series (from _load_series(), already has
    adj_open/adj_close/ret) with the NIGHT session's own continuous series
    (session="after_market", round 91 addition to continuous_contract.py) on
    the same date label.

    Round 63 (fut_verify_night_session_timing.py) established that a night
    session row dated T represents "the evening before T through T's early
    morning" -- i.e. night session T PRECEDES day session T within the SAME
    date label, not a lagged/shifted relationship across different date
    values. Round 90/91 confirmed rollover events are exactly synchronized
    between the two sessions (92/92 exact match), so this same-date join is
    not expected to introduce any front-month mismatch across the merged
    columns.

    Inner join is deliberate (not an oversight): night session data starts
    2017-05-16 (continuous_contract.py module docstring), well after day
    session's 2000 start -- same precedent as _load_institutional_net_position()
    and _load_basis(), both of which also inner-join a later-starting dataset
    onto the full day-session history.
    """
    night, skipped = build_continuous_series(session="after_market")
    if skipped:
        print(f"  [note] night session: {len(skipped)} rollover events had no clean "
              f"adjustment ratio -- proceeding, raw price used unadjusted")
    night = night[["date", "adj_open", "adj_close"]].rename(
        columns={"adj_open": "night_open", "adj_close": "night_close"}
    )
    merged = series.merge(night, on="date", how="inner").sort_values("date").reset_index(drop=True)
    merged["night_ret"] = merged["night_close"] / merged["night_open"] - 1.0  # night
    # session's own open-to-close return, i.e. the price move that happened
    # BEFORE day session T even opens (per round 63 timing)
    merged["day_ret"] = merged["adj_close"] / merged["adj_open"] - 1.0  # day session's
    # own intraday open-to-close return, computed fresh here (not series["ret"],
    # which is close-to-close across day-session dates -- a different, coarser
    # return definition not usable for same-day pairing)
    return merged


def hyp_night_session_momentum(series: pd.DataFrame) -> CheapGateResult:
    """First 盤別效應 (session-effect) hypothesis, round 91's infra now used
    for the first time. Since night session T precedes day session T within
    the same date label (round 63), this is a same-day pairing, not a
    cross-day shift -- position decided from night T's own realized return
    is traded against day T's own intraday return, using
    _permutation_test_same_day (same convention as
    hyp_intraday_gap_reversal/continuation's overnight-gap pairing)."""
    merged = _load_session_pair(series)
    position = np.sign(merged["night_ret"])  # trade with night session's direction
    return _permutation_test_same_day("fut_night_session_momentum", position, merged["day_ret"])


def hyp_night_session_reversal(series: pd.DataFrame) -> CheapGateResult:
    """Paired reversal hypothesis to hyp_night_session_momentum (same round,
    not a parameter-tuning rescue -- testing the opposite direction of a
    brand-new signal family is the established precedent from
    hyp_intraday_gap_reversal/continuation, #14/#15)."""
    merged = _load_session_pair(series)
    position = -np.sign(merged["night_ret"])  # fade night session's direction
    return _permutation_test_same_day("fut_night_session_reversal", position, merged["day_ret"])


def hyp_night_gap_reversal(series: pd.DataFrame) -> CheapGateResult:
    """Eleventh round's gap-construct hypothesis (round 98 next-step item
    (a), first of the two gap constructs it flagged: day close T-1 -> night
    open T). Unlike hyp_night_session_momentum/reversal (round 98, which
    used night session's OWN full open-to-close return night_ret to predict
    day_ret), this tests whether the GAP leading INTO the night session
    predicts that same night session's own subsequent return -- structural
    analog of hyp_intraday_gap_reversal/continuation (#14/#15: day close
    T-1 -> day open T gap predicting day's own intraday_ret), substituting
    the night session for the day session. _permutation_test_same_day is
    used because the gap is realized at night_open(T) and traded against
    night_ret(T), both carrying the same date label T (round 63 timing) --
    same convention as #14/#15 and hyp_night_session_momentum/reversal."""
    merged = _load_session_pair(series)
    gap = merged["night_open"] / merged["adj_close"].shift(1) - 1.0  # day
    # session's close on the PRIOR row -> night session's own open on this
    # row's date T; .shift(1) operates on merged's row order (already
    # date-sorted, inner-joined subset starting 2017-05-16), same pattern
    # as hyp_intraday_gap_reversal/continuation's series["adj_close"].shift(1)
    position = -np.sign(gap)  # fade the gap leading into night session
    return _permutation_test_same_day("fut_night_gap_reversal", position, merged["night_ret"])


def hyp_night_gap_continuation(series: pd.DataFrame) -> CheapGateResult:
    """Paired continuation hypothesis to hyp_night_gap_reversal (same round,
    not a parameter-tuning rescue -- testing the opposite direction of a
    brand-new gap construct, same precedent as #14/#15 and round 98's
    night_session_momentum/reversal pair)."""
    merged = _load_session_pair(series)
    gap = merged["night_open"] / merged["adj_close"].shift(1) - 1.0
    position = np.sign(gap)  # trade with the gap leading into night session
    return _permutation_test_same_day("fut_night_gap_continuation", position, merged["night_ret"])


def hyp_day_gap_reversal(series: pd.DataFrame) -> CheapGateResult:
    """Round 109's gap-construct hypothesis -- the second (and last) of the
    two gap constructs round 98's next-step item (a) flagged, explicitly
    left untested by round 104's #22/#23 (which only covered the OTHER gap:
    day close T-1 -> night open T, predicting night_ret). This one is night
    close T -> day open T, predicting day session T's OWN intraday_ret
    (day_ret) -- structural mirror of hyp_night_gap_reversal/continuation
    with night/day roles swapped. Per round 63 timing, night session T
    precedes day session T within the SAME date label, so night_close(T) ->
    day_open(T) is still a same-date-T gap (not a cross-day T -> T+1 shift),
    same as hyp_night_gap_reversal/continuation's day_close(T-1) ->
    night_open(T) construct -- _permutation_test_same_day applies for the
    same reason."""
    merged = _load_session_pair(series)
    gap = merged["adj_open"] / merged["night_close"] - 1.0  # night session's own
    # close on THIS row's date T -> day session's own open on the SAME row's
    # date T (round 63: night T precedes day T within one date label), mirror
    # of hyp_night_gap_reversal's night_open / adj_close.shift(1) but without
    # the .shift(1) since both legs already share date T here
    position = -np.sign(gap)  # fade the gap leading into day session
    return _permutation_test_same_day("fut_day_gap_reversal", position, merged["day_ret"])


def hyp_day_gap_continuation(series: pd.DataFrame) -> CheapGateResult:
    """Paired continuation hypothesis to hyp_day_gap_reversal (same round,
    not a parameter-tuning rescue -- testing the opposite direction of a
    brand-new gap construct, same precedent as #14/#15, round 98's
    night_session pair, and round 104's night_gap pair)."""
    merged = _load_session_pair(series)
    gap = merged["adj_open"] / merged["night_close"] - 1.0
    position = np.sign(gap)  # trade with the gap leading into day session
    return _permutation_test_same_day("fut_day_gap_continuation", position, merged["day_ret"])


def hyp_combo_trend_ma_oi_v1(series: pd.DataFrame) -> CheapGateResult:
    """Round 361's combination-level hypothesis, per MARATHON_PROTOCOL.md's
    2026-09-03 pivot to portfolio/combination-level work being the primary
    axis (not single-factor trials). Round 358 closed off the multi-round
    (341-358) individual-stock-futures cross-section direction as
    infeasible (see FUT_MARATHON_STATE.md round 361 for the closure
    reasoning); this is a first attempt at the FUT-track equivalent of TW's
    portfolio_multifactor combination -- since TX/MTX has no cross-sectional
    stock universe to combine factors over, "combination" here means
    combining multiple already-individually-FAILed but correctly-directioned
    single-instrument signals into one composite position, testing whether
    their consensus reduces noise (the diversification argument used for
    combining weak stock factors into a portfolio, applied at the
    single-instrument multi-signal level instead).

    Three components, chosen to span two independent information sources
    (not three variants of the same underlying signal, which would just
    re-test collinear noise under a new name):
      - hyp_trend_multi_tf's 10/20/60-day momentum vote (percentile 82.5,
        FAIL, TRIALS_LEDGER #18) -- price-only trend consensus.
      - hyp_ma_crossover's 20/60 SMA crossover (percentile 75.5, FAIL,
        TRIALS_LEDGER #20) -- price-only, different construction (smoothing
        lag vs raw momentum), correlated with trend_multi_tf but not
        identical.
      - hyp_oi_price_confirm's 5-day OI-confirmed 1-day price direction
        (percentile 62.0, FAIL, TRIALS_LEDGER #22) -- the only non-price-only
        component (uses open_interest), included specifically for
        diversification against the two price-only components above.
    hyp_vol_regime_trend and hyp_donchian_breakout are deliberately excluded:
    both are trend-following variants near-identical in spirit to
    trend_multi_tf (vol_regime_trend IS trend_multi_tf gated by volatility;
    round 33 already found the gating added no improvement), so including
    them would just weight the trend-following mechanism 3x rather than add
    a genuinely independent vote.

    Combination rule: majority sign vote across the 3 component positions
    (each already -1/0/+1), no weighting -- deliberately the simplest
    possible combination rule for a first test, before considering IC-
    weighted or volatility-targeted variants (paralleling
    PORTFOLIO_STRATEGY_SPEC.md's equal-weight baseline before its
    IC-weighted iteration). Pairwise position correlation is printed as a
    diagnostic: if the components turn out to be highly correlated, the
    combo is not really adding diversification and a percentile improvement
    (if any) should be read cautiously."""
    close = series["adj_close"]

    trend_scores = pd.DataFrame({f"mom_{n}": close.pct_change(n) for n in (10, 20, 60)})
    trend_vote = np.sign(np.sign(trend_scores).sum(axis=1))

    sma_fast = close.rolling(20).mean()
    sma_slow = close.rolling(60).mean()
    ma_vote = np.sign(sma_fast - sma_slow)

    raw_direction = np.sign(close.diff(1))
    oi_rising = series["open_interest"].diff(5) > 0
    oi_vote = raw_direction.where(oi_rising, 0.0)

    components = pd.DataFrame({"trend": trend_vote, "ma": ma_vote, "oi": oi_vote})
    valid_mask = components.notna().all(axis=1)
    pairwise_corr = components[valid_mask].corr()
    print(f"  [combo diagnostic] pairwise position correlation (n={int(valid_mask.sum())} valid days):")
    print(pairwise_corr.to_string())

    combined_score = components.sum(axis=1)
    position = np.sign(combined_score)
    return _permutation_test("fut_combo_trend_ma_oi_v1", position, series["ret"])


def hyp_combo_trend_oi_v1(series: pd.DataFrame) -> CheapGateResult:
    """Round 362's follow-up to hyp_combo_trend_ma_oi_v1, per that function's
    round 361 diagnostic finding: pairwise position correlation was
    trend-ma=0.418 (not independent), trend-oi=0.125, ma-oi=0.019 (both
    genuinely independent of everything). The 3-way majority-vote combo
    FAILed (percentile 76.5, TRIALS_LEDGER #130) at a strength *below* the
    single best component (trend_multi_tf alone, 82.5) -- consistent with
    ma's correlation with trend diluting rather than diversifying the vote,
    and oi's frequent 0 (flat, when open interest isn't rising) further
    diluting the 3-way sum whenever trend+ma agree but oi is silent.

    This is FUT_MARATHON_STATE.md round 361's "下一步(b)" candidate: drop ma
    entirely, keep only the two components with genuinely low pairwise
    correlation (trend-oi=0.125) -- testing whether removing the
    non-independent component recovers some of the diversification the
    3-way combo lost.

    Combination rule: same equal-weight sum-then-sign as the 3-way version
    (no re-tuning to a different rule; changing the rule *and* the
    component set in the same trial would confound which change mattered).
    With only 2 components (both in {-1,0,+1}), the sum ranges over
    {-2,-1,0,+1,+2}: agreement gives {-2,+2} (position +-1 after sign), a
    lone opinion (one flat) gives {-1,+1} (position follows the
    non-flat one), and direct disagreement gives 0 (flat) -- there is no
    tie-breaking ambiguity to pre-register since np.sign(0) == 0 already
    resolves the two-vs-one and disagreement cases identically to how
    _permutation_test treats 0 elsewhere in this file.

    Pre-registered (hash-locked) pass criterion, written before running:
    percentile >= 90.0, same bar as every other hyp_* in this file --
    no bar adjustment for having fewer components. Diagnostic-only,
    non-binding context: if percentile ends up between the single-best
    component's 82.5 and the 3-way combo's 76.5, that's read as "still no
    diversification benefit, just less dilution than the 3-way version";
    only >=90.0 counts as CHEAP_PASS regardless of where it lands relative
    to those two reference points."""
    close = series["adj_close"]

    trend_scores = pd.DataFrame({f"mom_{n}": close.pct_change(n) for n in (10, 20, 60)})
    trend_vote = np.sign(np.sign(trend_scores).sum(axis=1))

    raw_direction = np.sign(close.diff(1))
    oi_rising = series["open_interest"].diff(5) > 0
    oi_vote = raw_direction.where(oi_rising, 0.0)

    components = pd.DataFrame({"trend": trend_vote, "oi": oi_vote})
    valid_mask = components.notna().all(axis=1)
    pairwise_corr = components[valid_mask].corr()
    print(f"  [combo diagnostic] pairwise position correlation (n={int(valid_mask.sum())} valid days):")
    print(pairwise_corr.to_string())

    combined_score = components.sum(axis=1)
    position = np.sign(combined_score)
    return _permutation_test("fut_combo_trend_oi_v1", position, series["ret"])


def hyp_combo_trend_oi_weighted_v1(series: pd.DataFrame) -> CheapGateResult:
    """Round 366's follow-up, FUT_MARATHON_STATE.md round 364 "下一步(a)":
    equal-weight vote (hyp_combo_trend_oi_v1, TRIALS_LEDGER #132) FAILed at
    percentile 82.5 -- statistically indistinguishable from trend_multi_tf
    alone (also 82.5, TRIALS_LEDGER #18), because equal-weight sign-of-sum
    only differs from trend-alone on days oi actively disagrees (its silent
    days already reduce to trend-alone under sign()), and those disagreement
    days evidently weren't enough to move the needle either way.

    This variant replaces the unweighted vote with a percentile-derived
    weight, pre-registered from already-published single-factor cheap-gate
    numbers (not tuned by looking at this trial's own result): weight =
    max(single-factor percentile - 50, 0), i.e. "how far above a coin flip".
      - trend_multi_tf: percentile 82.5 (TRIALS_LEDGER #18) -> weight 32.5
      - oi_price_confirm: percentile 62.0 (TRIALS_LEDGER #22) -> weight 12.0
    combined_score = trend_vote * 32.5 + oi_vote * 12.0; position =
    sign(combined_score). Because trend's weight (32.5) exceeds oi's (12.0),
    the combo now always follows trend's direction when oi is silent or
    agrees, and only flips to flat -- never to oi's direction -- when they
    disagree (32.5 - 12.0 = 20.5, same sign as trend). This is a genuinely
    different rule from the equal-weight version (there, disagreement always
    produced exactly 0; here, disagreement damps trend's conviction to 0 only
    because oi's weight is large enough to fully cancel, not overturn it --
    same numeric outcome on disagreement days as equal-weight in this
    specific 2-component case, but the mechanism generalizes correctly to
    >2 components and is the honest reason to test it rather than assume
    the equal-weight result already covered this).

    Pre-registered (hash-locked) pass criterion: percentile >= 90.0, same
    bar as every other hyp_* in this file. If this lands at/near 82.5 again
    (same as trend-alone and the equal-weight combo), that would be strong
    evidence the oi component contributes nothing to this specific
    trend+oi pairing regardless of weighting scheme, closing off the
    weighting-scheme branch of FUT_MARATHON_STATE.md round 364's "下一步"
    options and leaving only (b) [different oi variant] or (c) [deprioritize
    FUT] as live options for future rounds."""
    close = series["adj_close"]

    trend_scores = pd.DataFrame({f"mom_{n}": close.pct_change(n) for n in (10, 20, 60)})
    trend_vote = np.sign(np.sign(trend_scores).sum(axis=1))

    raw_direction = np.sign(close.diff(1))
    oi_rising = series["open_interest"].diff(5) > 0
    oi_vote = raw_direction.where(oi_rising, 0.0)

    TREND_WEIGHT = 82.5 - 50.0  # TRIALS_LEDGER #18, pre-registered
    OI_WEIGHT = 62.0 - 50.0     # TRIALS_LEDGER #22, pre-registered

    components = pd.DataFrame({"trend": trend_vote, "oi": oi_vote})
    valid_mask = components.notna().all(axis=1)
    pairwise_corr = components[valid_mask].corr()
    print(f"  [combo diagnostic] pairwise position correlation (n={int(valid_mask.sum())} valid days), "
          f"weights: trend={TREND_WEIGHT}, oi={OI_WEIGHT}")
    print(pairwise_corr.to_string())

    combined_score = trend_vote * TREND_WEIGHT + oi_vote * OI_WEIGHT
    position = np.sign(combined_score)
    return _permutation_test("fut_combo_trend_oi_weighted_v1", position, series["ret"])


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"

    series = _load_series()
    print(f"loaded continuous series: {len(series)} rows, "
          f"{series['date'].min().date()} .. {series['date'].max().date()}")

    results = [
        hyp_oi_price_confirm_graded(series),
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
