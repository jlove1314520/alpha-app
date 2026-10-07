"""先.五十二-1：把 research/MARGIN_RATIO_RECONCILE.md 的八日對帳比值（外部口徑÷本站）轉成機器可讀檔
data/margin_ratio_calibration.json，App 從這裡讀比值（程式碼不寫死數字）。
只存比值與日期，不存外部網站的數值本身。"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "research" / "MARGIN_RATIO_RECONCILE.md"
OUT = REPO / "data" / "margin_ratio_calibration.json"
TW = timezone(timedelta(hours=8))


def main() -> int:
    txt = SRC.read_text(encoding="utf-8")
    m = re.search(r"外部／A 比值：(.+)", txt)
    if not m:
        print("找不到「外部／A 比值」那一行，未產生")
        return 1
    pairs = re.findall(r"(\d{2})/(\d{2})\s+([0-9.]+)", m.group(1))
    if len(pairs) < 5:
        print("比值筆數不足，未產生")
        return 1
    rows = [{"date": f"2026-{mm}-{dd}", "ratio": float(v)} for mm, dd, v in pairs]
    mean = sum(r["ratio"] for r in rows) / len(rows)
    out = {"generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "ratio_mean": round(mean, 4), "ratio_min": min(r["ratio"] for r in rows), "ratio_max": max(r["ratio"] for r in rows),
           "n_days": len(rows), "date_from": rows[0]["date"], "date_to": rows[-1]["date"], "daily": rows,
           "meaning": "籌碼K口徑 ≈ 本站算法 × ratio_mean（八日對帳比值，估算；原因未查明）",
           "source": "research/MARGIN_RATIO_RECONCILE.md（先.四十三-三，外部值由總司令提供；本檔只存比值）"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("寫入", OUT.name, "ratio_mean", out["ratio_mean"], "n", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
