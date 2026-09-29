"""自我測試：0050 在 [起, 迄] 之間的每個實際交易日都必須有資料列（不含休市日）。
休市日以 TWSE 官方 holidaySchedule 為準；平日且非休市日卻缺列即 FAIL。
用法：python scripts/check_0050_continuity.py 2026-09-24 2026-09-29"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

HOLIDAY_URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"


def holidays() -> set[str]:
    r = requests.get(HOLIDAY_URL, timeout=30)
    r.raise_for_status()
    out = set()
    for x in r.json():
        s = str(x.get("Date", ""))
        if len(s) == 7 and s.isdigit():
            out.add(f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}")
    return out


def main(start: str, end: str) -> int:
    prices = json.loads((Path(__file__).resolve().parent.parent / "data" / "price_history.json")
                        .read_text(encoding="utf-8"))["prices"]
    have = {r["date"] for r in prices.get("0050", [])}
    hol = holidays()
    d = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    missing, trading = [], []
    while d <= e:
        iso = d.strftime("%Y-%m-%d")
        if d.weekday() < 5 and iso not in hol:
            trading.append(iso)
            if iso not in have:
                missing.append(iso)
        d += timedelta(days=1)
    print(f"實際交易日={trading}；缺列={missing}")
    print("PASS" if not missing else "FAIL")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
