# -*- coding: utf-8 -*-
"""從 sitemap 收集新聞連結（題材驗證 v3.3，2026-09-09）。

**為什麼改走 sitemap**：RSS 每次只給 20~50 則最新的，累積 30 天才 300 則，
而題材驗證需要的量級是數萬則（180 篇內文只萃出 12 句可用證據）。
兩家都在 robots.txt **主動宣告 sitemap**——那是網站明確邀請爬蟲索引的清單，
性質上比自己去翻列表頁乾淨得多。

**歷史回補行不通**（2026-09-09 實測）：Yahoo 子 sitemap 檔名帶日期，
但只有最近幾天存在，`2026-09-01` 以前一律 404；中央社只涵蓋 6 天。
sitemap 是滾動窗口不是封存。**所以這支只能往前累積，不能回補過去。**

本階段用途（總司令選項 3）：**先抓一天全量試水溫**，
量出「N 則新聞能產出幾句題材證據」的真實產出率，再決定常態要抓多少、抓哪些分類。
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data" / "news_urls.json"
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaResearch/1.0)"}
REQ_INTERVAL = 2.0
_last = [0.0]

# 中央社的分類代碼。afe＝財經、aie＝產經。其餘（國際 aopl、生活 ahel、
# 地方 aloc、體育 aspt…）對題材沒有幫助，收集階段就過濾掉，不浪費抓取額度。
CNA_WANTED = ("/afe/", "/aie/")


def _get(url: str, timeout: int = 30) -> str:
    wait = REQ_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    r = requests.get(url, timeout=timeout, headers=UA)
    return r.text if r.status_code == 200 else ""


def collect() -> dict:
    urls: dict[str, dict] = {}

    # ── 中央社：單一 sitemap，涵蓋約 6 天 ──────────────────────────────
    t = _get("https://www.cna.com.tw/sitemap_fromRemote_cfp.xml")
    cna_all = re.findall(r"<loc>(.*?)</loc>", t)
    cna = [u for u in cna_all if any(w in u for w in CNA_WANTED)]
    for u in cna:
        urls[u] = {"url": u, "source": "中央社", "host": "www.cna.com.tw"}
    print(f"  中央社 sitemap：全部 {len(cna_all)} 則，財經/產經 {len(cna)} 則")

    # ── Yahoo：index → 子 sitemap（每檔一天）──────────────────────────
    idx = _get("https://tw.stock.yahoo.com/news-sitemap-index.xml")
    subs = re.findall(r"<loc>(.*?)</loc>", idx)
    print(f"  Yahoo news-sitemap-index：{len(subs)} 個子檔（每檔一天）")
    for sub in subs:
        s = _get(sub)
        locs = re.findall(r"<loc>(.*?)</loc>", s)
        day = re.search(r"(\d{4}-\d{2}-\d{2})", sub)
        for u in locs:
            urls[u] = {"url": u, "source": "Yahoo股市", "host": "tw.stock.yahoo.com"}
        print(f"    {day.group(1) if day else sub[-24:]}：{len(locs)} 則")

    return urls


def main() -> int:
    print("=" * 62)
    print("  從 sitemap 收集新聞連結（試水溫，只收連結不抓內文）")
    print("=" * 62)
    urls = collect()

    prior = {}
    if OUT.exists():
        try:
            prior = {e["url"]: e for e in
                     json.loads(OUT.read_text(encoding="utf-8")).get("urls", [])}
        except (OSError, json.JSONDecodeError):
            prior = {}
    new = {u: v for u, v in urls.items() if u not in prior}
    merged = list(prior.values()) + list(new.values())

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "note": "只收集連結，內文另由 news_body_extract.py 抓（白名單：中央社、Yahoo）。",
            "history": "sitemap 是滾動窗口（6~7 天），舊日期 404，無法回補歷史。",
            "cna_filter": f"中央社只收 {CNA_WANTED}（財經/產經），其餘分類對題材無幫助。",
            "total": len(merged), "new_this_run": len(new),
        },
        "urls": merged,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    by_src = Counter(v["source"] for v in merged)
    print(f"\n  本輪新增 {len(new)} 則，累計 {len(merged)} 則")
    print(f"  來源分布：{dict(by_src)}")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
