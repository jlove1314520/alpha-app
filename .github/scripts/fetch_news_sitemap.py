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


def _load_prev_meta():
    """讀上一輪的 meta，供排程健康度比對（排程一.三.2）。"""
    try:
        return json.loads(OUT.read_text(encoding="utf-8")).get("meta") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_entries(xml: str) -> dict:
    """把 sitemap 拆成 url → 發布時間（新聞一.1）。

    **為什麼一定要現在撿**：sitemap 是 6~7 天滾動窗口，
    每天約 1/7 的發布日期永久流失——今天不撿就沒了。
    第一版只抓 `<loc>` 丟掉時間，導致 3,597 則的 published 全是空的。

    兩種時間欄位都要看：
    - `<news:publication_date>`：新聞 sitemap 專用，最準
    - `<lastmod>`：一般 sitemap 的最後修改時間，次佳
    """
    out = {}
    # 以 <url> 為單位切塊，才能把 loc 與同一塊裡的時間欄位配起來
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        m = re.search(r"<loc>(.*?)</loc>", block)
        if not m:
            continue
        pub = (re.search(r"<news:publication_date>(.*?)</news:publication_date>", block)
               or re.search(r"<lastmod>(.*?)</lastmod>", block))
        out[m.group(1).strip()] = (pub.group(1).strip() if pub else None)
    if not out:      # 有些 sitemap 不用 <url> 包，退回逐個 loc（此時拿不到時間）
        for u in re.findall(r"<loc>(.*?)</loc>", xml):
            out[u.strip()] = None
    return out


def collect() -> dict:
    urls: dict[str, dict] = {}

    # ── 中央社：單一 sitemap，涵蓋約 6 天 ──────────────────────────────
    t = _get("https://www.cna.com.tw/sitemap_fromRemote_cfp.xml")
    cna_entries = _parse_entries(t)
    cna = {u: p for u, p in cna_entries.items() if any(w in u for w in CNA_WANTED)}
    for u, pub in cna.items():
        urls[u] = {"url": u, "source": "中央社", "host": "www.cna.com.tw",
                   "published": pub}
    got = sum(1 for p in cna.values() if p)
    print(f"  中央社 sitemap：全部 {len(cna_entries)} 則，財經/產經 {len(cna)} 則"
          f"（其中 {got} 則有發布時間）")

    # ── Yahoo：index → 子 sitemap（每檔一天）──────────────────────────
    idx = _get("https://tw.stock.yahoo.com/news-sitemap-index.xml")
    subs = re.findall(r"<loc>(.*?)</loc>", idx)
    print(f"  Yahoo news-sitemap-index：{len(subs)} 個子檔（每檔一天）")
    for sub in subs:
        entries = _parse_entries(_get(sub))
        day = re.search(r"(\d{4}-\d{2}-\d{2})", sub)
        got = sum(1 for p in entries.values() if p)
        for u, pub in entries.items():
            urls[u] = {"url": u, "source": "Yahoo股市", "host": "tw.stock.yahoo.com",
                       "published": pub}
        print(f"    {day.group(1) if day else sub[-24:]}：{len(entries)} 則"
              f"（{got} 則有發布時間）")

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
    # 新聞一.2 回頭補：已收錄但缺 published 的，用當前 sitemap 補上。
    # **掉出窗口的標 published_unknown，不瞎猜**——寧可標「不知道」，
    # 也不要拿抓取日冒充發布日，那會讓 effective_from 系統性偏晚。
    backfilled = still_unknown = 0
    for u, rec in prior.items():
        if rec.get("published"):
            continue
        pub = (urls.get(u) or {}).get("published")
        if pub:
            rec["published"] = pub
            rec.pop("published_unknown", None)
            backfilled += 1
        else:
            rec["published_unknown"] = True
            still_unknown += 1
    new = {u: v for u, v in urls.items() if u not in prior}
    merged = list(prior.values()) + list(new.values())
    print(f"  回頭補發布時間：補上 {backfilled} 則，"
          f"已掉出窗口標 published_unknown {still_unknown} 則")

    # 排程一.三.2 排程健康度：記錄與上一輪的間隔，供稽核判斷排程有無退化
    prev_at = (_load_prev_meta() or {}).get("generated_at")
    gap_min = None
    if prev_at:
        try:
            gap_min = round(
                (datetime.now(TZ) - datetime.fromisoformat(prev_at)).total_seconds() / 60)
        except ValueError:
            gap_min = None
    hist = (_load_prev_meta() or {}).get("run_gaps_min") or []
    if gap_min is not None:
        hist = (hist + [gap_min])[-6:]      # 只留最近 6 次
        print(f"  距上一輪 {gap_min} 分鐘（最近幾輪：{hist}）")

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "note": "只收集連結，內文另由 news_body_extract.py 抓（白名單：中央社、Yahoo）。",
            "history": "sitemap 是滾動窗口（6~7 天），舊日期 404，無法回補歷史。",
            "cna_filter": f"中央社只收 {CNA_WANTED}（財經/產經），其餘分類對題材無幫助。",
            "total": len(merged), "new_this_run": len(new),
            "published_backfilled": backfilled,
            "published_unknown": still_unknown,
            # 排程健康度：cron 設 */30 但實測只跑到 15%（見 workflow 註解），
            # 把間隔記下來讓稽核能自己看見退化，不用等總司令發現
            "last_run_gap_min": gap_min,
            "run_gaps_min": hist,
            "schedule_degraded": bool(len(hist) >= 3 and all(g > 360 for g in hist[-3:])),
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
