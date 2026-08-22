"""Pre-registered pass/fail criteria, locked before any holdout evaluation.

CONSTITUTION.md: "事前綁定通過標準,絕不事後移動門柱" -- Cybex's clearest example of
doing this right was letting three candidates FAIL on a technicality (max
drawdown slightly too deep) rather than loosening the bar after seeing the
result. This module makes that mechanically enforced rather than relying on
willpower: write criteria to a file, lock it (hash recorded in the return
value -- write that hash down, e.g. into STRATEGY_LOG.md), and any later
evaluation must reproduce that hash or it refuses to run.

Locked criteria files live in research/criteria/ and are committed to git
(NOT gitignored) -- the whole point is that they must survive as an
unforgeable-ish record, same reasoning as validation/holdout.py's lock file.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CRITERIA_DIR = Path(__file__).parent.parent / "criteria"
CRITERIA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PassCriteria:
    name: str
    min_sharpe: float | None = None
    max_drawdown: float | None = None      # e.g. 0.25 = must not exceed -25%
    min_trades: int = 100                   # CONSTITUTION.md: "交易<100筆不可信"
    beats_random_control_pct: int = 90      # must reach this percentile vs the random control group
    beats_buy_and_hold: bool = True         # long-only strategies must beat buy-and-hold + index
    notes: str = ""


def lock_criteria(criteria: PassCriteria) -> str:
    """Write criteria to disk (refusing to overwrite an existing file with
    the same name) and return its sha256 hash. Call this BEFORE running the
    holdout evaluation, and record the returned hash somewhere durable
    (STRATEGY_LOG.md) -- it's what proves the bar wasn't moved afterward.
    """
    path = CRITERIA_DIR / f"{criteria.name}.json"
    if path.exists():
        raise FileExistsError(
            f"Criteria file {path} already exists -- locked criteria must never be edited or "
            "overwritten. If this is genuinely a new attempt, use a new `name` (e.g. a version "
            "suffix) instead of overwriting the old one."
        )
    payload = asdict(criteria)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_criteria(name: str, expected_hash: str) -> PassCriteria:
    """Load locked criteria and verify its hash matches what lock_criteria()
    returned at lock time. Raises if the file was edited since locking, or
    doesn't exist at all.
    """
    path = CRITERIA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No locked criteria named {name!r} at {path}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Criteria {name!r} has been modified since locking! "
            f"expected hash {expected_hash}, got {actual_hash}. "
            "This is exactly the goalpost-moving failure mode CONSTITUTION.md forbids -- "
            "do not proceed with this evaluation."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PassCriteria(**payload)


def evaluate(
    criteria: PassCriteria, *, sharpe: float | None = None, max_dd: float | None = None,
    n_trades: int, control_percentile: float, beat_buy_and_hold: bool,
) -> dict:
    """Check a result against locked criteria. Returns per-check pass/fail
    plus an overall verdict -- never collapses to a single boolean that
    would hide which specific bar was missed.
    """
    checks: dict[str, bool] = {
        "min_trades": n_trades >= criteria.min_trades,
        "beats_random_control": control_percentile >= criteria.beats_random_control_pct,
    }
    if criteria.min_sharpe is not None:
        if sharpe is None:
            raise ValueError("criteria requires min_sharpe but no sharpe value was supplied")
        checks["min_sharpe"] = sharpe >= criteria.min_sharpe
    if criteria.max_drawdown is not None:
        if max_dd is None:
            raise ValueError("criteria requires max_drawdown but no max_dd value was supplied")
        checks["max_drawdown"] = max_dd <= criteria.max_drawdown
    if criteria.beats_buy_and_hold:
        checks["beats_buy_and_hold"] = beat_buy_and_hold

    return {"passed": all(checks.values()), "checks": checks}
