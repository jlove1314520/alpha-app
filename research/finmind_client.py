"""Shared FinMind fetch + local parquet cache layer for the research pipeline.

Every dataset pull in this project should go through fetch() here, for two
reasons:
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


def fetch(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    force_refresh: bool = False,
    max_retries: int = 3,
    timeout: float = 15.0,
) -> pd.DataFrame:
    """Fetch one FinMind dataset, cached to parquet. Returns a DataFrame.

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


def clear_cache(pattern: str = "*") -> int:
    """Delete cached parquet files matching a glob pattern. Returns count deleted."""
    n = 0
    for p in DATA_DIR.glob(f"{pattern}.parquet"):
        p.unlink()
        n += 1
    return n
