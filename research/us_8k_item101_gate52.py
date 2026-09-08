"""#52-US cheap gate, third item family: Item 1.01 8-K filings (entry into a
material definitive agreement) vs post-announcement drift.

Round456's leftover three-way choice after Item 5.02 (management turnover)
also FAILed (TRAIN percentile 55.0, VAL percentile 8.0, reversed direction)
was: (a) conclude #52-US has no edge across the two families tested so far,
or (b) test a third family before drawing that conclusion. This round picks
(b): with the same 22 tickers' full submission history already cached from
round454/456 (get_8k_events(cik, full_history=True) is per-CIK cached, not
per-item-family), testing a third family costs zero new API calls.

**Why 1.01 is a distinct economic mechanism, not a reskin of 2.02 or 5.02**:
2.02 tests underreaction to a *scheduled* disclosure (quarterly earnings);
5.02 tests an *unscheduled negative-leaning* disclosure (officer/director
departures). 1.01 (entry into a material definitive agreement -- e.g. new
supply contracts, credit facilities, licensing/partnership deals, M&A
agreements) is an *unscheduled, typically positive-or-neutral-leaning*
disclosure. The literature on contract-announcement drift (e.g. studies of
analyst/market underreaction to new-business announcements, distinct from
both earnings-PEAD and forced-turnover literatures) motivates testing this
as its own economic claim rather than folding it into either prior verdict.
This is the third and, per round456's framing, likely final family tested
before an overall #52-US no-edge conclusion (if this also FAILs).

**Everything else -- PIT anchor, reaction-day rule, r0/r_drift windows,
control-exclusion buffer, TRAIN/VAL split, control draw mechanics --
reuses us_8k_pead_gate52.py verbatim via its parameterized process_ticker()/
main(), so none of that machinery is re-decided here.**

**Not pre-filtering by agreement type or materiality tier**: the raw `items`
field only says "1.01", not the deal's size, counterparty, or economic
direction (e.g. a new credit facility vs. a landmark supply contract carry
very different expected market reactions) -- that stratification would need
parsing filing text/exhibits, out of scope for a cheap-gate pilot. This means
the pooled result mixes plausibly-large-reaction events with routine/small
agreements, which biases toward null if the mix is routine-heavy. Disclosed
here per CONSTITUTION's dilution-vs-null-bias honesty norm, not corrected
for in this pilot.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from us_8k_pead_gate52 import main

if __name__ == "__main__":
    sys.exit(main("1.01", "Item 1.01 8-K material definitive agreements"))
