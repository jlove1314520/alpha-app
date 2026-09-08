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

**Round-436 update (`us_reverse_split_corporate_action_verify.py`)**: did the
per-ticker corporate-action lookup the round433 note above said was still
missing, for all 59 flagged-but-unconfirmed candidates. Method: SEC EDGAR
full-text search for "reverse stock split" filed by each ticker's CIK,
restricted to 8-K filings whose file_date falls inside the price series
window, **requiring SEC item 5.03** ("Amendments to Articles of
Incorporation or Bylaws" -- the mandated disclosure item for an executed
change to share structure). A first pass without the item-5.03 requirement
(just counting in-window phrase hits) produced a confirmed false positive on
`FCNCA` (a real, never-split bank stock whose hits were all boilerplate
mentions of "reverse stock split" inside merger/securities-agreement items
1.01/7.01/8.01/9.01, not its own stock being split) -- requiring 5.03 at the
search-result level (item codes are already in the SEC full-text search
response, zero extra HTTP calls) rules that class out, and correctly leaves
`FCNCA` unconfirmed. Result: **23/59 confirmed** via >=1 in-window item-5.03
filing, including `AMN` and `IBCP` -- the two names round433's docstring had
cited as examples of "genuine business deterioration, not contamination";
both turned out to have documented reverse splits inside their price window
and are added below. The remaining 36 (24 `no_reverse_split_found` + 12
`phrase_mentioned_no_item503_likely_boilerplate`) are still NOT added --
full detail in `data/us_reverse_split_corporate_action_verify.csv`.

This blacklist (now 48 names) is still a known-bad list, not a
verified-clean guarantee for the remaining tickers.
"""
from __future__ import annotations

KNOWN_CONTAMINATED_TICKERS: frozenset[str] = frozenset({
    "WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI", "LEE",
    # round433 additions (see docstring above for the confirmation rule):
    "AIRI", "BDRX", "CISS", "COCP", "CPOP", "DARE", "EJH", "EPM", "GRCE",
    "NIKI", "NTRP", "RENX", "RMTI", "RVSN", "SMX", "TRAW", "TRNR",
    # round436 additions (SEC 8-K item-5.03-confirmed, see docstring above):
    "ATNM", "LRMR", "QTTB", "XOS", "PVLA", "IDN", "ELTX", "HHS", "CTOR",
    "KLXE", "ONIT", "CRK", "ASUR", "STI", "OIS", "SRG", "TMC", "HPP",
    "POWW", "IRON", "ILPT", "AMN", "IBCP",
})
