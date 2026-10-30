"""自測：美股 SEC 三支雲端抓取程式（先.一三五-1dj／1dk／1dl）。

全部把 `requests.get`／`time.sleep` 換成假的、輸出路徑換暫存檔，零外部請求，不碰真的 data/。
1dj：`fetch_us_sic.py` 正常寫出、單檔失敗沿用上一份（標 stale）、全失敗（含對映表失敗）不覆寫。
1dk：`fetch_us_insider_trading.py` Form 4 XML 解析（只取 Transaction、代碼對照、衍生表標記）、
     整檔清單失敗沿用上一份（標 stale）、單筆申報失敗不沿用、全失敗不覆寫。
1dl：`fetch_us_8k.py` Item 條號解析、超過保留天數剔除、整檔失敗沿用上一份（標 stale、仍套保留天數）、全失敗不覆寫。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_us_sic as SIC  # noqa: E402
import fetch_us_insider_trading as F4  # noqa: E402
import fetch_us_8k as K8  # noqa: E402

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
    def __init__(self, body=None, content=b"", status=200):
        self._body, self.content, self.status_code = body, content, status

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


SIC.time.sleep = lambda *_a, **_k: None  # time／requests 是同一個模組物件，換一次三支都生效

tmp = Path(tempfile.mkdtemp(prefix="selftest_sec_us_"))

# ───────────── 1dj fetch_us_sic ─────────────
print("1dj fetch_us_sic.py")
SIC.OUT_PATH = tmp / "us_sic.json"
SIC.US_TICKERS = ["AAPL", "TSM", "NVDA"]
CIKS = {"AAPL": 320193, "TSM": 1046179, "NVDA": 1045810}


def make_sic_get(fail_tickers=(), map_fail=False):
    def get(url, params=None, headers=None, timeout=None):
        if "company_tickers" in url:
            if map_fail:
                return FakeResp(status=503)
            return FakeResp({str(i): {"ticker": t, "cik_str": c} for i, (t, c) in enumerate(CIKS.items())})
        cik = int(url.split("CIK")[1].split(".")[0])
        tk = next(t for t, c in CIKS.items() if c == cik)
        if tk in fail_tickers:
            return FakeResp(status=500)
        return FakeResp({"sic": "3674", "sicDescription": "Semiconductors", "name": tk + " Inc"})
    return get


SIC.requests.get = make_sic_get()
rv, _ = quiet(SIC.main)
d = json.loads(SIC.OUT_PATH.read_text(encoding="utf-8"))
check("正常：三檔全寫出、順序照清單", list(d["tickers"]) == ["AAPL", "TSM", "NVDA"], list(d["tickers"]))
check("正常：沒有 stale 標記", not any(v.get("stale") for v in d["tickers"].values()))

SIC.requests.get = make_sic_get(fail_tickers=("TSM",))
rv, _ = quiet(SIC.main)
d = json.loads(SIC.OUT_PATH.read_text(encoding="utf-8"))
check("單檔失敗：TSM 沿用上一份且標 stale",
      d["tickers"].get("TSM", {}).get("stale") is True and d["tickers"]["TSM"]["cik"] == 1046179, d["tickers"].get("TSM"))
check("單檔失敗：errors 仍記 TSM", any(e.get("ticker") == "TSM" for e in d["errors"]))
check("單檔失敗：順序仍照清單", list(d["tickers"]) == ["AAPL", "TSM", "NVDA"], list(d["tickers"]))

before = SIC.OUT_PATH.read_text(encoding="utf-8")
SIC.requests.get = make_sic_get(fail_tickers=tuple(CIKS))
rv, _ = quiet(SIC.main)
check("全失敗：exit 1", rv == ("exit", 1), rv)
check("全失敗：不覆寫既有檔", SIC.OUT_PATH.read_text(encoding="utf-8") == before)

SIC.requests.get = make_sic_get(map_fail=True)
rv, _ = quiet(SIC.main)
check("對映表失敗：exit 1 且不覆寫", rv == ("exit", 1) and SIC.OUT_PATH.read_text(encoding="utf-8") == before, rv)

SIC.OUT_PATH = tmp / "us_sic_none.json"
SIC.requests.get = make_sic_get(fail_tickers=("TSM",))
rv, _ = quiet(SIC.main)
d = json.loads(SIC.OUT_PATH.read_text(encoding="utf-8"))
check("沒有上一份時單檔失敗：該檔不出現、其他照寫", list(d["tickers"]) == ["AAPL", "NVDA"], list(d["tickers"]))

# ───────────── 1dk fetch_us_insider_trading ─────────────
print("1dk fetch_us_insider_trading.py")
SIC_FILE = tmp / "sic_for_downstream.json"
SIC_FILE.write_text(json.dumps({"tickers": {"AAPL": {"cik": 320193, "entity_name": "Apple"},
                                            "TSM": {"cik": 1046179, "entity_name": "TSMC"}}}), encoding="utf-8")
F4.SIC_PATH = SIC_FILE
F4.OUT_PATH = tmp / "us_insider.json"

FORM4_XML = b"""<?xml version="1.0"?>
<ownershipDocument>
 <reportingOwner>
  <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
  <reportingOwnerRelationship><isOfficer>true</isOfficer><officerTitle>SVP</officerTitle><isDirector>true</isDirector></reportingOwnerRelationship>
 </reportingOwner>
 <nonDerivativeTable>
  <nonDerivativeTransaction>
   <securityTitle><value>Common Stock</value></securityTitle>
   <transactionDate><value>2026-09-10</value></transactionDate>
   <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
   <transactionAmounts><transactionShares><value>1438</value></transactionShares>
    <transactionPricePerShare><value>317.23</value></transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts>
   <postTransactionAmounts><sharesOwnedFollowingTransaction><value>10000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
  </nonDerivativeTransaction>
  <nonDerivativeHolding><securityTitle><value>Common Stock</value></securityTitle></nonDerivativeHolding>
 </nonDerivativeTable>
 <derivativeTable>
  <derivativeTransaction>
   <transactionDate><value>2026-09-11</value></transactionDate>
   <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
   <transactionAmounts><transactionShares><value>500</value></transactionShares><transactionPricePerShare><value></value></transactionPricePerShare></transactionAmounts>
  </derivativeTransaction>
 </derivativeTable>
</ownershipDocument>"""

rows = F4.parse_form4_xml(FORM4_XML, "0001-26-000001", "2026-09-12")
check("Form4：只取 Transaction（跳過 Holding）", len(rows) == 2, len(rows))
check("Form4：職稱組合 SVP、董事", rows[0]["title"] == "SVP、董事", rows[0]["title"])
check("Form4：代碼 S 對照公開市場賣出、股數價格",
      rows[0]["code_label"] == "公開市場賣出" and rows[0]["shares"] == 1438.0 and rows[0]["price"] == 317.23)
check("Form4：衍生表標記、空價格為 None", rows[1]["is_derivative"] is True and rows[1]["price"] is None)

ATOM_F4 = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><content><accession-number>0001-26-000001</accession-number><filing-date>2026-09-12</filing-date></content></entry>
</feed>"""


def make_f4_get(list_fail=(), xml_fail=()):
    def get(url, params=None, headers=None, timeout=None):
        if "browse-edgar" in url:
            if int(params["CIK"]) in list_fail:
                return FakeResp(status=500)
            return FakeResp(content=ATOM_F4)
        cik = int(url.split("/data/")[1].split("/")[0])
        if url.endswith("index.json"):
            return FakeResp({"directory": {"item": [{"name": "x-index.htm"}, {"name": "wf-form4_1.xml"}]}})
        if cik in xml_fail:
            return FakeResp(status=500)
        return FakeResp(content=FORM4_XML)
    return get


F4.requests.get = make_f4_get()
rv, _ = quiet(F4.main)
d = json.loads(F4.OUT_PATH.read_text(encoding="utf-8"))
check("正常：兩檔各 2 筆、賣 1、回 0",
      d["tickers"]["AAPL"]["sell_count"] == 1 and len(d["tickers"]["TSM"]["transactions"]) == 2 and rv == 0, rv)
check("正常：交易依日期新到舊", d["tickers"]["AAPL"]["transactions"][0]["transaction_date"] == "2026-09-11")

F4.requests.get = make_f4_get(list_fail=(1046179,))
rv, _ = quiet(F4.main)
d = json.loads(F4.OUT_PATH.read_text(encoding="utf-8"))
check("整檔清單失敗：TSM 沿用上一份 2 筆且標 stale",
      d["tickers"]["TSM"].get("stale") is True and len(d["tickers"]["TSM"]["transactions"]) == 2, d["tickers"]["TSM"])
check("整檔清單失敗：errors 仍記錄", bool(d["tickers"]["TSM"]["errors"]) and bool(d["errors"]))

F4.requests.get = make_f4_get(xml_fail=(1046179,))
rv, _ = quiet(F4.main)
d = json.loads(F4.OUT_PATH.read_text(encoding="utf-8"))
check("單筆申報失敗：不沿用、不標 stale（照實只剩這次抓到的）",
      not d["tickers"]["TSM"].get("stale") and d["tickers"]["TSM"]["transactions"] == [], d["tickers"]["TSM"])

before = F4.OUT_PATH.read_text(encoding="utf-8")
F4.requests.get = make_f4_get(list_fail=(320193, 1046179))
rv, _ = quiet(F4.main)
check("全失敗：回 1 且不覆寫", rv == 1 and F4.OUT_PATH.read_text(encoding="utf-8") == before, rv)

F4.SIC_PATH = tmp / "no_such.json"
rv, _ = quiet(F4.main)
check("讀不到 us_sic.json：回 1 且不覆寫", rv == 1 and F4.OUT_PATH.read_text(encoding="utf-8") == before, rv)
F4.SIC_PATH = SIC_FILE

# ───────────── 1dl fetch_us_8k ─────────────
print("1dl fetch_us_8k.py")
K8.SIC_PATH = SIC_FILE
K8.OUT_PATH = tmp / "us_events.json"
items = K8.parse_items("<b>Filed:</b> 2026-10-01 <b>AccNo:</b> 1<br>Item 2.02: Results of Operations and Financial Condition"
                       "<br>Item 9.01: Financial Statements and Exhibits")
check("Item 解析：兩條", items == ["Item 2.02: Results of Operations and Financial Condition",
                                  "Item 9.01: Financial Statements and Exhibits"], items)
check("Item 解析：空字串回空陣列", K8.parse_items("") == [])

today = datetime.now(timezone.utc)
recent = (today - timedelta(days=5)).strftime("%Y-%m-%d")
old_day = (today - timedelta(days=400)).strftime("%Y-%m-%d")
ATOM_8K = f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><summary>Item 2.02: Results of Operations and Financial Condition&lt;br&gt;</summary><content>
<accession-number>A1</accession-number><filing-date>{recent}</filing-date><filing-href>https://x/1</filing-href><filing-type>8-K</filing-type></content></entry>
<entry><summary></summary><content>
<accession-number>A0</accession-number><filing-date>{old_day}</filing-date><filing-href>https://x/0</filing-href></content></entry>
</feed>""".encode("utf-8")


def make_8k_get(fail=()):
    def get(url, params=None, headers=None, timeout=None):
        if int(params["CIK"]) in fail:
            return FakeResp(status=500)
        return FakeResp(content=ATOM_8K)
    return get


K8.requests.get = make_8k_get()
rv, _ = quiet(K8.main)
d = json.loads(K8.OUT_PATH.read_text(encoding="utf-8"))
f = d["tickers"]["AAPL"]["filings"]
check("正常：超過保留天數剔除、只剩近期 1 筆、回 0", len(f) == 1 and f[0]["accession"] == "A1" and rv == 0, f)

# 上一份塞一筆已過期的舊申報，確認沿用時仍套保留天數
prev = json.loads(K8.OUT_PATH.read_text(encoding="utf-8"))
prev["tickers"]["TSM"]["filings"].append({"accession": "OLD", "filed_at": old_day, "url": "u", "filing_type": "8-K", "items": []})
K8.OUT_PATH.write_text(json.dumps(prev), encoding="utf-8")
K8.requests.get = make_8k_get(fail=(1046179,))
rv, _ = quiet(K8.main)
d = json.loads(K8.OUT_PATH.read_text(encoding="utf-8"))
t = d["tickers"]["TSM"]
check("整檔失敗：TSM 沿用上一份、剔除過期、標 stale",
      t.get("stale") is True and [x["accession"] for x in t["filings"]] == ["A1"], t)
check("整檔失敗：errors 仍記錄", bool(t["errors"]) and bool(d["errors"]))
check("整檔失敗：AAPL 不受影響、沒有 stale", not d["tickers"]["AAPL"].get("stale"))

before = K8.OUT_PATH.read_text(encoding="utf-8")
K8.requests.get = make_8k_get(fail=(320193, 1046179))
rv, _ = quiet(K8.main)
check("全失敗：回 1 且不覆寫", rv == 1 and K8.OUT_PATH.read_text(encoding="utf-8") == before, rv)

print(f"\n合計：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
