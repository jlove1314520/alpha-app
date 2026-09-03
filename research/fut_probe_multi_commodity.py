"""Probe: does FinMind's TaiwanFuturesDaily carry other TAIFEX products besides
TX, with enough depth/history to eventually pool as a "cross-sectional" set of
instruments for a portfolio-level backtest -- analogous to how TW/US stocks
have many names, FUT currently has exactly one (TX), which is why the
2026-09-04 portfolio-strategy-axis decree (CALIBRATION_PROBE.md, round 328
FUT_LEADS.md entry) flagged multi-commodity pooling as the only plausible path
to a "portfolio" concept on the futures track.

This round (marathon round ~332) is step 1 of that direction: pure data-
availability check, zero strategy testing, zero factor design. Read-only via
finmind_client.load_dev() (dev-capped, same as every other FUT script).

Candidates checked: MTX (小型台指), TE (電子期), TF (金融期) -- the three
named in FUT_LEADS.md round 328 as "未來可考慮的方向". Uses the exact same
(FULL_HISTORY_START, FULL_HISTORY_END) window as continuous_contract.py so
each call is a single full-history fetch (same convention as TX), not an
incremental/narrow probe.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import FULL_HISTORY_START, FULL_HISTORY_END
from finmind_client import load_dev

CANDIDATES = ["MTX", "TE", "TF"]


def probe_one(contract: str) -> dict:
    df = load_dev("TaiwanFuturesDaily", contract, start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    if df.empty:
        return {"contract": contract, "available": False, "rows": 0}
    df["date"] = pd.to_datetime(df["date"])
    single_month = df[~df["contract_date"].astype(str).str.contains("/")].copy()
    sessions = sorted(single_month["trading_session"].unique().tolist()) if "trading_session" in single_month.columns else []
    return {
        "contract": contract,
        "available": True,
        "rows_raw": len(df),
        "rows_single_month": len(single_month),
        "date_min": str(single_month["date"].min().date()) if not single_month.empty else None,
        "date_max": str(single_month["date"].max().date()) if not single_month.empty else None,
        "sessions": sessions,
        "distinct_contract_dates": single_month["contract_date"].nunique() if not single_month.empty else 0,
    }


if __name__ == "__main__":
    results = []
    for c in CANDIDATES:
        try:
            r = probe_one(c)
        except Exception as e:  # noqa: BLE001 -- probe script, honest-fail per-contract
            r = {"contract": c, "available": False, "error": repr(e)}
        results.append(r)
        print(r)

    print("\n=== 摘要 ===")
    for r in results:
        print(r)
