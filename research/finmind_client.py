"""Shared FinMind fetch + local parquet cache layer for the research pipeline.

**Strategy/analysis code must never call _fetch() directly.** The one sanctioned
entry point is load_dev() below, which always caps at VAL_END -- per
CONSTITUTION.md, "資料載入預設就截斷在 holdout 邊界前". _fetch() is the raw,
uncapped primitive; it exists only so load_dev() and load_full_history() (the
one legitimate path to holdout data, used exclusively to feed
validation.holdout.unlock_holdout_once()) have something to build on.

This split exists because a Cowork audit (2026-08-22) found that the original
single fetch() function had no cap at all -- validation.holdout.cap_to_dev()
was opt-in, so any research code that fetched data and forgot to filter it
would silently get holdout rows mixed into what looked like ordinary data.
See STRATEGY_LOG.md's 2026-08-22 entry on this for the full incident writeup.

Caching, independent of the above: every dataset pull should go through one
of the functions in this module, for two reasons:
  1. FinMind's free tier has a rate limit (see DATA.md) -- re-fetching the
     same range on every script run burns quota for nothing.
  2. The cached parquet file under research/data/raw/ IS the audit trail:
     any number downstream can be traced back to the exact raw response it
     came from, by filename.

This deliberately does NOT try to be a smart incremental cache (merging new
date ranges into existing files, deduping, etc). Caching is keyed on the
exact (dataset, data_id, start_date, end_date) request. Ask for a different
range and you get a new cache file, possibly with overlapping data. That is
wasteful of disk but never wrong -- a dumb cache you can trust beats a clever
one that might silently serve stale-and-wrong data. Revisit if disk usage
ever actually becomes a problem.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FM_BASE = "https://api.finmindtrade.com/api/v4/data"


def _cache_path(dataset: str, data_id: str, start_date: str, end_date: str | None) -> Path:
    id_part = data_id or "ALL"
    end_part = end_date or "latest"
    safe = lambda s: str(s).replace("/", "-").replace("\\", "-")
    return DATA_DIR / f"{safe(dataset)}__{safe(id_part)}__{safe(start_date)}__{safe(end_part)}.parquet"


def _fetch(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    force_refresh: bool = False,
    max_retries: int = 3,
    timeout: float = 15.0,
) -> pd.DataFrame:
    """Raw, uncapped fetch of one FinMind dataset, cached to parquet.

    INTERNAL. Do not call this from strategy/analysis code -- use load_dev()
    instead. This has no holdout protection whatsoever; it will happily
    return rows past VAL_END if you ask it to (start_date/end_date exactly as
    given, no clamping).

    Raises RuntimeError if every retry fails -- callers should not silently
    treat a fetch failure as "no data" (that was the App's old bug pattern;
    the research pipeline holds itself to a higher bar than the phone UI).
    """
    path = _cache_path(dataset, data_id, start_date, end_date)
    if path.exists() and not force_refresh:
        return pd.read_parquet(path)

    params = {"dataset": dataset, "start_date": start_date}
    if data_id:
        params["data_id"] = data_id
    if end_date:
        params["end_date"] = end_date

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(FM_BASE, params=params, timeout=timeout)
            if 400 <= resp.status_code < 500:
                # Client error (bad dataset name, bad params, paid-tier gate) -- this will
                # never succeed on retry, so fail fast instead of burning the retry budget.
                raise RuntimeError(
                    f"FinMind rejected the request (HTTP {resp.status_code}): "
                    f"dataset={dataset} data_id={data_id} -- {resp.text[:300]}"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001 -- network/5xx/timeout: worth retrying
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(
            f"FinMind fetch failed after {max_retries} attempts: "
            f"dataset={dataset} data_id={data_id} start={start_date} end={end_date} ({last_err})"
        )

    if isinstance(body, dict) and body.get("status") not in (200, None):
        raise RuntimeError(
            f"FinMind returned status={body.get('status')} msg={body.get('msg')!r} "
            f"for dataset={dataset} data_id={data_id} -- not caching this as if it were valid data"
        )

    data = body.get("data", []) if isinstance(body, dict) else []
    df = pd.DataFrame(data)
    df.to_parquet(path, index=False)
    return df


def load_dev(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    date_col: str = "date",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """THE sanctioned entry point for strategy/analysis code. Always returns
    data capped at VAL_END or earlier -- no row with `date_col` > VAL_END can
    ever come back from this function, full stop.

    `end_date`, if given, further narrows the window (e.g. for a walk-forward
    test that wants dev data only up to some earlier date) but can never
    widen past VAL_END -- passing an end_date after VAL_END is silently
    clamped down to VAL_END, not honored.

    If the underlying dataset has no `date_col` column (e.g. a dataset that
    isn't time-series shaped), this raises rather than skip the check --
    silently trusting an uncapped fetch because "this one probably doesn't
    need it" is exactly the class of assumption that caused the original
    leak. Pass a correct date_col, or use _fetch() directly with a code
    comment explaining why this dataset is exempt.
    """
    from validation.holdout import VAL_END  # local import: avoids a hard import-order

    # requirement between finmind_client and validation at module-load time
    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    df = _fetch(dataset, data_id, start_date, effective_end, force_refresh=force_refresh)
    if df.empty:
        return df
    if date_col not in df.columns:
        raise ValueError(
            f"load_dev(dataset={dataset!r}): no {date_col!r} column to enforce the holdout cap on. "
            "Either pass the correct date_col, or this dataset genuinely isn't a capped time series "
            "and should be fetched with _fetch() directly (with a comment explaining why)."
        )
    # _fetch already asked FinMind for <= effective_end, but re-filter defensively in case the
    # API ever ignores end_date for some dataset -- belt and suspenders, per the whole point of this fix.
    return df[df[date_col] <= effective_end].reset_index(drop=True)


def load_full_history(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Uncapped fetch, through today. The ONLY legitimate use is to build the
    DataFrame handed to validation.holdout.unlock_holdout_once() during a
    real, one-time holdout evaluation -- that function does its own
    logging/locking and will refuse a second unlock.

    Do not call this to "just get the latest data" for ordinary analysis.
    If you find yourself reaching for this function outside of an actual
    holdout unlock, you almost certainly want load_dev() instead.
    """
    return _fetch(dataset, data_id, start_date, end_date=None, force_refresh=force_refresh)


def clear_cache(pattern: str = "*") -> int:
    """Delete cached parquet files matching a glob pattern. Returns count deleted."""
    n = 0
    for p in DATA_DIR.glob(f"{pattern}.parquet"):
        p.unlink()
        n += 1
    return n
