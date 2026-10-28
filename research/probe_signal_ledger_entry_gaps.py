# -*- coding: utf-8 -*-
"""先.一四〇-1：前瞻台帳（data/signal_ledger.json）進場日缺列的官方查證。

10 筆訊號的「寫入日後第一個交易日」在 data/price_history 沒有該股的列，要分辨是
「當天無成交／停牌／未掛牌」還是「我們漏抓」。做法：對每檔上櫃股送一次 TPEx「個股日成交資訊」
（端點同 var1018_v1_tpex_stock_fill；tpex_www 節流同源 ≥3 秒、402/403/428/429 封鎖 2 小時不重試；
原始回應存 research/data/raw/signal_ledger_entry_probe/{代號}_{YYYYMM}.json 不重抓。
2026 年的回應欄位是「成交張數」不是舊年度的「成交仟股」，所以這裡自己解析、不改舊腳本），
再拿官方列跟本機 price_history 逐日比對。官方未公布上限；本支一次最多 7 次請求。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import price_history_store as PHS  # noqa: E402
import update_picks_ledger_returns as upl  # noqa: E402
import requests  # noqa: E402

import var1018_v1_tpex_stock_fill as T  # noqa: E402

RAW = HERE / "data" / "raw" / "signal_ledger_entry_probe"


def fetch_raw(code: str, month: str) -> dict:
    p = RAW / f"{code}_{month}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    T._rate_limit_wait_or_raise("tpex_www")
    r = requests.get(T.URL, params={"code": code, "date": f"{month[:4]}/{month[4:]}/01", "response": "json"},
                     headers=T.UA, timeout=30)
    if r.status_code in T.BLOCK:
        T._rate_limit_record_block("tpex_www", r.status_code)
        raise RuntimeError(f"HTTP {r.status_code}，封鎖 2 小時、停抓")
    r.raise_for_status()
    j = r.json()
    RAW.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return j


def parse_rows(j: dict) -> tuple[str, dict]:
    tbl = next((t for t in (j.get("tables") or []) if "個股日成交資訊" in str(t.get("title") or "")), None)
    if tbl is None or not tbl.get("data"):
        return "no_data", {}
    f = [str(x).replace(" ", "") for x in (tbl.get("fields") or [])]
    vol = next(k for k in ("成交張數", "成交仟股") if k in f)
    rows = {}
    for r in tbl["data"]:
        rows[T._roc(r[f.index("日期")])] = {"volume": r[f.index(vol)], "close": r[f.index("收盤")],
                                           "trades": r[f.index("筆數")] if "筆數" in f else None}
    return "ok", rows


def main() -> int:
    ledger = json.loads((ROOT / "data" / "signal_ledger.json").read_text(encoding="utf-8"))
    prices = PHS.load(upl.PRICE_HISTORY_PATH)["prices"]
    cal = sorted(r["date"] for r in prices[upl.CALENDAR_PROXY_CODE])
    targets = {}
    for s in ledger["signals"]:
        if s.get("entry_close") is not None or not prices.get(s["code"]):
            continue
        nxt = next((d for d in cal if d > s["recorded_at"][:10]), None)
        if nxt is None or prices[s["code"]][-1]["date"] < nxt:
            continue
        if not any(r["date"] == nxt for r in prices[s["code"]]):
            targets.setdefault(s["code"], set()).add(nxt)
    out = {}
    for code, days in sorted(targets.items()):
        month = min(days)[:7].replace("-", "")
        status, rows = parse_rows(fetch_raw(code, month))
        mine = {r["date"] for r in prices[code]}
        off_days = sorted(rows)
        missing = [d for d in off_days if d not in mine]
        out[code] = {"entry_days": sorted(days), "official_status": status, "official_days": off_days,
                     "official_on_entry": {d: rows.get(d) for d in sorted(days)},
                     "official_days_missing_in_price_history": missing}
        print(code, json.dumps(out[code], ensure_ascii=False))
    (HERE / "data" / "signal_ledger_entry_gap_probe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
