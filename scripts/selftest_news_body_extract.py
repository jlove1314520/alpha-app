"""自測：新聞內文題材句萃取 `.github/scripts/news_body_extract.py`（先.一三五-1co）。

`D`／`OUT` 換成暫存目錄、`requests.get` 換成假函式（零外部請求）、節流間隔設 0、
公司名冊（news_matcher.load_company_names／load_active_codes）換成固定小名冊，不讀也不動真實 data/。
題材頁的內文句全靠它，這裡確認：句型明確才收題材句（同句共現不夠）、只存那一句、版面雜訊句不收、
抓失敗只記 extract_diag 不中斷、連續失敗達上限停止本輪、已萃取的不重抓、白名單外不抓、
輸入讀不出來不寫空檔也不拋未處理例外、既有輸出損壞不從空白重建覆蓋。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("news_body_extract", ROOT / ".github" / "scripts" / "news_body_extract.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)  # 會把 .github/scripts 放進 sys.path
import news_matcher as NM  # noqa: E402

M.REQ_INTERVAL = 0.0
M.RETRY_BACKOFF = 0.0
M.PATTERNS = ["打入{theme}供應鏈", "{theme}概念股"]
NM.load_company_names = lambda: ({"台積電": "2330", "奇鋐": "3017"}, set())
NM.load_active_codes = lambda: {"2330", "3017"}

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class _Resp:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code = status
        self.text = text


class FakeRequests:
    """依網址回固定頁面；記錄每個被請求的網址。"""

    def __init__(self, pages: dict) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url, timeout=None, headers=None):  # noqa: ARG002
        self.calls.append(url)
        v = self.pages.get(url, 404)
        if isinstance(v, Exception):
            raise v
        if isinstance(v, int):
            return _Resp(v)
        return _Resp(200, v)


def article(*paras: str, extra: str = "") -> str:
    ps = "".join(f"<p>{p}</p>" for p in paras)
    return f"<html><body><nav><p>熱門股 台積電打入CoWoS供應鏈</p></nav><article>{ps}{extra}</article></body></html>"


Y = "https://tw.stock.yahoo.com/news/"
C = "https://www.cna.com.tw/news/afe/"


def setup(d: Path, urls: list | None, kw=True) -> None:
    (d / "seed").mkdir(parents=True, exist_ok=True)
    if kw:
        (d / "seed" / "theme_keywords.json").write_text(json.dumps({
            "themes": {"adv_package": {"keywords": ["CoWoS", "先進封裝"]}, "cooling": {"keywords": ["散熱"]}},
            "sentence_patterns": {"patterns": ["打入{theme}供應鏈", "{theme}概念股"]},
        }, ensure_ascii=False), encoding="utf-8")
    if urls is not None:
        (d / "news_urls.json").write_text(json.dumps({"meta": {"source": "sitemap"}, "urls": urls}, ensure_ascii=False), encoding="utf-8")


def run(d: Path, fake: FakeRequests):
    M.D = d
    M.ROOT = d  # 收尾印 OUT.relative_to(ROOT) 用
    M.OUT = d / "news_evidence.json"
    M.requests = fake
    M.DIAG.clear()
    M._last[0] = 0.0
    try:
        return M.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：題材句萃取＋失敗只記診斷＋白名單外不抓＋已萃取不重抓")
    d1 = base / "d1"
    u_hit, u_cooc, u_fail, u_exc, u_nocont, u_udn, u_prior = (
        Y + "a-1.html", Y + "b-2.html", C + "202610300001.aspx", C + "202610300002.aspx",
        Y + "c-3.html", "https://money.udn.com/money/story/1/2", Y + "old-0.html")
    setup(d1, [{"url": u, "source": "x"} for u in (u_hit, u_cooc, u_fail, u_exc, u_nocont, u_udn, u_prior, u_hit)])
    (d1 / "news_evidence.json").write_text(json.dumps({"meta": {}, "evidence": [
        {"url": u_prior, "quotes": [], "note": "上一輪已抓"}]}, ensure_ascii=False), encoding="utf-8")
    long_tail = "，".join(["後續營運展望樂觀"] * 30)
    fake = FakeRequests({
        u_hit: article("台積電先進封裝產能擴充。奇鋐打入CoWoS供應鏈，市場關注。" + long_tail,
                       "加入為 Google 偏好來源，奇鋐打入CoWoS供應鏈"),
        u_cooc: article("台積電與CoWoS產能同步提升，法人看好。"),  # 同句共現但沒有句型 → 不收
        u_fail: 500,
        u_exc: ConnectionError("斷線"),
        u_nocont: "<html><body><div>沒有文章容器</div></body></html>",
    })
    rc, err = run(d1, fake)
    check("正常結束 rc=0", rc == 0 and err is None, (rc, err))
    doc = json.loads((d1 / "news_evidence.json").read_text(encoding="utf-8"))
    ev = {e["url"]: e for e in doc["evidence"]}
    check("白名單外（UDN）沒有送請求", u_udn not in fake.calls, fake.calls)
    check("已萃取的不重抓（上一輪的網址沒送請求、紀錄保留）", u_prior not in fake.calls and ev.get(u_prior, {}).get("note") == "上一輪已抓")
    check("重複網址只抓一次", fake.calls.count(u_hit) == 1, fake.calls.count(u_hit))
    q = ev.get(u_hit, {}).get("quotes", [])
    check("句型明確才收：奇鋐打入CoWoS供應鏈 → adv_package、代號 3017", len(q) == 1 and q[0]["theme_id"] == "adv_package" and q[0]["codes"] == ["3017"], q)
    check("只存命中那一句（不含全文、≤ SENT_MAX）", q and "後續營運展望" not in q[0]["quote"] and len(q[0]["quote"]) <= M.SENT_MAX, q)
    check("nav 裡的熱門股文字、版面雜訊句不收", all("偏好來源" not in x["quote"] and "熱門股" not in x["quote"] for x in q), q)
    check("同句共現但沒有句型 → 不收題材句", ev.get(u_cooc, {}).get("quotes") == [], ev.get(u_cooc))
    check("HTTP 500 抓不到 → 記「內文取得為空」不中斷", ev.get(u_fail, {}).get("note") == "內文取得為空", ev.get(u_fail))
    check("連線例外 → 記「內文取得為空」不中斷", ev.get(u_exc, {}).get("note") == "內文取得為空", ev.get(u_exc))
    check("HTTP 500 有重試（首次＋MAX_RETRY）", fake.calls.count(u_fail) == M.MAX_RETRY + 1, fake.calls.count(u_fail))
    urls_doc = json.loads((d1 / "news_urls.json").read_text(encoding="utf-8"))
    diag = urls_doc.get("meta", {}).get("extract_diag", {})
    cnt = diag.get("counts", {})
    check("extract_diag 分別記 500／連線例外／找不到容器", cnt.get("500") == 3 and cnt.get("exc:ConnectionError") == 3 and cnt.get("no_article_container") == 1, cnt)
    check("extract_diag attempted＝5、with_theme_quote＝1", diag.get("attempted") == 5 and diag.get("with_theme_quote") == 1, diag)
    check("news_urls.json 其他欄位原封不動", urls_doc.get("meta", {}).get("source") == "sitemap" and len(urls_doc.get("urls", [])) == 8)
    check("meta 計數：累計 6 則、含題材句 1 則", doc["meta"]["articles_total"] == 6 and doc["meta"]["articles_with_theme_quote"] == 1, doc["meta"])

    print("情境二：連續 404 達上限 → 停止本輪、已抓的照寫")
    d2 = base / "d2"
    many = [{"url": Y + f"x-{i}.html"} for i in range(M.MAX_CONSECUTIVE_FAIL + 5)]
    setup(d2, many)
    fake2 = FakeRequests({})
    rc, err = run(d2, fake2)
    check("連續失敗 rc=0 不拋例外", rc == 0 and err is None, (rc, err))
    check(f"送出 {M.MAX_CONSECUTIVE_FAIL} 次請求後停止（404 不重試）", len(fake2.calls) == M.MAX_CONSECUTIVE_FAIL, len(fake2.calls))

    print("情境三：月營收公告類排到最後")
    todo, low = M.prioritize([{"url": Y + "公告-台積電9月合併營收-1.html"}, {"url": Y + "台積電擴產-2.html"}])
    check("月營收公告降優先", low == 1 and todo[0]["url"].endswith("擴產-2.html"), todo)

    sentinel = '{"meta":{},"evidence":[{"url":"keep"}]}'

    print("情境四：news_urls.json 不存在 → 不拋未處理例外、不覆寫既有輸出")
    d4 = base / "d4"
    setup(d4, None)
    (d4 / "news_evidence.json").write_text(sentinel, encoding="utf-8")
    rc, err = run(d4, FakeRequests({}))
    check("缺 news_urls.json rc≠0 且沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("缺 news_urls.json 時既有輸出不動", (d4 / "news_evidence.json").read_text(encoding="utf-8") == sentinel)

    print("情境五：news_urls.json 損壞 → 同上")
    d5 = base / "d5"
    setup(d5, [])
    (d5 / "news_urls.json").write_text("<<<<<<< HEAD\n{", encoding="utf-8")
    (d5 / "news_evidence.json").write_text(sentinel, encoding="utf-8")
    rc, err = run(d5, FakeRequests({}))
    check("損壞 news_urls.json rc≠0 且沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("損壞 news_urls.json 時既有輸出不動", (d5 / "news_evidence.json").read_text(encoding="utf-8") == sentinel)

    print("情境六：題材規則檔不存在 → 同上、且不送任何請求")
    d6 = base / "d6"
    setup(d6, [{"url": u_hit}], kw=False)
    (d6 / "news_evidence.json").write_text(sentinel, encoding="utf-8")
    fake6 = FakeRequests({u_hit: article("奇鋐打入CoWoS供應鏈。")})
    rc, err = run(d6, fake6)
    check("缺題材規則檔 rc≠0 且沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("缺題材規則檔時既有輸出不動、零請求", (d6 / "news_evidence.json").read_text(encoding="utf-8") == sentinel and not fake6.calls, fake6.calls)

    print("情境七：既有輸出損壞 → 拒絕從空白重建覆蓋")
    d7 = base / "d7"
    setup(d7, [{"url": u_hit}])
    (d7 / "news_evidence.json").write_text("{壞掉", encoding="utf-8")
    rc, err = run(d7, FakeRequests({u_hit: article("奇鋐打入CoWoS供應鏈。")}))
    check("既有輸出損壞 rc≠0 且沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("既有輸出損壞時檔案不動", (d7 / "news_evidence.json").read_text(encoding="utf-8") == "{壞掉")

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
