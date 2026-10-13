# -*- coding: utf-8 -*-
"""先.八十三-3a-2：美股 PIT 宇宙每月「在宇宙內／有代號」檔數表（只建資料，不計任何報酬、不登記試驗）。

口徑（與先.八十三-3a 的表逐字相同，2026-10-14 用延伸前備份重算 2011-01／2015-01／
2019-01／2023-01／2024-12 五個月份，十個數字全部一致才採用）：
  - 在宇宙內：first_periodic_report ≤ 該月，且結束日 ≥ 該月
    （結束日＝delisted_at；stopped_filing 用 last_periodic_report；active 視為未結束）；
    SIC 已知（research/data/us_sic_universe.json）且不在 6000–6799（金融／SPAC）。
  - 有代號：名冊的 ticker 欄非空（可能拿到 yfinance 價格；不代表真的有價）。

延伸到 1994 以後多一個欄位 sic_unknown：2010 年以前就停止申報的公司不在 SIC 檔裡
（SIC 檔只抓過 2010 版名冊的 21,315 個 CIK），3a 口徑會把它們整批排除；
這裡另列出來，不偷偷算進也不偷偷丟掉。補抓它們的 SIC 是另一項工作（見 PENDING_QUEUE）。

用法：python research/us_universe_monthly_coverage.py [--universe 路徑]
輸出：research/data/us_universe_monthly_coverage.json（research/data 已 gitignore），並印出摘要。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
UNI = HERE / "data" / "us_universe_pit.json"
SIC = HERE / "data" / "us_sic_universe.json"
OUT = HERE / "data" / "us_universe_monthly_coverage.json"


def _months(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _end(r: dict) -> str:
    if r.get("delisted_at"):
        return r["delisted_at"][:7]
    if r.get("status") == "stopped_filing" and r.get("last_periodic_report"):
        return r["last_periodic_report"][:7]
    return "9999-12"


def table(uni: dict, sic: dict, months: list[str]) -> list[dict]:
    recs = []
    for c, r in uni.items():
        f = r.get("first_periodic_report")
        if not f:
            continue
        s = sic.get(c) or {}
        try:
            si = int(s.get("sic"))
        except (TypeError, ValueError):
            si = None
        recs.append((f[:7], _end(r), si, bool(r.get("ticker"))))
    rows = []
    for m in months:
        n = t = unk = fin = 0
        for f, e, si, tk in recs:
            if f > m or e < m:
                continue
            if si is None:
                unk += 1
                continue
            if 6000 <= si <= 6799:
                fin += 1
                continue
            n += 1
            t += tk
        rows.append({"month": m, "in_universe": n, "has_ticker": t,
                     "ticker_pct": round(100 * t / n, 1) if n else None,
                     "sic_unknown": unk, "financial_excluded": fin})
    return rows


def main() -> int:
    args = sys.argv[1:]
    up = Path(args[args.index("--universe") + 1]) if "--universe" in args else UNI
    doc = json.loads(up.read_text(encoding="utf-8"))
    uni = doc["universe"]
    sic = json.loads(SIC.read_text(encoding="utf-8"))["sic"]
    rows = table(uni, sic, _months("1994-01", "2024-12"))
    out = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "universe_file": up.name, "universe_source": doc.get("source"),
           "universe_counts": doc.get("counts"),
           "definition": __doc__.split("用法：")[0].strip(),
           "rows": rows}
    if up == UNI:
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已寫入 {OUT}")
    for r in rows:
        if r["month"][5:] == "01" or r["month"] == "2024-12":
            print(r["month"], r["in_universe"], r["has_ticker"], r["ticker_pct"], "SIC未知", r["sic_unknown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
