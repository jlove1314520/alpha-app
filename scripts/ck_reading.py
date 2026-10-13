# -*- coding: utf-8 -*-
"""籌碼K 融資維持率讀數登錄（2026-10-13 總司令【先.八十二】11）。總司令每週貼一次讀數，存本機檔（不進 repo）。

讀數存 research/data/margin_reconcile/external_cm.json（.gitignore；與 research/reconcile_cm_external.py 同一份，
格式 points＝[[日期, 融資餘額（億元）, 維持率%], …]）。**不爬籌碼K**：數字一律由總司令提供。
用法：
  python scripts/ck_reading.py add 2026-10-17 3456.7 172.4   ← 日期、籌碼K顯示的融資餘額（億）、維持率（%）
  python scripts/ck_reading.py list                          ← 只印筆數與最新日期
同一天再加一次會取代舊值。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "research" / "data" / "margin_reconcile" / "external_cm.json"
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(path: Path | None = None) -> dict:
    path = path or EXT
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"source": "CMoney 估算（經籌碼K顯示）；總司令提供，只存本機", "fields": ["date", "margin_balance_100m", "ratio_pct"], "points": []}


def add(day: str, bal: float, pct: float, path: Path | None = None) -> dict:
    path = path or EXT
    date.fromisoformat(day)  # 日期格式不對就直接報錯
    if not (50 <= pct <= 400) or bal <= 0:
        raise ValueError(f"數字看起來不對：融資餘額 {bal} 億、維持率 {pct}%")
    doc = load(path)
    pts = [p for p in doc.get("points") or [] if p[0] != day] + [[day, bal, pct]]
    doc["points"] = sorted(pts, key=lambda p: p[0])
    doc["provided_at"] = datetime.now(TW).isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return doc


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "add":
        doc = add(argv[1], float(argv[2]), float(argv[3]))
        print(f"已存 {argv[1]} 的籌碼K讀數（本機檔，不進 repo）；共 {len(doc['points'])} 筆")
        return 0
    if argv[:1] == ["list"]:
        pts = load().get("points") or []
        print(f"共 {len(pts)} 筆；最新 {pts[-1][0] if pts else '—'}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
