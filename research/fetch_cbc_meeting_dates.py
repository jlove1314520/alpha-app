# -*- coding: utf-8 -*-
"""先.九十五-R5：央行理監事聯席會議 2015～2017 決策日期＋利率決定補登（research/DATA_GAP_PLAN.md 2.16 #61 日期部分）。
只補資料，不登記試驗、不回測（#61 仍因每年只有 4 場、檢定力不足維持死亡）。

來源：央行官網「重要政策新聞」列表 www.cbc.gov.tw/tw/lp-971-1-{6,7}-20.html（2026-10-14 這兩頁涵蓋 2012-06～2018-06），
從列表取標題含「聯席會議決議」的新聞稿，逐篇讀「本行重貼現率…」那一句。
央行 robots.txt 不存在（/robots.txt 轉址到首頁），官方未公布次數上限；本腳本最多 2＋12＝14 次請求，
共用 data/rate_limit_state.json（來源名 cbc_www，同源間隔 ≥3 秒）。原始頁存 research/data/raw/cbc_meetings/（已存在不重抓）。
SSL：央行中繼 CA 缺 Subject Key Identifier，只關 ssl.VERIFY_X509_STRICT（同 .github/scripts/fetch_fx.py），不是 verify=False。
輸出 research/data/cbc_meeting_dates.json。
"""
from __future__ import annotations

import html
import json
import re
import ssl
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

SRC = "cbc_www"
RAW = HERE / "data" / "raw" / "cbc_meetings"
OUT = HERE / "data" / "cbc_meeting_dates.json"
LIST_PAGES = ["https://www.cbc.gov.tw/tw/lp-971-1-6-20.html", "https://www.cbc.gov.tw/tw/lp-971-1-7-20.html"]
UA = "alpha-research/1.0 (personal research)"


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _get(sess, url: str, cache: Path) -> str:
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    _rate_limit_wait_or_raise(SRC)
    r = sess.get(url, timeout=30, headers={"User-Agent": UA})
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block(SRC, r.status_code, url)
        raise RuntimeError(f"HTTP {r.status_code}，封鎖 2 小時")
    r.raise_for_status()
    r.encoding = "utf-8"
    cache.write_text(r.text, encoding="utf-8")
    return r.text


def _text(t: str) -> str:
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", t)))


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    sess.mount("https://", _StrictOffAdapter())
    rows = []
    for i, u in enumerate(LIST_PAGES):
        t = _get(sess, u, RAW / f"_list_{i + 6}.html")
        for d, href, title in re.findall(r'<time>([\d-]+)</time><a href="([^"]+)" title="([^"]+)"', t):
            if "2015" <= d[:4] <= "2017" and "聯席會議決議" in title:
                rows.append({"date": d, "url": href if href.startswith("http") else "https://www.cbc.gov.tw" + href, "title": title})
    rows.sort(key=lambda r: r["date"])
    out = []
    for r in rows:
        x = _text(_get(sess, r["url"], RAW / f"{r['date']}.html"))
        m = re.search(r"本行重貼現率[^。]*?(?:維持年息([\d.]+)%|調(升|降)([\d.]+)個百分點，分別由年息([\d.]+)%[^。]*?調整為([\d.]+)%)", x)
        rec = {"date": r["date"], "title": r["title"], "source_url": r["url"]}
        if m and m.group(1):
            rec.update(decision="維持", discount_rate_pct=float(m.group(1)), change_pct=0.0, basis="新聞稿原文")
        elif m:
            sign = 1 if m.group(2) == "升" else -1
            rec.update(decision="調" + m.group(2), discount_rate_pct=float(m.group(5)), change_pct=sign * float(m.group(3)),
                       prev_rate_pct=float(m.group(4)), basis="新聞稿原文")
        else:
            rec.update(decision=None, discount_rate_pct=None, basis="新聞稿頁面沒有利率句（版型不同），由前後兩次決議推導，見 note")
        out.append(rec)
    # 推導：讀不到的那場，用「上一場決議後利率」與「下一場的 prev_rate_pct（或維持值）」補，兩者不同才算有調整
    for k, rec in enumerate(out):
        if rec["discount_rate_pct"] is None and 0 < k < len(out) - 1:
            before, nxt = out[k - 1]["discount_rate_pct"], out[k + 1]
            after = nxt.get("prev_rate_pct", nxt["discount_rate_pct"])
            if before is not None and after is not None:
                rec.update(discount_rate_pct=after, change_pct=round(after - before, 4),
                           decision="維持" if after == before else ("調升" if after > before else "調降"),
                           note=f"上一場決議後 {before}%，下一場新聞稿寫『由年息 {after}%』或維持 {after}% → 本場決議後 {after}%")
    OUT.write_text(json.dumps({"meta": {"source": "www.cbc.gov.tw 重要政策新聞（lp-971）理監事聯席會議決議新聞稿",
                                        "range": "2015-2017", "n": len(out), "script": "research/fetch_cbc_meeting_dates.py"},
                               "meetings": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in out:
        print(r["date"], r["decision"], r["discount_rate_pct"], r.get("change_pct"), r["basis"][:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
