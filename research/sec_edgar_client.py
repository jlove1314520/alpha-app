"""Reusable SEC EDGAR public JSON API client for the US track.

This wraps the logic that `sec_edgar_probe.py` (2026-08-23, marathon round 3)
proved out ad hoc: ticker->CIK lookup and per-filing filingDate/reportDate
extraction (the PIT signal for US 10-K/10-Q filings). That script was a
one-off probe meant to be read by hand; this module is the callable version
so later work (a future `pit.py` analog, `universe.py` analog, etc.) doesn't
have to re-copy the same requests calls.

Scope, deliberately narrow (see US_MARATHON_STATE.md 下一輪建議工作單位 item 5,
extended item 10 in round 61): this module covers the
`submissions/CIK{cik}.json` endpoint's `filings.recent` block, plus optional
pagination into its `filings.files[]` archive pointers (`full_history=True`
on `get_filing_dates()`) for filers whose recent window doesn't reach back
far enough. It does NOT wrap the XBRL company-facts endpoint (`sec_edgar_xbrl_facts_probe.py` /
`sec_edgar_xbrl_facts_dedup_probe.py`) or the delisting/Form-25 probes
(`sec_edgar_delisting_probe.py`, `sec_edgar_frc_cik_probe.py`) -- those are
separate, still-probe-only concerns with their own open questions (see
US_MARATHON_STATE.md) and shouldn't be bolted onto this module speculatively.

Known limitations carried over from the probe scripts (see
US_MARATHON_STATE.md for full detail -- not re-litigated here):
- Ticker->CIK is many-to-one over time (ticker reuse is real and dangerous,
  see US_MARATHON_STATE.md "美股存活者偏差" notes) -- get_cik() resolves the
  *current* mapping only. It is not a substitute for the entity-identity
  verification work done by hand in sec_edgar_frc_cik_probe.py for known
  delisted/reused tickers.
- No XBRL-based PIT correction (pre-XBRL-mandate gap, pre-IPO gap) is applied
  here -- get_filing_dates() returns raw filingDate/reportDate pairs only.

Caching mirrors finmind_client.py's approach: dumb, exact-key, on-disk JSON
cache under research/data/raw/ (gitignored). SEC's fair-use policy asks for
an identifying User-Agent and reasonable request volume (documented
~10 req/sec ceiling) -- caching avoids re-hitting the same CIK/ticker-map
endpoint across repeated runs within a marathon session.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Not the user's personal email (jlove201314@yahoo.com.tw) -- CLAUDE.md /
# system rules say never send that to an unrelated third-party service.
# This is a project-identifying placeholder per SEC's fair-use guidance.
HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_CACHE_MAX_AGE_SECONDS = 24 * 3600  # ticker map / filing lists don't change intra-day


def _cache_path(name: str) -> Path:
    return DATA_DIR / f"SEC_{name}.json"


def _cached_get(url: str, cache_name: str, timeout: float = 20.0) -> dict:
    path = _cache_path(cache_name)
    if path.exists() and (time.time() - path.stat().st_mtime) < _CACHE_MAX_AGE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def get_cik_map() -> dict[str, int]:
    """Return {ticker: cik} from SEC's current ticker->CIK map.

    This is a snapshot of *today's* mapping, not a historical record --
    a ticker that was reused (see US_MARATHON_STATE.md) will only show the
    CIK of whichever company currently holds that ticker.
    """
    data = _cached_get(_TICKER_MAP_URL, "cik_map")
    return {v["ticker"]: v["cik_str"] for v in data.values()}


def get_cik(ticker: str, cik_map: dict[str, int] | None = None) -> int | None:
    """Look up a single ticker's current CIK. Returns None if not found."""
    cik_map = cik_map if cik_map is not None else get_cik_map()
    return cik_map.get(ticker)


def get_submissions(cik: int) -> dict:
    """Raw submissions/CIK{cik}.json payload for a given CIK.

    Cached per-CIK (not shared with get_cik_map's cache). Caller is
    responsible for verifying the CIK actually corresponds to the intended
    entity -- see the ticker-reuse warning in the module docstring.
    """
    cik_padded = str(cik).zfill(10)
    url = _SUBMISSIONS_URL.format(cik=cik_padded)
    return _cached_get(url, f"submissions_{cik_padded}")


def _filings_to_records(
    filings_block: dict, forms: tuple[str, ...]
) -> list[dict]:
    """Shared parsing for one filings-shaped block (either `filings.recent`
    from the submissions payload, or a `filings.files[]` archive file's
    top-level payload -- both have the same array-of-parallel-fields shape,
    confirmed by direct probe 2026-08-25 marathon round 61 against
    CIK0000320193-submissions-001.json)."""
    n = len(filings_block.get("form", []))
    out = []
    for i in range(n):
        form = filings_block["form"][i]
        if form not in forms:
            continue
        fd, rd = filings_block["filingDate"][i], filings_block["reportDate"][i]
        if not fd or not rd:
            continue
        gap_days = (date.fromisoformat(fd) - date.fromisoformat(rd)).days
        out.append({"form": form, "filingDate": fd, "reportDate": rd, "gap_days": gap_days})
    return out


def get_archive_filings(cik: int, file_name: str) -> dict:
    """Fetch one `filings.files[]` archive pointer's JSON payload.

    `file_name` comes from `get_submissions(cik)["filings"]["files"]`, e.g.
    "CIK0000320193-submissions-001.json". Cached per-file (the file name
    itself is the cache key, since archive files are immutable once SEC
    publishes them -- unlike the 'recent' window they never change, so the
    24h cache-max-age in `_cached_get` is conservative but harmless here).
    """
    url = f"https://data.sec.gov/submissions/{file_name}"
    cache_key = file_name.replace(".json", "")
    return _cached_get(url, f"archive_{cache_key}")


def get_filing_dates(
    cik: int,
    forms: tuple[str, ...] = ("10-K", "10-Q"),
    full_history: bool = False,
) -> list[dict]:
    """Return the PIT signal: one dict per matching filing, each with
    form/filingDate/reportDate/gap_days (filingDate - reportDate, in
    calendar days).

    By default (`full_history=False`) only covers the `filings.recent`
    rolling window -- for long-tenured large filers this can be as shallow
    as ~5-10 years (observed for AAPL/MSFT, see US_MARATHON_STATE.md
    round 59). Set `full_history=True` to also paginate through every
    `filings.files[]` archive pointer, extending coverage back to the
    filer's earliest EDGAR filing (AAPL: 1994, confirmed by direct probe
    round 61). This costs one extra HTTP request per archive file (cached
    thereafter) -- for filers with few archive files this is cheap, but is
    unverified for filers with many (e.g. very frequent Section 16 filers).

    Silently skips filings missing either date field (observed in practice
    for some non-10-K/10-Q form types, not expected for 10-K/10-Q but kept
    defensive since this is unverified across the full filer population).
    Does not attempt to de-duplicate across recent/archive boundaries --
    unverified whether SEC guarantees no overlap, but the two are described
    as covering disjoint date ranges (`filingFrom`/`filingTo` per archive
    file) so overlap is not expected in practice.
    """
    data = get_submissions(cik)
    out = _filings_to_records(data.get("filings", {}).get("recent", {}), forms)
    if full_history:
        for archive in data.get("filings", {}).get("files", []):
            archive_data = get_archive_filings(cik, archive["name"])
            out.extend(_filings_to_records(archive_data, forms))
    return out


if __name__ == "__main__":
    # Smoke test mirroring sec_edgar_probe.py's original manual run, to
    # confirm the wrapped functions reproduce the same shape of result.
    # Uses the on-disk cache from prior probe-script runs if present, so
    # this doesn't necessarily burn a fresh SEC request.
    cik_map = get_cik_map()
    for ticker in ["AAPL", "MSFT", "PLTR"]:
        cik = get_cik(ticker, cik_map)
        print(f"{ticker}: CIK={cik}")
        if cik is None:
            continue
        filings = get_filing_dates(cik)
        gaps = [f["gap_days"] for f in filings]
        if gaps:
            print(
                f"  recent-only: n={len(gaps)}, earliest={min(f['filingDate'] for f in filings)}, "
                f"min_gap={min(gaps)}, max_gap={max(gaps)}, avg_gap={sum(gaps) / len(gaps):.1f}"
            )
        else:
            print("  no 10-K/10-Q filings in recent window")

        filings_full = get_filing_dates(cik, full_history=True)
        gaps_full = [f["gap_days"] for f in filings_full]
        if gaps_full:
            print(
                f"  full_history: n={len(gaps_full)}, earliest={min(f['filingDate'] for f in filings_full)}, "
                f"min_gap={min(gaps_full)}, max_gap={max(gaps_full)}, avg_gap={sum(gaps_full) / len(gaps_full):.1f}"
            )
        else:
            print("  full_history: no 10-K/10-Q filings found")
