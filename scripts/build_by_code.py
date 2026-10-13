# -*- coding: utf-8 -*-
"""先.八十一-9（2026-10-13）：個股頁「每檔一個小檔」——data/by_code/<代號>.json。

個股頁原本要下載整份全市場檔（fundamentals 545KB、scores 518KB、events 400KB、holders 317KB、
institutional_history 220KB、sector_flow 120KB…，合計約 2.8MB）只為了看一檔。這支把每一份全市場檔切成
「同樣結構、只留這一檔」的子集，合併成一檔一個小檔；App 個股頁各載入函式先讀小檔、沒有才退回整份檔。

切法（通用規則，不寫死各檔欄位）：
- 頂層 dict 若大多數 key 是股票代號（≥50 個且 ≥60% 符合代號格式）→ 小檔只留這一檔那一筆
- 頂層 list 若元素是含 code 欄位的 dict → 小檔只留 code＝這一檔的元素
- 其他頂層欄位（meta、dates…）每檔都一樣，不重複寫進四千多個小檔，集中寫進 data/by_code/_meta.json，
  App 讀一次後跟小檔合併成「原本整份檔的同樣結構」；個股頁用不到的大區塊（sector_flow.sectors）不收
- scores.json（價值成長榜）只留這一檔那一列，另把「同產業百分位」先算好放進 row._industry_pct，
  不把同產業所有列複製進每個小檔（第一版這樣做，4385 檔合計 1.3GB，不可行）
- price：price_history 該檔最近 30 個交易日，精簡成 [日期,開,高,低,收,量] 陣列（個股頁總覽走勢用；
  技術分析長圖仍走 FinMind）
- company：company_info 該檔（名稱／產業）
- scores_momentum／scores_future：這一檔在題材動能榜／未來性濾網的完整列（選股頁清單改讀精簡檔
  scores*_list.json，展開與報告時才讀這裡的完整列，見 scripts/build_scores_list.py）
內容沒變的小檔不重寫（避免每天無謂改動四千多個檔案）。零外部請求，只讀 repo 內既有檔案。
排程：market.yml（每日三班）在 split_stock_detail 之後跑；holders（本機週排程）、cash_flow（手動）
更新後最晚在下一班 market.yml 反映進小檔。
用法：python scripts/build_by_code.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "by_code"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")
SOURCES = {  # 小檔裡的節名 → 來源檔
    "fundamentals": DATA / "fundamentals.json",
    "holders": DATA / "holders.json",
    "institutional_history": DATA / "institutional_history.json",
    "foreign_holding": DATA / "foreign_holding.json",
    "securities_lending_sell": DATA / "securities_lending_sell.json",
    "short_lending_available": DATA / "short_lending_available.json",
    "cash_flow": DATA / "cash_flow.json",
    "sector_flow": DATA / "sector_flow.json",
}  # events 不收：事件每 30 分鐘更新（news_events.yml），個股頁改讀同步切出的 data/events_by_code/<代號>.json
SCORES_FILE = ROOT / "scores.json"
OTHER_BOARDS = {"scores_momentum": ROOT / "scores_momentum.json", "scores_future": ROOT / "scores_future.json"}  # 選股頁展開／報告用的完整列
DROP = {"sector_flow": {"sectors"}}  # 個股頁用不到、又大的共用區塊
PRICE_DAYS = 30
PRICE_COLS = ("date", "open", "high", "low", "close", "volume")


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[warn] 讀不到 {p.name}：{type(e).__name__}（這一節略過）")
        return None


def _is_code_dict(v) -> bool:
    if not isinstance(v, dict) or len(v) < 50:
        return False
    ks = list(v.keys())
    return sum(1 for k in ks if CODE_RE.match(str(k))) >= 0.6 * len(ks)


def _is_code_list(v) -> bool:
    return isinstance(v, list) and len(v) >= 20 and all(isinstance(x, dict) and "code" in x for x in v[:20])


def plan(doc: dict) -> dict:
    """回傳 {頂層key: 'dict'|'list'|'keep'}。"""
    return {k: ("dict" if _is_code_dict(v) else "list" if _is_code_list(v) else "keep") for k, v in doc.items()}




def industry_pct(rows: list, row: dict) -> dict:
    """同 app-shared.js industryPercentileFor：同產業有分數者 ≥5 檔才給，pct＝(≤自己分數的檔數)/n。"""
    out = {}
    for k, f in (row.get("factors") or {}).items():
        if not isinstance(f, dict) or not isinstance(f.get("score"), (int, float)):
            continue
        vals = [r["factors"][k]["score"] for r in rows if r.get("industry") == row.get("industry")
                and isinstance((r.get("factors") or {}).get(k), dict) and isinstance(r["factors"][k].get("score"), (int, float))]
        if len(vals) >= 5:
            out[k] = {"pct": sum(1 for v in vals if v <= f["score"]) / len(vals), "n": len(vals)}
    return out


def _write_if_changed(p: Path, obj) -> bool:
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        if p.read_text(encoding="utf-8") == txt:
            return False
    except OSError:
        pass
    p.write_text(txt, encoding="utf-8")
    return True


def main() -> int:
    docs = {n: _load(p) for n, p in SOURCES.items()}
    docs = {n: d for n, d in docs.items() if isinstance(d, dict)}
    hows = {n: plan(d) for n, d in docs.items()}
    lidx = {}
    for n, d in docs.items():
        for k, h in hows[n].items():
            if h == "list":
                idx = {}
                for x in d[k]:
                    idx.setdefault(str(x.get("code")), []).append(x)
                lidx.setdefault(n, {})[k] = idx
    sc = _load(SCORES_FILE) or {}
    sc_rows = sc.get("stocks") or []
    sc_by_code = {r.get("code"): r for r in sc_rows}
    other = {n: {r.get("code"): r for r in ((_load(p) or {}).get("stocks") or [])} for n, p in OTHER_BOARDS.items()}
    company = (_load(DATA / "company_info.json") or {}).get("companies") or {}
    ph = (_load(DATA / "price_history.json") or {}).get("prices") or {}
    codes = set()
    for n, d in docs.items():
        for k, h in hows[n].items():
            if h == "dict":
                codes |= {c for c in d[k] if CODE_RE.match(str(c))}
    codes |= {c for c in sc_by_code if c and CODE_RE.match(str(c))}
    codes |= {c for c in ph if CODE_RE.match(c)}
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"generated_by": "scripts/build_by_code.py（先.八十一-9）", "sections": {}}
    for n, d in docs.items():
        meta["sections"][n] = {"shape": {k: h for k, h in hows[n].items() if k not in DROP.get(n, set())},
                               "common": {k: v for k, v in d.items() if hows[n][k] == "keep" and k not in DROP.get(n, set())}}
    meta["sections"]["scores"] = {"common": {"meta": sc.get("meta"), "weights": sc.get("weights")}, "total_rows": len(sc_rows)}
    _write_if_changed(OUT / "_meta.json", meta)
    keep, changed = {"_meta.json"}, 0
    for code in sorted(codes):
        doc = {"code": code}
        for n, d in docs.items():
            part = {}
            for k, h in hows[n].items():
                if h == "dict" and code in d[k]:
                    part[k] = {code: d[k][code]}
                elif h == "list":
                    hit = lidx[n][k].get(code)
                    if hit:
                        part[k] = hit
            if part:
                doc[n] = part
        row = sc_by_code.get(code)
        if row:
            doc["scores"] = dict(row, _industry_pct=industry_pct(sc_rows, row))
        for n, by in other.items():
            if code in by:
                doc[n] = by[code]
        rows = ph.get(code) or []
        if rows:
            doc["price"] = [[r.get(c) for c in PRICE_COLS] for r in rows[-PRICE_DAYS:]]
        if code in company:
            doc["company"] = company[code]
        changed += _write_if_changed(OUT / f"{code}.json", doc)
        keep.add(f"{code}.json")
    stale = [p for p in OUT.glob("*.json") if p.name not in keep]
    for p in stale:
        p.unlink()
    print(f"by_code：{len(keep) - 1} 檔（其中 {changed} 檔內容有變而重寫）＋_meta.json，移除 {len(stale)} 個已不存在的代號")
    return 0


if __name__ == "__main__":
    sys.exit(main())
