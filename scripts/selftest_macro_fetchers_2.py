"""自測：BLS 總經／海關進出口／工業生產／美股分析師評等四支雲端抓取程式（先.一三五-1by／1bz／1ca）。

全部把 `requests`（或 Session）換成假回應、輸出路徑換暫存檔，零外部請求，不碰真的 data/。
1by：`fetch_bls_macro.py` 解析（M13 略過、「-」略過、CPI 年增率同月對齊、缺基期記 null、月增）、
     status 非成功／無 series 報錯；單一序列失敗沿用上一份（標 stale）、三支全失敗不覆蓋。
1bz：`fetch_customs_trade.py`／`fetch_industrial_production.py` CSV 解析（BOM、民國年、非總計代碼、壞數字）、
     YoY／MoM；失敗時保留上一版並標 kept_previous_*、沒有舊檔照實寫 null、外銷訂單單邊失敗不影響生產指數。
1ca：`fetch_us_analyst_reco.py` 20 小時節流、沒金鑰不寫檔、只留 4 期新到舊、空陣列／非陣列記 failed、
     錯誤訊息遮蔽金鑰、單檔失敗沿用上一份（列 stale_tickers）、全失敗不覆寫。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_bls_macro as BL  # noqa: E402
import fetch_customs_trade as CU  # noqa: E402
import fetch_industrial_production as IP  # noqa: E402
import fetch_us_analyst_reco as AR  # noqa: E402

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


tmp = Path(tempfile.mkdtemp(prefix="selftest_macro2_"))

# ───────────── 1by BLS ─────────────
print("1by fetch_bls_macro.py")
BL.REQUEST_SLEEP_SEC = 0
BL.OUT_PATH = tmp / "bls_macro.json"


def bls_body(rows, status="REQUEST_SUCCEEDED"):
    return {"status": status, "Results": {"series": [{"data": rows}]}}


def r(y, m, v):
    return {"year": str(y), "period": f"M{m:02d}", "periodName": "x", "value": str(v)}


BLS_OK = {
    "LNS14000000": bls_body([r(2026, 8, 4.3), r(2026, 7, 4.2), {"year": "2025", "period": "M13", "value": "4.0"}]),
    "CUUR0000SA0": bls_body([r(2026, 8, 324.0), r(2025, 8, 315.0), r(2026, 7, "-")]),
    "CES0000000001": bls_body([r(2026, 8, 159500), r(2026, 7, 159420)]),
}
bls_plan: dict = {}


def bls_get(url, **k):
    sid = url.rsplit("/", 1)[-1]
    v = bls_plan.get(sid, BLS_OK.get(sid))
    if isinstance(v, FakeResp):
        return v
    return FakeResp(body=v)


BL.requests.get = bls_get
rows = BL.fetch_series("LNS14000000")
check("M13 年度列略過、由舊到新排序", [x["period"] for x in rows] == ["M07", "M08"], rows)
bls_plan = {"LNS14000000": bls_body([], status="REQUEST_NOT_PROCESSED")}
try:
    BL.fetch_series("LNS14000000"); check("status 非成功報錯", False)
except RuntimeError:
    check("status 非成功報錯", True)
bls_plan = {"LNS14000000": {"status": "REQUEST_SUCCEEDED", "Results": {"series": []}}}
try:
    BL.fetch_series("LNS14000000"); check("無 series 報錯", False)
except RuntimeError:
    check("無 series 報錯", True)

bls_plan = {}
rv, _ = quiet(BL.main)
d = json.loads(BL.OUT_PATH.read_text(encoding="utf-8"))
s = d["series"]
check("全部成功回 0、三個序列都在", rv == 0 and set(s) == {"unemployment_rate", "cpi_u", "nonfarm_payrolls"}, (rv, list(s)))
check("CPI 年增率＝324/315-1、基期 2025-08（「-」列略過）", s["cpi_u"]["yoy_pct"] == round((324 / 315 - 1) * 100, 2)
      and s["cpi_u"]["yoy_base_date"] == "2025-08" and s["cpi_u"]["latest_date"] == "2026-08", s["cpi_u"])
check("失業率月增 0.1、非農月增 80", s["unemployment_rate"]["change_mom"] == 0.1 and s["nonfarm_payrolls"]["change_mom"] == 80.0)
check("成功序列沒有 stale 標記", not any(v.get("stale") for v in s.values()))

bls_plan = {"CUUR0000SA0": bls_body([r(2026, 8, 324.0)])}
quiet(BL.main)
d = json.loads(BL.OUT_PATH.read_text(encoding="utf-8"))
check("缺 12 個月前同月 → yoy_pct null＋errors 記原因", d["series"]["cpi_u"]["yoy_pct"] is None
      and any("無法計算YoY" in e["reason"] for e in d["errors"]), d["errors"])

bls_plan = {}
quiet(BL.main)
bls_plan = {"CES0000000001": FakeResp(status=503)}
rv, out = quiet(BL.main)
d = json.loads(BL.OUT_PATH.read_text(encoding="utf-8"))
check("單一序列失敗：檔案仍有該序列、標 stale、值沿用", d["series"].get("nonfarm_payrolls", {}).get("stale") is True
      and d["series"]["nonfarm_payrolls"]["latest_value"] == 159500, d["series"].get("nonfarm_payrolls"))
check("單一序列失敗：其他序列照常更新、errors 記原因、回 0", rv == 0 and not d["series"]["cpi_u"].get("stale")
      and any(e["series"] == "nonfarm_payrolls" for e in d["errors"]), (rv, d["errors"]))

bls_plan = {"UNRATE": None}
bls_plan = {"LNS14000000": bls_body([r(2026, 8, "-")])}
quiet(BL.main)
d = json.loads(BL.OUT_PATH.read_text(encoding="utf-8"))
check("查無可解析數值也沿用上一份", d["series"]["unemployment_rate"].get("stale") is True)

quiet(lambda: (bls_plan.clear(), BL.main()))
before = BL.OUT_PATH.read_text(encoding="utf-8")
bls_plan = {k: FakeResp(status=429) for k in BLS_OK}
rv, out = quiet(BL.main)
check("三支全失敗：回 1、檔案原封不動", rv == 1 and BL.OUT_PATH.read_text(encoding="utf-8") == before, rv)
BL.OUT_PATH.unlink()
rv, _ = quiet(BL.main)
d = json.loads(BL.OUT_PATH.read_text(encoding="utf-8"))
check("沒有舊檔時全失敗：照實寫空 series＋errors、回 1", rv == 1 and d["series"] == {} and len(d["errors"]) == 3, d)

# ───────────── 1bz 海關／工業生產 ─────────────
print("1bz fetch_customs_trade.py／fetch_industrial_production.py")
CU.OUT_PATH = tmp / "customs_trade.json"
CU_CSV = ("﻿年度,月份,出口總值(新臺幣千元),進口總值(新臺幣千元),出入超(新臺幣千元)\n"
          "115,9,1200,1000,200\n114,9,1000,800,200\n115,8,1100,900,200\n小計,9,1,1,0\n115,7,abc,1,1\n")
cu_resp = {"r": FakeResp(content=CU_CSV.encode("utf-8"))}


class FakeSession:
    def mount(self, *a):
        pass

    def get(self, *a, **k):
        v = cu_resp["r"]
        if isinstance(v, Exception):
            raise v
        return v


CU.requests.Session = FakeSession
rows = CU._fetch_rows()
check("海關：BOM 去除、民國年轉西元、壞年度／壞數字列略過", [(x["year"], x["month"]) for x in rows] == [(2025, 9), (2026, 8), (2026, 9)], rows)
rv, _ = quiet(CU.main)
d = json.loads(CU.OUT_PATH.read_text(encoding="utf-8"))
check("海關：最新 2026-09、出口年增 20%、進口年增 25%、回 0", rv == 0 and d["latest"]["date"] == "2026-09"
      and d["yoy"]["export_yoy_pct"] == 20.0 and d["yoy"]["import_yoy_pct"] == 25.0, d)
cu_resp["r"] = TimeoutError("ConnectTimeout")
rv, _ = quiet(CU.main)
d = json.loads(CU.OUT_PATH.read_text(encoding="utf-8"))
check("海關：失敗保留上一版＋kept_previous_latest＋errors、回 1", rv == 1 and d["latest"]["date"] == "2026-09"
      and d.get("kept_previous_latest") is True and d["previous_fetched_at"] and d["errors"], d)
quiet(CU.main)
d2 = json.loads(CU.OUT_PATH.read_text(encoding="utf-8"))
check("海關：連續失敗 previous_fetched_at 不被洗成上一次失敗時間", d2["previous_fetched_at"] == d["previous_fetched_at"])
CU.OUT_PATH.unlink()
rv, _ = quiet(CU.main)
d = json.loads(CU.OUT_PATH.read_text(encoding="utf-8"))
check("海關：沒有舊檔時失敗照實寫 null", rv == 1 and d["latest"] is None and "kept_previous_latest" not in d, d)

IP.OUT_PATH = tmp / "industrial_production.json"
IP_CSV = ("﻿資料期(民國年),行業代碼,統計值(指數),計量單位\n"
          "11509,Z,120,110年=100\n11409,Z,100,110年=100\n11508,Z,110,110年=100\n11509,C,999,110年=100\n"
          "1150,Z,1,110年=100\n11507,Z,-,110年=100\n")
EO_CSV = ("﻿資料期(民國年),地區代碼,統計值(金額),計量單位\n"
          "11509,00,600,百萬美元\n11409,00,500,百萬美元\n11508,00,480,百萬美元\n11509,01,1,百萬美元\n")
ip_plan = {"ip": FakeResp(content=IP_CSV.encode("utf-8")), "eo": FakeResp(content=EO_CSV.encode("utf-8"))}


def ip_get(url, **k):
    v = ip_plan["ip" if url == IP.SOURCE_URL else "eo"]
    if isinstance(v, Exception):
        raise v
    return v


IP.requests.get = ip_get
rows = IP._fetch_rows()
check("工業生產：只取代碼 Z、資料期長度不對／壞數字略過", [(x["year"], x["month"], x["value"]) for x in rows]
      == [(2025, 9, 100.0), (2026, 8, 110.0), (2026, 9, 120.0)], rows)
rv, _ = quiet(IP.main)
d = json.loads(IP.OUT_PATH.read_text(encoding="utf-8"))
check("工業生產：年增 20%、月增 9.09%、基期原樣、回 0", rv == 0 and d["yoy_pct"] == 20.0
      and d["latest"]["change_mom_pct"] == 9.09 and d["latest"]["base_period"] == "110年=100", d)
check("外銷訂單：只取代碼 00、年增 20%、月增 25%", d["export_orders"]["value"] == 600.0 and d["export_orders"]["yoy_pct"] == 20.0
      and d["export_orders"]["change_mom_pct"] == 25.0, d["export_orders"])
ip_plan["eo"] = FakeResp(status=403)
rv, _ = quiet(IP.main)
d = json.loads(IP.OUT_PATH.read_text(encoding="utf-8"))
check("外銷訂單單邊失敗：生產指數照常、回 0、外銷沿用上一版並標記", rv == 0 and not d.get("kept_previous_latest")
      and d["export_orders"]["value"] == 600.0 and d.get("kept_previous_export_orders") is True, d)
ip_plan["ip"] = FakeResp(status=403)
rv, _ = quiet(IP.main)
d = json.loads(IP.OUT_PATH.read_text(encoding="utf-8"))
check("工業生產失敗：保留上一版數值＋kept_previous_latest、回 1", rv == 1 and d["latest"]["value"] == 120.0
      and d["yoy_pct"] == 20.0 and d.get("kept_previous_latest") is True, d)
IP.OUT_PATH.unlink()
rv, _ = quiet(IP.main)
d = json.loads(IP.OUT_PATH.read_text(encoding="utf-8"))
check("工業生產：沒有舊檔時兩邊都失敗照實寫 null", rv == 1 and d["latest"] is None and d["export_orders"] is None, d)

# ───────────── 1ca 分析師評等 ─────────────
print("1ca fetch_us_analyst_reco.py")
AR.OUT_PATH = tmp / "us_analyst_reco.json"
AR.US_TICKERS[:] = ["AAA", "BBB", "CCC"]
AR.time.sleep = lambda s: None
KEY = "SECRETKEY123"


def reco(n):
    return [{"period": f"2026-{m:02d}-01", "strongBuy": m, "buy": 1, "hold": 1, "sell": 0, "strongSell": 0, "symbol": "x"}
            for m in range(1, n + 1)]


ar_plan: dict = {}


def ar_get(url, params=None, **k):
    v = ar_plan.get(params["symbol"], reco(6))
    if isinstance(v, FakeResp):
        return v
    return FakeResp(text=json.dumps(v), body=v)


AR.requests.get = ar_get
os.environ.pop("FINNHUB_API_KEY", None)
rv, _ = quiet(AR.main)
check("沒金鑰：exit 1、不寫檔", rv == ("exit", 1) and not AR.OUT_PATH.exists(), rv)
os.environ["FINNHUB_API_KEY"] = KEY
rv, _ = quiet(AR.main)
d = json.loads(AR.OUT_PATH.read_text(encoding="utf-8"))
check("成功：三檔都在、只留 4 期、新到舊、symbol 欄不保留", set(d["tickers"]) == {"AAA", "BBB", "CCC"}
      and [x["period"] for x in d["tickers"]["AAA"]] == ["2026-06-01", "2026-05-01", "2026-04-01", "2026-03-01"]
      and "symbol" not in d["tickers"]["AAA"][0] and d["stale_tickers"] == [], d["tickers"].get("AAA"))
mt = AR.OUT_PATH.read_text(encoding="utf-8")
calls = []
AR.requests.get = lambda *a, **k: calls.append(1)
quiet(AR.main)
check("未滿 20 小時：不送請求、不改檔", calls == [] and AR.OUT_PATH.read_text(encoding="utf-8") == mt)
AR.requests.get = ar_get
d["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=21)).isoformat(timespec="seconds")
AR.OUT_PATH.write_text(json.dumps(d), encoding="utf-8")
ar_plan = {"BBB": FakeResp(status=500, text=f"error token={KEY}"), "CCC": []}
rv, out = quiet(AR.main)
d = json.loads(AR.OUT_PATH.read_text(encoding="utf-8"))
check("單檔失敗／空陣列：沿用上一份、列進 stale_tickers", set(d["tickers"]) == {"AAA", "BBB", "CCC"}
      and sorted(d["stale_tickers"]) == ["BBB", "CCC"], (list(d["tickers"]), d.get("stale_tickers")))
check("failed 記原因、輸出與檔案都沒有金鑰", len(d["failed"]) == 2 and KEY not in out
      and KEY not in AR.OUT_PATH.read_text(encoding="utf-8"), d["failed"])
ar_plan = {"AAA": {"error": "x"}}
d["generated_at"] = "2000-01-01T00:00:00+00:00"
AR.OUT_PATH.write_text(json.dumps(d), encoding="utf-8")
quiet(AR.main)
d = json.loads(AR.OUT_PATH.read_text(encoding="utf-8"))
check("回應不是陣列記 failed", any(f["symbol"] == "AAA" and "不是陣列" in f["reason"] for f in d["failed"]), d["failed"])
d["generated_at"] = "2000-01-01T00:00:00+00:00"
AR.OUT_PATH.write_text(json.dumps(d), encoding="utf-8")
before = AR.OUT_PATH.read_text(encoding="utf-8")
ar_plan = {t: FakeResp(status=429) for t in AR.US_TICKERS}
rv, _ = quiet(AR.main)
check("全失敗（即使有舊檔可沿用）：exit 1、不覆寫", rv == ("exit", 1) and AR.OUT_PATH.read_text(encoding="utf-8") == before, rv)
os.environ.pop("FINNHUB_API_KEY", None)

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
