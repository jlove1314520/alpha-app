# -*- coding: utf-8 -*-
"""先.八十一-19（2026-10-13）：搜尋用名稱清單 data/stock_names.json（repo 為主，FinMind 只補充）。

原本打開搜尋要下載 FinMind TaiwanStockInfo（約 490KB）＋USStockInfo（約 58KB）。改成：
- 台股：data/company_info.json（3 千多檔，含 ETF；只取名稱與產業，去掉網站等欄位）
- 美股：data/us_financials.json 的 SEC 名冊公司名＋data/us_sic.json 的 entity_name（目前約 250 檔，非全市場）
App 搜尋先查這份；查不到才向 FinMind 完整名單補查（見 app.js loadStockInfo／doSearch）。
零外部請求、內容沒變不重寫。排程：market.yml。用法：python scripts/build_stock_names.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "stock_names.json"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load(name: str) -> dict:
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[warn] 讀不到 {name}（{type(e).__name__}），該部分略過")
        return {}


def main() -> int:
    comp = _load("company_info.json").get("companies") or {}
    tw = []
    for code, c in sorted(comp.items()):
        if not c or not c.get("name"):
            continue
        if not (4 <= len(code) <= 6) or (len(code) == 6 and code.isdigit()):  # 同 App 舊規則：濾掉權證
            continue
        tw.append([code, c["name"], c.get("industry") or ""])
    us = {}
    for t, f in ((_load("us_financials.json").get("financials")) or {}).items():
        if f and f.get("name"):
            us[t] = [t, re.sub(r"\s*Common Stock\s*$", "", f["name"], flags=re.I), ""]
    for t, s in ((_load("us_sic.json").get("tickers")) or {}).items():
        if s and s.get("entity_name"):
            us[t] = [t, s["entity_name"], s.get("sic_description") or (us.get(t) or ["", "", ""])[2]]
    if not tw:
        print("[warn] 台股名稱為空，不覆蓋既有檔")
        return 0
    doc = {"meta": {"source": "台股 data/company_info.json；美股 data/us_financials.json（SEC 名冊）＋data/us_sic.json；scripts/build_stock_names.py",
                    "note": "repo 名單為主；查不到的代號 App 才向 FinMind 完整名單補查", "tw_count": len(tw), "us_count": len(us)},
           "tw": tw, "us": [us[k] for k in sorted(us)]}
    txt = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    try:
        if OUT.read_text(encoding="utf-8") == txt:
            print("stock_names：內容沒變")
            return 0
    except OSError:
        pass
    OUT.write_text(txt, encoding="utf-8")
    print(f"stock_names：台股 {len(tw)} 檔、美股 {len(us)} 檔，{len(txt.encode('utf-8')) // 1024}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
