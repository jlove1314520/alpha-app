# -*- coding: utf-8 -*-
"""每日全市場「股價÷本益比」快照（2026-10-13 總司令【先.八十二】6 裁示⑤）。

**只累積、不進評分。**目的：一年後（約 2027-10 起）可以用「一年前的近四季 EPS」算 EPS 年增，
補 earnings_growth 因子目前只涵蓋 43.6% 的缺口（先.八十一-41）。現在任何評分程式都不讀這個資料夾。

來源：data/fundamentals.json 每檔 ratios（官方 BWIBBU_ALL／tpex_mainboard_peratio_analysis 的 PER，含 ratios.date），
收盤取 price_history 同一天的 close（官方 STOCK_DAY_ALL／TPEx）。零額外網路請求。
輸出：data/pe_snapshot/<資料日>.json，rows＝{代號: [收盤, 本益比, 近四季EPS＝收盤÷本益比]}；
本益比空白（虧損或官方未提供）記 [收盤, null, null]。同一資料日已存在且內容相同就不重寫（market.yml 一天三班）；
上市／上櫃資料日不同時各自併進對應日期的檔（先.一三八-8）。
用法：python scripts/build_pe_snapshot.py
"""
from __future__ import annotations

import json
import sys
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


MIN_ROWS_PER_DAY = 100  # 資料日少於這個檔數（個別停牌股的舊日期）不寫快照


def build() -> dict[str, dict]:
    """回傳 {資料日: rows}。

    先.一三八-8：上市（BWIBBU_ALL 次日早上才發布）與上櫃（當日傍晚就有）的 ratios.date 常差一天，
    舊版只取「多數檔的資料日」，上櫃永遠被丟掉（10-16～10-22 每份快照上櫃 0 檔）。改為每個資料日各自產出，
    由 main() 併進同日檔案。
    """
    fund = json.loads((DATA / "fundamentals.json").read_text(encoding="utf-8")).get("fundamentals") or {}
    by_day: dict[str, list[str]] = {}
    for c, v in fund.items():
        d = ((v or {}).get("ratios") or {}).get("date")
        if d:
            by_day.setdefault(d, []).append(c)
    by_day = {d: cs for d, cs in by_day.items() if len(cs) >= MIN_ROWS_PER_DAY}
    if not by_day:
        return {}
    want = [c for cs in by_day.values() for c in cs]
    prices = PHS.load(codes=want).get("prices") or {}
    out: dict[str, dict] = {}
    for day, codes in by_day.items():
        rows = {}
        for c in codes:
            close = next((r.get("close") for r in reversed(prices.get(c) or []) if r.get("date") == day), None)
            if not close:
                continue
            per = (fund[c].get("ratios") or {}).get("per")
            per = per if isinstance(per, (int, float)) and per > 0 else None
            rows[c] = [close, per, round(close / per, 4) if per else None]
        if rows:
            out[day] = rows
    return out


def write_day(day: str, rows: dict) -> None:
    out = OUT_DIR / f"{day}.json"
    merged = dict(rows)
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8")).get("rows") or {}
            merged = {**old, **rows}  # 同日另一市場先寫過的列保留，本輪有的列以本輪為準
            if merged == old:
                print(f"pe_snapshot {day} 已存在且內容相同，略過")
                return
        except Exception as e:  # noqa: BLE001 — 舊檔壞了就重寫
            print(f"[warn] 舊快照讀取失敗（{type(e).__name__}），重寫")
            merged = dict(rows)
    doc = {"meta": {"generated_at": datetime.now(TW).isoformat(timespec="seconds"), "date": day,
                    "count": len(merged), "with_per": sum(1 for v in merged.values() if v[1]),
                    "fields": ["close", "per", "eps_ttm"],
                    "source": "data/fundamentals.json ratios（官方 BWIBBU_ALL／tpex_mainboard_peratio_analysis）＋price_history 同日收盤；scripts/build_pe_snapshot.py",
                    "note": "只累積、不進評分（2026-10-13 總司令【先.八十二】6 裁示⑤）；eps_ttm＝收盤÷本益比；上市與上櫃資料日不同時各自併進對應日期的檔（先.一三八-8）"},
           "rows": merged}
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)
    print(f"pe_snapshot {day}：{len(merged)} 檔（本輪 {len(rows)}，有本益比 {doc['meta']['with_per']}），{out.stat().st_size / 1024:.0f} KB")


def main() -> int:
    days = build()
    if not days:
        print("[warn] 找不到本益比資料日或當日收盤，本輪不寫快照")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for day in sorted(days):
        write_day(day, days[day])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — 只累積的旁支，失敗不擋排程（十二節）
        print(f"::warning::pe_snapshot 產生失敗：{type(e).__name__}: {e}")
        sys.exit(0)
