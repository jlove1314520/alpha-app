# -*- coding: utf-8 -*-
"""新聞內文題材句萃取（題材驗證 v3.2，2026-09-09）。

**為什麼一定要讀內文**（2026-09-08 實測的死結）：
300 則新聞**標題**裡，「先進封裝／CoWoS／PCB／CCL／探針卡／散熱／IC設計／
AI伺服器／玻璃基板」這些詞**出現次數全部是 0**。
再查 RSS 本身的 `<description>`——三個來源全都只有標題長度，超過 60 字的 0 段。

標題的語言是「台積電撐盤攻2505元」，不是「台積電先進封裝產能擴充」。
**題材詞彙只存在於內文。不讀內文，再多新聞量也驗不出題材**——
這解釋了新聞量 179→300、命中 17→55，題材卻只從 1→3。

**取得範圍（總司令 2026-09-09 選項 2）**：
只讀**中央社**與 **Yahoo** 的內文；**經濟日報維持只用標題與連結**。
理由：中央社是國營通訊社、Yahoo 是聚合平台，條款相對寬鬆；
UDN 著作權聲明明文禁止未經授權之下載／轉貼／重製，先不碰內文，
等有明確授權再擴大。

**合規做法**：
- 三家文章頁路徑都已逐一比對 robots.txt 的 `User-agent: *` 規則，**均未被 Disallow 涵蓋**
- 每次請求間隔 ≥2 秒
- **只保存命中的那一句**，不保存全文（總司令裁示：只存必要的一句、不轉載全文）
- 每句都附出處 URL 與日期，可回頭追溯
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent.parent
D = ROOT / "data"
OUT = D / "news_evidence.json"
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaResearch/1.0)"}

# **白名單制**：只抓這兩家的內文。沒列在這裡的一律不抓——
# 白名單比黑名單安全：新增來源時必須明確決定，不會因為忘記排除而誤抓。
BODY_ALLOWED = {"www.cna.com.tw", "tw.stock.yahoo.com"}
REQ_INTERVAL = 2.0
MAX_PER_RUN = 200          # 每輪上限，避免一次打太多；增量累積
SENT_MAX = 160            # 單句保存長度上限

_last = [0.0]

# 句型規則（來自 theme_keywords.json，與 build_themes.py 共用同一份規則檔）
def _load_patterns() -> list:
    try:
        d = json.loads((ROOT / "data" / "seed" / "theme_keywords.json").read_text(encoding="utf-8"))
        return (d.get("sentence_patterns") or {}).get("patterns") or []
    except (OSError, json.JSONDecodeError):
        return []


PATTERNS = _load_patterns()


def pattern_hit(text: str, kws: list, patterns: list) -> str | None:
    """句型明確？「<句型前綴>+<題材關鍵詞>」出現才算。"""
    for kw in kws:
        for pat in patterns:
            frag = pat.replace("{theme}", kw).replace("{code}", "").strip()
            if frag and frag in text:
                return frag
    return None


def fetch_body(url: str) -> str:
    wait = REQ_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    r = requests.get(url, timeout=25, headers=UA)
    if r.status_code != 200:
        return ""
    html = r.text
    # 2026-09-09 修正：**第一版抓全頁的 <p> 是錯的**，會把側欄「相關新聞」的
    # 連結文字一起抓進來。實測抽驗立刻露餡——「中方不證實女警西藏土石流失聯…
    # 盧秀燕憂中火增氣不拆煤…」這種一整團無關標題被判定成台積電的水冷散熱證據，
    # 因為那團文字沒有標點、切不開句子，整團當成一句去比對關鍵詞。
    # 這是「拿到資料不等於拿到正確的資料」的同一個形狀：
    # 58/60 的命中率看起來很成功，內容全是導覽湯。
    # 改成**先取文章容器再取 p**。找不到容器就誠實回空，不退回全頁抓。
    body_html = ""
    for pat in (r'<div[^>]*class="[^"]*paragraph[^"]*"[^>]*>(.*?)(?:<aside|<footer|</article)',
                r"<article[^>]*>(.*?)</article>"):
        m = re.search(pat, html, re.S)
        if m:
            body_html = m.group(1)
            break
    if not body_html:
        return ""
    ps = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)
    txt = " ".join(re.sub(r"<[^>]+>", "", p) for p in ps)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def split_sentences(text: str) -> list:
    """切句，並擋掉「導覽湯」。

    導覽湯的特徵是**超長但沒有標點**——那是多則標題被串在一起，不是一個句子。
    中文新聞裡真正的句子很少超過 60 字還一個逗號都沒有。
    這道防線是第二層：就算容器抓錯，這裡還能擋下明顯不是句子的東西。
    """
    out = []
    for s in re.split(r"[。！？；\n]", text):
        s = s.strip()
        if len(s) <= 8 or len(s) > 200:
            continue
        if len(s) > 60 and "，" not in s and "、" not in s:
            continue
        out.append(s)
    return out


def main() -> int:
    news = (json.loads((D / "news.json").read_text(encoding="utf-8"))
            .get("news") or [])
    kwdoc = json.loads((D / "seed" / "theme_keywords.json").read_text(encoding="utf-8"))
    theme_kw = {tid: v["keywords"] for tid, v in (kwdoc.get("themes") or {}).items()}

    from news_matcher import load_company_names, load_active_codes, match_article
    name2code, _amb = load_company_names()
    active = load_active_codes()

    prior = {}
    if OUT.exists():
        try:
            prior = {e["url"]: e for e in
                     json.loads(OUT.read_text(encoding="utf-8")).get("evidence", [])}
        except (OSError, json.JSONDecodeError):
            prior = {}

    todo = [n for n in news
            if any(h in (n.get("url") or "") for h in BODY_ALLOWED)
            and n.get("url") not in prior]
    print(f"新聞 {len(news)} 則｜白名單內未抓過的 {len(todo)} 則｜本輪上限 {MAX_PER_RUN}")

    out = list(prior.values())
    fetched = hit_articles = 0
    for n in todo[:MAX_PER_RUN]:
        url = n["url"]
        try:
            body = fetch_body(url)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {url[:60]} 失敗 {type(e).__name__}")
            continue
        fetched += 1
        if not body:
            out.append({"url": url, "quotes": [], "note": "內文取得為空"})
            continue
        m = match_article(n.get("title", ""), body, name2code, active)
        codes = set(m["codes"])
        quotes = []
        if codes:
            for sent in split_sentences(body):
                for tid, kws in theme_kw.items():
                    k = next((k for k in kws if k in sent), None)
                    if not k:
                        continue
                    in_sent = {c for c in codes
                               if c in sent or any(nm in sent and cc == c
                                                   for nm, cc in name2code.items())}
                    if not in_sent:
                        continue
                    # 2026-09-09 收緊：**同句共現不夠，必須句型明確。**
                    # 實測抽驗 6 句只有 2 句是對的，錯的那四種都是共現造成：
                    #   英業達→PCB：句子說它「被 PCB 缺料所苦」，是客戶不是供應商
                    #   千興→散熱：句子講的是汎瑋，張冠李戴
                    #   大成鋼→光模組：句子講 Lumentum，完全沒提大成鋼
                    #   台積電→記憶體：同句出現但台積電不做記憶體
                    # 共現只能證明「這兩件事被寫在同一句」，不能證明「這家公司做這件事」。
                    frag = pattern_hit(sent, [k], PATTERNS)
                    if not frag:
                        continue
                    quotes.append({"theme_id": tid, "matched": k, "pattern": frag,
                                   "codes": sorted(in_sent),
                                   # **只存這一句**，不存全文
                                   "quote": sent[:SENT_MAX]})
                    break
        if quotes:
            hit_articles += 1
        out.append({"url": url, "source": n.get("source"),
                    "date": (n.get("published") or "")[:16],
                    "codes": sorted(codes), "quotes": quotes[:6]})

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "policy": "只抓中央社與 Yahoo 內文（總司令 2026-09-09 選項 2）；"
                      "經濟日報維持只用標題與連結。",
            "storage": "只保存命中題材關鍵詞的那一句，不保存全文。",
            "robots": "三家文章頁路徑均已比對 robots.txt 的 User-agent:* 規則，未被 Disallow 涵蓋。",
            "interval_sec": REQ_INTERVAL,
            "articles_total": len(out),
            "articles_with_theme_quote": sum(1 for e in out if e.get("quotes")),
        },
        "evidence": out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  本輪抓取 {fetched} 則，其中 {hit_articles} 則含題材句")
    print(f"  累計 {len(out)} 則，含題材句 {doc['meta']['articles_with_theme_quote']} 則")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
