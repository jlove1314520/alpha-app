"""自測：三支沒有自測的排程腳本（先.一三五-1dp／1dq／1dr）。

全部把 `requests.get`／`time.sleep`（及 yfinance）換成假的、輸出路徑換暫存，零外部請求，不碰真的 data/。
1dp：`fetch_us_financials_sec.py` 年度值挑選、去年同期、毛利／負債比推導、名冊宇宙、
     失敗分類、成功 <50 或名冊失敗不覆蓋。
1dq：`build_us_scores_v0.py` 百分位／去極值／EPS 年增、價值排除規則、yfinance 失敗退回、
     coverage 門檻、讀不到財報或不足 50 檔不覆蓋。只用合成數字，不算任何報酬、不登記試驗。
1dr：`probe_twse_publish_time.py` 民國日期、四種回應判讀、`--report` 最早成功時刻與壞行略過。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import types
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_us_financials_sec as FIN  # noqa: E402
import build_us_scores_v0 as SC  # noqa: E402
import probe_twse_publish_time as PR  # noqa: E402

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
    def __init__(self, body=None, status=200):
        self._body, self.status_code = body, status

    def json(self):
        if self._body is None:
            raise ValueError("Expecting value")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


# ───────────── 1dp fetch_us_financials_sec ─────────────
def row(start, end, val, filed, form="10-K"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def inst(end, val, filed, form="10-K"):
    return {"end": end, "val": val, "filed": filed, "form": form}


def facts_payload(end_year: int) -> dict:
    y, p = end_year, end_year - 1
    return {"facts": {"us-gaap": {
        # 舊 tag 只到前年；新 tag 有今年 → 應選新 tag
        "SalesRevenueNet": {"units": {"USD": [row(f"{p-1}-01-01", f"{p-1}-12-31", 50, f"{p}-02-01")]}},
        "Revenues": {"units": {"USD": [
            row(f"{y}-01-01", f"{y}-12-31", 120, f"{y+1}-02-01"),
            row(f"{y}-01-01", f"{y}-12-31", 125, f"{y+1}-03-01", "10-K/A"),  # 同期末 filed 較晚 → 取 125
            row(f"{p}-01-01", f"{p}-12-31", 100, f"{y}-02-01"),
            row(f"{y}-10-01", f"{y}-12-31", 40, f"{y+1}-02-01"),  # 季度（92 天）不收
            row(f"{y}-01-01", f"{y}-12-31", 999, f"{y+1}-02-01", "10-Q"),  # 非年報表單不收
        ]}},
        "CostOfRevenue": {"units": {"USD": [
            row(f"{y}-01-01", f"{y}-12-31", 75, f"{y+1}-02-01"),
            row(f"{p}-01-01", f"{p}-12-31", 70, f"{y}-02-01")]}},
        "OperatingIncomeLoss": {"units": {"USD": [row(f"{y}-01-01", f"{y}-12-31", 25, f"{y+1}-02-01")]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            row(f"{y}-01-01", f"{y}-12-31", 2.0, f"{y+1}-02-01"),
            row(f"{p}-01-01", f"{p}-12-31", 1.6, f"{y}-02-01")]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [row(f"{y}-01-01", f"{y}-12-31", 30, f"{y+1}-02-01")]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [row(f"{y}-01-01", f"{y}-12-31", 10, f"{y+1}-02-01")]}},
        # 沒有 Liabilities → 用 負債及權益 − 權益 推導
        "Assets": {"units": {"USD": [inst(f"{y}-12-31", 200, f"{y+1}-02-01")]}},
        "LiabilitiesAndStockholdersEquity": {"units": {"USD": [inst(f"{y}-12-31", 200, f"{y+1}-02-01")]}},
        "StockholdersEquity": {"units": {"USD": [inst(f"{y}-12-31", 150, f"{y+1}-02-01")]}},
    }}}


def test_fin() -> None:
    print("1dp fetch_us_financials_sec.py")
    yr = date.today().year - 1
    rec = FIN.compute(facts_payload(yr))
    check("營收取新 tag、同期末 filed 最新者（125）", rec.get("revenue") == 125 and rec.get("revenue_tag") == "us-gaap:Revenues", rec)
    check("季度與 10-Q 不收（期末＝年底）", rec.get("period_end") == f"{yr}-12-31", rec.get("period_end"))
    check("營收年增 125/100−1", rec.get("revenue_yoy") == 0.25, rec.get("revenue_yoy"))
    check("毛利缺時用營收−成本 → 毛利率 0.4", rec.get("gross_margin") == 0.4, rec.get("gross_margin"))
    check("去年毛利率（100−70）/100", rec.get("gross_margin_prior") == 0.3, rec.get("gross_margin_prior"))
    check("營益率 25/125", rec.get("operating_margin") == 0.2, rec.get("operating_margin"))
    check("EPS 與去年 EPS", rec.get("eps") == 2.0 and rec.get("eps_prior") == 1.6, rec)
    check("FCF 30−10、利潤率 20/125", rec.get("free_cash_flow") == 20 and rec.get("fcf_margin") == 0.16, rec)
    check("負債比推導（200−150）/200 並寫 warnings",
          rec.get("debt_ratio") == 0.25 and any("推導" in w for w in rec["warnings"]), rec)
    check("去年同期 ±20 天外不算", FIN._prior_end({"2024-12-31": 1, "2023-11-01": 1}, "2024-12-31") is None)
    empty = FIN.compute({"facts": {}})
    check("沒有營收 → missing_fields 含 revenue、不崩潰", "revenue" in empty["missing_fields"] and empty.get("revenue") is None)

    names = {"fields": ["cik", "name", "ticker", "exchange"], "data": [
        [1, "A Corp", "AAA", "Nasdaq"], [1, "A Corp", "AAA2", "Nasdaq"],  # 同 CIK 只取一次
        [2, "B Corp", "BBB", "OTC"], [3, "C Corp", "CCC", "NYSE"], [4, "Taiwan Semi", "TSM", "OTC"]]}
    orig = (FIN.requests.get, FIN.MAX_TICKERS, FIN.OUT_PATH, FIN.get_company_facts, FIN.time.sleep, FIN.MIN_OK_TO_WRITE)
    try:
        FIN.requests.get = lambda *a, **k: FakeResp(names)
        FIN.MAX_TICKERS = 2
        uni = FIN.build_universe()
        tick = [t for t, _, _ in uni]
        check("名冊：OTC 排除、同 CIK 去重、MUST_INCLUDE 補入", tick == ["AAA", "CCC", "TSM"], tick)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "us_financials.json"
            out.write_text('{"old": true}', encoding="utf-8")
            FIN.OUT_PATH = out
            FIN.time.sleep = lambda s: None
            good, stale = facts_payload(yr), facts_payload(date.today().year - 5)

            def fake_facts(cik, use_cache=False, headers=None):
                if cik == 2:
                    return {}
                if cik == 3:
                    raise RuntimeError("boom")
                if cik == 4:
                    return stale
                return good
            FIN.get_company_facts = fake_facts
            FIN.requests.get = lambda *a, **k: FakeResp({"fields": ["cik", "name", "ticker", "exchange"], "data": [
                [1, "A", "AAA", "NYSE"], [2, "B", "BBB", "NYSE"], [3, "C", "CCC", "NYSE"], [4, "D", "DDD", "NYSE"]]})
            FIN.MAX_TICKERS = 10
            FIN.MIN_OK_TO_WRITE = 50
            rc = quiet(FIN.main)
            check("成功 <50 → 回 1、不覆蓋", rc == 1 and json.loads(out.read_text(encoding="utf-8")) == {"old": True})
            FIN.MIN_OK_TO_WRITE = 1
            rc = quiet(FIN.main)
            d = json.loads(out.read_text(encoding="utf-8"))
            e = d.get("errors", {})
            check("門檻達到 → 寫出、成功 1 檔", rc == 0 and list(d.get("financials", {})) == ["AAA"], d.get("coverage"))
            check("404／例外／過期各自分類記 errors",
                  e.get("BBB", "").startswith("no_companyfacts") and e.get("CCC", "").startswith("fetch_or_parse_error")
                  and e.get("DDD", "").startswith("stale_annual_revenue"), e)
            check(".tmp 不殘留", not out.with_suffix(".json.tmp").exists())
            out.write_text('{"old": true}', encoding="utf-8")

            def boom(*a, **k):
                raise RuntimeError("down")
            FIN.requests.get = boom
            rc = quiet(FIN.main)
            check("名冊抓不到 → 回 1、不覆蓋", rc == 1 and json.loads(out.read_text(encoding="utf-8")) == {"old": True})
    finally:
        (FIN.requests.get, FIN.MAX_TICKERS, FIN.OUT_PATH, FIN.get_company_facts, FIN.time.sleep, FIN.MIN_OK_TO_WRITE) = orig


# ───────────── 1dq build_us_scores_v0 ─────────────
def fake_yf(prices: dict | None):
    import pandas as pd
    mod = types.ModuleType("yfinance")

    def download(tickers, **k):
        if prices is None:
            raise RuntimeError("yf down")
        idx = pd.to_datetime(["2026-10-28", "2026-10-29"])
        close = pd.DataFrame({t: [v, v] for t, v in prices.items()}, index=idx)
        return pd.concat({"Close": close}, axis=1)
    mod.download = download
    return mod


def test_scores() -> None:
    print("1dq build_us_scores_v0.py")
    r = SC._rank_pct({"a": 1, "b": 2, "c": 2, "d": None})
    check("同值取平均名次、None 保留", r == {"a": 1 / 3, "b": 2.5 / 3, "c": 2.5 / 3, "d": None}, r)
    sc, _ = SC.pct_score({"a": 1, "b": 2, "c": 3}, higher_better=False)
    check("pct_score 方向反轉（越低越高分）", sc["a"] > sc["c"], sc)
    check("不足 3 檔 → 全 None", SC.pct_score({"a": 1, "b": 2}, True)[0] == {"a": None, "b": None})
    check("EPS 年增正基期", abs(SC.eps_yoy(1.2, 1.0) - 0.2) < 1e-9)
    check("EPS 年增負基期（−1→1 = +2）", SC.eps_yoy(1.0, -1.0) == 2.0, SC.eps_yoy(1.0, -1.0))
    check("EPS 年增 ±200% 上限", SC.eps_yoy(10.0, 1.0) == 2.0)
    check("基期 |≤0.05| → None", SC.eps_yoy(1.0, 0.04) is None)

    def fin_rec(i, **kw):
        base = {"eps": 1 + i * 0.1, "eps_prior": 1.0, "revenue_yoy": 0.01 * i, "gross_margin": 0.3 + i * 0.005,
                "gross_margin_prior": 0.3, "operating_margin": 0.1, "operating_margin_prior": 0.1,
                "fcf_margin": 0.1, "debt_ratio": 0.5, "currency": "USD", "warnings": [], "period_end": "2025-12-31"}
        base.update(kw)
        return base
    fin = {f"T{i:02d}": fin_rec(i) for i in range(55)}
    fin["T00"] = fin_rec(0, currency="TWD")
    fin["T01"] = fin_rec(1, warnings=["IFRS申報（20-F）：EPS為每普通股，非每ADR"])
    fin["T02"] = fin_rec(2, eps=None, eps_prior=None, revenue_yoy=None, gross_margin=None, gross_margin_prior=None,
                         operating_margin=None, operating_margin_prior=None, fcf_margin=None, debt_ratio=None)
    orig = (SC.FIN_PATH, SC.QUOTES_PATH, SC.SIC_PATH, SC.OUT_PATH, sys.modules.get("yfinance"))
    try:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            SC.FIN_PATH, SC.QUOTES_PATH, SC.SIC_PATH, SC.OUT_PATH = t / "f.json", t / "q.json", t / "s.json", t / "o.json"
            SC.OUT_PATH.write_text('{"old": true}', encoding="utf-8")
            rc = quiet(SC.main)
            check("讀不到財報 → 回 1、不覆蓋", rc == 1 and json.loads(SC.OUT_PATH.read_text(encoding="utf-8")) == {"old": True})
            SC.FIN_PATH.write_text(json.dumps({"financials": dict(list(fin.items())[:10])}), encoding="utf-8")
            rc = quiet(SC.main)
            check("財報 <50 檔 → 回 1、不覆蓋", rc == 1 and json.loads(SC.OUT_PATH.read_text(encoding="utf-8")) == {"old": True})

            SC.FIN_PATH.write_text(json.dumps({"financials": fin, "generated_at": "x"}), encoding="utf-8")
            prices = {k: 20.0 for k in fin if k != "T03"}
            sys.modules["yfinance"] = fake_yf(prices)
            rc = quiet(SC.main)
            d = json.loads(SC.OUT_PATH.read_text(encoding="utf-8"))
            st = {s["code"]: s for s in d["stocks"]}
            check("正常寫出 55 檔", rc == 0 and d["meta"]["count"] == 55, d["meta"].get("count"))
            check("非 USD 不算價值", "value" not in st["T00"]["pillars"] and any("幣別" in w for w in st["T00"]["warnings"]))
            check("IFRS 不算價值", "value" not in st["T01"]["pillars"])
            check("無股價不算價值", "value" not in st["T03"]["pillars"] and any("無股價" in w for w in st["T03"]["warnings"]))
            check("有股價有 EPS → 有價值分", "value" in st["T10"]["pillars"])
            check("coverage <0.5 不排名", st["T02"]["rank"] is None and st["T02"]["coverage"] < 0.5, st["T02"].get("coverage"))
            ranks = sorted(s["rank"] for s in d["stocks"] if s["rank"] is not None)
            check("名次連續從 1 開始", ranks == list(range(1, len(ranks) + 1)) and len(ranks) == d["meta"]["ranked_count"])

            sys.modules["yfinance"] = fake_yf(None)
            SC.QUOTES_PATH.write_text(json.dumps({"quotes": {"T10": {"price": 30.0}}}), encoding="utf-8")
            rc = quiet(SC.main)
            d = json.loads(SC.OUT_PATH.read_text(encoding="utf-8"))
            ps = d["meta"]["price_source"]
            check("yfinance 失敗 → 退回 quotes_us、記錯誤",
                  rc == 0 and ps["fallback_used"] == ["T10"] and ps["error"], ps)
    finally:
        SC.FIN_PATH, SC.QUOTES_PATH, SC.SIC_PATH, SC.OUT_PATH = orig[:4]
        if orig[4] is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = orig[4]


# ───────────── 1dr probe_twse_publish_time ─────────────
def test_probe() -> None:
    print("1dr probe_twse_publish_time.py")
    check("民國日期轉換", PR._roc_date_to_iso("1151030") == "2026-10-30")
    check("非 7 位數 → None", PR._roc_date_to_iso("20261030") is None and PR._roc_date_to_iso(None) is None)
    orig = (PR.requests.get, PR.LOG)
    try:
        cases = {
            "env_no": FakeResp({"stat": "很抱歉，沒有符合條件的資料", "data": []}),
            "env_ok": FakeResp({"stat": "OK", "data": [[1], [2]], "date": "20261030"}),
            "list": FakeResp([{"Date": "1151029", "Code": "2330"}]),
            "http": FakeResp(None, 503),
            "nojson": FakeResp(None, 200),
        }
        PR.requests.get = lambda url, **k: cases[url]
        r = PR.probe_one("env_no", "envelope")
        check("envelope「很抱歉」→ 未發布", r["ok"] is False and r["rows"] == 0, r)
        r = PR.probe_one("env_ok", "envelope")
        check("envelope OK 有列 → 已發布", r["ok"] is True and r["rows"] == 2, r)
        r = PR.probe_one("list", "list")
        check("openapi list 取 payload_date", r["ok"] and r["payload_date"] == "2026-10-29", r)
        check("HTTP 503 → 未發布並記碼", PR.probe_one("http", "envelope")["note"] == "HTTP 503")
        check("回應非 JSON → 未發布", PR.probe_one("nojson", "envelope")["note"] == "回應非 JSON")

        with tempfile.TemporaryDirectory() as td:
            PR.LOG = Path(td) / "probe.jsonl"
            check("--report 無檔 → 回 1", quiet(PR.report) == 1)
            lines = [
                {"ts": "2026-10-30T16:00:00+08:00", "query_date": "20261030",
                 "results": {"T86": {"ok": True}, "STOCK_DAY_ALL_OPENAPI": {"ok": True, "payload_date": "2026-10-29"}}},
                {"ts": "2026-10-30T15:30:00+08:00", "query_date": "20261030",
                 "results": {"T86": {"ok": True}}},
                {"ts": "2026-10-30T17:30:00+08:00", "query_date": "20261030",
                 "results": {"STOCK_DAY_ALL_OPENAPI": {"ok": True, "payload_date": "2026-10-30"}}},
            ]
            text = "\n".join(json.dumps(x) for x in lines) + "\n{壞行\n" + json.dumps({"query_date": "20261030"}) + "\n" \
                + json.dumps({"ts": "2026-10-30T18:00:00+08:00", "query_date": "20261030", "results": ["x"]}) + "\n"
            PR.LOG.write_text(text, encoding="utf-8")
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    rc = PR.report()
                crashed = None
            except Exception as e:  # noqa: BLE001
                rc, crashed = None, e
            out = buf.getvalue()
            check("--report 壞行／缺 ts／results 非 dict 都不崩潰", crashed is None and rc == 0, repr(crashed))
            check("T86 最早成功 15:30", "15:30" in out.split("STOCK_DAY_ALL_OPENAPI（管線")[0], out[:400])
            check("openapi payload_date 追上查詢日 17:30", "20261030    17:30" in out, out[-300:])
            run_lines = []
            PR.requests.get = lambda url, **k: FakeResp({"stat": "OK", "data": [[1]]}) if "www" in url else FakeResp([{"Date": "1151030"}])
            PR.LOG.unlink()
            quiet(PR.run_probe)
            run_lines = PR.LOG.read_text(encoding="utf-8").splitlines()
            rec = json.loads(run_lines[0])
            check("run_probe 一輪 append 一行、四個端點", len(run_lines) == 1 and len(rec["results"]) == 4, rec.get("results", {}).keys())
    finally:
        PR.requests.get, PR.LOG = orig


if __name__ == "__main__":
    for fn in (test_fin, test_scores, test_probe):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  ✗ {fn.__name__} 例外：{type(e).__name__}: {e}")
    print(f"\n結果：{ok} 過／{fail} 失敗")
    sys.exit(1 if fail else 0)
