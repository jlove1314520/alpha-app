# -*- coding: utf-8 -*-
"""研究室.四（2026-10-15，先.一百）：季報 2025Q1～2026Q2 補齊——App 顯示與研究紀錄用的回補檔。

只寫 data/financials_backfill.json，不改 stock_detail.json；build_research.py 會自動合併（同季以官方每日管線為準）。
**研究端回測程式不得讀這個檔**：它涵蓋 2025 年以後（holdout 期間），已登記在
research/validation/holdout.py 的 DISPLAY_ONLY_DATA_FILES，scripts/selftest_display_only_files.py 會掃
research/ 底下所有 .py，引用到就 FAIL。

取得方式（README 分支照實走，與研究室.三相同）：
- 原案「FinMind TaiwanStockFinancialStatements 以日期抓全市場（6 次）」2026-10-15 實測被拒（HTTP 400：
  "Your level is register"，免費註冊會員不開放不帶 data_id 的查詢）。
- 研究端本機 parquet 快取只到 2024-12-31（holdout 截斷），2025 年以後沒有。
- 官方 TWSE／TPEx openapi 的 t187ap06 系列只有「最新一季累計數」，沒有歷史季。
- → 逐檔抓（帶 data_id，免費層允許），**每輪上限 300 檔**，已抓完的代號記在輸出檔裡當斷點，下一輪續跑。
  季報過期（q_stale）的代號排前面先抓。節流、權杖、402/403/428/429 封鎖 2 小時都沿用
  research/finmind_client.py::_fetch()（共用 data/rate_limit_state.json 來源 finmind）；
  另外滾動 1 小時用量 ≥ --hour-cap（預設 450）就先停，留額度給其他排程。
FinMind 的季報值是單季數（2026-10-15 以 6488 核對：2024Q4 營收與官方管線單季值相同；2026Q1＋Q2＝官方累計數）。
EquityAttributableToOwnersOfParent 在 FinMind 損益表裡是「歸屬母公司淨利」（6488 2024Q4 與官方 net_income_parent 相同）。
用法：python scripts/backfill_financials_display.py [--max 300] [--until HH:MM] [--hour-cap 450]
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

OUT = ROOT / "data" / "financials_backfill.json"
UNIVERSE = ROOT / "data" / "research.json"
TW = timezone(timedelta(hours=8))
Q_START, Q_END = "2025-03-31", "2026-06-30"
KEEP_FROM, KEEP_TO = (2025, 1), (2026, 2)
MAX_PER_RUN = 300
QEND = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  讀不到就從頭
        return default


def rows_for(df) -> list[dict]:
    by = {}
    for r in df.to_dict("records"):
        d = str(r.get("date") or "")
        q = QEND.get(d[5:10])
        if not q:
            continue
        try:
            v = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
        by.setdefault((int(d[:4]), q), {})[r.get("type")] = v
    out = []
    for (y, q), t in sorted(by.items()):
        if not (KEEP_FROM <= (y, q) <= KEEP_TO):
            continue
        rev, gp, op = t.get("Revenue"), t.get("GrossProfit"), t.get("OperatingIncome")
        eps = t.get("EPS")
        if rev is None and eps is None:
            continue
        out.append({"year": y, "quarter": q, "revenue": rev,
                    "gross_margin_pct": round(gp / rev * 100, 2) if gp is not None and rev else None,
                    "op_margin_pct": round(op / rev * 100, 2) if op is not None and rev else None,
                    "net_income_parent": t.get("EquityAttributableToOwnersOfParent"),
                    "eps": round(eps, 2) if eps is not None else None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=MAX_PER_RUN)
    ap.add_argument("--until", default=None, help="台北時間 HH:MM 到了就停（排程時間上限用）")
    ap.add_argument("--hour-cap", type=int, default=450)
    a = ap.parse_args()
    import finmind_client as fc

    until = None
    if a.until:
        hh, mm = map(int, a.until.split(":"))
        until = datetime.now(TW).replace(hour=hh, minute=mm, second=0, microsecond=0)
    uni = (_load(UNIVERSE, {}) or {}).get("stocks") or {}
    stale_first = sorted(uni, key=lambda c: (not ((uni[c].get("q") or {}).get("q_stale")), c))
    doc = _load(OUT, {}) or {}
    stocks = doc.get("stocks") or {}
    done = set((doc.get("meta") or {}).get("done") or []) | set(stocks)
    todo = [c for c in stale_first if c not in done][: max(0, a.max)]
    print(f"宇宙 {len(uni)} 檔；已完成 {len(done & set(uni))}；本輪 {len(todo)} 檔（上限 {a.max}）", flush=True)
    n_ok = n_empty = 0
    stop = None
    for i, code in enumerate(todo, 1):
        if until and datetime.now(TW) >= until:
            stop = f"到達時間上限 {a.until}，停在 {code}（第 {i} 檔），下一輪續跑"
            break
        used = fc.calls_last_hour()
        if used >= a.hour_cap:
            stop = f"FinMind 滾動 1 小時用量 {used} ≥ {a.hour_cap}，停在 {code}（第 {i} 檔），下一輪續跑"
            break
        try:
            df = fc._fetch("TaiwanStockFinancialStatements", code, Q_START, Q_END)
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
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
            _write(stocks, done, uni, n_ok, n_empty, None)  # 中途存檔，被外層砍掉也不丟進度
    remaining = _write(stocks, done, uni, n_ok, n_empty, stop)
    print(f"本輪有資料 {n_ok}、空 {n_empty}；累計有資料 {len(stocks)} 檔；剩 {remaining} 檔" + (f"；{stop}" if stop else ""))
    return 0


def _write(stocks, done, uni, n_ok, n_empty, stop) -> int:
    remaining = len([c for c in uni if c not in done])
    meta = {"source": "FinMind TaiwanStockFinancialStatements（逐檔帶 data_id；不帶 data_id 的全市場查詢免費層被拒）",
            "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
            "quarters": [f"{KEEP_FROM[0]}Q{KEEP_FROM[1]}", f"{KEEP_TO[0]}Q{KEEP_TO[1]}"],
            "unit": "revenue／net_income_parent 為元（單季）；毛利率、營益率為 %；eps 為元（單季）",
            "purpose": "App 顯示與研究紀錄用；研究端回測不得讀（holdout 期間，見 research/validation/holdout.py DISPLAY_ONLY_DATA_FILES）",
            "done": sorted(done), "n_with_rows": len(stocks), "remaining": remaining,
            "last_run": {"fetched": n_ok, "empty": n_empty, "stopped": stop},
            "note": "研究室.四（先.一百）；非投資建議。"}
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"meta": meta, "stocks": stocks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT)
    return remaining


if __name__ == "__main__":
    raise SystemExit(main())
