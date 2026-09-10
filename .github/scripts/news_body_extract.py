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

# ── 節流常數（題材一.2：全部寫在檔頭，改的人一眼看得到）────────────────
# **白名單制**：只抓這兩家的內文。沒列在這裡的一律不抓——
# 白名單比黑名單安全：新增來源時必須明確決定，不會因為忘記排除而誤抓。
# 這兩家都在 robots.txt **主動宣告 sitemap**，是明確邀請索引的來源。
BODY_ALLOWED = {"www.cna.com.tw", "tw.stock.yahoo.com"}
REQ_INTERVAL = 2.0         # 逐則間隔（秒）
MAX_PER_RUN = 200          # 每輪上限。2026-09-10 總司令裁示【停擺一】.4：
                           # 根因未明前 600 只是放大風險，先退回 200。
                           # 根因後來查明是 strip_frame_blocks 的 re.PatternError
                           # （見該函式註解），與速率無關。要再調回 600 之前，
                           # 請先用下面 extract_diag 的數字確認積壓真的是速率問題。
                           # 以下為當初調到 600 的原註（排程一.三.1），保留備查：
                           # **不是為了更快，是為了吸收排程降級。**
                           # 實測 cron */30 只跑到 15%（24 小時 7 次而非 48 次），
                           # 200/輪 × 7 = 1,400/日，積壓要 2.3 天。
                           # 改 600 → 4,200/日，不到一天清完。
                           # 2 秒間隔 × 600 = 20 分鐘，遠低於 runner 上限，
                           # **且完全不改變對來源站的請求速率**（仍是 2 秒一則）。
MAX_RETRY = 2              # 單則失敗重試上限
RETRY_BACKOFF = 5.0        # 重試間隔（秒）
MAX_CONSECUTIVE_FAIL = 10  # 連續失敗這麼多則就停止本輪——
                           # 多半是被限流或斷網，繼續打只會延長問題
SENT_MAX = 160             # 單句保存長度上限

_last = [0.0]

# ── 每輪診斷計數（總司令 2026-09-10 指示【停擺一】.1）────────────────────
# **為什麼要有這個**：這支的每一種失敗最後都變成同一個空字串——
# HTTP 4xx／5xx、連線例外、剝版面時的正規表示式例外、找不到文章容器，
# 外觀完全一樣，再加上 MAX_CONSECUTIVE_FAIL 提早中止，
# 根因被壓成一句「連續失敗，停止本輪」。
# 2026-09-09 那次就是這樣：真正的原因是 strip_frame_blocks 拋 re.PatternError，
# 但看起來像被 Yahoo 限流，白白停了 20 小時、Actions 空跑 6 輪。
# 所以每一輪都要把「分別各發生幾次」寫進 news_urls.json 的 meta.extract_diag，
# 下次再停就直接看數字分辨，不必再猜。
DIAG: dict = {}


def _diag(key: str) -> None:
    DIAG[key] = DIAG.get(key, 0) + 1


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
    html = ""
    for attempt in range(1, MAX_RETRY + 2):      # 首次 + MAX_RETRY 次重試
        wait = REQ_INTERVAL - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(url, timeout=25, headers=UA)
        except Exception as e:                   # noqa: BLE001
            _diag(f"exc:{type(e).__name__}")
            if attempt > MAX_RETRY:
                return ""
            time.sleep(RETRY_BACKOFF)
            continue
        _diag(str(r.status_code))
        if r.status_code == 200:
            html = r.text
            break
        # 4xx 不重試——那是「這頁就是沒有」，重試只是浪費額度
        if 400 <= r.status_code < 500 or attempt > MAX_RETRY:
            return ""
        time.sleep(RETRY_BACKOFF)
    if not html:
        _diag("empty_html")
        return ""
    # 2026-09-09 修正：**第一版抓全頁的 <p> 是錯的**，會把側欄「相關新聞」的
    # 連結文字一起抓進來。實測抽驗立刻露餡——「中方不證實女警西藏土石流失聯…
    # 盧秀燕憂中火增氣不拆煤…」這種一整團無關標題被判定成台積電的水冷散熱證據，
    # 因為那團文字沒有標點、切不開句子，整團當成一句去比對關鍵詞。
    # 這是「拿到資料不等於拿到正確的資料」的同一個形狀：
    # 58/60 的命中率看起來很成功，內容全是導覽湯。
    # 改成**先取文章容器再取 p**。找不到容器就誠實回空，不退回全頁抓。
    # 剝版面這一步以前**不在任何 try 裡**，一拋例外就直接冒到主迴圈被算成
    # 「這一則抓失敗」，連續 10 則整輪中止——2026-09-09 的 20 小時空轉就是這樣。
    # 現在單獨接住並記進診斷：解析壞掉是解析壞掉，不要偽裝成抓不到。
    try:
        html = strip_frame_blocks(html)  # 題材六.1：先剝版面區塊再取容器
    except Exception as e:  # noqa: BLE001
        _diag(f"exc:strip_frame_blocks:{type(e).__name__}")
        print(f"  ! strip_frame_blocks 失敗 {type(e).__name__}: {e}")
        return ""
    body_html = ""
    for pat in (r'<div[^>]*class="[^"]*paragraph[^"]*"[^>]*>(.*?)(?:<aside|<footer|</article)',
                r"<article[^>]*>(.*?)</article>"):
        m = re.search(pat, html, re.S)
        if m:
            body_html = m.group(1)
            break
    if not body_html:
        _diag("no_article_container")   # 抓到了 200 但找不到文章容器＝版型變了，
        return ""                        # 跟被擋、跟斷網是完全不同的問題
    ps = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)
    txt = " ".join(re.sub(r"<[^>]+>", "", p) for p in ps)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


# ── 題材六：版面雜訊黑名單 ──────────────────────────────────────────────
# 實測 36 條題材句有 3 條（8.3%）是頁面框架文字，不是報導內容。
# 3017 奇鋐那筆的引文整段都是版面雜訊——**答案碰巧對，但引文不能給使用者看**。
# 更危險的是 Yahoo 側欄的「熱門股」清單：它把一堆不相干的股票名稱堆在一起，
# 任意兩詞都會共現，**等於從後門繞過我們的關係方向要求**。
# Yahoo 佔 779 篇裡的 621 篇，這個後門不堵，整批證據都不可信。
FRAME_NOISE = (
    "加入為 Google 偏好來源", "加入為Google偏好來源", "偏好來源",
    "將 Yahoo 設為", "將Yahoo設為", "設為首選來源",
    "在 Google 上查看更多", "在Google上查看更多",
    "熱門股", "本網站資料僅供參考", "投資有風險", "免責聲明",
    "版權所有", "轉載請註明", "追蹤我們", "訂閱電子報",
    "更多相關新聞", "延伸閱讀", "看更多", "點我下載", "立即下載",
)


def strip_frame_blocks(html: str) -> str:
    """萃取前先剝掉版面區塊（題材六.1）。

    `<article>` 容器裡仍可能包著側欄與推薦區塊，光靠容器不夠。
    這裡再剝一層：導覽、側欄、推薦、頁尾、免責聲明。
    """
    # 2026-09-10 根因修正：原本第二個分支前面又寫了一次 `(?is)`。
    # Python 3.11 起「不在表達式開頭的全域旗標」是**錯誤**不是警告，
    # 這支在 3.12（Actions）／3.13（本機）上**每一次呼叫都拋 re.PatternError**。
    # 而這個呼叫在 fetch_body 的 try/except 之外，例外直接冒到主迴圈，
    # 被算成「這一則抓失敗」，連續 10 則就觸發 MAX_CONSECUTIVE_FAIL 中止整輪，
    # 於是 28eefa9 之後每一輪都萃取 0 則，**外觀跟被限流一模一樣**。
    # 旗標只保留在最前面那一個。
    pat = (r"(?is)<(nav|aside|footer|header)[^>]*>.*?</\1>"
           r"|<div[^>]*class=\"[^\"]*(sidebar|related|recommend|trending|"
           r"hot-?stock|disclaimer|footer|promo)[^\"]*\"[^>]*>.*?</div>")
    prev = None
    out = html
    for _ in range(3):          # 巢狀區塊要多剝幾輪
        prev = out
        out = re.sub(pat, " ", out)
        if out == prev:
            break
    return out


def is_frame_noise(sent: str) -> bool:
    """整句含框架用語一律不採（題材六.2）。"""
    return any(k in sent for k in FRAME_NOISE)


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
        if is_frame_noise(s):
            continue          # 題材六.2：整句含框架用語一律不採
        out.append(s)
    return out


def _publish_diag(todo_total: int, fetched: int, hit_articles: int) -> None:
    """把本輪診斷寫進 news_urls.json 的 meta.extract_diag（總司令指定的位置）。

    只改 meta 這一個 key，其餘（urls 清單、sitemap 那邊寫的欄位）原封不動——
    這支不是 news_urls.json 的擁有者，只是借它的 meta 放診斷。

    這裡自己絕不能拋例外：它是診斷，診斷失敗不該把真正跑成功的一輪弄成失敗。
    """
    src = D / "news_urls.json"
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "meta" not in doc:
            return
        doc["meta"]["extract_diag"] = {
            "at": datetime.now(TZ).isoformat(),
            "max_per_run": MAX_PER_RUN,
            "todo_total": todo_total,
            "attempted": fetched,
            "with_theme_quote": hit_articles,
            "counts": dict(sorted(DIAG.items())),
            "note": "counts 的鍵：HTTP 狀態碼（\"200\"/\"403\"/\"429\"…）、"
                    "exc:<例外類別> 是連線層例外、"
                    "exc:strip_frame_blocks:<例外類別> 是剝版面時的解析例外、"
                    "no_article_container 是拿到 200 但版型比對不到文章容器、"
                    "empty_html 是重試用盡仍無內容。"
                    "四者是完全不同的問題，不要再混成一句「連續失敗」。",
        }
        src.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"  ! 寫入 extract_diag 失敗（{type(e).__name__}: {e}），不影響本輪萃取結果")


def main() -> int:
    # 2026-09-09（題材一.1）**輸入改讀 news_urls.json**（sitemap 收集的 3,537 則），
    # 不再讀 RSS 產出的 news.json。理由：RSS 每次只給 20~50 則最新的，
    # sitemap 一次就有數千則，而且下游原本一則都沒用到——管線是斷的。
    # news.json 仍保留作為標題層證據（build_themes 的 C 級之二）。
    urls_doc = json.loads((D / "news_urls.json").read_text(encoding="utf-8"))
    news = []
    seen_url = set()
    for u in urls_doc.get("urls") or []:
        url = u.get("url")
        # 去重 + 只取白名單內的兩家
        if not url or url in seen_url:
            continue
        if not any(h in url for h in BODY_ALLOWED):
            continue
        seen_url.add(url)
        news.append({"url": url, "source": u.get("source"), "title": "", "published": ""})
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
    consecutive_fail = 0
    for n in todo[:MAX_PER_RUN]:
        url = n["url"]
        try:
            body = fetch_body(url)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {url[:60]} 失敗 {type(e).__name__}")
            consecutive_fail += 1
            if consecutive_fail >= MAX_CONSECUTIVE_FAIL:
                print(f"  連續失敗 {consecutive_fail} 則，判斷是限流或斷網，停止本輪")
                break
            continue
        consecutive_fail = 0 if body else consecutive_fail + 1
        if consecutive_fail >= MAX_CONSECUTIVE_FAIL:
            print(f"  連續 {consecutive_fail} 則取不到內文，停止本輪")
            break
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
    _publish_diag(len(todo), fetched, hit_articles)
    print(f"  本輪診斷 extract_diag：{json.dumps(DIAG, ensure_ascii=False, sort_keys=True)}")
    print(f"  本輪抓取 {fetched} 則，其中 {hit_articles} 則含題材句")
    print(f"  累計 {len(out)} 則，含題材句 {doc['meta']['articles_with_theme_quote']} 則")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
