# -*- coding: utf-8 -*-
"""研究室.三（2026-10-15，先.一百）：月營收歷史補齊——App 顯示與研究紀錄用的回補檔。

只寫 data/revenue_backfill.json，不改 fundamentals.json；build_research.py 會自動合併（同月以官方每日管線為準）。
**研究端回測程式不得讀這個檔**：它涵蓋 2025 年以後（holdout 期間），已登記在
research/validation/holdout.py 的 DISPLAY_ONLY_DATA_FILES，scripts/selftest_display_only_files.py 會掃
research/ 底下所有 .py，引用到就 FAIL。

取得方式（README 分支照實走）：
- 原案「FinMind TaiwanStockMonthRevenue 不帶 data_id、以月份抓全市場（19 次）」實測被拒（HTTP 400：
  免費註冊會員不開放，要付費方案；App 賺錢前不花錢買資料）。
- 研究端本機 parquet 快取只到 2024-12-31（load_dev 的 holdout 截斷），2025 年以後沒有。
- → 逐檔抓（帶 data_id，免費層允許），**每輪上限 300 檔**，已抓完的代號記在輸出檔裡當斷點，下一輪續跑。
  節流、權杖（只從環境變數／本機 .env 讀進記憶體，不印出）、402/403/428/429 封鎖 2 小時都沿用
  research/finmind_client.py::_fetch()（共用 data/rate_limit_state.json 來源 finmind）。
期間：營收月份 2023-12～2026-06（FinMind 的 date＝營收月份的下個月 1 日，所以查 2024-01-01～2026-07-01）；
2023-12～2024-11 只用來算年增，輸出只留 2024-12～2026-06。
用法：python scripts/backfill_revenue_display.py [--max 300]
非投資建議。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = ROOT / "data" / "revenue_backfill.json"
UNIVERSE = ROOT / "data" / "research.json"
TW = timezone(timedelta(hours=8))
Q_START, Q_END = "2024-01-01", "2026-07-01"
KEEP_FROM, KEEP_TO = (2024, 12), (2026, 6)
MAX_PER_RUN = 300


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  讀不到就從頭（不覆蓋既有進度：寫檔前會再合併）
        return default


def rows_for(df) -> list[dict]:
    m = {}
    for r in df.to_dict("records"):
        try:
            y, mo, rev = int(r["revenue_year"]), int(r["revenue_month"]), r.get("revenue")
        except (KeyError, TypeError, ValueError):
            continue
        if rev is None:
            continue
        m[(y, mo)] = float(rev)
    out = []
    for (y, mo), rev in sorted(m.items()):
        if not (KEEP_FROM <= (y, mo) <= KEEP_TO):
            continue
        prev = m.get((y - 1, mo))
        yoy = round(rev / prev - 1, 4) if prev and prev > 0 else None
        out.append({"year": y, "month": mo, "revenue": rev, "yoy": yoy})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=MAX_PER_RUN)
    a = ap.parse_args()
    import finmind_client as fc

    codes = sorted(((_load(UNIVERSE, {}) or {}).get("stocks") or {}).keys())
    doc = _load(OUT, {}) or {}
    stocks = doc.get("stocks") or {}
    meta = doc.get("meta") or {}
    done = set(meta.get("done") or []) | set(stocks)
    todo = [c for c in codes if c not in done][: max(0, a.max)]
    print(f"宇宙 {len(codes)} 檔；已完成 {len(done & set(codes))}；本輪 {len(todo)} 檔（上限 {a.max}）", flush=True)
    n_ok = n_empty = 0
    stop = None
    for i, code in enumerate(todo, 1):
        try:
            df = fc._fetch("TaiwanStockMonthRevenue", code, Q_START, Q_END)
        except RuntimeError as e:
            msg = str(e)
            if any(f"HTTP {c}" in msg for c in (402, 403, 428, 429)) or "封鎖" in msg:
                stop = f"額度／封鎖類錯誤，停在 {code}（第 {i} 檔），下一輪續跑"
                break
            print(f"  [warn] {code} 抓取失敗：{msg[:160]}", flush=True)  # 單檔失敗只警告（十二節），不記成已完成
            continue
        rs = rows_for(df) if len(df) else []
        if rs:
            stocks[code] = rs
            n_ok += 1
        else:
            n_empty += 1
        done.add(code)
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
    remaining = len([c for c in codes if c not in done])
    meta = {"source": "FinMind TaiwanStockMonthRevenue（逐檔帶 data_id；不帶 data_id 的全市場查詢免費層被拒）",
            "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
            "months": [f"{KEEP_FROM[0]}-{KEEP_FROM[1]:02d}", f"{KEEP_TO[0]}-{KEEP_TO[1]:02d}"],
            "unit": "元；yoy 為小數（0.12＝+12%）",
            "purpose": "App 顯示與研究紀錄用；研究端回測不得讀（holdout 期間，見 research/validation/holdout.py DISPLAY_ONLY_DATA_FILES）",
            "done": sorted(done), "n_with_rows": len(stocks), "remaining": remaining,
            "last_run": {"fetched": n_ok, "empty": n_empty, "stopped": stop},
            "note": "研究室.三（先.一百）；非投資建議。"}
    OUT.write_text(json.dumps({"meta": meta, "stocks": stocks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"本輪有資料 {n_ok}、空 {n_empty}；累計有資料 {len(stocks)} 檔；剩 {remaining} 檔" + (f"；{stop}" if stop else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
