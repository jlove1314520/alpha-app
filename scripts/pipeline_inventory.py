# -*- coding: utf-8 -*-
"""本機管線清點表（2026-09-10 停擺四）。

印出「每條管線最後一次真正產出是什麼時候」，並把超過預期新鮮度的全部列出來。
判定邏輯不在這裡，在 `scripts/pipeline_freshness.py`——**這支跟每 5 分鐘的
停擺自檢讀同一份登錄檔、走同一套判定**，表上有的自檢一定也在監控。

用法：
    python scripts/pipeline_inventory.py          # 印表
    python scripts/pipeline_inventory.py --json   # 給程式吃的 JSON

離開碼：有任何一條停擺回 1，全部正常回 0。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from pipeline_freshness import evaluate, load_registry

TZ = timezone(timedelta(hours=8))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

MARK = {"ok": "✓", "stalled": "✗", "missing": "✗", "skipped": "－", "unknown": "?"}


def _age(row: dict) -> str:
    if "age_min" not in row:
        return row.get("reason", "")[:34]
    a = row["age_min"]
    if a < 90:
        return f"{a:.0f} 分鐘前"
    if a < 60 * 48:
        return f"{a/60:.1f} 小時前"
    return f"{a/1440:.1f} 天前"


def _expect(row: dict) -> str:
    m = row["expected_interval_min"]
    if m < 60:
        return f"每 {m} 分"
    if m < 1440:
        return f"每 {m//60} 小時"
    if m < 10080:
        return f"每 {m//1440} 天"
    return f"每 {m//10080} 週"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    now = datetime.now(TZ)
    rows, stalled = evaluate(now)

    if a.json:
        print(json.dumps({"checked_at": now.isoformat(), "stalled": stalled,
                          "pipelines": rows}, ensure_ascii=False, indent=1))
        return 1 if stalled else 0

    reg = load_registry()
    print("=" * 96)
    print(f"  本機管線清點　{now.strftime('%Y-%m-%d %H:%M:%S')}　"
          f"（停擺門檻＝預期間隔 × {reg.get('stall_factor', 3)}）")
    print("=" * 96)
    print(f"  {'':2}{'工作':<23}{'產出檔':<44}{'預期':<9}{'最後產出'}")
    print("  " + "-" * 92)
    for r in rows:
        print(f"  {MARK.get(r['status'], '?')} {r['task']:<22}"
              f"{r['artifact']:<44}{_expect(r):<9}{_age(r)}")
        if r["status"] in ("stalled", "missing", "unknown") and r.get("source"):
            print(f"      └ {r['source']}")

    print()
    if stalled:
        print(f"  ⚠ {len(stalled)} 條停擺：")
        for s in stalled:
            print(f"    ‧ {s}")
        print()
        print("  提醒：mtime 新鮮不代表資料新鮮。上表凡是標「max(date)」或「JSON 欄位」的，")
        print("  看的都是**資料層**的時間戳——alpha.db 就是 mtime 天天更新但資料停了 20 天。")
        return 1
    print("  ✓ 全部在預期新鮮度內")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
