"""自測：三支雲端抓取程式（先.一三五-1dm／1dn／1do）。

全部把 `requests.get`／`time.sleep`（及 yfinance）換成假的、輸出路徑換暫存，零外部請求，不碰真的 data/。
1dm：`fetch_us_13f_holdings.py` 資訊表解析、同一發行人多列加總、未對映不收、
     抓取失敗沿用上一份（標 stale）、這次一家都沒成功就不覆寫。
1dn：`fetch_news_sitemap.py` sitemap 拆解、中央社分類過濾、回頭補 published、
     既有檔損壞拒絕覆蓋、排程間隔只留 6 筆。
1do：`build_us_screener.py` 季度 frame 名稱、frames 取 end 最新者與失敗只讓市值缺、
     盤中未收盤 K 捨棄、讀不到財報／有收盤不足不覆蓋、正常寫出。只用合成價格，不算任何報酬。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import types
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_us_13f_holdings as F13  # noqa: E402
import fetch_news_sitemap as NS  # noqa: E402
import build_us_screener as SC  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class FakeResp:
    def __init__(self, text="", body=None, status=200):
        self.text, self._body, self.status_code = text, body, status

    def json(self):
        if self._body is None:
            raise ValueError("Expecting value")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        try:
            rv = fn(*a, **k)
        except SystemExit as e:
            rv = ("exit", e.code)
    return rv, buf.getvalue()


F13.time.sleep = lambda *_a, **_k: None  # time 是同一個模組物件，三支都生效
real_get = F13.requests.get
tmp = Path(tempfile.mkdtemp(prefix="selftest_us_misc_"))

# ───────────── 1dm fetch_us_13f_holdings ─────────────
print("1dm fetch_us_13f_holdings.py")
F13.OUT_PATH = tmp / "us_13f_holdings.json"
INFO_XML = """<informationTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>1000</value><shrsOrPrnAmt><sshPrnamt>10</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>Apple Inc</nameOfIssuer><cusip>037833100</cusip><value>500</value><shrsOrPrnAmt><sshPrnamt>5</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>ALPHABET INC</nameOfIssuer><cusip>02079K305</cusip><value>300</value><shrsOrPrnAmt><sshPrnamt>3</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>ALPHABET INC</nameOfIssuer><cusip>02079K107</cusip><value>200</value><shrsOrPrnAmt><sshPrnamt>2</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE HOSPITALITY REIT</nameOfIssuer><cusip>03784Y200</cusip><value>9</value><shrsOrPrnAmt><sshPrnamt>9</sshPrnamt></shrsOrPrnAmt></infoTable>
</informationTable>"""


def make_13f_get(mode="ok"):
    def get(url, params=None, headers=None, timeout=None):
        if "browse-edgar" in url:
            if mode == "list_fail":
                return FakeResp(status=503)
            if mode == "no_filing":
                return FakeResp(text="<feed></feed>")
            return FakeResp(text="<accession-number>0001-26-000001</accession-number><filing-date>2026-08-14</filing-date>")
        if url.endswith("index.json"):
            items = [{"name": "primary_doc.xml"}, {"name": "56757.xml"}]
            if mode == "no_xml":
                items = [{"name": "primary_doc.xml"}]
            return FakeResp(body={"directory": {"item": items}})
        if url.endswith("56757.xml"):
            return FakeResp(text=INFO_XML)
        return FakeResp(status=404)
    return get


rows = F13.parse_infotable(INFO_XML)
check("解析 5 列、value 存原始數字不乘 1000", len(rows) == 5 and rows[0]["value_usd"] == 1000, rows[:1])

F13.requests.get = make_13f_get("ok")
rv, _ = quiet(F13.main)
d = json.loads(F13.OUT_PATH.read_text(encoding="utf-8"))
h = d["filers"]["berkshire_hathaway"]["holdings"]
check("正常回 0", rv == 0, rv)
check("同一發行人多列加總（大小寫不敏感）", h.get("AAPL", {}).get("value_usd") == 1500 and h["AAPL"]["row_count"] == 2, h.get("AAPL"))
check("GOOGL 兩個 CUSIP 都留", sorted(h.get("GOOGL", {}).get("cusips", [])) == ["02079K107", "02079K305"], h.get("GOOGL"))
check("未對映名稱（相似但不同）不收", set(h) == {"AAPL", "GOOGL"}, list(h))
check("正常時沒有 stale 標記", "stale" not in d["filers"]["berkshire_hathaway"])

for mode in ("list_fail", "no_filing", "no_xml"):
    F13.requests.get = make_13f_get(mode)
    before = F13.OUT_PATH.read_text(encoding="utf-8")
    rv, _ = quiet(F13.main)
    check(f"{mode}：一家都沒成功 → 回 1 且不覆寫", rv == 1 and F13.OUT_PATH.read_text(encoding="utf-8") == before, rv)

# 兩家申報人、其中一家失敗 → 失敗那家沿用上一份標 stale
F13.FILERS = {"berkshire_hathaway": {"name": "BRK", "cik": 1067983}, "other": {"name": "X", "cik": 1}}
prev = json.loads(F13.OUT_PATH.read_text(encoding="utf-8"))
prev["filers"]["other"] = {"name": "X", "cik": 1, "holdings": {"MSFT": {"value_usd": 7}}}
F13.OUT_PATH.write_text(json.dumps(prev), encoding="utf-8")
base = make_13f_get("ok")
F13.requests.get = lambda url, params=None, **k: (FakeResp(status=503) if params and params.get("CIK") == "0000000001" else base(url, params))
rv, _ = quiet(F13.main)
d = json.loads(F13.OUT_PATH.read_text(encoding="utf-8"))
check("部分失敗回 0", rv == 0, rv)
check("失敗那家沿用上一份並標 stale", d["filers"].get("other", {}).get("stale") is True and d["filers"]["other"]["holdings"] == {"MSFT": {"value_usd": 7}}, d["filers"].get("other"))
check("錯誤照記", any(e["filer"] == "other" for e in d["errors"]), d["errors"])
F13.OUT_PATH.unlink()
F13.FILERS = {"berkshire_hathaway": {"name": "BRK", "cik": 1067983}}
F13.requests.get = make_13f_get("list_fail")
rv, _ = quiet(F13.main)
check("沒有上一份＋全失敗 → 回 1、不建檔", rv == 1 and not F13.OUT_PATH.exists(), rv)

# ───────────── 1dn fetch_news_sitemap ─────────────
print("1dn fetch_news_sitemap.py")
NS.ROOT = tmp  # 只影響結尾印出的相對路徑
NS.OUT = tmp / "news_urls.json"
CNA_XML = """<urlset>
<url><loc>https://www.cna.com.tw/news/afe/1.aspx</loc><news:publication_date>2026-10-30T09:00:00+08:00</news:publication_date></url>
<url><loc>https://www.cna.com.tw/news/aie/2.aspx</loc><lastmod>2026-10-30T10:00:00+08:00</lastmod></url>
<url><loc>https://www.cna.com.tw/news/aspt/3.aspx</loc><lastmod>2026-10-30T11:00:00+08:00</lastmod></url>
</urlset>"""
YIDX = "<sitemapindex><sitemap><loc>https://tw.stock.yahoo.com/sm-2026-10-30.xml</loc></sitemap></sitemapindex>"
YSUB = "<urlset><loc>https://tw.stock.yahoo.com/news/a.html</loc><loc>https://tw.stock.yahoo.com/news/b.html</loc></urlset>"


def make_ns_get(blocked=False):
    def get(url, timeout=None, headers=None):
        if blocked:
            return FakeResp(status=403)
        if "cna" in url:
            return FakeResp(text=CNA_XML)
        if "index" in url:
            return FakeResp(text=YIDX)
        return FakeResp(text=YSUB)
    return get


e = NS._parse_entries(CNA_XML)
check("<url> 區塊配發布時間（news:publication_date 優先、退 lastmod）",
      e["https://www.cna.com.tw/news/afe/1.aspx"].startswith("2026-10-30T09") and e["https://www.cna.com.tw/news/aie/2.aspx"].startswith("2026-10-30T10"), e)
e2 = NS._parse_entries(YSUB)
check("無 <url> 包裝退回逐個 loc（時間為 None）", len(e2) == 2 and all(v is None for v in e2.values()), e2)

NS.requests.get = make_ns_get()
prior_rec = {"url": "https://www.cna.com.tw/news/afe/1.aspx", "source": "中央社", "published": None}
gone_rec = {"url": "https://old/x", "source": "中央社", "published": None}
NS.OUT.write_text(json.dumps({"meta": {"generated_at": (datetime.now(NS.TZ) - timedelta(minutes=90)).isoformat(),
                                       "run_gaps_min": [1, 2, 3, 4, 5, 6]},
                              "urls": [prior_rec, gone_rec]}), encoding="utf-8")
rv, _ = quiet(NS.main)
d = json.loads(NS.OUT.read_text(encoding="utf-8"))
by = {x["url"]: x for x in d["urls"]}
check("正常回 0", rv == 0, rv)
check("中央社只收財經／產經（體育不收）", "https://www.cna.com.tw/news/aspt/3.aspx" not in by and "https://www.cna.com.tw/news/aie/2.aspx" in by, list(by))
check("既有缺 published 的回頭補上", by[prior_rec["url"]].get("published", "").startswith("2026-10-30T09") and "published_unknown" not in by[prior_rec["url"]])
check("掉出窗口的標 published_unknown、不瞎猜", by["https://old/x"].get("published_unknown") is True and by["https://old/x"]["published"] is None)
check("新增計數（不含既有）", d["meta"]["new_this_run"] == 3 and d["meta"]["total"] == 5, d["meta"])
check("排程間隔只留最近 6 筆", len(d["meta"]["run_gaps_min"]) == 6 and d["meta"]["run_gaps_min"][-1] in (89, 90, 91), d["meta"]["run_gaps_min"])

NS.OUT.write_text("<<<<<<< HEAD\n{}", encoding="utf-8")
rv, _ = quiet(NS.main)
check("既有檔損壞 → 中止、不覆蓋累積歷史", rv[0] == "exit" and NS.OUT.read_text(encoding="utf-8").startswith("<<<<<<<"), rv)

# 兩邊都被擋：記錄行為（照分支只記不改）
NS.OUT.write_text(json.dumps({"meta": {}, "urls": [dict(prior_rec)]}), encoding="utf-8")
NS.requests.get = make_ns_get(blocked=True)
rv, _ = quiet(NS.main)
d = json.loads(NS.OUT.read_text(encoding="utf-8"))
check("兩邊都抓不到時不刪既有連結（累積數不減）", rv == 0 and d["meta"]["total"] == 1, d["meta"])
blocked_marks_unknown = d["urls"][0].get("published_unknown") is True
print(f"  · 觀察：兩邊都抓不到時，既有缺時間的連結被標 published_unknown＝{blocked_marks_unknown}（下次抓到會自動補回並移除標記）")

# ───────────── 1do build_us_screener ─────────────
print("1do build_us_screener.py")
import pandas as pd  # noqa: E402

check("季度 frame 名稱跨年", SC._recent_instant_frames(date(2026, 2, 1)) == ["CY2026Q1I", "CY2025Q4I", "CY2025Q3I", "CY2025Q2I"],
      SC._recent_instant_frames(date(2026, 2, 1)))


def make_sec_get(fail_frames=()):
    def get(url, headers=None, timeout=None):
        fr = url.rsplit("/", 1)[-1].replace(".json", "")
        if fr in fail_frames:
            return FakeResp(status=503) if fail_frames[fr] == 503 else FakeResp(status=404)
        rows = [{"cik": 1, "val": 100, "end": f"2026-0{1 + len(fr) % 3}-01", "accn": fr},
                {"cik": 2, "val": 0, "end": "2026-09-30"}, {"cik": 999, "val": 5, "end": "2026-09-30"}]
        if fr == "CY2026Q3I":
            rows.append({"cik": 1, "val": 200, "end": "2026-09-30", "accn": "new"})
        return FakeResp(body={"data": rows})
    return get


SC.requests.get = make_sec_get()
best, meta = quiet(SC.fetch_shares, {1, 2}, date(2026, 10, 30))[0]
check("frames 取 end 最新者、股數 0 與宇宙外不收", best.get(1, {}).get("accn") == "new" and 2 not in best and 999 not in best, best)
SC.requests.get = make_sec_get({"CY2026Q4I": 404, "CY2026Q3I": 503})
best, meta = quiet(SC.fetch_shares, {1}, date(2026, 10, 30))[0]
check("404 記 status、失敗記 errors 不拋例外", meta["frames"][0]["status"] == 404 and len(meta["errors"]) == 1 and 1 in best, meta)

N = 60
TICKERS = [f"T{i:02d}" for i in range(N)] + ["BRK.B"]
days = pd.bdate_range(end=date.today() - timedelta(days=1), periods=22)


def fake_download(tickers, **kw):
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], tickers])
    df = pd.DataFrame(index=days, columns=cols, dtype=float)
    for i, t in enumerate(tickers):
        px = [10.0 + i + j * 0.1 for j in range(len(days))]
        df[("Close", t)] = px
        df[("Open", t)] = px
        df[("High", t)] = [p + 0.5 for p in px]
        df[("Low", t)] = [p - 0.5 for p in px]
        df[("Volume", t)] = 1000.0
    return df


yf = types.ModuleType("yfinance")
yf.download = fake_download
sys.modules["yfinance"] = yf

# 盤中未收盤 K 捨棄
now_open = datetime.combine(days[-1].date(), datetime.min.time()).replace(hour=11, tzinfo=SC.ET)
c, v, dropped = SC.fetch_bars(["AAA"], now_open, {})
check("美東 16:15 前當日 K 捨棄", dropped == str(days[-1].date()) and len(c.index) == len(days) - 1, dropped)
c, v, dropped = SC.fetch_bars(["BRK.B"], now_open.replace(hour=17), {})
check("收盤後不捨棄、BRK.B↔BRK-B 換回原代號", dropped is None and list(c.columns) == ["BRK.B"], (dropped, list(c.columns)))

SC.FIN_PATH = tmp / "us_financials.json"
SC.OUT_PATH = tmp / "us_screener.json"
SC.DAILY_DIR = tmp / "us_daily"
SC.OUT_PATH.write_text('{"old":1}', encoding="utf-8")
rv, _ = quiet(SC.main)
check("讀不到 us_financials → 回 1、不覆蓋", rv == 1 and SC.OUT_PATH.read_text(encoding="utf-8") == '{"old":1}', rv)

SC.FIN_PATH.write_text(json.dumps({"financials": {t: {"name": t, "cik": 1 if t == "T00" else None} for t in TICKERS[:10]}}), encoding="utf-8")
SC.requests.get = make_sec_get()
rv, _ = quiet(SC.main)
check("有收盤 <50 檔 → 回 1、不覆蓋", rv == 1 and SC.OUT_PATH.read_text(encoding="utf-8") == '{"old":1}', rv)

yf.download = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("YFRateLimitError"))
SC.FIN_PATH.write_text(json.dumps({"financials": {t: {"name": t, "cik": 1 if t == "T00" else None} for t in TICKERS}}), encoding="utf-8")
rv, _ = quiet(SC.main)
check("yfinance 整批失敗 → 回 1、不覆蓋", rv == 1 and SC.OUT_PATH.read_text(encoding="utf-8") == '{"old":1}', rv)

yf.download = fake_download
rv, out = quiet(SC.main)
d = json.loads(SC.OUT_PATH.read_text(encoding="utf-8"))
row0 = next(r for r in d["stocks"] if r["code"] == "T00")
check("正常回 0、寫出全部檔數", rv == 0 and d["meta"]["count"] == N + 1 and d["meta"]["priced_count"] == N + 1, (rv, d["meta"].get("count")))
check("市值＝股數×收盤（只有有 CIK 的那檔）", row0.get("market_cap_est") == round(200 * row0["close"], 0) and d["meta"]["market_cap_count"] == 1, row0)
check("沒股數的標旗標", "無流通股數（市值缺）" in next(r for r in d["stocks"] if r["code"] == "T01")["flags"])
check("as_of＝最後一個已收盤日", d["meta"]["as_of"] == str(days[-1].date()), d["meta"]["as_of"])
daily = json.loads((SC.DAILY_DIR / "T00.json").read_text(encoding="utf-8"))
check("us_daily 個股檔寫出開高低收量", len(daily["bars"]) == len(days) and len(daily["bars"][0]) == 6, daily["bars"][:1])
check("暫存 .tmp 不殘留", not SC.OUT_PATH.with_suffix(".json.tmp").exists())

F13.requests.get = real_get
print(f"\n合計 {ok} 過 {fail} 失敗")
sys.exit(1 if fail else 0)
