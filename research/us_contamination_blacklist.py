"""Canonical US-track contamination blacklist (round431, universe-level fix
requested by `US_MARATHON_STATE.md` round429's "下一輪US軌接手(1)").

**What this is**: 8 tickers independently identified across three separate
factor investigations (`#20` f_us_value_bm round410 `us_short_leg_holdings_check.py`,
`#21` f_us_low_vol round410 same script, `#23` f_us_gross_profitability
round429 `deep_dive_f_us_gross_profitability_contamination_check.py`) as
death-spiral reverse-split microcaps: FinMind's (and Yahoo Finance's --
round423 `TRIALS_LEDGER.md`#188 confirmed this is not FinMind-specific)
`adj_close` retroactively inflates their historical nominal prices to
reflect FUTURE reverse splits (e.g. `MNTS` shows a VAL-period-start
adj_close of $224,500 -- a price that never existed in reality at that
date). Any decile/Top-N ranking whose short leg or extreme bucket can land
on these names produces backtest returns that cannot be executed in
reality (see `STRATEGY_GRAVEYARD.md` "f_us_value_bm/f_us_low_vol 乾淨宇宙
版本" entry for the full 9-round diagnostic chain that traced this).

**Why centralize instead of leaving each factor script to rediscover it**:
`#20`/`#21`/`#23` each independently burned multiple rounds tracing the same
root cause. `US_MARATHON_STATE.md` round429 explicitly asked for the
universe-level fix "這比每個新因子各自撞一次同一個陷阱更有效率". Any future
US-track factor built on `data/us_stratified_universe_sample.csv` should
exclude these at the loading layer, not re-diagnose them.

**Known limitation (do not overstate this list's completeness)**: the original
8 were found because they happened to dominate the short/extreme leg of the
THREE factors tested so far (value_bm, low_vol, gross_profitability) --
opportunistic discovery, not a systematic scan.

**round433 update (`us_reverse_split_contamination_scan.py`)**: `US_MARATHON_STATE.md`
round431's "下一輪US軌接手(1)" asked for a systematic scan instead of waiting
for the next factor to stumble onto another one. Scanned all 240
non-blacklisted usable tickers in `data/us_stratified_universe_sample.csv`
for the same adj_close-magnitude signature. Result: **76/240 (31.7%) tripped
a coarse threshold** (max(adj_close) > $1,000 OR max/last ratio > 5x,
calibrated on the original 8's measured range of 6.4x-3,304,364x) -- far more
pervasive than the original 8 suggested. Manual inspection (checking whether
the peak price sits near the series start / is transient vs. near the
current price) found this coarse threshold has real false positives -- e.g.
`FCNCA` is a genuine never-split, high-nominal-price bank stock
(last=$2,099.96, still near its $2,336.57 peak), not a death spiral. Applying
the tighter, still purely mechanical rule **max(adj_close) > $1,000 AND last
< 50% of that max** (i.e. the extreme price was transient, not where the
stock currently sits) yields **17 additional high-confidence names added
below**, all with max in the thousands-to-billions range while trading at
single/low-double-digit dollars now -- economically impossible without
repeated reverse splits.

**The other 59 flagged-but-unconfirmed candidates are NOT added here**
(see `data/us_reverse_split_contamination_scan.csv`,
`flagged_new_candidate=True` rows not in this frozenset) -- their ratios
(5x-160x) are within the range a genuine, non-contaminated microcap can
plausibly show through ordinary business deterioration (e.g. `AMN`/`IBCP`
-style names), and confirming them needs per-ticker corporate-action lookup
this round did not do. Treat that 59-name list as a lead for a future round,
not a finding.

This blacklist (now 25 names) is still a known-bad list, not a
verified-clean guarantee for the remaining ~215 usable tickers.
"""
from __future__ import annotations

KNOWN_CONTAMINATED_TICKERS: frozenset[str] = frozenset({
    "WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI", "LEE",
    # round433 additions (see docstring above for the confirmation rule):
    "AIRI", "BDRX", "CISS", "COCP", "CPOP", "DARE", "EJH", "EPM", "GRCE",
    "NIKI", "NTRP", "RENX", "RMTI", "RVSN", "SMX", "TRAW", "TRNR",
})
