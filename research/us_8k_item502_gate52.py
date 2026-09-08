"""#52-US cheap gate, second item family: Item 5.02 8-K filings (departure/
election of directors and officers) vs post-announcement drift.

Round454's three-way choice after Item 2.02's FAIL (TRAIN percentile 62.5,
VAL 83.5, both below the 90.0 threshold) was: (a) conclude no edge, (b) build
a CIK-history consistency check and scale to full tier, or (c) test another
item family. This round picks (c): with 22 tickers' full submission history
already cached from round454 (get_8k_events(cik, full_history=True) is
per-CIK cached, not per-item-family), testing a second family costs zero
new API calls and finishes in seconds -- the cheapest possible next step,
and one round454 explicitly left open.

**Why 5.02 is a distinct economic mechanism, not a reskin of 2.02**: 2.02
tests underreaction to a *scheduled, anticipated* disclosure (quarterly
earnings). 5.02 (officer/director departures, especially unplanned CFO/CEO
exits) is an *unscheduled* disclosure that the literature (e.g. Fee & Hadlock
2004; Cziraki & Jenter 2020 on forced turnover) associates with negative
information the market has less time/data to price correctly, plausibly
driving a *stronger*, not weaker, underreaction drift -- a different claim
than "PEAD exists", worth its own test rather than folding into 2.02's
verdict.

**Everything else -- PIT anchor, reaction-day rule, r0/r_drift windows,
control-exclusion buffer, TRAIN/VAL split, control draw mechanics --
reuses us_8k_pead_gate52.py verbatim via its parameterized process_ticker()/
main(), so none of that machinery is re-decided here.**

**Not pre-filtering by departure sentiment (forced vs voluntary, CEO vs
lower officer)**: the raw `items` field only says "5.02", not who or why --
that stratification would need parsing filing text, out of scope for a
cheap-gate pilot. This means the pooled result mixes routine retirements
(no expected drift) with forced departures (literature's expected-drift
case), which biases toward null if the mix is retirement-heavy. Disclosed
here per CONSTITUTION's dilution-vs-null-bias honesty norm, not corrected
for in this pilot.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from us_8k_pead_gate52 import main

if __name__ == "__main__":
    sys.exit(main("5.02", "Item 5.02 8-K officer/director departures"))
