# -*- coding: utf-8 -*-
"""新聞來源合規查證（題材萃取二，2026-09-08）。

**先查 robots.txt 與使用條款，禁止即停止並記錄。** 不試探、不繞。

判讀規則（保守）：
- robots.txt 對 `User-agent: *` 出現 `Disallow: /` → **一律不可用**
  （MOPS 的 `mopsov` 就是這樣，只放行 bingbot）
- 目標路徑落在任一 `Disallow` 前綴 → 該路徑不可用
- **robots.txt 不存在不等於允許**——還要看使用條款
  （櫃買 `ic.tpex.org.tw` 沒有 robots.txt，但條款明文禁止爬蟲）

本腳本只做**唯讀查證**：抓 robots.txt、試一個候選 RSS 路徑看回什麼，
不下載任何內容資料。
"""
from __future__ import annotations

import sys
from urllib.parse import urlparse

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaResearch/1.0)"}

# (顯示名, 主機, 候選 RSS/公開端點)
SOURCES = [
    ("中央社（現用）", "https://www.cna.com.tw", "https://feeds.feedburner.com/cnaFinance"),
    ("Yahoo 股市（現用）", "https://tw.stock.yahoo.com", "https://tw.stock.yahoo.com/rss?category=news"),
    ("經濟日報", "https://money.udn.com", "https://money.udn.com/rssfeed/news/1001/5591?ch=money"),
    ("工商時報", "https://www.ctee.com.tw", "https://www.ctee.com.tw/rss/all"),
    ("MoneyDJ", "https://www.moneydj.com", "https://www.moneydj.com/kmdj/rss/rsslist.aspx"),
    ("鉅亨網", "https://news.cnyes.com", "https://news.cnyes.com/rss/news/cat/tw_stock"),
    ("證交所新聞", "https://www.twse.com.tw", "https://www.twse.com.tw/rss/news.xml"),
    ("櫃買中心", "https://www.tpex.org.tw", "https://www.tpex.org.tw/rss/news.xml"),
]


def parse_robots(txt: str) -> tuple[list, bool]:
    """回傳 (對 * 的 Disallow 前綴清單, 是否整站禁止)。"""
    rules, cur_star, blocked_all = [], False, False
    for raw in txt.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("user-agent:"):
            cur_star = line.split(":", 1)[1].strip() == "*"
        elif cur_star and low.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path == "/":
                blocked_all = True
            if path:
                rules.append(path)
    return rules, blocked_all


def main() -> int:
    print("=" * 74)
    print("  新聞來源合規查證（題材萃取二）— 先 robots.txt，禁止即停止")
    print("=" * 74)
    for name, host, feed in SOURCES:
        print(f"\n■ {name}　{host}")
        # 1) robots.txt
        try:
            r = requests.get(host.rstrip("/") + "/robots.txt", timeout=20, headers=UA)
            body = r.text
            looks_html = "<html" in body[:400].lower() or "<!doctype" in body[:60].lower()
            if r.status_code != 200 or looks_html:
                print(f"   robots.txt：HTTP {r.status_code}"
                      f"{'（回 HTML，等於沒有 robots.txt）' if looks_html else ''}")
                rules, blocked_all = [], False
                has_robots = False
            else:
                rules, blocked_all = parse_robots(body)
                has_robots = True
                print(f"   robots.txt：HTTP 200，對 * 的 Disallow {len(rules)} 條"
                      f"{'　**整站 Disallow: /**' if blocked_all else ''}")
        except Exception as e:  # noqa: BLE001
            print(f"   robots.txt：取得失敗 {type(e).__name__}")
            rules, blocked_all, has_robots = [], False, False

        if blocked_all:
            print("   → 🔴 **整站禁止程式取用，停止，不再測試內容端點**")
            continue

        # 2) 目標路徑是否被 Disallow
        path = urlparse(feed).path or "/"
        hit = [p for p in rules if p != "/" and path.startswith(p)]
        if hit:
            print(f"   → 🔴 目標路徑 {path} 命中 Disallow {hit}，**停止**")
            continue

        # 3) 候選端點回什麼（只看格式，不落地內容）
        try:
            rr = requests.get(feed, timeout=20, headers=UA)
            t = rr.text.lstrip()
            if rr.status_code != 200:
                kind = f"HTTP {rr.status_code}"
            elif t.startswith("<?xml") or "<rss" in t[:400].lower() or "<feed" in t[:400].lower():
                n = t.count("<item") + t.count("<entry")
                kind = f"✅ RSS/Atom，約 {n} 則"
            elif "<html" in t[:400].lower():
                kind = "❌ 回 HTML（此路徑不是 RSS）"
            else:
                kind = f"？未知格式（前 40 字：{t[:40]!r}）"
            print(f"   候選端點 {feed}")
            print(f"   → {kind}")
        except Exception as e:  # noqa: BLE001
            print(f"   候選端點：失敗 {type(e).__name__}")
        if not has_robots:
            print("   ⚠ 無 robots.txt——**不等於允許**，仍須查使用條款才能下結論")
    print("\n" + "=" * 74)
    print("  註：本查證只看 robots.txt 與端點格式。robots 允許不代表條款允許，")
    print("      要實際接入前仍須逐一確認使用條款（見 docs/DATA_SOURCE_MAP.md）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
