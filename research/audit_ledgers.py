"""Read-only audit script: checks accounting identities against the paper-trading ledger.

CONSTITUTION.md: "每修一類 bug,就加一條永久稽核恆等式" -- every category of bug found and
fixed earns a permanent check here, so that class of error gets caught automatically
forever, not just remembered by whoever fixed it once. Three checks are seeded now:

  1. Every close/sell trade must reference a real, existing entry trade. Cybex once had a
     global `last_run_date` filter silently swallow 7000+ trades with no traceable entry
     before anyone noticed -- this check exists specifically to catch that class of bug.
  2. No NaN price or share count on any row. Cybex had unclosed daily bars leak into a
     ledger and create phantom exits -- this check exists specifically to catch that.
  3. No trade dated after VAL_END unless holdout has been unlocked. Added 2026-08-22 after
     a Cowork audit found finmind_client's original fetch() had no holdout cap at all --
     see STRATEGY_LOG.md's 2026-08-22 entry for the full incident writeup.

This script is READ-ONLY: it never writes to trades.csv or any ledger file. Run it after
every paper-trading update (or on a schedule once that infra exists) and treat a non-zero
exit code as a hard stop -- do not re-run hoping it passes, fix the underlying data/code.

There are currently ZERO real rows for these checks to run against, because there is no
paper-trading book yet (Milestone 3 hasn't started -- see MARATHON_STATE.md). The checks
are written NOW, ahead of the data existing, on purpose: locking them in before anyone is
tempted to skip them under time pressure once trades actually start flowing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
LEDGER_DIR = DATA_DIR / "ledger"
TRADES_CSV = LEDGER_DIR / "trades.csv"

# Every trade row must have at least these columns. Additional columns are fine.
TRADES_SCHEMA = [
    "trade_id", "book", "stock_id", "side", "date", "price", "shares",
    "fees", "tax", "realized_pnl", "entry_trade_id", "note",
]


def load_trades(path: Path = TRADES_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=TRADES_SCHEMA)
    return pd.read_csv(path)


def check_every_close_has_entry(trades: pd.DataFrame) -> list[str]:
    """Every 'sell'/'close' row must reference a real prior 'buy'/'open' row via
    entry_trade_id -- every position must be traceable back to how it was opened.
    """
    if trades.empty:
        return []
    problems = []
    closes = trades[trades["side"].isin(["sell", "close"])]
    known_ids = set(trades["trade_id"])
    for _, row in closes.iterrows():
        entry_id = row.get("entry_trade_id")
        if pd.isna(entry_id) or entry_id == "":
            problems.append(f"trade_id={row['trade_id']}: close with no entry_trade_id")
        elif entry_id not in known_ids:
            problems.append(f"trade_id={row['trade_id']}: entry_trade_id={entry_id!r} not found in ledger")
    return problems


def check_no_nan_prices(trades: pd.DataFrame) -> list[str]:
    """NaN price/shares on a row means an unclosed daily bar or a bad fetch leaked
    into the ledger.
    """
    if trades.empty:
        return []
    bad = trades[trades["price"].isna() | trades["shares"].isna()]
    return [f"trade_id={r['trade_id']}: NaN price or shares" for _, r in bad.iterrows()]


def check_no_holdout_leakage(trades: pd.DataFrame) -> list[str]:
    """No trade in the ledger may be dated after VAL_END unless holdout has
    been legitimately unlocked (added 2026-08-22, after a Cowork audit found
    finmind_client's original fetch() had no holdout cap at all -- see
    STRATEGY_LOG.md's 2026-08-22 entry). This is the ledger-level line of
    defense; validation.holdout.assert_no_holdout_leakage() is the
    independent data-loading-time line of defense for the same failure
    mode. Having both is deliberate, not redundant -- a leak could enter the
    ledger through a path that never went through the data loader at all
    (e.g. a manually-entered paper trade).
    """
    from validation.holdout import VAL_END, is_holdout_consumed
    if trades.empty or is_holdout_consumed():
        return []
    leaked = trades[trades["date"] > VAL_END]
    return [f"trade_id={r['trade_id']}: date={r['date']} is after VAL_END ({VAL_END}) but holdout not unlocked"
            for _, r in leaked.iterrows()]


def check_equity_identity(cash: float, realized: float, unrealized: float, reported_equity: float,
                            tolerance: float = 0.01) -> list[str]:
    """權益 = 現金 + 已實現損益 + 未實現損益.

    Not part of the automatic CHECKS list below -- it needs a book's cash/realized/
    unrealized numbers as external input, which don't exist until Milestone 3's paper
    ledger is built. Call this directly once that exists.
    """
    expected = cash + realized + unrealized
    if abs(expected - reported_equity) > tolerance:
        return [f"equity identity broken: cash({cash})+realized({realized})+unrealized({unrealized})"
                f"={expected} != reported_equity({reported_equity}), diff={expected-reported_equity}"]
    return []


# Every entry here runs automatically in run(). Add one line per new bug category fixed.
CHECKS: list[tuple[str, "callable"]] = [
    ("每個平倉都有對應進場記錄", check_every_close_has_entry),
    ("沒有 NaN 價格/股數", check_no_nan_prices),
    ("沒有未經 holdout 解鎖就出現的未來日期交易", check_no_holdout_leakage),
]


def run(trades: pd.DataFrame | None = None, verbose: bool = True) -> bool:
    if trades is None:
        trades = load_trades()
    all_problems: list[str] = []
    for name, fn in CHECKS:
        problems = fn(trades)
        status = "PASS" if not problems else f"FAIL ({len(problems)})"
        if verbose:
            print(f"[{status}] {name}")
            for p in problems:
                print(f"    - {p}")
        all_problems.extend(problems)
    if verbose:
        verdict = "ALL PASS" if not all_problems else f"{len(all_problems)} PROBLEM(S) FOUND"
        print(f"\n{verdict} — {len(trades)} trade rows checked")
    return not all_problems


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
