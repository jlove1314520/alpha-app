# -*- coding: utf-8 -*-
"""先.八十七-1：從 SEC EDGAR Form 25 抽 60 檔已下市美股（分散年份與交易所），固定清單。

總司令 2026-10-13【先.八十七（修正版：只用免費管道）】1：
「從 SEC EDGAR Form 25 抽 60 檔已下市美股（分散年份與交易所），固定這份清單並 commit。」
這份清單是 先.八十八-3（Tiingo 免費版覆蓋率實測）的固定受測母體。

**不計任何報酬、不登記試驗、不計 N、不碰 holdout**——只決定「要拿哪 60 檔去問資料源」。

做法（全部可重現，種子固定）：
1. 母體＝`us_universe_rebuild.py` 已解析過的 Form 25／25-NSE（2010 起，本機快取
   `data/raw/sec_form25/`），只留：
   - 證券類別是普通股（`is_common`）；
   - 這筆 Form 25 的日期＝`us_universe_pit.json` 判定的該 CIK 下市日（排除轉板，
     轉板判別沿用 rebuild 的「其後 180 天不再申報定期報告」規則）；
   - 有過 10-K／10-Q（`first_periodic_report` 非空，排除只申報 N-CSR 的封閉型基金）。
2. 交易所：讀 Form 25 原文。XML 版取 `<exchange><entityName>`；HTML 版（2010 年代前期，
   公司自行申報的 Form 25）在內文找交易所名稱。歸成 Nasdaq／NYSE／NYSE American
   （含 AMEX、NYSE Amex、NYSE MKT）三類，其餘（NYSE Arca 等）不抽。
3. 分層：下市年份 6 段（2010-12／13-15／16-18／19-21／22-24／25-26）×
   交易所配額（Nasdaq 4、NYSE 4、NYSE American 2）＝ 6×10＝60。
   [自行裁量] 配額比例取近似實際下市件數分布（NYSE American 家數最少），且讓每段都有三所。
4. 每層用固定種子洗牌後依序解析「下市前代號」，解析到才收；解析不到就換同層下一檔，
   並把換掉幾檔、為什麼換掉全數記錄（代號解析率本身是要誠實揭露的數字）。
   代號來源依可靠度：
   (a) 下市日前最後一份 10-K／10-Q 主文件裡的 iXBRL `dei:TradingSymbol`（2019 年後必填）；
   (b) 同一份申報的 XBRL instance 檔裡的 `dei:TradingSymbol`；
   （封面頁文字句型比對試跑時誤抓收購方代號，只記錄不採用，見 resolve_ticker 註解。）
   **刻意不用** SEC 現行 `company_tickers.json`／submissions 的 `tickers`：
   下市股的代號常被別家公司沿用（BBBY 案例），用現行對照會拿到錯的公司。

SEC 禮儀：共用 `sec_rate_limiter`（跨行程合計 ≤5 req/秒，官方上限 10 req/秒）；
本次請求數上限 `MAX_REQUESTS`，用完就停、照實記錄未完成的層。

用法：python research/us_delisted_sample60.py
輸出：research/data/us_delisted_sample60.json（進 repo；原始申報快取不進 repo）
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sec_rate_limiter import acquire_slot  # noqa: E402
from us_delisted_ticker_resolve import _extract_symbol, _plain  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW = HERE / "data" / "raw"
STATE = RAW / "us_universe_rebuild_state.json"
UNIV = HERE / "data" / "us_universe_pit.json"
F25 = RAW / "sec_form25"
CACHE = RAW / "us_sample60"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = HERE / "data" / "us_delisted_sample60.json"
HEADERS = {"User-Agent": "AlphaResearch-USTrack contact@alpha-research-project.example",
           "Accept-Encoding": "gzip, deflate"}
SEED = 20261014
MAX_REQUESTS = 900
MAX_TRIES_PER_CELL = 30
YEAR_BUCKETS = [(2010, 2012), (2013, 2015), (2016, 2018), (2019, 2021), (2022, 2024), (2025, 2026)]
QUOTA = {"Nasdaq": 4, "NYSE": 4, "NYSE American": 2}

EXCH_XML = re.compile(r"<exchange>.*?<entityName>(.*?)</entityName>", re.I | re.S)
FILED_BY = re.compile(r"FILED BY:\s*COMPANY DATA:\s*COMPANY CONFORMED NAME:\s*(.+)", re.I)
DEI_SYM = re.compile(r"dei:TradingSymbol[^>]*>\s*(?:<[^>]+>\s*)*([A-Za-z][A-Za-z.\-]{0,6})\s*<", re.I)
SYM_OK = re.compile(r"^[A-Z]{1,5}(?:[.\-][A-Z]{1,2})?$")
# 抽樣端自己的證券類別過濾（比 us_universe_rebuild 的 is_common 嚴）：
# 上游 _only_noncommon() 對「Redeemable Warrants ... exercisable for ... Class A Common Stock」
# 這種同時含兩種字樣的標題會判成普通股（實測 BKSY 2026-08-26 權證下市被當成公司下市），
# 所以這裡要求「至少一個標題是普通股、且該標題不含權證／單位／優先股等字樣」。
COMMON_T = re.compile(r"common\s*stock|common\s*shares|ordinary\s*shares|ordinary\s*stock|"
                      r"class\s+[ab]\b|common\s*equity|share[s]?\s+of\s+common", re.I)
NONCOMMON_T = re.compile(r"preferred|warrant|\bunit[s]?\b|\bnote[s]?\b|bond|debenture|right[s]?\b|"
                         r"depositary\s+share|subordinat|contingent\s+value|exercisable", re.I)
# 下市日要夠舊：上游轉板判別靠「Form 25 後 180 天內不再申報定期報告」，但「180 天後還有
# 申報」要等 180 天＋一季申報期才看得到。第一版取 183 天，結果混進 UAMY（2026-03-16
# NYSE American 轉 NYSE，之後 2026-08-11 照常申報 10-Q）。[自行裁量] 改成往前約 270 天。
EVENT_CUTOFF = "2026-01-14"

_used = [0]


def exchange_of(txt: str) -> str | None:
    """Form 25 原文 → 交易所三類之一；判斷不出來回 None（不猜）。"""
    m = EXCH_XML.search(txt)
    name = m.group(1) if m else None
    if not name:
        m2 = FILED_BY.search(txt)
        if m2 and re.search(r"exchange|nasdaq|nyse", m2.group(1), re.I):
            name = m2.group(1)
    if not name:
        body = txt.split("<TEXT>", 1)[-1][:20000]
        body = re.sub(r"<[^>]+>|&#\d+;|&[a-zA-Z]+;", " ", body)
        body = re.sub(r"\s+", " ", body)
        hits = []
        for lab, rx in (("NYSE American", r"NYSE\s*(?:Amex|MKT|American)|American\s+Stock\s+Exchange"),
                        ("NYSE Arca", r"NYSE\s*Arca|Archipelago"),
                        ("Nasdaq", r"NASDAQ|Nasdaq"),
                        ("NYSE", r"New\s+York\s+Stock\s+Exchange|\bNYSE\b")):
            mm = re.search(rx, body, re.I)
            if mm:
                hits.append((mm.start(), lab))
        if not hits:
            return None
        return sorted(hits)[0][1]
    n = name.upper()
    if re.search(r"AMEX|MKT|AMERICAN", n):
        return "NYSE American"
    if "ARCA" in n:
        return "NYSE Arca"
    if "NASDAQ" in n:
        return "Nasdaq"
    if "NEW YORK STOCK EXCHANGE" in n or re.search(r"\bNYSE\b", n):
        return "NYSE"
    return "其他:" + name.strip()[:40]


def _get(url: str, cache: Path) -> str | None:
    if cache.exists():
        try:
            t = gzip.decompress(cache.read_bytes()).decode("utf-8", "replace")
            return None if t.startswith("_HTTP_") or t.startswith("_ERR_") else t
        except Exception as e:  # noqa: BLE001
            print(f"  [快取壞檔，重抓] {cache.name}: {type(e).__name__}", flush=True)
    if _used[0] >= MAX_REQUESTS:
        raise RuntimeError("REQUEST_BUDGET_EXHAUSTED")
    acquire_slot()
    _used[0] += 1
    try:
        r = requests.get(url, headers=HEADERS, timeout=90)
        t = r.text if r.status_code == 200 else f"_HTTP_{r.status_code}"
    except Exception as e:  # noqa: BLE001
        t = f"_ERR_{type(e).__name__}"
    cache.write_bytes(gzip.compress(t.encode("utf-8", "replace")))
    return None if t.startswith("_") else t


def _scan(block: dict, before: str, best):
    for f, d, a, p in zip(block.get("form") or [], block.get("filingDate") or [],
                          block.get("accessionNumber") or [], block.get("primaryDocument") or []):
        if str(f) in ("10-K", "10-Q", "10-K405", "10-KSB", "10-QSB", "20-F", "40-F") and d and d <= before:
            if best is None or d > best[0]:
                best = (d, a, p, str(f))
    return best


def last_report_before(cik: int, before: str):
    sub_t = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", CACHE / f"SUB_{cik}.json.gz")
    if not sub_t:
        return None, None, "submissions 取得失敗"
    sub = json.loads(sub_t)
    meta = {"sic": sub.get("sic"), "sicDescription": sub.get("sicDescription"),
            "current_tickers_NOT_USED": sub.get("tickers") or []}
    filings = sub.get("filings") or {}
    best = _scan(filings.get("recent") or {}, before, None)
    if not best:
        for fm in filings.get("files") or []:
            nm = fm.get("name")
            if not nm:
                continue
            t = _get(f"https://data.sec.gov/submissions/{nm}", CACHE / f"HIST_{nm}.gz")
            if t:
                best = _scan(json.loads(t), before, best)
    return best, meta, None if best else "下市日前找不到 10-K／10-Q"


def _pick_symbol(txt: str):
    """同一份申報常有多個 dei:TradingSymbol（SPAC 的普通股／單位／權證：QLEP、QLEPU、QLEPW）。
    取最短的那個（普通股代號是單位／權證代號的字首）；長度相同取先出現者。"""
    found = []
    for m in DEI_SYM.finditer(txt):
        s = m.group(1).upper()
        if SYM_OK.match(s):
            found.append((len(s), m.start(), s, re.sub(r"\s+", " ", txt[max(0, m.start() - 60):m.end() + 10])))
    if not found:
        return None
    best = min(found)
    alts = sorted({f[2] for f in found} - {best[2]})
    return best[2], best[3] + (f" ｜同申報其他代號：{','.join(alts)}" if alts else "")


def resolve_ticker(cik: int, before: str) -> dict:
    best, meta, err = last_report_before(cik, before)
    out = {"meta": meta or {}, "ticker": None, "ticker_source": None, "evidence": None, "doc_url": None}
    if not best:
        out["fail"] = err
        return out
    d, acc, doc, form = best
    accn = acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}"
    out["doc_url"] = f"{base}/{doc}"
    out["report_date"], out["report_form"] = d, form
    raw = _get(out["doc_url"], CACHE / f"DOC_{cik}_{accn}.gz") if doc else None
    if raw:
        hit = _pick_symbol(raw)
        if hit:
            out.update(ticker=hit[0], ticker_source="ixbrl_dei_TradingSymbol", evidence=hit[1])
            return out
    idx = _get(f"{base}/index.json", CACHE / f"IDX_{cik}_{accn}.gz")
    if idx:
        try:
            items = json.loads(idx).get("directory", {}).get("item", [])
        except Exception as e:  # noqa: BLE001
            print(f"  [index.json 解析失敗] {cik}: {type(e).__name__}", flush=True)
            items = []
        inst = [it["name"] for it in items if it.get("name", "").lower().endswith(".xml")
                and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary|^R\d+)\.xml$", it["name"], re.I)]
        for nm in inst[:2]:
            x = _get(f"{base}/{nm}", CACHE / f"XBRL_{cik}_{accn}_{nm}.gz")
            if not x:
                continue
            hit = _pick_symbol(x)
            if hit:
                out.update(ticker=hit[0], ticker_source="xbrl_instance_dei_TradingSymbol",
                           evidence=f"{nm}: " + hit[1])
                return out
    # 封面頁文字那條路（_extract_symbol）第一次試跑就抓錯：KSW INC 被抓成收購方 Tutor Perini
    # 的 TPC（10-Q 內文提到併購方「NYSE: TPC」）。錯代號會把「我們抓錯」算成「資料源不正確」，
    # 所以只採用公司自己在 XBRL 申報的 dei:TradingSymbol；封面頁結果只記錄、不採用。
    if raw:
        sym, _ev = _extract_symbol(_plain(raw)[:20000])
        out["cover_page_guess_NOT_USED"] = sym
    out["fail"] = "XBRL 裡沒有 dei:TradingSymbol"
    return out


def main() -> int:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    uni = json.loads(UNIV.read_text(encoding="utf-8"))["universe"]
    frame = {}
    for acc, v in st["form25_classes"].items():
        if not v.get("is_common") or v["date"] > EVENT_CUTOFF:
            continue
        if not any(COMMON_T.search(t) and not NONCOMMON_T.search(t) for t in (v.get("titles") or [])):
            continue
        for c in (v.get("issuer_ciks") or [int(v["cik"])]):
            u = uni.get(str(int(c)))
            if not u or u.get("status") != "delisted" or u.get("delisted_at") != v["date"]:
                continue
            if not u.get("first_periodic_report"):
                continue
            if int(c) in frame:
                continue
            frame[int(c)] = {"cik": int(c), "name": u["name"], "delisted_at": v["date"],
                             "form25_accession": acc, "form25_type": v["form"],
                             "form25_class_titles": v.get("titles", [])[:3],
                             "first_periodic_report": u["first_periodic_report"],
                             "last_periodic_report": u["last_periodic_report"]}
    exch_cnt = Counter()
    for c, r in frame.items():
        p = F25 / f"{r['form25_accession']}.txt.gz"
        try:
            txt = gzip.decompress(p.read_bytes()).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  [Form 25 快取讀取失敗] {p.name}: {type(e).__name__}", flush=True)
            txt = ""
        r["exchange"] = exchange_of(txt) if txt else None
        exch_cnt[r["exchange"] or "判斷不出"] += 1
    print(f"母體（普通股、非轉板、有定期報告）{len(frame)} 檔；交易所分布 {dict(exch_cnt)}", flush=True)

    rng = random.Random(SEED)
    cells, picked, frame_counts = [], [], {}
    try:
        for lo, hi in YEAR_BUCKETS:
            for ex, q in QUOTA.items():
                pool = sorted((r for r in frame.values()
                               if r["exchange"] == ex and lo <= int(r["delisted_at"][:4]) <= hi),
                              key=lambda r: r["cik"])
                rng.shuffle(pool)
                key = f"{lo}-{hi}|{ex}"
                frame_counts[key] = len(pool)
                got, tried, skipped = [], 0, []
                for r in pool:
                    if len(got) >= q or tried >= MAX_TRIES_PER_CELL:
                        break
                    tried += 1
                    res = resolve_ticker(r["cik"], r["delisted_at"])
                    if res.get("ticker"):
                        got.append({**r, "ticker": res["ticker"], "ticker_source": res["ticker_source"],
                                    "ticker_evidence": (res["evidence"] or "")[:240],
                                    "ticker_doc_url": res["doc_url"],
                                    "ticker_report_date": res.get("report_date"),
                                    "sic": res["meta"].get("sic"),
                                    "sic_description": res["meta"].get("sicDescription"),
                                    "stratum": key})
                        print(f"  {key:26s} {r['cik']:>8} {r['name'][:30]:30s} → {res['ticker']} "
                              f"({res['ticker_source']})", flush=True)
                    else:
                        skipped.append({"cik": r["cik"], "name": r["name"], "reason": res.get("fail"),
                                        "cover_page_guess_NOT_USED": res.get("cover_page_guess_NOT_USED")})
                picked += got
                cells.append({"stratum": key, "frame_n": len(pool), "quota": q, "picked": len(got),
                              "tried": tried, "skipped_no_ticker": skipped})
    except RuntimeError as e:
        print(f"  [停止] {e}：已用 {_used[0]} 次請求", flush=True)
        cells.append({"stratum": "（中止）", "error": str(e)})

    n_tried = sum(c.get("tried", 0) for c in cells)
    doc = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "ruling": "先.八十七-1（2026-10-13 總司令【先.八十七（修正版：只用免費管道）】1）",
        "purpose": "先.八十八-3 Tiingo 免費版下市股覆蓋率實測的固定受測清單；不計報酬、不登記試驗、不計 N、不碰 holdout",
        "seed": SEED,
        "frame": {"definition": f"SEC EDGAR Form 25／25-NSE（2010 起）普通股下市事件（標題含普通股且不含權證／單位等字樣；事件日 ≤{EVENT_CUTOFF}），日期＝us_universe_pit.json 判定的下市日"
                                "（排除轉板），且曾申報 10-K／10-Q；交易所取自 Form 25 原文",
                  "n": len(frame), "by_exchange": dict(exch_cnt), "by_stratum": frame_counts},
        "design": {"year_buckets": [f"{a}-{b}" for a, b in YEAR_BUCKETS], "quota_per_bucket": QUOTA,
                   "rule": "每層固定種子洗牌，依序解析下市前代號，解析到才收，解析不到換同層下一檔並記錄"},
        "ticker_resolution": {
            "sources_in_order": ["下市前最後一份定期報告主文件 iXBRL dei:TradingSymbol",
                                 "同申報 XBRL instance dei:TradingSymbol"],
            "not_used": "封面頁文字句型（試跑誤抓收購方代號：KSW→TPC）；SEC 現行 company_tickers.json／submissions.tickers（下市代號常被沿用，會對到錯的公司）",
            "tried": n_tried, "resolved": len(picked),
            "resolve_rate_pct": round(100.0 * len(picked) / max(1, n_tried), 1),
            "caveat": "清單只含「解析得到下市前代號」的公司；解析不到的（多為 2010～2012 年未附 XBRL 代號的小型股）"
                      "被換掉，故本清單對 Tiingo 是偏樂觀的受測母體，覆蓋率結果要連同這個解析率一起讀",
        },
        "sec_requests_used": _used[0],
        "cells": cells,
        "sample": picked,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n抽到 {len(picked)}/60；嘗試 {n_tried} 檔、代號解析率 {doc['ticker_resolution']['resolve_rate_pct']}%；"
          f"SEC 請求 {_used[0]} 次 → {OUT}", flush=True)
    return 0 if len(picked) == 60 else 2


if __name__ == "__main__":
    raise SystemExit(main())
