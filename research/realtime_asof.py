"""Real-time as-of-today window for the App-facing scores.json pipeline ONLY.

**Policy this implements (user ruling, 2026-08-25; reiterated 2026-08-26):**
`score_v2.py`'s factor definitions and category weights (`FACTOR_DEFS`) are
frozen at dev-period design values and are never re-estimated from data seen
through the window this module opens. Feeding that already-frozen formula
today's inputs to produce today's score is the formula's ordinary
out-of-sample production use, NOT a research holdout look -- holdout
protects "don't let recent data influence which factors/weights get
chosen", not "the calendar may never say today". See MARATHON_STATE.md's
2026-08-25 entry ("使用者解除卡關指令" #3) for the full policy text.

**Mechanism:** every capped data loader in this codebase
(`finmind_client.load_dev()`, `yf_price_client.fetch_yf_adjusted()`,
`twse_t86_client.institutional_daily_net_t86()`) reads
`validation.holdout.VAL_END` fresh on every call (a local
`from validation.holdout import VAL_END`, or `holdout.VAL_END` attribute
access -- never a value snapshotted once at import time). That means
temporarily reassigning the module attribute widens every one of those caps
at once, for exactly the duration of a `with` block, with zero changes to
any of those loaders' code and zero interaction with the actual holdout
lock (`is_holdout_consumed()`/`HOLDOUT_LOCK.json` are never touched -- this
raises the VAL_END boundary itself rather than looking past it, so
`assert_no_holdout_leakage()` stays satisfied throughout).

**Hard rule, not a suggestion:** never use this to run factor_ic.py-style
statistical validation, never use it to decide which factors/weights
`score_v2.py` should use, and never leave it wrapping anything beyond the
scores.json generation call itself. It exists for exactly one purpose --
computing today's score from yesterday's-and-earlier's frozen formula.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import validation.holdout as _holdout


@contextmanager
def as_of_today():
    """Widen validation.holdout.VAL_END to today for the wrapped block, then
    restore it. Yields today's date string (YYYY-MM-DD) for callers that
    need it as the "基準日" to stamp into their output."""
    today = datetime.now().strftime("%Y-%m-%d")
    original = _holdout.VAL_END
    _holdout.VAL_END = today
    try:
        yield today
    finally:
        _holdout.VAL_END = original
