"""Verify the timing hypothesis for `after_market` (night session) rows'
`date` label, per FUT_MARATHON_STATE.md 第60輪's "未解決、留給下一輪" risk
and 下一輪建議工作單位 #1.

Two competing hypotheses for what a night-session row labeled calendar date T
represents (TAIFEX's actual night session runs 15:00 to next-morning 05:00):

  H_A (night(T) follows day(T)):  night session on date T starts right after
      day session T closes (15:00 T) and ends the next morning (05:00 T+1),
      i.e. chronologically it sits BETWEEN day(T) and day(T+1).
  H_B (night(T) precedes day(T)): night session on date T already ended
      before day session T opens, i.e. it sits BETWEEN day(T-1) and day(T).

We cannot get an official TAIFEX trading-calendar document via network calls
(would burn API/robots-restricted budget for a one-off check), so we use an
indirect but standard method: session-boundary price gaps. Markets don't
teleport -- the true chronologically-adjacent session pair should show a
SMALLER average |log-return| gap at the boundary than the wrong pairing,
because the wrong pairing spans an entire extra session's worth of
information flow. We test this on both boundaries (night-open vs surrounding
day-closes, night-close vs surrounding day-opens) using every single-month
TX contract_date in the full history, zero new API calls (same on-disk
parquet cache key as fut_probe_night_session.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from continuous_contract import FULL_HISTORY_END, FULL_HISTORY_START
from finmind_client import load_dev


def _log_gap(a: pd.Series, b: pd.Series) -> pd.Series:
    return (np.log(a.astype(float)) - np.log(b.astype(float))).abs()


def main() -> None:
    df = load_dev("TaiwanFuturesDaily", "TX", start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    df["date"] = pd.to_datetime(df["date"])

    is_spread = df["contract_date"].astype(str).str.contains("/")
    df = df[~is_spread].copy()
    df["contract_date"] = df["contract_date"].astype(int)

    night = df[df["trading_session"] == "after_market"][["date", "contract_date", "open", "close"]].copy()
    day = df[df["trading_session"] == "position"][["date", "contract_date", "open", "close"]].copy()
    night = night.rename(columns={"open": "n_open", "close": "n_close"})
    day = day.rename(columns={"open": "d_open", "close": "d_close"})

    print(f"night rows (single-month only): {len(night)}, day rows (single-month only): {len(day)}")

    # Zero-volume days (no trade, common for far-month contracts) leave open==close==0.0
    # rather than NaN in this dataset -- confirmed via direct inspection (1,386/42,995 rows
    # league-wide, ~1.4% within night session, matches fut_probe_night_session.py's earlier
    # note). log(0) => -inf and corrupts mean-based comparisons, so drop them explicitly
    # rather than relying on dropna (which wouldn't catch 0.0).
    night = night[(night["n_open"] > 0) & (night["n_close"] > 0)]
    day = day[(day["d_open"] > 0) & (day["d_close"] > 0)]

    rows = []
    for cid, day_c in day.groupby("contract_date"):
        night_c = night[night["contract_date"] == cid]
        if night_c.empty:
            continue
        day_c = day_c.sort_values("date").reset_index(drop=True)
        day_c["prev_close"] = day_c["d_close"].shift(1)
        day_c["prev_date"] = day_c["date"].shift(1)
        day_c["next_open"] = day_c["d_open"].shift(-1)
        day_c["next_date"] = day_c["date"].shift(-1)
        merged = night_c.merge(day_c, on=["contract_date", "date"], how="inner")
        rows.append(merged)

    m = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    print(f"\nnight rows with a same-date day-session row in the same contract_date: {len(m)} / {len(night)}")
    if m.empty:
        print("No overlapping rows -- cannot test. Stop here.")
        return

    # --- night_open boundary: does it sit closer to day_close(T) (H_A) or day_close(T-1) (H_B)? ---
    valid_open = m.dropna(subset=["n_open", "d_close", "prev_close"])
    gap_open_HA = _log_gap(valid_open["n_open"], valid_open["d_close"])       # night(T) right after day(T)
    gap_open_HB = _log_gap(valid_open["n_open"], valid_open["prev_close"])    # night(T) right after day(T-1)
    print(f"\n[night_open boundary] n={len(valid_open)}")
    print(f"  H_A pairing |ln(n_open(T) / d_close(T))|      mean={gap_open_HA.mean():.6f}  median={gap_open_HA.median():.6f}")
    print(f"  H_B pairing |ln(n_open(T) / d_close(T-1))|    mean={gap_open_HB.mean():.6f}  median={gap_open_HB.median():.6f}")
    win_open = (gap_open_HA < gap_open_HB).mean()
    print(f"  fraction of rows where H_A gap < H_B gap: {win_open:.1%}")

    # --- night_close boundary: does it sit closer to day_open(T+1) (H_A) or day_open(T) (H_B)? ---
    valid_close = m.dropna(subset=["n_close", "d_open", "next_open"])
    gap_close_HA = _log_gap(valid_close["next_open"], valid_close["n_close"])  # night(T) closes, day(T+1) opens next
    gap_close_HB = _log_gap(valid_close["d_open"], valid_close["n_close"])     # night(T) closes, day(T) opens next (same date)
    print(f"\n[night_close boundary] n={len(valid_close)}")
    print(f"  H_A pairing |ln(d_open(T+1) / n_close(T))|    mean={gap_close_HA.mean():.6f}  median={gap_close_HA.median():.6f}")
    print(f"  H_B pairing |ln(d_open(T) / n_close(T))|      mean={gap_close_HB.mean():.6f}  median={gap_close_HB.median():.6f}")
    win_close = (gap_close_HA < gap_close_HB).mean()
    print(f"  fraction of rows where H_A gap < H_B gap: {win_close:.1%}")

    # --- sanity baseline: same-date day close vs day open of the SAME day session (should be
    # a same-session intraday move, not a boundary gap -- gives a rough sense of scale so the
    # two hypothesis gaps above aren't interpreted in a vacuum). ---
    day_intraday_src = m.dropna(subset=["d_open", "d_close"])
    same_day_intraday = _log_gap(day_intraday_src["d_close"], day_intraday_src["d_open"])
    print(f"\n[reference scale] same-day day-session |ln(d_close/d_open)| mean={same_day_intraday.mean():.6f} (intraday move, not a boundary gap)")

    print("\n=== VERDICT ===")
    if win_open > 0.5 and win_close > 0.5 and gap_open_HA.mean() < gap_open_HB.mean() and gap_close_HA.mean() < gap_close_HB.mean():
        print("H_A supported on both boundaries and on majority-of-rows basis: night(T) sits chronologically "
              "BETWEEN day(T) and day(T+1), i.e. night(T) STARTS after day(T) closes and ENDS before day(T+1) opens.")
    elif win_open < 0.5 and win_close < 0.5 and gap_open_HB.mean() < gap_open_HA.mean() and gap_close_HB.mean() < gap_close_HA.mean():
        print("H_B supported on both boundaries: night(T) sits chronologically BETWEEN day(T-1) and day(T).")
    else:
        print("MIXED / INCONCLUSIVE signal across the two boundaries -- do not treat either hypothesis as "
              "confirmed. Record as unresolved and do not proceed to build a night-session continuous series "
              "or session-effect hypothesis until this is clarified with an independent source (e.g. TAIFEX "
              "official trading-hours documentation).")


if __name__ == "__main__":
    main()
