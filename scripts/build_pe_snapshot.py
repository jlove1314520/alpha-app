# -*- coding: utf-8 -*-
"""每日全市場「股價÷本益比」快照（2026-10-13 總司令【先.八十二】6 裁示⑤）。

**只累積、不進評分。**目的：一年後（約 2027-10 起）可以用「一年前的近四季 EPS」算 EPS 年增，
補 earnings_growth 因子目前只涵蓋 43.6% 的缺口（先.八十一-41）。現在任何評分程式都不讀這個資料夾。

來源：data/fundamentals.json 每檔 ratios（官方 BWIBBU_ALL／tpex_mainboard_peratio_analysis 的 PER，含 ratios.date），
收盤取 price_history 同一天的 close（官方 STOCK_DAY_ALL／TPEx）。零額外網路請求。
輸出：data/pe_snapshot/<資料日>.json，rows＝{代號: [收盤, 本益比, 近四季EPS＝收盤÷本益比]}；
本益比空白（虧損或官方未提供）記 [收盤, null, null]。同一資料日已存在且內容相同就不重寫（market.yml 一天三班）。
用法：python scripts/build_pe_snapshot.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import price_history_store as PHS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TW = timezone(timedelta(hours=8))
DATA = ROOT / "data"
OUT_DIR = DATA / "pe_snapshot"


def build() -> tuple[str | None, dict]:
    fund = json.loads((DATA / "fundamentals.json").read_text(encoding="utf-8")).get("fundamentals") or {}
    dates = Counter(((v or {}).get("ratios") or {}).get("date") for v in fund.values())
    dates.pop(None, None)
    if not dates:
        return None, {}
    day = dates.most_common(1)[0][0]  # 全市場本益比資料日（多數檔一致）
    want = [c for c, v in fund.items() if ((v or {}).get("ratios") or {}).get("date") == day]
    prices = PHS.load(codes=want).get("prices") or {}
    rows = {}
    for c in want:
        close = next((r.get("close") for r in reversed(prices.get(c) or []) if r.get("date") == day), None)
        if not close:
            continue
        per = (fund[c].get("ratios") or {}).get("per")
        per = per if isinstance(per, (int, float)) and per > 0 else None
        rows[c] = [close, per, round(close / per, 4) if per else None]
    return day, rows


def main() -> int:
    day, rows = build()
    if not day or not rows:
        print("[warn] 找不到本益比資料日或當日收盤，本輪不寫快照")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{day}.json"
    if out.exists():
        try:
            if json.loads(out.read_text(encoding="utf-8")).get("rows") == rows:
                print(f"pe_snapshot {day} 已存在且內容相同，略過")
                return 0
        except Exception as e:  # noqa: BLE001 — 舊檔壞了就重寫
            print(f"[warn] 舊快照讀取失敗（{type(e).__name__}），重寫")
    doc = {"meta": {"generated_at": datetime.now(TW).isoformat(timespec="seconds"), "date": day,
                    "count": len(rows), "with_per": sum(1 for v in rows.values() if v[1]),
                    "fields": ["close", "per", "eps_ttm"],
                    "source": "data/fundamentals.json ratios（官方 BWIBBU_ALL／tpex_mainboard_peratio_analysis）＋price_history 同日收盤；scripts/build_pe_snapshot.py",
                    "note": "只累積、不進評分（2026-10-13 總司令【先.八十二】6 裁示⑤）；eps_ttm＝收盤÷本益比"},
           "rows": rows}
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)
    print(f"pe_snapshot {day}：{len(rows)} 檔（有本益比 {doc['meta']['with_per']}），{out.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — 只累積的旁支，失敗不擋排程（十二節）
        print(f"::warning::pe_snapshot 產生失敗：{type(e).__name__}: {e}")
        sys.exit(0)
