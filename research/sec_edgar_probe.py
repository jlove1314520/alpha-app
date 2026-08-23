"""US track, marathon round 2026-08-23 (round 3): first live probe of the SEC
EDGAR public JSON API, following up on the round-2 documentation-only survey
(see DATA.md "美股 PIT 資料源調查" and US_LOG.md round 2 entry).

That round only read third-party docs describing `filingDate`/`reportDate`
fields; nothing was actually fetched from `data.sec.gov`. This script makes
the first real HTTP calls to confirm the documented structure is real,
usable, and precise enough to build a US-track pit.py analog on top of.

Three endpoints tested, all public/no-auth per SEC's own developer docs:
- https://www.sec.gov/files/company_tickers.json          (ticker -> CIK map)
- https://data.sec.gov/submissions/CIK{cik}.json           (filing list, has
  both filingDate and reportDate per filing -- this is the PIT signal)
- https://data.sec.gov/robots.txt and www.sec.gov/robots.txt were checked by
  hand before this script was written (data.sec.gov has none -> no crawl
  restriction on it; www.sec.gov's robots.txt doesn't disallow /files/ or the
  data.sec.gov subdomain). Not re-checked here on every run to avoid an extra
  request; if SEC's policy changes, re-verify by hand before reusing this
  script's User-Agent pattern.

Rate/identification: SEC's fair-use policy asks for an identifying
User-Agent string. This script uses a project-identifying placeholder
(not the actual user's personal email -- CLAUDE.md/system rules say not to
send the user's real email to unrelated third-party services), and makes at
most a handful of requests per run, well under SEC's documented ~10 req/sec
guidance.

This script only fetches SEC EDGAR data (not FinMind, not alpha.db), so the
holdout-boundary rules in MARATHON_PROTOCOL.md section 4 don't apply to it --
there's no VAL_END concept for SEC filing metadata. It prints; it does not
write to any other research/*.md file itself (those get updated by hand
after reading this script's output, same convention as us_probe_milestone1.py).
"""
from __future__ import annotations

from datetime import date

import requests

HEADERS = {"User-Agent": "AlphaResearchMarathon-USTrack contact@alpha-research-project.example"}


def probe_ticker_cik_map(sample_tickers: list[str]) -> dict[str, int]:
    print("=== 1. Ticker -> CIK map (www.sec.gov/files/company_tickers.json) ===")
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}, content-type={r.headers.get('Content-Type')}")
    data = r.json()
    print(f"  entry count: {len(data)}")
    by_ticker = {v["ticker"]: v["cik_str"] for v in data.values()}
    found = {}
    for t in sample_tickers:
        cik = by_ticker.get(t)
        print(f"  {t}: CIK={cik}")
        if cik is not None:
            found[t] = cik
    return found


def probe_submissions(ticker: str, cik: int) -> None:
    print(f"\n=== 2. Submissions API ({ticker}, CIK={cik}) ===")
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    print(f"  status={r.status_code}, content-type={r.headers.get('Content-Type')}")
    if r.status_code != 200:
        print(f"  FAILED, body snippet: {r.text[:300]}")
        return
    data = r.json()
    recent = data.get("filings", {}).get("recent", {})
    n = len(recent.get("form", []))
    print(f"  top-level keys: {list(data.keys())}")
    print(f"  filings.recent keys: {list(recent.keys())}")
    print(f"  filings.recent row count: {n}")

    gaps = []
    for i in range(n):
        form = recent["form"][i]
        if form in ("10-K", "10-Q"):
            fd, rd = recent["filingDate"][i], recent["reportDate"][i]
            if fd and rd:
                gaps.append((date.fromisoformat(fd) - date.fromisoformat(rd)).days)
    if gaps:
        print(
            f"  10-K/10-Q filingDate-minus-reportDate gap (days): "
            f"n={len(gaps)}, min={min(gaps)}, max={max(gaps)}, avg={sum(gaps) / len(gaps):.1f}"
        )
    else:
        print("  no 10-K/10-Q filings found in the 'recent' window (may be a smaller/newer filer)")

    archive_files = data.get("filings", {}).get("files", [])
    print(f"  older-filings archive pointers (files[]): {archive_files}")
    print(f"  earliest filingDate in 'recent' window: {min(recent['filingDate']) if n else 'N/A'}")


if __name__ == "__main__":
    # AAPL + one mid-sized, more recently active filer as a second data point
    # (round 2's price-depth probe only tested mega-caps; doing the same
    # mistake twice for the PIT probe would leave the same blind spot).
    cik_map = probe_ticker_cik_map(["AAPL", "MSFT", "PLTR"])
    for ticker, cik in cik_map.items():
        probe_submissions(ticker, cik)
