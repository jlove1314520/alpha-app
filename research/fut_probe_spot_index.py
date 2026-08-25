"""Probe: does FinMind's free tier expose a usable daily TAIEX spot price
index (加權指數本身的價格序列，不是還原/報酬指數)，as the foundational data
source needed for a basis (期現價差) family hypothesis per
MARATHON_PROTOCOL.md 5 ("期現價差basis，近月期貨 vs 現貨指數")?

This is pure 1c infra probing -- item 2 in FUT_MARATHON_STATE.md's "下一輪
建議工作單位" (the basis-family foundation branch, chosen this round instead
of touching continuous_contract.py for night-session awareness, since that
is higher-risk core-infra work better done in its own dedicated round).

Per MARATHON_PROTOCOL.md section 3's rule on web-sourced leads: WebSearch/
WebFetch summaries of FinMind's docs this round gave inconsistent/uncertain
answers about which exact dataset+data_id returns a plain OHLC price index
for TAIEX (as opposed to the 報酬指數/total-return index, which tracks a
different, dividend-reinvested series and would NOT be the right thing to
subtract from futures settlement price for a basis calc). So: treat those
doc summaries as leads only, verify empirically against the live API with a
SHORT date range each (cheap: a handful of small requests, not a full-
history pull) before trusting any of them as the actual data source.

All fetches go through finmind_client.load_dev() (holdout-safe), per
MARATHON_PROTOCOL.md section 4.
"""
from __future__ import annotations

from finmind_client import load_dev

# Short recent window -- enough to see shape/columns/values without burning
# a meaningful chunk of the hourly rate limit on candidates that turn out to
# be wrong.
PROBE_START = "2024-01-01"
PROBE_END = "2024-01-31"

CANDIDATES = [
    ("TaiwanStockPrice", "TAIEX"),
    ("TaiwanVariousIndicators5Seconds", ""),
    ("TaiwanStockTotalReturnIndex", "TAIEX"),
]


def probe_one(dataset: str, data_id: str) -> None:
    print(f"\n=== dataset={dataset!r} data_id={data_id!r} ===")
    try:
        df = load_dev(dataset, data_id, start_date=PROBE_START, end_date=PROBE_END)
    except Exception as e:  # noqa: BLE001 -- want to see and report every failure mode, not crash the probe
        print(f"FAILED: {type(e).__name__}: {e}")
        return

    if df.empty:
        print("returned EMPTY dataframe (dataset/data_id combo likely wrong, or no data in this window)")
        return

    print(f"rows: {len(df)}")
    print(f"columns: {list(df.columns)}")
    print(df.head(5).to_string())


def probe_full_history_winner() -> None:
    """Once the short-window probe above identifies the right (dataset, data_id)
    pair, pull the full continuous-contract-matching history range and check
    coverage/gaps -- still one single request (this dataset isn't per-stock),
    not a per-ticker backfill, so this is cheap regardless of the outcome.
    """
    from continuous_contract import FULL_HISTORY_END, FULL_HISTORY_START

    print(f"\n=== full-history check: TaiwanStockPrice/TAIEX, {FULL_HISTORY_START}..{FULL_HISTORY_END} ===")
    df = load_dev("TaiwanStockPrice", "TAIEX", start_date=FULL_HISTORY_START, end_date=FULL_HISTORY_END)
    print(f"rows: {len(df)}")
    if df.empty:
        print("EMPTY over full range -- unexpected given the short-window probe succeeded, investigate before use.")
        return
    print(f"date range: {df['date'].min()} .. {df['date'].max()}")
    for col in ("open", "max", "min", "close"):
        n_null = df[col].isna().sum()
        n_nonpos = (df[col] <= 0).sum()
        print(f"{col}: null={n_null}, <=0={n_nonpos}")
    # sanity: TAIEX open should never be exactly 0 (that would indicate a bad/placeholder
    # row, same class of check as continuous_contract.py does on futures OHLC).
    dup_dates = df["date"].duplicated().sum()
    print(f"duplicate date rows: {dup_dates}")


def main() -> None:
    for dataset, data_id in CANDIDATES:
        probe_one(dataset, data_id)
    probe_full_history_winner()


if __name__ == "__main__":
    main()
