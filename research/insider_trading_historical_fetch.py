# -*- coding: utf-8 -*-
"""#75 美股內部人交易假設：批次歷史抓取（非即時8筆快照版）。

跟 .github/scripts/fetch_us_insider_trading.py 的差異：後者只抓「每檔最近8筆」
即時快照（MAX_FILINGS_PER_TICKER=8），本腳本抓 submissions.json 全歷史
（filings.recent + filings.files 舊分頁），供回測用。解析XML邏輯複用同一套
（form=='4'過濾、P/S/A/F/M代碼判斷），避免重寫已驗證過的解析。

用法：python insider_trading_historical_fetch.py
輸出：research/data/insider_trading_historical.csv（append-only，逐CIK可續跑）
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PICKS_PATH = HERE / "data" / "insider_trading_pilot_ciks.json"
OUT_CSV = HERE / "data" / "insider_trading_historical.csv"
HEADERS = {"User-Agent": "AlphaApp-USInsiderTradingHistorical contact@alpha-app-project.example"}
REQUEST_SLEEP_SEC = 0.2


def _get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        time.sleep(REQUEST_SLEEP_SEC)
        return data
    except Exception as e:  # noqa: BLE001 — 守門員自身失敗只能降級警告，不得中斷主流程
        print(f"[warn] GET失敗 {url}: {e}")
        time.sleep(REQUEST_SLEEP_SEC)
        return None


def list_all_form4_filings(cik: int) -> list[dict]:
    """回傳這個CIK歷史上所有Form 4申報的 {accession, filed_at} 清單。"""
    cik10 = str(cik).zfill(10)
    main_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    raw = _get(main_url)
    if raw is None:
        return []
    try:
        doc = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] JSON解析失敗 CIK{cik10}: {e}")
        return []

    out: list[dict] = []

    def _collect(forms, dates, accns):
        for form, date, accn in zip(forms, dates, accns):
            if form == "4":
                out.append({"accession": accn, "filed_at": date})

    recent = doc.get("filings", {}).get("recent", {})
    _collect(
        recent.get("form", []),
        recent.get("filingDate", []),
        recent.get("accessionNumber", []),
    )

    for f in doc.get("filings", {}).get("files", []):
        fname = f.get("name")
        if not fname:
            continue
        old_url = f"https://data.sec.gov/submissions/{fname}"
        old_raw = _get(old_url)
        if old_raw is None:
            continue
        try:
            old_doc = json.loads(old_raw)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 舊分頁JSON解析失敗 {fname}: {e}")
            continue
        _collect(
            old_doc.get("form", []),
            old_doc.get("filingDate", []),
            old_doc.get("accessionNumber", []),
        )

    return out


def main() -> int:
    if not PICKS_PATH.exists():
        print(f"[error] 找不到pilot樣本清單: {PICKS_PATH}")
        return 1
    picks = json.loads(PICKS_PATH.read_text(encoding="utf-8"))["picks"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if is_new:
            writer.writerow(["ticker", "cik", "accession", "filed_at"])
        total = 0
        for p in picks:
            ticker, cik = p["ticker"], p["cik"]
            filings = list_all_form4_filings(cik)
            print(f"[info] {ticker} (CIK {cik}): {len(filings)} 筆Form 4申報")
            for f in filings:
                writer.writerow([ticker, cik, f["accession"], f["filed_at"]])
            total += len(filings)
        print(f"[info] 合計 {total} 筆Form 4申報索引，已寫入 {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
