# -*- coding: utf-8 -*-
"""新聞與事件管線 → `data/news.json`／`data/events.json`（2026-09-08 建置一.1）。

**這支存在的理由**：個股頁的「題材判斷」卡從 9/5 起就寫著「本輪尚未實作」。
總司令看到兩次，並明確裁示「要的是把功能做出來，不是刪字」。這支就是那個功能的資料層。

**只存索引，不存全文**（總司令指定）：標題、連結、時間、標的、類型。
理由有兩個——全文有著作權疑慮，而且 repo 是公開的；再者我們要的是「這檔最近發生
什麼事」，點進去看原文才是正確的閱讀路徑。

## 資料源與查證紀錄（依 CLAUDE.md 三來源查證紀律）

事件（官方，全部實測 200）：
- TWSE 重大訊息 `openapi.twse.com.tw/v1/opendata/t187ap04_L`
- TPEx 重大訊息 `www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O`
- TWSE 月營收 `openapi.twse.com.tw/v1/opendata/t187ap05_L`
- 除權息：沿用既有 `data/ex_dividend_events.json`（由既有排程產生）

新聞（RSS）：
- 中央社財經 `feeds.feedburner.com/rsscna/finance` — 實測 200
- Yahoo 台股 `tw.stock.yahoo.com/rss?category=news` — 實測 200
- **鉅亨網：不採用**。查證三個路徑：`news.cnyes.com/rss/news/cat/tw_stock` 404、
  `news.cnyes.com/rss` 404、`api.cnyes.com/media/api/v1/newslist/...` 200。
  唯一能通的是**站台後端 API**，不是公開 RSS 或有文件的公開 API。
  依 CLAUDE.md「取得方式鐵律」——不撈任何 App／站台後端——**不採用**。
  若日後鉅亨恢復公開 RSS 或提供正式 API，再加回來。

用法：python .github/scripts/fetch_news_events.py
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_importance import VERSION as IMPORTANCE_VERSION, event_importance, news_importance  # noqa: E402  先.一一〇-9

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaNewsEvents/1.0)"}

TWSE_MOPS = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_MOPS = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
TWSE_REVENUE = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
RSS_FEEDS = [
    ("中央社財經", "https://feeds.feedburner.com/rsscna/finance"),
    ("Yahoo股市", "https://tw.stock.yahoo.com/rss?category=news"),
    # 2026-09-08（題材萃取二）新增經濟日報三個分類。查證紀錄：
    #   robots.txt 對 `User-agent: *` **零條 Disallow**（實測），
    #   且 udn 主動提供 RSS 訂閱服務。
    #   **但其著作權聲明比中央社/Yahoo 嚴格**：「除法令另有規定或事前經
    #   聯合線上所屬網站之經營單位授權外，使用者不得擅自以下載、轉貼或
    #   以他法重製聯合線上所屬網站的內容。」
    #   我們的用法是**只存索引（標題／連結／日期）＋萃取事實**，
    #   不重製全文；引用原句時只存必要的一句並附出處，
    #   依總司令 2026-09-08 裁示「事實不受著作權保護、只存必要的一句、不轉載全文」。
    #   完整條款紀錄見 docs/DATA_SOURCE_MAP.md。
    ("經濟日報證券", "https://money.udn.com/rssfeed/news/1001/5590?ch=money"),
    ("經濟日報產業", "https://money.udn.com/rssfeed/news/1001/5591?ch=money"),
    ("經濟日報焦點", "https://money.udn.com/rssfeed/news/1001/5588?ch=money"),
]
KEEP_DAYS = 90          # 事件保留 90 天：個股頁只顯示近 30 日，多留一些供研究端用
NEWS_STALE_DAYS = 2     # 先.一〇四-1：最新一則超過 2 天就黃色警告
# 先.一〇五-3（2026-10-16）：兩個檔的分工——
#   data/news.json           首頁／搜尋用的「最新新聞小檔」：只留最近 NEWS_KEEP 則，且整檔 ≤ NEWS_MAX_BYTES（約 150KB），一打開 App 就下載。
#   data/news_by_code/<代號>.json  個股頁與「近 7 天」計數用的「存檔」：只收有標到個股的新聞，每檔保留最近 NEWS_ARCHIVE_DAYS 天，
#                            點進個股頁才下載那一檔；_index.json 記每檔近 7 天／14 天則數。
#   news.json 只留約 2 天份（RSS 一班 200 則左右），個股頁要看 2 週內新聞就讀存檔，不再受首頁小檔的則數上限影響。
NEWS_MAX_BYTES = 150_000
NEWS_ARCHIVE_DAYS = 14
NEWS_ARCHIVE_DIR = DATA / "news_by_code"
NEWS_KEEP = 300         # 新聞只留最近 300 則，避免檔案無限長大


class _StrictOffAdapter(HTTPAdapter):
    """TPEx 的中介 CA 沒有 Subject Key Identifier，Python 3.13 的嚴格檢查會擋。
    只關掉那一項擴充檢查，憑證鏈與主機名驗證照常（詳見 scripts/data_audit.py）。"""

    def init_poolmanager(self, *a, **kw):
        ctx = create_urllib3_context()
        ctx.load_verify_locations(certifi.where())
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kw["ssl_context"] = ctx
        return super().init_poolmanager(*a, **kw)


def session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _StrictOffAdapter())
    s.headers.update(UA)
    return s


def roc_to_iso(v: str) -> str | None:
    """民國日期字串轉 ISO。抓不出來就回 None，不猜。"""
    t = re.sub(r"\D", "", str(v or ""))
    if len(t) == 7:
        return f"{int(t[:3]) + 1911:04d}-{t[3:5]}-{t[5:7]}"
    if len(t) == 8 and t[:4].isdigit() and 1990 <= int(t[:4]) <= 2100:
        return f"{t[:4]}-{t[4:6]}-{t[6:8]}"
    return None


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def classify(subject: str, clause: str) -> str:
    """把重大訊息分類。分類是「題材判斷」卡分群顯示的依據。

    刻意用關鍵字而不是條款號：條款號會改版，而且同一條款底下的實際內容差很多。
    分不出來就回「其他」——**不硬塞一個看起來合理的分類**。
    """
    t = subject + " " + clause
    rules = [
        ("法說會", r"法人說明會|法說"),
        ("併購", r"併購|合併|收購|受讓|股份轉換"),
        ("增減資", r"現金增資|減資|私募|可轉換公司債|轉換價"),
        ("重大訂單", r"接單|訂單|得標|簽約|合作備忘"),
        ("人事", r"董事|監察人|經理人|總經理|董事長|辭任|解任"),
        ("財務", r"財務報告|財報|自結|營運報告"),
        ("訴訟", r"訴訟|假扣押|裁定|判決"),
        ("處分資產", r"取得或處分|處分資產|不動產"),
        ("停復牌", r"停止買賣|恢復買賣|變更交易|處置"),
    ]
    for name, pat in rules:
        if re.search(pat, t):
            return name
    return "其他"


def _valid_date(y: int, m: int, d: int) -> str | None:
    try:
        return datetime(y, m, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def call_date_of(announce: str, title: str, desc: str = "", fact_date: str = "", clause: str = "") -> tuple[str | None, str | None]:
    """法說會舉行日（先.一〇三-4）。回 (YYYY-MM-DD, 依據)；抓不到回 (None, None)，不猜。

    依序：①重大訊息「說明」欄的「召開法人說明會之日期：115/10/28」（官方制式欄位）
    ②符合條款＝第12款（法說會條款）時的「事實發生日」③主旨裡寫的日期（西元／民國／只寫月日）。
    只寫月日的，年份取公告年；推出來比公告日早 30 天以上就算明年。與公告日差超過 180 天的視為不是舉行日，丟掉。
    """
    try:
        ann = datetime.fromisoformat(str(announce)[:10])
    except (TypeError, ValueError):
        return None, None

    def ok(iso):
        if not iso:
            return None
        dd = (datetime.fromisoformat(iso) - ann).days
        return iso if -180 <= dd <= 180 else None

    m = re.search(r"召開法人說明會之日期\s*[:：]\s*(\d{2,4})\s*[/／.-]\s*(\d{1,2})\s*[/／.-]\s*(\d{1,2})", desc or "")
    if m:
        y = int(m.group(1))
        iso = ok(_valid_date(y + 1911 if y < 1000 else y, int(m.group(2)), int(m.group(3))))
        if iso:
            return iso, "重大訊息說明欄「召開法人說明會之日期」"
    if re.search(r"第\s*12\s*款", clause or ""):
        iso = ok(roc_to_iso(fact_date))
        if iso:
            return iso, "重大訊息事實發生日（第12款）"
    t = title or ""
    m = re.search(r"(\d{2,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", t)
    if m:
        y = int(m.group(1))
        iso = ok(_valid_date(y + 1911 if y < 1000 else y, int(m.group(2)), int(m.group(3))))
        if iso:
            return iso, "重大訊息主旨"
    m = re.search(r"(?<![\d年])(\d{1,2})\s*月\s*(\d{1,2})\s*日", t)
    if m:
        iso = _valid_date(ann.year, int(m.group(1)), int(m.group(2)))
        if iso and (datetime.fromisoformat(iso) - ann).days < -30:
            iso = _valid_date(ann.year + 1, int(m.group(1)), int(m.group(2)))
        iso = ok(iso)
        if iso:
            return iso, "重大訊息主旨（只寫月日，年份依公告日推）"
    return None, None


def ym_label(ym: str) -> tuple[str | None, str | None]:
    """月營收資料年月（民國 11509 或西元 202609）→ ("2026-09", "9 月營收")。解析不了回 (None, None)。"""
    t = re.sub(r"\D", "", str(ym or ""))
    y = mo = None
    if len(t) == 5:
        y, mo = int(t[:3]) + 1911, int(t[3:])
    elif len(t) == 6 and t.startswith(("19", "20")):
        y, mo = int(t[:4]), int(t[4:])
    if not y or not (1 <= mo <= 12):
        return None, None
    return f"{y:04d}-{mo:02d}", f"{mo} 月營收"


def normalize_revenue_events(rows: list[dict]) -> list[dict]:
    """先.一〇三-4：月營收事件以「代號＋資料年月」去重。

    TWSE openapi t187ap05_L 是「當下最新一個月」的全市場彙總表，沒有公告日欄位；每天重抓同一個月會用新的
    出表日期再記一筆，同一家同一個月最多累積 7 筆。這裡每組只留**最早**那筆的日期——那是我們第一次在官方
    彙總表看到它的日子，實際公告日不晚於此日（官方未提供逐家公告日，MOPS 網頁不開放程式抓取，不爬）。
    舊列標題「11509 月營收公布」一併改成「9 月營收公布」。非月營收列原樣保留、順序不動。
    """
    groups: dict[tuple, dict] = {}
    out: list = []
    for r in rows:
        if r.get("type") != "月營收":
            out.append(r)
            continue
        ym_iso = r.get("data_ym")
        if ym_iso:
            label = f"{int(str(ym_iso)[5:7])} 月營收"
        else:
            m = re.match(r"\s*(\d{5,6})\s*月營收", str(r.get("title") or ""))
            ym_iso, label = ym_label(m.group(1)) if m else (None, None)
        if not ym_iso:
            out.append(r)  # 解析不了的不硬併，原樣保留
            continue
        key = (r.get("code"), ym_iso)
        cur = groups.get(key)
        if cur is None or str(r.get("date") or "") < str(cur.get("date") or ""):
            nr = dict(r)
            nr["data_ym"] = ym_iso
            nr["title"] = re.sub(r"^\s*\d{5,6}\s*月營收", label, str(r.get("title") or ""))
            nr["date_basis"] = "首次出現在 TWSE 月營收彙總表的日期（官方未提供逐家公告日；實際公告日不晚於此日）"
            if cur is None:
                out.append(key)  # 佔位：這一組放在第一次出現的位置
            groups[key] = nr
    return [groups[x] if isinstance(x, tuple) else x for x in out]


def finalize_events(rows: list[dict]) -> list[dict]:
    """先.一〇三-4：合併後收尾——月營收去重；舊法說會列（當時沒存說明欄）用主旨補舉行日。"""
    rows = normalize_revenue_events(rows)
    for r in rows:
        if r.get("type") == "法說會" and not r.get("call_date"):
            cd, basis = call_date_of(str(r.get("date") or ""), str(r.get("title") or ""))
            if cd:
                r["call_date"], r["call_date_basis"] = cd, basis
    return rows


def fetch_events(s: requests.Session) -> tuple[list[dict], dict]:
    events, meta = [], {}

    # ── 重大訊息（上市）──────────────────────────────────────────────
    try:
        rows = s.get(TWSE_MOPS, timeout=60).json()
        n = 0
        for r in rows:
            code = clean(r.get("公司代號"))
            d = roc_to_iso(r.get("發言日期"))
            subj = clean(r.get("主旨 ") or r.get("主旨"))
            if not (code and d and subj):
                continue
            ev = {"code": code, "name": clean(r.get("公司名稱")), "date": d,
                  "type": classify(subj, clean(r.get("符合條款"))),
                  "title": subj[:120], "source": "TWSE 重大訊息",
                  "url": "https://mops.twse.com.tw/mops/web/t05st01"}
            if ev["type"] == "法說會":  # 先.一〇三-4：另存舉行日（date 仍是公告日）
                cd, basis = call_date_of(d, subj, r.get("說明") or "", r.get("事實發生日") or "", r.get("符合條款") or "")
                if cd:
                    ev["call_date"], ev["call_date_basis"] = cd, basis
            events.append(ev)
            n += 1
        meta["twse_mops"] = {"ok": True, "rows": len(rows), "kept": n}
    except Exception as e:  # noqa: BLE001
        meta["twse_mops"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ── 重大訊息（上櫃）──────────────────────────────────────────────
    try:
        rows = s.get(TPEX_MOPS, timeout=60).json()
        n = 0
        for r in rows:
            code = clean(r.get("SecuritiesCompanyCode"))
            d = roc_to_iso(r.get("發言日期"))
            subj = clean(r.get("主旨"))
            if not (code and d and subj):
                continue
            ev = {"code": code, "name": clean(r.get("CompanyName")), "date": d,
                  "type": classify(subj, clean(r.get("符合條款"))),
                  "title": subj[:120], "source": "TPEx 重大訊息",
                  "url": "https://mops.twse.com.tw/mops/web/t05st01"}
            if ev["type"] == "法說會":  # 先.一〇三-4：另存舉行日（date 仍是公告日）
                cd, basis = call_date_of(d, subj, r.get("說明") or "", r.get("事實發生日") or "", r.get("符合條款") or "")
                if cd:
                    ev["call_date"], ev["call_date_basis"] = cd, basis
            events.append(ev)
            n += 1
        meta["tpex_mops"] = {"ok": True, "rows": len(rows), "kept": n}
    except Exception as e:  # noqa: BLE001
        meta["tpex_mops"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ── 月營收公布 ──────────────────────────────────────────────────
    try:
        rows = s.get(TWSE_REVENUE, timeout=60).json()
        n = 0
        for r in rows:
            code = clean(r.get("公司代號"))
            d = roc_to_iso(r.get("出表日期"))
            if not (code and d):
                continue
            yoy = r.get("營業收入-去年同月增減(%)")
            try:
                yoy_f = float(str(yoy).replace(",", ""))
            except (TypeError, ValueError):
                yoy_f = None
            # 先.一〇三-4：標題寫「9 月營收」不寫民國「11509」；資料年月另存 data_ym（2026-09），去重靠它
            ym_iso, label = ym_label(clean(r.get("資料年月")))
            if not ym_iso:
                continue
            title = f"{label}公布" + (f"，年增 {yoy_f:.1f}%" if yoy_f is not None else "")
            events.append({"code": code, "name": clean(r.get("公司名稱")), "date": d,
                           "type": "月營收", "title": title, "source": "TWSE 月營收",
                           "url": "https://mops.twse.com.tw/mops/web/t21sc03",
                           "yoy_pct": yoy_f, "data_ym": ym_iso})
            n += 1
        meta["twse_revenue"] = {"ok": True, "rows": len(rows), "kept": n}
    except Exception as e:  # noqa: BLE001
        meta["twse_revenue"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ── 除權息（沿用既有排程產生的檔案，不重抓）───────────────────────
    try:
        d = json.loads((DATA / "ex_dividend_events.json").read_text(encoding="utf-8"))
        n = 0
        # 這個檔的結構是 {events: {股票代號: [該檔的除權息紀錄, ...]}}，不是事件陣列。
        # 第一版寫成陣列走訪，直接吃到 AttributeError——照著欄位名猜結構會踩到這種事，
        # 先印出來看再寫比較快。
        for code, recs in (d.get("events") or {}).items():
            code = clean(code)
            for e in (recs if isinstance(recs, list) else [recs]):
                if not isinstance(e, dict):
                    continue
                dt = clean(e.get("ex_date"))
                if not (code and dt):
                    continue
                cash, stock = e.get("cash") or 0, e.get("stock_ratio") or 0
                bits = []
                if cash:
                    bits.append(f"現金 {cash:.4g} 元")
                if stock:
                    bits.append(f"股票 {stock:.4g}")
                title = ("除權息交易日" + ("（" + "、".join(bits) + "）" if bits else ""))
                events.append({"code": code, "name": "", "date": dt,
                               "type": "除權息", "title": title,
                               "source": "TWSE 除權息",
                               "url": "https://www.twse.com.tw/zh/exchangeReport/twt48u"})
                n += 1
        meta["ex_dividend"] = {"ok": True, "kept": n, "note": "沿用既有排程產物，未額外請求"}
    except Exception as e:  # noqa: BLE001
        meta["ex_dividend"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return events, meta


CODE_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


# 2026-09-08（題材萃取一.1）精確比對器，取代原本的「標題四位數」規則。
try:
    from news_matcher import (load_company_names as _load_names,
                              match_article as _match_article)
    _NAME2CODE, _AMBIGUOUS = _load_names()
except Exception as _e:  # noqa: BLE001
    # 比對器載入失敗時退回「不標記」，**不要退回舊的錯誤規則**——
    # 舊規則的精確率只有 1/6，退回去等於刻意產生錯誤資料。
    print(f"! news_matcher 載入失敗（{type(_e).__name__}），本輪不標記個股")
    _NAME2CODE, _AMBIGUOUS = {}, set()
    def _match_article(t, b, n, a):  # noqa: ANN001
        return {"codes": [], "by_number": [], "by_name": []}


def fetch_news(s: requests.Session, known_codes: set[str]) -> tuple[list[dict], dict]:
    """RSS 新聞。標的用「標題裡出現的 4 位數代號」比對，比對不到就留空。

    刻意不做公司名稱模糊比對：中文公司名跟一般詞彙撞得很兇（「台塑」「大成」
    「聯合」都會誤判），寧可少標也不要標錯——標錯的個股新聞比沒有新聞更糟。
    """
    news, meta = [], {}
    for name, url in RSS_FEEDS:
        try:
            r = s.get(url, timeout=45)
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            n = 0
            for it in items:
                title = clean(it.findtext("title"))
                link = clean(it.findtext("link"))
                pub = clean(it.findtext("pubDate"))
                if not (title and link):
                    continue
                # 2026-09-08（題材萃取一.1）改用精確比對器。
                # 舊寫法只認標題裡的四位數，實測 179 則標到 6 筆、**其中 5 筆是錯的**
                # （2505元被當成國揚、2030年/2023年被當成彰源/燁輝）。
                # 新規則：四位數後不得接單位字＋官方名稱精確比對＋歧義排除，
                # 實測標到 21 則、23 個 (股票,新聞) 組合，且假陽性由規則擋掉。
                m = _match_article(title, "", _NAME2CODE, known_codes)
                codes = m["codes"]
                news.append({"title": title[:140], "url": link, "published": pub,
                             "published_iso": published_iso(pub),
                             "source": name, "codes": codes})
                n += 1
            meta[name] = {"ok": True, "items": len(items), "kept": n}
        except Exception as e:  # noqa: BLE001
            meta[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return news, meta


def published_iso(pub) -> str | None:
    """RSS pubDate（RFC 822，例 'Wed, 30 Sep 2026 23:59:56 GMT'）→ 台北時間 ISO 字串；解析不了回 None。

    先.一〇四-1（2026-10-16）：原本直接拿 pubDate 字串排序，開頭是星期幾，'Wed' 永遠排在 'Thu'／'Tue' 前面，
    加上只留 300 則，10/01～10/15 的新聞一進來就被擠掉，news.json 停在 9/30。
    """
    if not pub:
        return None
    try:
        dt = parsedate_to_datetime(str(pub))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ).isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def _sort_key(r: dict) -> str:
    """排序用時間：published_iso → 補算 published → date（事件用的 YYYY-MM-DD）。都是可直接比大小的 ISO 字串。"""
    if r.get("published_iso"):
        return str(r["published_iso"])
    iso = published_iso(r.get("published"))
    if iso:
        return iso
    return str(r.get("date") or "")


def merge_keep(path: Path, key: str, new_rows: list[dict], id_fn, keep_days=None, cap=None):
    """跟既有檔案合併去重。事件是累積的——每次只抓得到當下快照，不累積就沒有歷史。"""
    old = []
    if path.exists():
        # 2026-10-13 修：既有檔存在卻讀不出（例如 rebase 衝突標記）時，不得當成「沒有歷史」從空白重建再覆蓋——那會把累積的歷史整個洗掉（10-13 05:12 實際發生：events 12,819→1,055、news_urls 40,918→2,636）。改為中止、不寫檔。
        try:
            old = json.loads(path.read_text(encoding="utf-8")).get(key) or []
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path.name} 存在但不是合法 JSON（{e}），拒絕從空白重建覆蓋累積歷史；本輪不寫檔")
        except OSError:
            old = []
    seen, out = set(), []
    for r in new_rows + old:          # 新的優先
        i = id_fn(r)
        if i in seen:
            continue
        seen.add(i)
        out.append(r)
    if keep_days:
        cutoff = (datetime.now(TZ) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        out = [r for r in out if str(r.get("date", "")) >= cutoff]
    # 先.一〇四-1：舊列沒有 published_iso 的順手補上，排序一律用可比大小的 ISO 時間
    for r in out:
        if r.get("published") and not r.get("published_iso"):
            iso = published_iso(r.get("published"))
            if iso:
                r["published_iso"] = iso
    out.sort(key=_sort_key, reverse=True)
    if cap:
        out = out[:cap]
    return out


def archive_news_by_code(news: list[dict], now: datetime) -> None:
    """先.一〇五-3：把有標到個股的新聞併進 data/news_by_code/<代號>.json（每檔保留最近 NEWS_ARCHIVE_DAYS 天、依網址去重、新到舊），
    並重寫 _index.json（每檔近 7 天／14 天則數）。零額外請求，只用這一班已抓到的新聞＋既有存檔。"""
    NEWS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = (now - timedelta(days=NEWS_ARCHIVE_DAYS)).isoformat()
    by_code: dict[str, list[dict]] = {}
    for n in news:
        for c in n.get("codes") or []:
            by_code.setdefault(str(c), []).append(n)
    touched = set()
    for code, rows in by_code.items():
        if not re.fullmatch(r"[0-9A-Za-z]{2,10}", code):
            continue
        p = NEWS_ARCHIVE_DIR / f"{code}.json"
        old = []
        if p.exists():
            try:
                old = json.loads(p.read_text(encoding="utf-8")).get("news") or []
            except json.JSONDecodeError:
                old = []
        seen, merged = set(), []
        for r in rows + old:
            u = r.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            merged.append({"title": r.get("title"), "url": u, "source": r.get("source"),
                           "published_iso": r.get("published_iso") or published_iso(r.get("published")),
                           # 先.一一〇-9：存檔裡每則都有點名這檔，代號加分一定成立
                           "importance": news_importance({"title": r.get("title"), "codes": [code]})})
        merged = [r for r in merged if (r.get("published_iso") or "") >= cutoff]
        merged.sort(key=lambda r: r.get("published_iso") or "", reverse=True)
        doc = {"code": code, "keep_days": NEWS_ARCHIVE_DAYS, "updated_at": now.isoformat(), "news": merged}
        txt = json.dumps(doc, ensure_ascii=False, indent=1)
        if not p.exists() or p.read_text(encoding="utf-8") != txt:
            p.write_text(txt, encoding="utf-8")
        touched.add(code)
    # 索引：掃全部存檔（含這班沒新新聞的），過期的列順便清掉，空檔刪除
    idx = {}
    c7 = (now - timedelta(days=7)).isoformat()
    for p in sorted(NEWS_ARCHIVE_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows = [r for r in d.get("news") or [] if (r.get("published_iso") or "") >= cutoff]
        if not rows:
            p.unlink()
            continue
        if len(rows) != len(d.get("news") or []):
            d["news"] = rows
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        idx[p.stem] = {"d7": sum(1 for r in rows if (r.get("published_iso") or "") >= c7), "d14": len(rows),
                       "latest": rows[0].get("published_iso")}
    (NEWS_ARCHIVE_DIR / "_index.json").write_text(json.dumps({
        "generated_at": now.isoformat(), "keep_days": NEWS_ARCHIVE_DAYS,
        "note": "個股新聞存檔索引（先.一〇五-3）：d7＝近 7 天則數、d14＝近 14 天則數；只含有標到個股代號的新聞",
        "codes": idx}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"新聞存檔：本班更新 {len(touched)} 檔，存檔共 {len(idx)} 檔（近 {NEWS_ARCHIVE_DAYS} 天）")


def main() -> int:
    s = session()
    now = datetime.now(TZ)

    print("抓事件…")
    events, ev_meta = fetch_events(s)
    for k, v in ev_meta.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")

    known = {e["code"] for e in events}
    try:
        ci = json.loads((DATA / "company_info.json").read_text(encoding="utf-8"))
        known |= set((ci.get("companies") or {}).keys())
    except (OSError, json.JSONDecodeError):
        pass

    print("抓新聞…")
    news, nw_meta = fetch_news(s, known)
    for k, v in nw_meta.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")

    ev_out = merge_keep(DATA / "events.json", "events", events,
                        lambda r: (r.get("code"), r.get("date"), r.get("title")),
                        keep_days=KEEP_DAYS)
    ev_out = finalize_events(ev_out)
    nw_out = merge_keep(DATA / "news.json", "news", news,
                        lambda r: r.get("url"), cap=NEWS_KEEP)
    # 先.一一〇-9：重要度 0～10（權重表 v0 見 news_importance.py）；每班全部重算，舊列也補上
    for e in ev_out:
        e["importance"] = event_importance(e)
    for n in nw_out:
        n["importance"] = news_importance(n)

    (DATA / "events.json").write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "source": "TWSE/TPEx 重大訊息＋TWSE 月營收＋既有除權息檔（全部官方端點）",
        "keep_days": KEEP_DAYS, "importance_version": IMPORTANCE_VERSION,
        "meta": ev_meta, "count": len(ev_out), "events": ev_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 先.一〇四-1 監測：最新一則超過 NEWS_STALE_DAYS 天 → 黃色警告（只標記與印 ::warning::，不擋流程、不中止寫檔）
    newest = _sort_key(nw_out[0]) if nw_out else ""
    stale_warning = None
    try:
        if not newest:
            stale_warning = "news.json 沒有任何可解析時間的新聞"
        else:
            nd = datetime.fromisoformat(newest) if "T" in newest else datetime.fromisoformat(newest + "T00:00:00+08:00")
            age_d = (now - nd).total_seconds() / 86400
            if age_d > NEWS_STALE_DAYS:
                stale_warning = f"最新一則新聞是 {newest[:10]}，已 {age_d:.1f} 天沒有新的新聞"
    except Exception as e:  # noqa: BLE001 -- 十二節：監測自身失敗只警告
        print(f"::warning::新聞新鮮度檢查失敗：{type(e).__name__}: {e}")
    if stale_warning:
        print(f"::warning::{stale_warning}")

    (DATA / "news.json").write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "newest_published_iso": newest or None,
        "stale_warning": stale_warning,
        "source": "中央社財經 RSS＋Yahoo股市 RSS（只存索引不存全文）",
        "not_used": {"鉅亨網": "公開 RSS 兩個路徑皆 404，唯一可通的是站台後端 API，"
                              "依 CLAUDE.md 取得方式鐵律不採用"},
        "importance_version": IMPORTANCE_VERSION,
        "meta": nw_meta, "count": len(nw_out), "news": nw_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 先.一〇五-3：news.json 整檔超過 150KB 就從最舊的開始砍（最新的優先保留）
    try:
        p = DATA / "news.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        while len(p.read_bytes()) > NEWS_MAX_BYTES and len(doc.get("news") or []) > 50:
            doc["news"] = doc["news"][:int(len(doc["news"]) * 0.9)]
            doc["count"] = len(doc["news"])
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        nw_out = doc.get("news") or nw_out
    except Exception as e:  # noqa: BLE001 -- 十二節：瘦身失敗只警告，不影響已寫好的檔
        print(f"::warning::news.json 瘦身失敗：{type(e).__name__}: {e}")
    try:
        archive_news_by_code(nw_out, now)
    except Exception as e:  # noqa: BLE001 -- 十二節：存檔失敗只警告，不影響 news.json／events.json
        print(f"::warning::新聞存檔（news_by_code）失敗：{type(e).__name__}: {e}")

    print(f"\nevents.json {len(ev_out)} 筆（近 {KEEP_DAYS} 天）｜news.json {len(nw_out)} 則")
    by_type: dict[str, int] = {}
    for e in ev_out:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    print("事件類型分佈：" + "、".join(f"{k} {v}" for k, v in sorted(by_type.items(), key=lambda x: -x[1])))
    tagged = sum(1 for n in nw_out if n.get("codes"))
    print(f"新聞有標到個股的：{tagged}/{len(nw_out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
