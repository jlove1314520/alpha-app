"""Futures track, marathon round 2026-08-24: root-cause probe for the
`institutional_investors` garbled-text problem in `TaiwanFuturesInstitutionalInvestors`
noted in DATA.md section 6 / FUT_MARATHON_STATE.md's "next round" priority #1.

This deliberately bypasses finmind_client._fetch()'s parquet cache and calls
`requests.get` directly, because the cached parquet already has the *decoded*
(garbled) strings baked in -- to find the root cause we need to see the raw
response bytes and headers, not the already-mangled cached value.

Still respects the holdout boundary: uses the same narrow window
(2024-06-03..2024-06-07) already probed in fut_probe_milestone1.py, which is
well inside VAL_END (2024-12-31). This is a one-off diagnostic call, not a
new sanctioned data-loading path -- do not reuse this pattern for factor code.
"""
from __future__ import annotations

import requests

FM_BASE = "https://api.finmindtrade.com/api/v4/data"


def probe() -> None:
    params = {
        "dataset": "TaiwanFuturesInstitutionalInvestors",
        "data_id": "TX",
        "start_date": "2024-06-03",
        "end_date": "2024-06-07",
    }
    resp = requests.get(FM_BASE, params=params, timeout=15.0)
    print(f"HTTP status: {resp.status_code}")
    print(f"Content-Type header: {resp.headers.get('Content-Type')!r}")
    print(f"requests-detected .encoding: {resp.encoding!r}")
    print(f"requests apparent_encoding: {resp.apparent_encoding!r}")

    raw_bytes = resp.content
    print(f"raw byte length: {len(raw_bytes)}")

    # requests' own .json() path (what _fetch() currently uses)
    body_via_requests_json = resp.json()
    data_via_requests_json = body_via_requests_json.get("data", [])
    if data_via_requests_json:
        sample_vals = sorted({row.get("institutional_investors") for row in data_via_requests_json[:20]})
        print(f"\n[requests .json()] sample institutional_investors values (repr): {[repr(v) for v in sample_vals]}")

    # Manually decode raw bytes as utf-8 and parse JSON ourselves, bypassing
    # whatever encoding requests guessed.
    import json

    try:
        text_utf8 = raw_bytes.decode("utf-8")
        body_utf8 = json.loads(text_utf8)
        data_utf8 = body_utf8.get("data", [])
        if data_utf8:
            sample_vals_utf8 = sorted({row.get("institutional_investors") for row in data_utf8[:20]})
            print(f"[manual utf-8 decode] sample institutional_investors values (repr): {[repr(v) for v in sample_vals_utf8]}")
    except Exception as e:  # noqa: BLE001 -- diagnostic script, want to see any decode failure
        print(f"[manual utf-8 decode] FAILED: {e}")

    # Try re-encoding the (already-decoded-by-requests) string back to latin-1
    # bytes and re-decoding as big5, in case requests silently mis-decoded as
    # latin-1/iso-8859-1 first (a known requests footgun when Content-Type
    # lacks an explicit charset and the body isn't ASCII).
    if data_via_requests_json:
        sample_raw = data_via_requests_json[0].get("institutional_investors", "")
        print(f"\nfirst row's institutional_investors (via requests .json()): {sample_raw!r}")
        for src_enc in ("latin-1", "iso-8859-1", "utf-8"):
            for dst_enc in ("big5", "gb2312", "utf-8", "cp950"):
                try:
                    fixed = sample_raw.encode(src_enc).decode(dst_enc)
                    print(f"  re-decode via encode({src_enc}).decode({dst_enc}) -> {fixed!r}")
                except Exception as e:  # noqa: BLE001
                    pass


if __name__ == "__main__":
    probe()
