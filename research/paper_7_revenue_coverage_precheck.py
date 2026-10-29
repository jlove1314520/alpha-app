# -*- coding: utf-8 -*-
"""先.一三五-1br：模擬 G（paper_7）首次建倉（2026-11-02）前，營收資料覆蓋率查核。

只計數：不輸出代號、SUE 值或排名；不讀價格（流動性濾網不跑）；零外部請求；不登記試驗、不算報酬。
SUE 與月份延遲規則直接呼叫追蹤程式本身（revenue_sue／MAX_REV_LAG_MONTHS），回補檔也走追蹤程式的 load_gap_fill()，
不另寫一份邏輯。輸出 research/data/paper_7_revenue_coverage_precheck.json。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_7_revsurprise_tracker as G  # noqa: E402

BASE_DAY = G.START_NOT_BEFORE
THRESHOLD = 600
OUT = HERE / "data" / "paper_7_revenue_coverage_precheck.json"


def main() -> int:
    funds = (G._load(ROOT / "data" / "fundamentals.json", {}) or {}).get("fundamentals") or {}
    active = set((G._load(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    gap = G.load_gap_fill()
    y, m = int(BASE_DAY[:4]), int(BASE_DAY[5:7])
    oldest_ok = G._ym_index(y, m) - G.MAX_REV_LAG_MONTHS
    common = sorted(c for c in active if G.is_common(c))
    cnt = Counter()
    latest_month = Counter()
    for code in common:
        entry = funds.get(code) or {}
        with_gap = G.revenue_sue(entry, gap.get(code))
        official = G.revenue_sue(entry)
        if not entry and not gap.get(code):
            cnt["no_revenue_at_all"] += 1
            continue
        if with_gap is None:
            cnt["blocked_missing_months_or_zero_sd"] += 1
            continue
        ym = with_gap[1]
        latest_month[ym] += 1
        if G._ym_index(int(ym[:4]), int(ym[5:])) < oldest_ok:
            cnt["too_stale"] += 1
            continue
        cnt["sue_ok_with_gap_fill"] += 1
        if official is not None:
            cnt["sue_ok_official_only"] += 1
    n_ok = cnt["sue_ok_with_gap_fill"]
    out = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "item": "先.一三五-1br",
        "base_day": BASE_DAY,
        "rule": f"revenue_sue()＝最近 {G.SUE_WINDOW} 個月 YoY 需連續；最新營收月份不早於基準月減 {G.MAX_REV_LAG_MONTHS}",
        "active_common_n": len(common),
        "counts": dict(cnt),
        "latest_revenue_month_dist": dict(sorted(latest_month.items())),
        "threshold": THRESHOLD,
        "verdict": "OK" if n_ok >= THRESHOLD else "LOW",
        "not_done": "未套流動性濾網（需讀價格）、未輸出代號／SUE／排名、零外部請求",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
