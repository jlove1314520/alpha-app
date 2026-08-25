"""US equity universe construction -- first draft (marathon round, US track).

**Status: explicitly NOT a complete survivorship-bias correction.** Per
US_MARATHON_STATE.md's "下一輪建議工作單位" item 6: the honest current
approach is "現存股票 + 已知的少數下市股手動名單", clearly labeled as such,
not dressed up as an automated solution that doesn't exist yet. Do not treat
`universe()`'s output as bias-free the way TW's `universe.py` output roughly
is (see that module's own caveats too -- TW isn't perfectly bias-free
either, but its known-gap is much smaller: TaiwanStockDelisting is a
proper, queryable delisted-name feed; the US side has no such feed at all,
see below).

**Why this can't mirror universe.py's method (2026-08-23/24/25 findings,
see US_MARATHON_STATE.md "美股存活者偏差調查" sections + us_delisting_client.py):**
- TW's method treats "does TaiwanStockPrice have a row for stock X on date D"
  as ground truth for tradeability. This does NOT work for US: 3/5 known-
  delisted tickers (TWTR/SIVB/FRC) return a completely EMPTY USStockPrice
  history on FinMind's free tier -- the price history vanishes rather than
  being retained through the last trading day.
- USStockInfo's snapshot-membership-diff method also doesn't work: TWTR
  (delisted 2022, actively traded for years before that) appears in only
  1 of 289 historical snapshots, proving the snapshot feed itself has
  coverage gaps unrelated to delisting.
- There is no free FinMind dataset equivalent to TaiwanStockDelisting for
  US equities. The only reliable sources found so far are per-ticker,
  not a queryable "give me the whole delisted list" feed: SEC EDGAR
  Form 25-family filings (via sec_edgar_client.py, wrapped into a decision
  function by us_delisting_client.py) and, for the small subset of tickers
  that are FDIC-insured banks that never filed with the SEC at all, the FDIC
  BankFind Suite failures table (fdic_client.py). Both require the caller to
  already know which ticker to check -- there is no "enumerate everyone who
  delisted between date A and date B" primitive here, unlike TaiwanStockDelisting.

**This module's actual approach, first version:**
1. `active_stock_ids()`: the latest USStockInfo snapshot, filtered to drop
   ETFs (Subsector == 'ETF', ~5,247/12,429 rows in the 2026-08-22 snapshot --
   this module is for equity factor research, not ETF research) and SPAC-
   related non-common-stock line items (warrants/units/rights -- these are
   derivative instruments layered on top of a SPAC's common stock, not a
   separate operating company; ~565 rows). This is a judgment call, not a
   validated rule -- flagged here so a future round can revisit if it turns
   out to drop something that should have stayed.
2. `known_delisted_stock_ids()`: a small, HAND-MAINTAINED table of the 5
   tickers this project has already independently verified as delisted
   across marathon rounds 4/5/7/41/44/47/50 (see us_delisting_client.py's
   own __main__ smoke test, which re-derives the same 5 answers
   programmatically as a cross-check). This is NOT an automated discovery
   process -- it is exactly as complete as this project's manual
   investigation history, which is to say: 5 tickers, out of an unknown
   (probably much larger) true population of US equities that delisted
   during the dev/val window. **Any backtest over `universe()`'s combined
   output still has an unquantified survivorship-bias gap** -- this module
   only removes the bias for the 5 specific names investigated so far, it
   does not claim the gap is closed.
3. `universe()`: active + known_delisted, same status/delist_date shape as
   TW's `universe.py` for interface consistency, but with an extra
   `bias_correction` column making the incompleteness impossible to miss
   downstream (constant 'active_snapshot_plus_hand_verified_delisted', not a
   free-text warning that's easy to skip past).

**On SIVB's date**: us_delisting_client.py's automated classifier flags SIVB
as "confirmed_sec_form25_multiple_events_ambiguous" (an unrelated 2017-2018
Form 25 cluster, likely a preferred-stock delisting, alongside the real 2023
common-stock collapse) -- it deliberately refuses to auto-pick a date. This
module uses the human-vetted date (2023-05-02, the collapse-driven common-
stock delisting, per US_MARATHON_STATE.md round 5) rather than re-running
the ambiguous automated path, and records that choice in `source_detail`.

Deliberately reuses `_fetch()` directly (not `load_dev()`) for USStockInfo,
same reasoning as TW's `universe.py`: this is a membership/snapshot dataset
whose `date` column is a scrape timestamp, not a trading date -- routing it
through load_dev()'s VAL_END cap would filter out literally every row (the
snapshot is stamped near-today) and return an empty universe.
"""
from __future__ import annotations

import pandas as pd

from finmind_client import _fetch

# Hand-verified across marathon rounds 4/5/7/41/44/47/50 -- see module
# docstring and us_delisting_client.py's __main__ smoke test for how each
# date was independently confirmed (SEC EDGAR Form 25 for TWTR/SIVB/BBBY,
# FDIC BankFind Suite failures record for SBNY/FRC).
KNOWN_DELISTED = [
    {"stock_id": "TWTR", "stock_name": "Twitter, Inc.", "delist_date": "2022-10-28",
     "source": "sec_edgar_form25", "note": "single clean event"},
    {"stock_id": "SIVB", "stock_name": "SVB Financial Group", "delist_date": "2023-05-02",
     "source": "sec_edgar_form25_human_disambiguated",
     "note": "automated classifier returns ambiguous (unrelated 2017-2018 Form 25 "
             "cluster present too); this date is the human-vetted collapse-driven "
             "common-stock delisting, not an automated pick"},
    {"stock_id": "BBBY", "stock_name": "Bed Bath & Beyond Inc.", "delist_date": "2023-07-10",
     "source": "sec_edgar_form25", "note": "single clean event; current ticker "
             "reassigned post-delisting, do not resolve BBBY via the live ticker map"},
    {"stock_id": "SBNY", "stock_name": "Signature Bank", "delist_date": "2023-03-12",
     "source": "fdic_failure", "note": "state-chartered non-Fed-member bank, "
             "never filed with SEC (12(i) exemption) -- no SEC CIK exists for this entity"},
    {"stock_id": "FRC", "stock_name": "First Republic Bank", "delist_date": "2023-05-01",
     "source": "fdic_failure", "note": "same 12(i) exemption pattern as SBNY"},
]

_ETF_SUBSECTOR = "ETF"
_NON_COMMON_STOCK_PATTERNS = ("Warrant", "Units", "Rights")


def active_stock_ids() -> pd.DataFrame:
    """Latest USStockInfo snapshot, ETFs and SPAC warrants/units/rights
    dropped. Columns: stock_id, stock_name, subsector, market_cap, ipo_year."""
    info = _fetch("USStockInfo", "", "2000-01-01")
    latest_date = info["date"].max()
    info = info[info["date"] == latest_date].drop_duplicates(subset="stock_id", keep="last")
    info = info[info["Subsector"] != _ETF_SUBSECTOR]
    non_common = info["stock_name"].str.contains(
        "|".join(_NON_COMMON_STOCK_PATTERNS), case=False, na=False
    )
    info = info[~non_common]
    info = info.rename(columns={
        "Subsector": "subsector", "MarketCap": "market_cap", "IPOYear": "ipo_year",
    })
    return info[["stock_id", "stock_name", "subsector", "market_cap", "ipo_year"]].reset_index(drop=True)


def known_delisted_stock_ids() -> pd.DataFrame:
    """The hand-maintained list documented in the module docstring. Columns:
    stock_id, stock_name, delist_date, source, note."""
    return pd.DataFrame(KNOWN_DELISTED)


def universe() -> pd.DataFrame:
    """Combined universe: active snapshot + hand-verified delisted names.

    Returns columns: stock_id, stock_name, subsector, market_cap, ipo_year,
    status ('active'|'delisted'), delist_date (NaT if active),
    bias_correction (constant string flagging this is NOT a complete
    survivorship-bias fix -- see module docstring before using this for any
    backtest that claims to be survivorship-bias-mitigated).
    """
    active = active_stock_ids().assign(status="active", delist_date=pd.NaT)
    delisted = known_delisted_stock_ids().assign(
        status="delisted", subsector=None, market_cap=None, ipo_year=None
    )
    delisted["delist_date"] = pd.to_datetime(delisted["delist_date"])
    cols = ["stock_id", "stock_name", "subsector", "market_cap", "ipo_year", "status", "delist_date"]
    combined = pd.concat([active[cols], delisted[cols]], ignore_index=True)
    # defensive: if a known-delisted ticker somehow still shows up in the
    # active snapshot (e.g. ticker reuse -- see BBBY's note above), keep the
    # verified 'delisted' row, not the possibly-wrong live snapshot row.
    combined = combined.sort_values("status", ascending=False).drop_duplicates(subset="stock_id", keep="first")
    combined["bias_correction"] = "active_snapshot_plus_hand_verified_delisted__NOT_COMPLETE"
    return combined.reset_index(drop=True)


if __name__ == "__main__":
    u = universe()
    n_active = (u["status"] == "active").sum()
    n_delisted = (u["status"] == "delisted").sum()
    print(f"universe(): {len(u)} rows total ({n_active} active, {n_delisted} known-delisted)")
    print(u[u["status"] == "delisted"][["stock_id", "stock_name", "delist_date"]].to_string(index=False))
    assert n_delisted == len(KNOWN_DELISTED), "known-delisted row count should exactly match KNOWN_DELISTED"
    print("OK: known-delisted rows all survived the dedup step unclobbered by the active snapshot.")
