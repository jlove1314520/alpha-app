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
from pathlib import Path

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

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
]
KEEP_DAYS = 90          # 事件保留 90 天：個股頁只顯示近 30 日，多留一些供研究端用
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
            events.append({"code": code, "name": clean(r.get("公司名稱")), "date": d,
                           "type": classify(subj, clean(r.get("符合條款"))),
                           "title": subj[:120], "source": "TWSE 重大訊息",
                           "url": "https://mops.twse.com.tw/mops/web/t05st01"})
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
            events.append({"code": code, "name": clean(r.get("CompanyName")), "date": d,
                           "type": classify(subj, clean(r.get("符合條款"))),
                           "title": subj[:120], "source": "TPEx 重大訊息",
                           "url": "https://mops.twse.com.tw/mops/web/t05st01"})
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
            ym = f'{clean(r.get("資料年月"))}'
            title = f"{ym} 月營收公布" + (f"，年增 {yoy_f:.1f}%" if yoy_f is not None else "")
            events.append({"code": code, "name": clean(r.get("公司名稱")), "date": d,
                           "type": "月營收", "title": title, "source": "TWSE 月營收",
                           "url": "https://mops.twse.com.tw/mops/web/t21sc03",
                           "yoy_pct": yoy_f})
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
                             "source": name, "codes": codes})
                n += 1
            meta[name] = {"ok": True, "items": len(items), "kept": n}
        except Exception as e:  # noqa: BLE001
            meta[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return news, meta


def merge_keep(path: Path, key: str, new_rows: list[dict], id_fn, keep_days=None, cap=None):
    """跟既有檔案合併去重。事件是累積的——每次只抓得到當下快照，不累積就沒有歷史。"""
    old = []
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8")).get(key) or []
        except (OSError, json.JSONDecodeError):
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
    out.sort(key=lambda r: str(r.get("date") or r.get("published") or ""), reverse=True)
    if cap:
        out = out[:cap]
    return out


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
    nw_out = merge_keep(DATA / "news.json", "news", news,
                        lambda r: r.get("url"), cap=NEWS_KEEP)

    (DATA / "events.json").write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "source": "TWSE/TPEx 重大訊息＋TWSE 月營收＋既有除權息檔（全部官方端點）",
        "keep_days": KEEP_DAYS, "meta": ev_meta, "count": len(ev_out), "events": ev_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (DATA / "news.json").write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "source": "中央社財經 RSS＋Yahoo股市 RSS（只存索引不存全文）",
        "not_used": {"鉅亨網": "公開 RSS 兩個路徑皆 404，唯一可通的是站台後端 API，"
                              "依 CLAUDE.md 取得方式鐵律不採用"},
        "meta": nw_meta, "count": len(nw_out), "news": nw_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

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
