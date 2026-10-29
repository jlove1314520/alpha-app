"""自測：期貨三大法人／匯率／CFTC COT 三支雲端抓取程式（先.一三五-1bv／1bw／1bx）。

全部把 `requests`（或 Session）換成假回應、輸出路徑換暫存檔，零外部請求，不碰真的 data/。
1bv：`fetch_futures_institutional.py` 的 `parse()` 接 JSON／CSV（含 BOM）、身份別與商品對應、HTML／空陣列／無目標商品報錯；
     `main()` 失敗（HTML、429）不覆蓋既有檔、429 會標封鎖、同日去重、只留最近 60 日。
1bw：`fetch_fx.py` 央行 CSV 最後一行壞掉時往回找有效列、表頭不對退備援、兩來源都失敗時不拿 null 蓋掉舊匯率。
1bx：`fetch_cftc_cot.py` 單一合約失敗沿用上一份（標 stale）、欄位解析不到也沿用、三檔全失敗不覆蓋。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_futures_institutional as FI  # noqa: E402
import fetch_fx as FX  # noqa: E402
import fetch_cftc_cot as CT  # noqa: E402

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
    def __init__(self, text="", status=200, body=None, content=None):
        self.text, self.status_code, self._body = text, status, body
        self.content = content if content is not None else text.encode("utf-8")
        self.encoding = None

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
        rv = fn(*a, **k)
    return rv, buf.getvalue()


tmp = Path(tempfile.mkdtemp(prefix="selftest_macro_"))

# ───────── 1bv 期貨三大法人 ─────────
print("1bv fetch_futures_institutional")
JSON_ROWS = [
    {"Date": "20261029", "ContractCode": "臺股期貨", "Item": "外資及陸資", "OpenInterest(Long)": "10,000",
     "OpenInterest(Short)": "40000", "OpenInterest(Net)": "-30000", "TradingVolume(Net)": "-500",
     "ContractValueofOpenInterest(Net)(Thousands)": "-1,234,567"},
    {"Date": "20261029", "ContractCode": "臺股期貨", "Item": "投信", "OpenInterest(Long)": "30000",
     "OpenInterest(Short)": "1000", "OpenInterest(Net)": "29000", "TradingVolume(Net)": "-", "ContractValueofOpenInterest(Net)(Thousands)": ""},
    {"Date": "20261029", "ContractCode": "股票期貨", "Item": "外資及陸資", "OpenInterest(Long)": "1"},  # 非目標商品
    {"Date": "2026-10-29", "ContractCode": "小型臺指期貨", "Item": "自營商"},  # 日期不是 8 碼 → 略過
]
p = FI.parse(json.dumps(JSON_ROWS, ensure_ascii=False))
tx = p.get("2026-10-29", {}).get("TX", {})
check("JSON：日期轉 ISO、外資逗號數字", tx.get("foreign", {}).get("net_oi_amount_k") == -1234567 and tx["foreign"]["long_oi"] == 10000, p)
check("JSON：'-'／空字串記 None 不報錯", tx.get("trust", {}).get("net_trade") is None and tx["trust"]["net_oi"] == 29000)
check("JSON：非目標商品與壞日期略過", set(p["2026-10-29"]) == {"TX"}, p)
CSV = ("﻿日期,商品名稱,身份別,多方未平倉口數,空方未平倉口數,多空未平倉口數淨額,多空交易口數淨額,多空未平倉契約金額淨額(千元)\n"
       "20261029,電子期貨,自營商,100,50,50,3,\"1,000\"\n")
pc = FI.parse(CSV)
check("CSV（開頭 BOM）：中文欄名對應", pc.get("2026-10-29", {}).get("TE", {}).get("dealer", {}).get("net_oi_amount_k") == 1000, pc)
for label, body in [("HTML", "<html>error</html>"), ("空陣列", "[]"), ("只有非目標商品", json.dumps(JSON_ROWS[2:3], ensure_ascii=False))]:
    try:
        FI.parse(body)
        check(f"parse {label} 要報錯", False)
    except ValueError:
        check(f"parse {label} 報錯", True)

FI.OUT = tmp / "futures_institutional.json"
old_hist = [{"date": f"2026-07-{d:02d}", "products": {"TX": {}}} for d in range(1, 32)] + \
           [{"date": f"2026-08-{d:02d}", "products": {"TX": {}}} for d in range(1, 32)] + \
           [{"date": "2026-10-29", "products": {"TX": {"foreign": {"net_oi": 1}}}}]
FI.OUT.write_text(json.dumps({"history": old_hist, "data_date": "2026-10-29"}), encoding="utf-8")
before = FI.OUT.read_text(encoding="utf-8")
FI._gate = lambda: None
blocked = []
FI._block = lambda code: blocked.append(code)
FI.requests.get = lambda *a, **k: FakeResp("<html>maintenance</html>")
rv, _ = quiet(FI.main)
check("main：回 HTML → exit 0 且不覆蓋", rv == 0 and FI.OUT.read_text(encoding="utf-8") == before)
FI.requests.get = lambda *a, **k: FakeResp("", status=429)
rv, _ = quiet(FI.main)
check("main：429 → 標封鎖、不覆蓋", blocked == [429] and FI.OUT.read_text(encoding="utf-8") == before, blocked)
FI.requests.get = lambda *a, **k: FakeResp(json.dumps(JSON_ROWS, ensure_ascii=False))
rv, _ = quiet(FI.main)
doc = json.loads(FI.OUT.read_text(encoding="utf-8"))
dates = [h["date"] for h in doc["history"]]
check("main：同日去重（10-29 只留一筆、換成新值）", dates.count("2026-10-29") == 1
      and doc["history"][-1]["products"]["TX"]["foreign"]["net_oi"] == -30000, dates[-3:])
check("main：只留最近 60 日、data_date＝最新", len(dates) == 60 and doc["data_date"] == "2026-10-29" and dates == sorted(dates), len(dates))

# ───────── 1bw 匯率 ─────────
print("1bw fetch_fx")
FX.OUT_PATH = tmp / "fx.json"


class FakeSession:
    body = b""

    def mount(self, *a):
        pass

    def get(self, *a, **k):
        return FakeResp(content=FakeSession.body)


FX.requests.Session = FakeSession
FakeSession.body = "﻿日期,NTD/USD\n20261028,32.4\n20261029,32.492\n20261030,\n".encode("utf-8")
r = FX._fetch_cbc_fx()
check("CSV 最後一行匯率空白 → 往回取 10-29", r["date"] == "2026-10-29" and r["rate"] == 32.492, r)
FakeSession.body = "﻿日期,NTD/USD\n20261029,32.492\n".encode("utf-8")
check("CSV 正常 → 取最後一行", FX._fetch_cbc_fx()["date"] == "2026-10-29")
for label, body in [("表頭不符", "date,rate\n20261029,32.4\n"), ("只有表頭", "日期,NTD/USD\n"), ("全部無效列", "日期,NTD/USD\n註:,單位\n")]:
    FakeSession.body = body.encode("utf-8")
    try:
        FX._fetch_cbc_fx()
        check(f"CSV {label} 要報錯", False)
    except RuntimeError:
        check(f"CSV {label} 報錯（會退備援）", True)


def _yf_fail():
    raise RuntimeError("yfinance down")


FX._fetch_yfinance_fx = _yf_fail
good = {"fetched_at": "2026-10-29T17:08:37+00:00", "errors": [], "usd_twd": {"rate": 32.492, "date": "2026-10-29", "source": "x"}}
FX.OUT_PATH.write_text(json.dumps(good), encoding="utf-8")
before = FX.OUT_PATH.read_text(encoding="utf-8")
FakeSession.body = b"<html>"
quiet(FX.main)
check("兩來源都失敗 → 保留既有檔原封不動", FX.OUT_PATH.read_text(encoding="utf-8") == before)
FX.OUT_PATH.unlink()
quiet(FX.main)
d = json.loads(FX.OUT_PATH.read_text(encoding="utf-8"))
check("兩來源都失敗且沒有舊檔 → 照實寫 null＋兩筆錯誤", d["usd_twd"] is None and len(d["errors"]) == 2, d)
FakeSession.body = "﻿日期,NTD/USD\n20261030,32.51\n".encode("utf-8")
quiet(FX.main)
d = json.loads(FX.OUT_PATH.read_text(encoding="utf-8"))
check("央行正常 → 覆寫成新值", d["usd_twd"]["date"] == "2026-10-30" and d["errors"] == [], d)

# ───────── 1bx CFTC COT ─────────
print("1bx fetch_cftc_cot")
CT.OUT_PATH = tmp / "cftc_cot.json"
CT.REQUEST_SLEEP_SEC = 0
CT.time.sleep = lambda s: None


def row(date, lo, sh):
    return {"report_date_as_yyyy_mm_dd": f"{date}T00:00:00.000", "noncomm_positions_long_all": str(lo),
            "noncomm_positions_short_all": str(sh), "open_interest_all": "1000"}


prev = {"contracts": {k: {"name": v["name"], "cftc_contract_market_code": v["code"],
                          "history": [{"date": "2026-10-13", "net": 1}, {"date": "2026-10-20", "net": 2}]}
                      for k, v in CT.CONTRACTS.items()}}
CT.OUT_PATH.write_text(json.dumps(prev), encoding="utf-8")
plan = {}


def fake_get(url, params=None, **k):
    code = params["$where"].split("'")[1]
    mode = plan.get(code, "ok")
    if mode == "err":
        return FakeResp("", status=500)
    if mode == "empty":
        return FakeResp(body=[])
    if mode == "badfields":
        return FakeResp(body=[{"report_date_as_yyyy_mm_dd": "2026-10-27", "foo": 1}])
    return FakeResp(body=[row("2026-10-27", 300, 100), row("2026-10-20", 200, 100)])


CT.requests.get = fake_get
plan = {"13874+": "err", "1170E1": "badfields"}
rv, _ = quiet(CT.main)
d = json.loads(CT.OUT_PATH.read_text(encoding="utf-8"))
c = d["contracts"]
check("sp500 抓取失敗 → 沿用舊歷史、標 stale", c["sp500"].get("stale") is True and c["sp500"]["history"][-1]["date"] == "2026-10-20", c.get("sp500"))
check("vix 欄位解析不到 → 沿用舊歷史、標 stale", c["vix"].get("stale") is True and len(d["errors"]) == 2, d["errors"])
check("nasdaq100 正常 → 新資料、未標 stale、日期排序", "stale" not in c["nasdaq100"]
      and [h["date"] for h in c["nasdaq100"]["history"]] == ["2026-10-20", "2026-10-27"] and c["nasdaq100"]["history"][-1]["net"] == 200)
check("部分失敗 exit 0", rv == 0, rv)
before = CT.OUT_PATH.read_text(encoding="utf-8")
plan = {"13874+": "err", "20974+": "empty", "1170E1": "err"}
rv, _ = quiet(CT.main)
check("三檔全失敗且有舊檔 → exit 1 不覆蓋", rv == 1 and CT.OUT_PATH.read_text(encoding="utf-8") == before, rv)
CT.OUT_PATH.unlink()
rv, _ = quiet(CT.main)
d = json.loads(CT.OUT_PATH.read_text(encoding="utf-8"))
check("三檔全失敗且沒有舊檔 → 照實寫空 contracts＋3 筆錯誤、exit 1", rv == 1 and d["contracts"] == {} and len(d["errors"]) == 3, d)
plan = {}
rv, _ = quiet(CT.main)
d = json.loads(CT.OUT_PATH.read_text(encoding="utf-8"))
check("全部正常 → 三檔新資料、無 stale", rv == 0 and len(d["contracts"]) == 3 and not any(v.get("stale") for v in d["contracts"].values()))

print(f"\n結果：{ok} 項通過，{fail} 項失敗")
sys.exit(1 if fail else 0)
