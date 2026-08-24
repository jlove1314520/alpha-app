"""Reusable FDIC BankFind Suite public REST API client for the US track.

This wraps the logic that marathon round 44 (2026-08-25T04:31, see
US_LOG.md/US_MARATHON_STATE.md) proved out as ad hoc WebFetch calls: bank
name -> CERT lookup via `institutions`, then failure-event detail via
`failures`. That round used it to independently confirm SBNY (Signature
Bank, CERT=57053) was a real FDIC-insured bank failure rather than a data
gap or ticker-reuse artifact. This module is the callable version so a
future US-track `universe.py` analog can call it directly instead of
re-deriving the same requests calls, and so the still-open FRC CERT lookup
(round 44 left this undone) can be answered without another ad hoc probe.

Why this exists (see US_MARATHON_STATE.md "美股存活者偏差" notes): some
US delisted/failed tickers are FDIC-insured banks that never file with SEC
EDGAR at all (12(i) of the Securities Exchange Act routes state-chartered,
non-Fed-member banks to their primary federal regulator -- FDIC for most --
instead of SEC). SEC EDGAR alone will silently look like "no CIK found",
indistinguishable from a real data gap unless you know to check FDIC too.
A future universe.py delisting-detection pass should treat FDIC `failures`
as ground truth for this bank subset, not SEC Form 25.

Endpoint base: `api.fdic.gov/banks/...` (the `banks.data.fdic.gov/api/...`
host 301-redirects here; using the direct host avoids the extra hop).
No authentication/API key required. This is FDIC's own public data
(BankFind Suite), reading it is within MARATHON_PROTOCOL.md 第3節's
"public, no-login" source rule.

Caching mirrors finmind_client.py / sec_edgar_client.py: dumb, exact-key,
on-disk JSON cache under research/data/raw/ (gitignored). Bank name search
results and failure records for a given historical CERT don't change
intra-day (failures are immutable historical facts once recorded), so a
generous cache TTL is safe here -- unlike a live price feed.

Known limitations (not yet needed by round 44's use case, so deliberately
left undone rather than speculatively built):
- `search_institutions()` does an exact-phrase NAME filter server-side, but
  bank name collisions are common (see round 44 and this module's own
  smoke test: 8 distinct "Signature Bank" entities, 3 distinct "First
  Republic Bank" entities) -- caller MUST cross-check CITY/STALP/ESTYMD/
  ENDEFYMD against known facts, same discipline as sec_edgar_client.py's
  ticker-reuse warning. This module does not attempt automatic
  disambiguation.
- No pagination handling beyond a single `limit` param -- fine for
  name-collision counts observed so far (single digits), would need
  revisiting if a name search ever returns hundreds of rows.
- Does not cover the `institutions` endpoint's full field set or the
  `history`/`locations` endpoints -- only what round 44's SBNY/FRC lookups
  needed (institution identity + failure-event detail).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Same identifying-User-Agent spirit as sec_edgar_client.py, even though
# FDIC's public API doesn't document a strict requirement for one -- being
# a good API citizen costs nothing.
HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}

_INSTITUTIONS_URL = "https://api.fdic.gov/banks/institutions"
_FAILURES_URL = "https://api.fdic.gov/banks/failures"

# Failure records and historical institution rows are immutable once
# recorded -- long TTL is safe (contrast with finmind_client.py's price
# data, which needs a short/no TTL because it's live).
_CACHE_MAX_AGE_SECONDS = 30 * 24 * 3600


def _cache_path(name: str) -> Path:
    return DATA_DIR / f"FDIC_{name}.json"


def _cached_get(url: str, params: dict, cache_name: str, timeout: float = 20.0) -> dict:
    path = _cache_path(cache_name)
    if path.exists() and (time.time() - path.stat().st_mtime) < _CACHE_MAX_AGE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _cache_key(url: str, params: dict) -> str:
    raw = url + "?" + json.dumps(params, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def search_institutions(
    name: str,
    fields: tuple[str, ...] = ("NAME", "CERT", "CITY", "STALP", "ESTYMD", "ACTIVE", "ENDEFYMD"),
    limit: int = 20,
) -> list[dict]:
    """Exact-phrase search of `institutions` by NAME. Returns raw rows.

    WARNING: bank name collisions are the norm, not the exception (see
    module docstring). Every row returned needs manual cross-checking
    against known facts (city/state/established/end-date) before a caller
    treats any single row as "the" entity -- this function does not pick
    a winner for you.
    """
    params = {
        "filters": f'NAME:"{name}"',
        "fields": ",".join(fields),
        "limit": limit,
        "format": "json",
    }
    data = _cached_get(_INSTITUTIONS_URL, params, f"institutions_{_cache_key(_INSTITUTIONS_URL, params)}")
    # Each row is {"data": {...fields...}, "score": ...} -- NOT the fields
    # directly. Discovered the hard way: an earlier WebFetch-summarized
    # response silently flattened this nesting away, so a first draft of
    # this function assumed rows were already flat and failed its own
    # smoke test (CERT always None). Trust the raw API shape, not a
    # model-summarized rendering of it.
    return [row["data"] for row in data.get("data", []) if "data" in row]


def get_failure(
    cert: int,
    fields: tuple[str, ...] = (
        "CERT", "NAME", "FAILDATE", "RESTYPE", "RESTYPE1", "SAVR", "QBFDEP", "QBFASSET",
    ),
) -> dict | None:
    """Look up the `failures` record for a given CERT. Returns None if the
    institution never appears in the failures table (e.g. still active, or
    closed for a reason other than a resolvable failure -- FDIC's
    `failures` table is specifically resolution events, not all closures).
    """
    params = {
        "filters": f"CERT:{cert}",
        "fields": ",".join(fields),
        "format": "json",
    }
    data = _cached_get(_FAILURES_URL, params, f"failures_{cert}")
    rows = data.get("data", [])  # same {"data": {...}, "score": ...} nesting as search_institutions
    return rows[0]["data"] if rows and "data" in rows[0] else None


if __name__ == "__main__":
    # Smoke test reproducing round 44's SBNY finding plus the FRC CERT
    # lookup round 44 explicitly left open ("下一輪如果要接，方法完全一樣").
    cases = [
        ("Signature Bank", 57053),  # expect CERT=57053, New York NY, ENDEFYMD 03/12/2023
        ("First Republic Bank", 59017),  # expect CERT=59017, San Francisco CA, ENDEFYMD 05/01/2023
    ]
    for search_name, expected_cert in cases:
        print(f"=== {search_name} ===")
        rows = search_institutions(search_name)
        print(f"  {len(rows)} name-collision candidates found")
        match = next((r for r in rows if r.get("CERT") == expected_cert), None)
        if match is None:
            print(f"  MISMATCH: expected CERT={expected_cert} not found in results")
            continue
        print(f"  matched CERT={match['CERT']}: {match['CITY']}, {match['STALP']}, "
              f"est {match['ESTYMD']}, end {match['ENDEFYMD']}, active={match['ACTIVE']}")
        failure = get_failure(expected_cert)
        if failure is None:
            print("  no failures-table record found")
        else:
            print(f"  failure: {failure['FAILDATE']}, {failure['RESTYPE']}/{failure['RESTYPE1']}, "
                  f"assets=${failure['QBFASSET']:,}k")
