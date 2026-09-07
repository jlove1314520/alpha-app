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

**Known limitation (do not overstate this list's completeness)**: these 8
were found because they happened to dominate the short/extreme leg of the
THREE factors tested so far (value_bm, low_vol, gross_profitability). There
may be other death-spiral reverse-split names in the 248-ticker sample that
simply haven't been selected into an extreme decile yet by any factor
tested to date. This blacklist is a known-bad list, not a verified-clean
guarantee for the remaining tickers.
"""
from __future__ import annotations

KNOWN_CONTAMINATED_TICKERS: frozenset[str] = frozenset({
    "WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI", "LEE",
})
