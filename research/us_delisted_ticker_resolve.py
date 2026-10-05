# -*- coding: utf-8 -*-
"""先.二十一-一：下市股代號解析的第 3、4 條路（**不計任何報酬**）。

總司令 2026-10-05【先.二十一】一，各限 1 小時／120 次請求：
  路徑3：該公司下市前最後一份 10-K／10-Q 的封面頁純文字，正則抓
         「(NYSE|NASDAQ|Nasdaq|NYSE MKT|AMEX)[:：]?\\s*([A-Z]{1,5})」
         及「Trading Symbol」「Symbol」附近的大寫代號。
  路徑4：以公司名稱（含 formerNames）模糊比對 Stooq 公開代號清單，相似度 ≥0.9。

**路徑4 的查證結果：不可行，且不得繞過。** 2026-10-05 實測 Stooq 三個端點
（`/db/l/?g=27` 代號清單、`/cmp/?q=` 搜尋、`/q/d/l/?s=` 公開 CSV）**全部回傳
「This site requires JavaScript」驗證牆**，連 AAPL 這種必定有資料的代號也一樣。
依 CLAUDE.md「取得方式鐵律」，繞過驗證牆（無頭瀏覽器、偽裝 UA）一律禁止，
故路徑4 判定為不可及並據實記錄，不嘗試替代繞法。
**連帶更正第一輪的「Stooq 0/60」**：那不是「這些代號沒有資料」，而是
「端點對所有請求都不可用」——兩者意義完全不同，不得混為一談。

SEC 禮儀：共用 sec_rate_limiter（與先.十八-二 的 SIC 抓取合計 ≤5 req/秒）。

用法：python research/us_delisted_ticker_resolve.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sec_rate_limiter import acquire_slot  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = HERE / "data" / "raw" / "us_delist_probe"
COVER = HERE / "data" / "raw" / "us_cover_pages"
COVER.mkdir(parents=True, exist_ok=True)
PROBE = HERE / "data" / "us_delisted_price_probe_unfiltered_frame.json"
OUT = HERE / "data" / "us_delisted_ticker_resolve.json"
HEADERS = {"User-Agent": "AlphaResearch-USTrack contact@alpha-research-project.example",
           "Accept-Encoding": "gzip, deflate"}
MAX_REQUESTS = 120

# 封面頁有三種形狀，依可靠度排序比對：
# (a) 2019 年後的結構化表格：「Title of each class | Trading Symbol(s) | Name of each exchange
#     on which registered」之後緊接資料列「Common Stock, par value $0.001 per share  PETX
#     The Nasdaq Stock Market LLC」——代號是夾在類別敘述與交易所名稱之間的獨立大寫 token。
# (b) 內文敘述：under the symbol "CYS" / (NASDAQ: SOHU)
# (c) 交易所: 代號
# **第一版只寫了 (c) 與一條寬鬆的 Symbol 標籤正則，結果 7 筆裡有 5 筆抓到表頭的
# 「Name」當代號**（"Trading Symbol(s) Name of each exchange" 的 Name），是典型的
# 正則誤命中；修法是改抓表頭之後的資料列，並把表頭字樣全部列入雜訊。
TABLE_HDR = re.compile(
    r"Trading\s+Symbol\(?s?\)?\s*(?:Name\s+of\s+each\s+exchange"
    r"(?:\s+on\s+which\s+registered)?)?", re.I)
QUOTED_SYM = re.compile(r"(?:under\s+the\s+)?symbols?\s*[:：]?\s*[\"'“]([A-Z]{1,5})[,.]?[\"'”]", re.I)
EXCH_SYM = re.compile(
    r"(?:NYSE\s*MKT|NYSE\s*American|NYSE\s*Amex|NYSE|NASDAQ|Nasdaq|AMEX)"
    r"(?:\s*(?:Stock\s*Market|Global\s*Select\s*Market|Global\s*Market|Capital\s*Market))?"
    r"\s*[:：]\s*([A-Z]{1,5})\b")
# 一定要有字元邊界 \b：少了它會切進單字內部（"Common" 會命中 "C"），
# 那會讓表格路徑永遠抓到雜訊字母而不是真代號。
TOKEN = re.compile(r"\b([A-Z]{1,5})\b")
TAG_RE = re.compile(r"<[^>]+>")
ENT_RE = re.compile(r"&#\d+;|&[a-zA-Z]+;")
NOISE = {"NYSE", "AMEX", "NASDAQ", "SEC", "CFR", "USA", "INC", "LLC", "LP", "THE", "AND",
         "OMB", "FORM", "ACT", "NA", "NONE", "NO", "YES", "X", "A", "B", "C", "D", "S",
         # 以下全部是封面頁表頭／樣板用字，第一版就是被這些誤命中
         "NAME", "TITLE", "CLASS", "EACH", "OF", "ON", "WHICH", "TRADING", "SYMBOL",
         "COMMON", "STOCK", "VALUE", "PAR", "PER", "SHARE", "SHARES", "ACCT", "ITEM",
         "PART", "NOTE", "TOTAL", "US", "U S", "LTD", "CORP", "CO", "PLC", "SA", "NV"}


def _extract_symbol(head: str) -> tuple[str | None, str | None]:
    """回傳 (代號, 證據片段)。三種形狀依可靠度排序，全不中就回 (None, None)——
    寧可回報解析不到，也不猜一個看起來像代號的字。"""
    m = TABLE_HDR.search(head)
    if m:
        # 表頭之後的資料列：跳過類別敘述（含 par value 等字樣），取第一個非雜訊大寫 token
        tail = head[m.end():m.end() + 300]
        for t in TOKEN.finditer(tail):
            c = t.group(1)
            if c not in NOISE and not c.isdigit():
                return c, tail[max(0, t.start() - 90):t.end() + 50]
    for rx in (QUOTED_SYM, EXCH_SYM):
        for m2 in rx.finditer(head):
            c = m2.group(1).upper()
            if c not in NOISE:
                return c, head[max(0, m2.start() - 80):m2.end() + 40]
    return None, None


def _plain(raw: str) -> str:
    t = TAG_RE.sub(" ", raw)
    t = ENT_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t)


def _scan_block(rec: dict, before: str, best):
    for f, d, a, p in zip(rec.get("form") or [], rec.get("filingDate") or [],
                          rec.get("accessionNumber") or [], rec.get("primaryDocument") or []):
        if str(f) in ("10-K", "10-Q") and d and d < before:
            if best is None or d > best[0]:
                best = (d, a, p)
    return best


def _pick_filing(sub: dict, before: str, cik: int, budget: list) -> tuple[str, str] | None:
    """回傳 (accessionNumber, primaryDocument)：下市日前最後一份 10-K／10-Q。

    `filings.recent` 只涵蓋近期；早年下市的公司其定期報告多半落在
    `filings.files[]` 的歷史分頁裡（第一輪有 14／60 卡在這一點）。
    recent 找不到時才去翻歷史分頁，每翻一頁算一次請求、計入本輪預算。"""
    filings = sub.get("filings") or {}
    best = _scan_block(filings.get("recent") or {}, before, None)
    if best:
        return (best[1], best[2])
    for meta in (filings.get("files") or []):
        nm = meta.get("name")
        if not nm or budget[0] <= 0:
            continue
        cp = CACHE / f"HIST_{cik}_{nm}"
        if cp.exists():
            try:
                blk = json.loads(cp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
        else:
            acquire_slot()
            budget[0] -= 1
            try:
                r = requests.get(f"https://data.sec.gov/submissions/{nm}", headers=HEADERS, timeout=60)
                blk = r.json() if r.status_code == 200 else {}
            except Exception:  # noqa: BLE001
                blk = {}
            cp.write_text(json.dumps(blk), encoding="utf-8")
        best = _scan_block(blk, before, best)
    return (best[1], best[2]) if best else None


def resolve(sample: list[dict], budget: int = MAX_REQUESTS) -> dict:
    rows, used = [], 0
    hist_budget = [budget]          # 歷史分頁與封面頁共用同一份 120 次預算
    for s in sample:
        cik, dl = int(s["cik"]), s["delisted_at"]
        rec = {"cik": cik, "name": s.get("name"), "delisted_at": dl,
               "path3_symbol": None, "path3_evidence": None, "path3_doc_url": None}
        sub_p = CACHE / f"SUB_{cik}.json"
        if not sub_p.exists():
            rec["path3_note"] = "submissions 快取缺"
            rows.append(rec)
            continue
        try:
            sub = json.loads(sub_p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            rec["path3_note"] = "submissions 快取壞檔"
            rows.append(rec)
            continue
        pick = _pick_filing(sub, dl, cik, hist_budget)
        if not pick:
            rec["path3_note"] = "下市日前無 10-K／10-Q（recent 視窗內）"
            rows.append(rec)
            continue
        acc, doc = pick
        accn = acc.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}"
        rec["path3_doc_url"] = url
        cp = COVER / f"{cik}_{accn}.txt"
        if cp.exists():
            txt = cp.read_text(encoding="utf-8", errors="replace")
        else:
            if used >= hist_budget[0]:
                rec["path3_note"] = "超出本輪 120 次請求預算，未抓"
                rows.append(rec)
                continue
            acquire_slot()
            used += 1
            try:
                r = requests.get(url, headers=HEADERS, timeout=60)
                txt = _plain(r.text)[:60000] if r.status_code == 200 else f"_HTTP_{r.status_code}"
            except Exception as e:  # noqa: BLE001
                txt = f"_ERR_{type(e).__name__}"
            cp.write_text(txt, encoding="utf-8")
        if txt.startswith("_"):
            rec["path3_note"] = f"取得失敗 {txt[:20]}"
            rows.append(rec)
            continue
        head = txt[:20000]          # 封面頁在最前面；再往後是本文，誤判風險高
        sym, ev = _extract_symbol(head)
        rec["path3_symbol"], rec["path3_evidence"] = sym, ev
        rows.append(rec)
        print(f"  CIK {cik} {str(s.get('name'))[:28]:28s} → {sym}", flush=True)
    return {"rows": rows, "requests_used": used + (budget - hist_budget[0])}


def main() -> int:
    d = json.loads(PROBE.read_text(encoding="utf-8"))
    sample = d["sample"]
    print(f"=== 路徑3：下市前最後一份 10-K／10-Q 封面頁（{len(sample)} 檔，預算 {MAX_REQUESTS} 次）===", flush=True)
    r3 = resolve(sample)
    n3 = sum(1 for x in r3["rows"] if x.get("path3_symbol"))
    prev = {int(x["cik"]): x.get("ticker") for x in (d.get("yfinance") or []) if x.get("ticker")}
    merged = {}
    for x in r3["rows"]:
        c = int(x["cik"])
        merged[c] = prev.get(c) or x.get("path3_symbol")
    res = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "ruling": "先.二十一-一",
        "frame": "第一輪未過濾母體的同一批 60 檔（同種子 20261005）",
        "path3_cover_page": {
            "n": len(sample), "n_resolved": n3,
            "pct": round(100.0 * n3 / max(1, len(sample)), 1),
            "requests_used": r3["requests_used"], "budget": MAX_REQUESTS,
            "method": "下市日前最後一份 10-K／10-Q 的 primaryDocument，去標籤後取前 20,000 字（封面頁），"
                      "先比對「交易所: 代號」再比對「Trading Symbol/Symbol: 代號」，排除 NYSE/SEC/FORM 等雜訊字",
            "rows": r3["rows"],
        },
        "path4_stooq_symbol_list": {
            "verdict": "不可及（不繞牆）",
            "evidence": "2026-10-05 實測 stooq.com 三端點 /db/l/?g=27、/cmp/?q=、/q/d/l/?s= "
                        "全部回傳 796 bytes 的「This site requires JavaScript」驗證牆頁，"
                        "連 aapl.us／twtr.us／sivb.us 皆然",
            "rule": "CLAUDE.md 取得方式鐵律：繞過驗證牆（無頭瀏覽器、偽裝 UA）一律禁止，不論是否自用",
            "correction_to_round1": "第一輪報的『Stooq 有價格 0/60』**不是**那些代號沒有資料，"
                                    "而是端點對所有請求都不可用——兩者意義完全不同，先前的呈現會誤導，特此更正",
        },
        "merged": {
            "n": len(sample),
            "n_resolved": sum(1 for v in merged.values() if v),
            "pct": round(100.0 * sum(1 for v in merged.values() if v) / max(1, len(sample)), 1),
            "note": "合併＝路徑1（submissions.tickers）∪ 路徑2（Form 25 括號代號）∪ 路徑3（封面頁）；"
                    "路徑4 不可及故不計入",
            "symbols": {str(k): v for k, v in merged.items() if v},
        },
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n路徑3 解析 {n3}/{len(sample)}（{res['path3_cover_page']['pct']}%），"
          f"用了 {r3['requests_used']} 次請求", flush=True)
    print(f"四路合併解析 {res['merged']['n_resolved']}/{len(sample)}（{res['merged']['pct']}%）", flush=True)
    print(f"已寫入 {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
