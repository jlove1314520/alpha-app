"""Train / validation / holdout split with physical isolation.

CONSTITUTION.md's single most expensive lesson from the Cybex project:
holdout contamination isn't a discipline problem, it's an availability
problem. A human WILL eventually look at holdout data if the code makes it
easy to -- Cybex's "post-2024 real out-of-sample" check was run over a
hundred times before anyone noticed its date boundary fully overlapped the
actual holdout. The fix is not "write a comment saying don't look" -- it's
"the data loader physically cannot return holdout rows unless you go
through one specific, logged, one-time-use function".

Split boundaries below are a first cut (not yet reviewed against how much
history an actual strategy will need) -- deliberately hardcoded rather than
a function parameter, so changing them means editing this file directly,
which is itself a small amount of intentional friction against casually
redefining "holdout" mid-project.

Dtype note (found FUT marathon round 69, fixed same round): under pandas
3.0.5, comparing a `pandas.Timestamp` scalar/Series directly against a raw
Python string (e.g. `Timestamp(...) > "2024-12-31"`) raises `TypeError`
instead of auto-parsing the string, unlike older pandas. All date
comparisons below now go through `pd.to_datetime(...)` / `pd.Timestamp(...)`
on both sides before comparing, so this module works whether `date_col` is
string-dtype (the common case -- FinMind raw responses) or already-parsed
datetime64-dtype (e.g. continuous_contract.py parses `date` immediately on
load). This was a real, fail-loud (crash, not silent-pass) gap, not a
theoretical one -- it was hit for real by fut_basis_series.py, whose input
already has parsed dates.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TRAIN_END = "2020-12-31"   # inclusive. TRAIN = [universe start, TRAIN_END]
VAL_END = "2024-12-31"     # inclusive. VAL = (TRAIN_END, VAL_END]
# HOLDOUT = (VAL_END, today]. Not given a fixed end date -- it grows every day
# that passes, which is the point: it should always be "the real, not-yet-seen future"
# relative to whenever a strategy's train/val work was actually done.

_RESEARCH_DIR = Path(__file__).parent.parent
HOLDOUT_LOCK = _RESEARCH_DIR / "HOLDOUT_LOCK.json"   # committed to git -- the lock must survive
HOLDOUT_LOG = _RESEARCH_DIR / "HOLDOUT_LOG.md"       # committed to git -- permanent audit trail


def cap_to_dev(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Train+validation only (<= VAL_END). Use this to cap a DataFrame you
    already have in hand (e.g. from finmind_client.load_full_history(), or
    from any non-FinMind source). If you're fetching FROM FinMind, prefer
    finmind_client.load_dev() instead -- it caps at the fetch/cache layer
    itself so an uncapped copy never even gets pulled or cached, which is a
    stronger guarantee than filtering after the fact.
    """
    return df[pd.to_datetime(df[date_col]) <= pd.Timestamp(VAL_END)].copy()


def cap_to_train(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    return df[pd.to_datetime(df[date_col]) <= pd.Timestamp(TRAIN_END)].copy()


def validation_slice(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    dates = pd.to_datetime(df[date_col])
    return df[(dates > pd.Timestamp(TRAIN_END)) & (dates <= pd.Timestamp(VAL_END))].copy()


def is_holdout_consumed() -> bool:
    return HOLDOUT_LOCK.exists()


def assert_no_holdout_leakage(df: pd.DataFrame, date_col: str = "date", context: str = "") -> None:
    """Permanent audit identity (added 2026-08-22, after a Cowork audit found
    finmind_client's original fetch() had no cap at all -- load_dev() fixes
    the fetch-time gap, this is the second, independent line of defense at
    the point data is actually about to be used).

    Call this at every point where data is about to be fed into a backtest/
    analysis computation -- ideally right at the top of a backtest runner's
    main loop, on whatever DataFrame it's about to consume. Raises
    AssertionError immediately on violation: this must be a hard stop a
    caller cannot accidentally ignore, not a warning that scrolls by in a
    log. Also wired into audit_ledgers.py's check list against the trade
    ledger itself, as a second layer independent of where the data came from.

    If holdout has been legitimately unlocked (is_holdout_consumed() is
    True), this check is a no-op -- at that point later dates are expected
    and allowed, since the whole point of unlocking was to look at them.
    """
    if is_holdout_consumed():
        return
    if df.empty or date_col not in df.columns:
        return
    max_date = df[date_col].max()
    if pd.Timestamp(max_date) > pd.Timestamp(VAL_END):
        raise AssertionError(
            f"HOLDOUT LEAKAGE{f' ({context})' if context else ''}: data contains rows up to "
            f"{max_date!r}, which is after VAL_END ({VAL_END}), but holdout has not been unlocked "
            "(is_holdout_consumed() is False). This should be impossible if finmind_client.load_dev() "
            "was used correctly -- check for a direct _fetch()/load_full_history() call, or a non-"
            "FinMind data source, that bypassed the cap."
        )


def unlock_holdout_once(df: pd.DataFrame, reason: str, approved_by: str, date_col: str = "date") -> pd.DataFrame:
    """The ONLY way to get holdout-period rows. Can succeed exactly once,
    ever -- enforced by a lock file that is committed to git, so it survives
    a fresh clone, a new machine, a new session. After the first successful
    call this always raises, in any future process.

    Both a success and a blocked attempt are appended to HOLDOUT_LOG.md, so
    there's a permanent record even of attempts that got refused.
    """
    if not reason or not reason.strip():
        raise ValueError("reason is required -- write down WHY you're unlocking holdout, before you see it")
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by is required -- this must be a recorded human decision")

    ts = datetime.now(timezone.utc).isoformat()

    if is_holdout_consumed():
        prior = json.loads(HOLDOUT_LOCK.read_text(encoding="utf-8"))
        _append_log(ts, reason, approved_by, blocked=True, prior=prior)
        raise RuntimeError(
            f"Holdout was already consumed on {prior['timestamp']} "
            f"(reason: {prior['reason']!r}, approved_by: {prior['approved_by']!r}). It is burned. "
            "Do not delete HOLDOUT_LOCK.json to get around this. If a new out-of-sample test is "
            "genuinely needed, that means deliberately defining a NEW holdout window (e.g. rolling "
            "VAL_END/TRAIN_END forward) and updating this module on purpose, not reusing the one "
            "that has already been looked at."
        )

    lock = {"timestamp": ts, "reason": reason, "approved_by": approved_by,
            "train_end": TRAIN_END, "val_end": VAL_END}
    HOLDOUT_LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
    _append_log(ts, reason, approved_by, blocked=False)

    end = datetime.now().strftime("%Y-%m-%d")
    dates = pd.to_datetime(df[date_col])
    return df[(dates > pd.Timestamp(VAL_END)) & (dates <= pd.Timestamp(end))].copy()


def _append_log(ts: str, reason: str, approved_by: str, blocked: bool, prior: dict | None = None) -> None:
    header_needed = not HOLDOUT_LOG.exists()
    with HOLDOUT_LOG.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write(
                "# Holdout access log\n\n"
                "Every call to `unlock_holdout_once()`, successful or blocked, appended here. "
                "Append-only by convention -- do not edit past entries.\n\n"
            )
        if blocked:
            f.write(
                f"- **{ts}** — BLOCKED (already consumed {prior['timestamp']} "
                f"by {prior['approved_by']!r}, reason {prior['reason']!r}). "
                f"Attempted reason this time: {reason!r}, by {approved_by!r}\n"
            )
        else:
            f.write(f"- **{ts}** — CONSUMED. reason={reason!r} approved_by={approved_by!r}\n")
