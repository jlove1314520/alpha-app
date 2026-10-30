"""自測：美股財報日曆 `.github/scripts/fetch_earnings_calendar.py`（先.一三五-1cp）。

`yf` 換成假模組（零外部請求）、`OUT_PATH` 換暫存檔，不讀也不動真實 data/。
確認：calendar 單一日期／日期區間／空值三種形狀、盤前盤後推估（含無歷史、只有估計、推估拋錯）、
單檔失敗不拖垮其他檔並記進 errors、估計值是 NaN 時寫 null 不讓整份寫檔失敗、全部失敗不覆寫既有輸出。
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("fetch_earnings_calendar", ROOT / ".github" / "scripts" / "fetch_earnings_calendar.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def hist(rows: list[tuple[str, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(t).tz_localize("America/New_York") for t, _ in rows])
    return pd.DataFrame({"Reported EPS": [v for _, v in rows]}, index=idx)


class FakeYF:
    """依代號回固定 calendar／歷史；值是 Exception 就拋出。"""

    def __init__(self, cals: dict, hists: dict) -> None:
        self.cals, self.hists, self.calls = cals, hists, []
        outer = self

        class Ticker:
            def __init__(self, tk):
                self.tk = tk
                outer.calls.append(tk)

            def get_calendar(self):
                v = outer.cals.get(self.tk, {})
                if isinstance(v, Exception):
                    raise v
                return v

            def get_earnings_dates(self, limit=4):  # noqa: ARG002
                v = outer.hists.get(self.tk)
                if isinstance(v, Exception):
                    raise v
                return v

        self.Ticker = Ticker


def run(fake: FakeYF, out: Path):
    E.yf = fake
    E.OUT_PATH = out
    try:
        return E.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：六檔各種形狀")
    E.US_TICKERS = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN"]
    fake = FakeYF(
        cals={
            "NVDA": {"Earnings Date": [date(2026, 11, 19)], "Earnings Average": 1.25, "Revenue Average": 5.4e10},
            "AAPL": {"Earnings Date": [date(2026, 10, 29), date(2026, 11, 3)], "Earnings Average": float("nan")},
            "MSFT": {"Earnings Date": []},
            "TSM": {},
            "GOOGL": RuntimeError("Yahoo 429"),
            "AMZN": {"Earnings Date": [date(2026, 10, 30)], "Earnings Average": 1.1},
        },
        hists={
            "NVDA": hist([("2026-11-19 16:20", float("nan")), ("2026-08-27 16:20", 1.05)]),
            "AAPL": hist([("2026-07-30 08:30", 1.4)]),
            "AMZN": ValueError("歷史壞掉"),
        },
    )
    out = base / "earnings_calendar.json"
    rc, err = run(fake, out)
    check("正常結束不拋例外", err is None and rc in (None, 0), (rc, err))
    doc = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    ea = doc.get("earnings", {})
    n = ea.get("NVDA", {})
    check("單一日期：next_earnings_date＝2026-11-19、range＝None", n.get("next_earnings_date") == "2026-11-19" and n.get("next_earnings_date_range") is None, n)
    check("略過尚未公布（NaN）那筆，用最近一次已公布 16:20 → post", n.get("estimated_session") == "post" and "2026-08-27" in n.get("session_basis", ""), n)
    check("EPS／營收估計照抄", n.get("eps_estimate") == 1.25 and n.get("revenue_estimate") == 5.4e10, n)
    a = ea.get("AAPL", {})
    check("日期區間：取第一天、range 兩天", a.get("next_earnings_date") == "2026-10-29" and a.get("next_earnings_date_range") == ["2026-10-29", "2026-11-03"], a)
    check("歷史 08:30 → pre", a.get("estimated_session") == "pre", a)
    check("估計值 NaN → 寫 null（不寫 NaN、不讓整份失敗）", "AAPL" in ea and a.get("eps_estimate") is None, a)
    check("空日期清單／沒有欄位 → 不輸出該檔（不補假值）", "MSFT" not in ea and "TSM" not in ea, sorted(ea))
    check("get_calendar 拋錯 → 只略過該檔", "GOOGL" not in ea and "AMZN" in ea, sorted(ea))
    z = ea.get("AMZN", {})
    check("推估拋錯 → unknown 並寫原因", z.get("estimated_session") == "unknown" and "推估失敗" in z.get("session_basis", ""), z)
    check("coverage＝3/6 檔", doc.get("meta", {}).get("coverage") == "3/6 檔", doc.get("meta"))
    check("盤前盤後推估免責聲明在 meta", "推估" in doc.get("meta", {}).get("session_disclaimer", ""))
    txt = out.read_text(encoding="utf-8") if out.exists() else ""
    check("輸出是合法 JSON（無 NaN）", "NaN" not in txt and txt != "")

    print("情境二：沒有歷史紀錄")
    E.US_TICKERS = ["NVDA"]
    fake2 = FakeYF({"NVDA": {"Earnings Date": [date(2026, 11, 19)]}}, {"NVDA": None})
    rc, err = run(fake2, base / "o2.json")
    d2 = json.loads((base / "o2.json").read_text(encoding="utf-8")).get("earnings", {}).get("NVDA", {}) if (base / "o2.json").exists() else {}
    check("無歷史 → unknown", d2.get("estimated_session") == "unknown" and "無歷史" in d2.get("session_basis", ""), d2)

    print("情境三：全部失敗 → 不覆寫既有輸出")
    E.US_TICKERS = ["NVDA", "AAPL"]
    out3 = base / "o3.json"
    sentinel = '{"keep": "上一份"}'
    out3.write_text(sentinel, encoding="utf-8")
    rc, err = run(FakeYF({"NVDA": RuntimeError("斷線"), "AAPL": {}}, {}), out3)
    check("全部失敗不拋未處理例外", err is None, err)
    check("全部失敗時既有輸出不動", out3.read_text(encoding="utf-8") == sentinel)

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
