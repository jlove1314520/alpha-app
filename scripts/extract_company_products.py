# -*- coding: utf-8 -*-
"""公司官網產品頁 → 題材（A 級，題材五.2，2026-09-09）。

**為什麼只做 38 家而不是全市場**（總司令更正我的框架錯誤）：
我上一輪把這件事估成「2,138 家逐站查」→ 判定為獨立子專案。**框架錯了。**
我們要做的是**驗證既有 D 級候選**，不是**發現新成員**——後者才需要掃全市場。
七個缺口題材（先進封裝／玻璃基板／PCB／CCL／散熱／探針卡／AI伺服器）
的 D 級候選去重後只有 **38 個代號**，全部 123 個題材去重後也只有 259 家。

**為什麼要走官網**：年報與法說會簡報 PDF 都在 `doc.twse.com.tw`，
該主機 robots.txt 對 `*` 是 `Disallow: /`（2026-09-09 查證）；
MOPS 查詢頁 `mopsov` 同樣 `Disallow: /`（僅 bingbot）。
368 個官方 openapi 端點也沒有營業比重或 IFRS 8 部門揭露。
**官網是唯一剩下的「公司自述產品」來源。**

**合規做法（逐站判斷，不做通則假設）**：
- 官網網址來自 `t187ap03_L`／`mopsfin_t187ap03_O`（官方公司基本資料）
- **每一家各自查自己的 robots.txt**，被 Disallow 涵蓋的**直接跳過並記錄原因**
- 不繞、不試別的路徑、不用快取或鏡像
- 逐站間隔 ≥2 秒（沿用 news_body_extract 的節流常數精神）
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

D = ROOT / "data"
OUT = D / "company_product_evidence.json"
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaResearch/1.0)"}

# ── 節流（沿用 news_body_extract.py 那套）────────────────────────────────
REQ_INTERVAL = 2.0          # 逐站間隔，不得低於 2 秒
PAGES_PER_SITE = 3          # 每家最多抓幾頁（首頁 + 產品頁）
TIMEOUT = 20
_last = [0.0]

# 產品頁的連結特徵。中英文都列，因為官網語言不一。
PRODUCT_HINTS = ("產品", "product", "solution", "解決方案", "業務", "技術",
                 "technolog", "service", "服務", "應用", "application")

GAP_THEMES = ["adv_package", "glass_substrate", "pcb", "ccl",
              "thermal", "probe_card", "ai_server"]


def _tpex_session() -> requests.Session:
    """TPEx 專用連線。

    Python 3.13 的預設 SSL context 開啟 `VERIFY_X509_STRICT`，會要求憑證鏈上的
    CA 都帶 Subject Key Identifier；TPEx 的中介 CA 沒有，於是本機所有
    tpex.org.tw 請求都掛在 CERTIFICATE_VERIFY_FAILED。
    這件事 `scripts/data_audit.py` 早就踩過並寫進 CLAUDE.md，**我這支第一版忘了套**
    ——結果 11 家上櫃公司全被記成「無網址」，其實是連不上 TPEx 的基本資料端點。
    這裡**只**關掉那一項 RFC 5280 擴充檢查，憑證鏈與主機名驗證都照常。
    """
    import ssl
    import certifi
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    class _StrictOff(HTTPAdapter):
        def init_poolmanager(self, *a, **kw):
            ctx = create_urllib3_context()
            ctx.load_verify_locations(certifi.where())
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
            kw["ssl_context"] = ctx
            return super().init_poolmanager(*a, **kw)

    s = requests.Session()
    s.mount("https://", _StrictOff())
    s.headers.update(UA)
    return s


_TPEX_SESS = None


def _get(url: str):
    global _TPEX_SESS
    wait = REQ_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    if "tpex.org.tw" in url:
        if _TPEX_SESS is None:
            _TPEX_SESS = _tpex_session()
        return _TPEX_SESS.get(url, timeout=TIMEOUT)
    return requests.get(url, timeout=TIMEOUT, headers=UA)


def robots_allows(site: str, path: str = "/") -> tuple[bool, str]:
    """這一站的 robots.txt 允不允許抓 path。

    **沒有 robots.txt 不等於允許**——但也不等於禁止。
    這裡採「沒有明文禁止就視為允許」，與 Google 等檢索器的通行判讀一致；
    有明文 Disallow 涵蓋就一律跳過，不做任何例外。
    """
    try:
        r = _get(site.rstrip("/") + "/robots.txt")
    except Exception as e:  # noqa: BLE001
        return False, f"robots 取得失敗（{type(e).__name__}）"
    if r.status_code != 200:
        return True, f"無 robots.txt（HTTP {r.status_code}）"
    body = r.text
    if "<html" in body[:400].lower():
        return True, "robots.txt 回 HTML（等於沒有）"
    dis, cur = [], False
    for raw in body.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("user-agent:"):
            cur = line.split(":", 1)[1].strip() == "*"
        elif cur and low.startswith("disallow:"):
            p = line.split(":", 1)[1].strip()
            if p:
                dis.append(p)
    if "/" in dis:
        return False, "robots.txt 對 * 是 Disallow: /（整站禁止）"
    hit = [p for p in dis if path.startswith(p)]
    if hit:
        return False, f"路徑被 Disallow 涵蓋：{hit[:3]}"
    return True, f"robots.txt 允許（{len(dis)} 條 Disallow 未涵蓋）"


def page_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def find_product_links(base: str, html: str) -> list:
    out, seen = [], set()
    for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>([^<]{0,40})', html, re.I):
        href, label = m.group(1), m.group(2)
        blob = (href + " " + label).lower()
        if not any(h.lower() in blob for h in PRODUCT_HINTS):
            continue
        u = urljoin(base, href)
        if urlparse(u).netloc != urlparse(base).netloc:
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= PAGES_PER_SITE - 1:
            break
    return out


def main() -> int:
    from news_body_extract import split_sentences, pattern_hit, PATTERNS

    themes = json.loads((D / "themes.json").read_text(encoding="utf-8"))
    kwdoc = json.loads((D / "seed" / "theme_keywords.json").read_text(encoding="utf-8"))
    theme_kw = {tid: v["keywords"] for tid, v in (kwdoc.get("themes") or {}).items()}

    codes = set()
    for t in themes["themes"]:
        if t["id"] in GAP_THEMES:
            codes |= set(t["members"])
    codes = sorted(codes)
    print(f"七個缺口題材的 D 級候選去重後：{len(codes)} 家")

    # 官網網址：上市走 t187ap03_L、上櫃走 mopsfin_t187ap03_O
    sites = {}
    for url, ckey, ukey in (
        ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司代號", "網址"),
        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "SecuritiesCompanyCode", "WebAddress"),
    ):
        try:
            for r in _get(url).json():
                c = str(r.get(ckey) or "").strip()
                w = str(r.get(ukey) or "").strip()
                if c and w and c not in sites:
                    sites[c] = w if w.startswith("http") else "https://" + w
        except Exception as e:  # noqa: BLE001
            print(f"  ! 取公司基本資料失敗 {url[-24:]}：{type(e).__name__}")

    stats = {"fetchable": 0, "robots_blocked": 0, "unreachable": 0, "no_url": 0}
    results, evidence = [], []
    for code in codes:
        site = sites.get(code)
        if not site:
            stats["no_url"] += 1
            results.append({"code": code, "status": "no_url", "note": "官方基本資料無網址欄位"})
            continue
        ok, why = robots_allows(site)
        if not ok:
            if "取得失敗" in why:
                stats["unreachable"] += 1
                results.append({"code": code, "site": site, "status": "unreachable", "note": why})
            else:
                stats["robots_blocked"] += 1
                results.append({"code": code, "site": site, "status": "robots_blocked", "note": why})
            print(f"  {code} 跳過：{why}")
            continue
        stats["fetchable"] += 1
        pages, texts = [site], []
        try:
            r = _get(site)
            if r.status_code == 200:
                texts.append(page_text(r.text))
                pages += find_product_links(site, r.text)
        except Exception as e:  # noqa: BLE001
            results.append({"code": code, "site": site, "status": "fetch_error",
                            "note": f"{type(e).__name__}"})
            continue
        for u in pages[1:]:
            try:
                rr = _get(u)
                if rr.status_code == 200:
                    texts.append(page_text(rr.text))
            except Exception:  # noqa: BLE001
                pass
        hits = []
        for txt in texts:
            for sent in split_sentences(txt):
                for tid in GAP_THEMES:
                    kws = theme_kw.get(tid) or []
                    k = next((kk for kk in kws if kk in sent), None)
                    if not k:
                        continue
                    frag = pattern_hit(sent, [k], PATTERNS)
                    if not frag:
                        continue      # 共現不算——與新聞路徑同一把尺
                    hits.append({"theme_id": tid, "matched": k, "pattern": frag,
                                 "quote": sent[:160], "url": site})
                    break
        results.append({"code": code, "site": site, "status": "ok",
                        "pages": len(texts), "hits": len(hits), "note": why})
        if hits:
            evidence.append({"code": code, "site": site, "quotes": hits[:6]})
        print(f"  {code} {site[:40]:42s} 抓 {len(texts)} 頁、題材句 {len(hits)}")

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "scope": "七個缺口題材的 D 級候選（驗證既有候選，非發現新成員）",
            "candidates": len(codes),
            "evidence_level": "A（公司自述產品）",
            "policy": "逐站查 robots.txt，被 Disallow 涵蓋者跳過並記錄原因；不繞、不用快取或鏡像。",
            "throttle": f"逐站間隔 {REQ_INTERVAL}s、每家最多 {PAGES_PER_SITE} 頁",
            "stats": stats,
        },
        "sites": results,
        "evidence": evidence,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=" * 60)
    print(f"  可抓 {stats['fetchable']}、robots 擋 {stats['robots_blocked']}、"
          f"連不上 {stats['unreachable']}、無網址 {stats['no_url']}")
    print(f"  產生 A 級證據的公司：{len(evidence)} 家")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
