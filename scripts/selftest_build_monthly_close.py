"""自測：個股月底收盤累積 `scripts/build_monthly_close.py`（先.一三五-1cr）。

`OUT` 換暫存檔、`price_history_store` 換假物件、「今天」固定 2026-10-30，零外部請求、不讀也不動真實 data/。
確認：只收「市場當月最後交易日」有收盤的檔（月中收盤不冒充月底、零星舊列不算月底）、同月以新算為準、保留 24 個月、
當月未結束標 partial_month、內容沒變不重寫、price_history 讀不到不動既有檔、既有檔讀不出來不覆寫已累積月份。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime as _dt
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_monthly_close", ROOT / "scripts" / "build_monthly_close.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class FixedNow(_dt):
    @classmethod
    def now(cls, tz=None):
        return _dt(2026, 10, 30, 10, 0, tzinfo=tz)


M.datetime = FixedNow


class FakePHS:
    def __init__(self, prices=None, exc: Exception | None = None) -> None:
        self.prices, self.exc = prices, exc

    def load(self, path, codes=None):  # noqa: ARG002
        if self.exc:
            raise self.exc
        return {"prices": self.prices}


def market(n: int = 520) -> dict:
    """n 檔填充股：9 月最後交易日 09-30、10 月目前 10-29；另有零星舊列 2019-05-31 只有少數檔。"""
    p = {}
    for i in range(n):
        p[f"9{i:03d}"] = [{"date": "2026-09-15", "close": 10.0}, {"date": "2026-09-30", "close": 11.0},
                          {"date": "2026-10-29", "close": 12.0}]
    return p


def run(out: Path, phs: FakePHS):
    M.OUT = out
    M.PHS = phs
    try:
        return M.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    out = base / "monthly_close.json"

    print("情境一：正常累積（含停牌缺月底、零星舊列、既有月份、超過 24 個月）")
    p = market()
    p["2330"] = [{"date": "2019-05-31", "close": 240.0}, {"date": "2026-09-30", "close": 1300.0},
                 {"date": "2026-10-29", "close": 1450.0}]
    p["1101"] = [{"date": "2026-09-15", "close": 30.0}, {"date": "2026-10-29", "close": 31.0}]  # 9/30 停牌
    p["2454"] = [{"date": "2026-09-30", "close": None}, {"date": "2026-10-29", "close": 1500.0}]  # 9/30 收盤缺
    old_months = {f"{2024 + (k // 12)}-{k % 12 + 1:02d}": float(k) for k in range(0, 32)}  # 2024-01～2026-08
    old_months["2026-09"] = 999.0  # 同月份舊值要被新算的蓋過
    out.write_text(json.dumps({"meta": {}, "closes": {"2330": old_months, "8888": {"2026-08": 50.0}}}), encoding="utf-8")
    rc, err = run(out, FakePHS(p))
    check("rc=0 不拋例外", rc == 0 and err is None, (rc, err))
    doc = json.loads(out.read_text(encoding="utf-8"))
    c = doc["closes"]
    check("2330：9 月＝09-30 收盤 1300（同月新算蓋舊值 999）", c["2330"].get("2026-09") == 1300.0, c["2330"].get("2026-09"))
    check("2330：10 月＝目前最後交易日 10-29 收盤", c["2330"].get("2026-10") == 1450.0)
    check("零星舊列 2019-05 不算月底（不足 500 檔）", "2019-05" not in c["2330"])
    check("保留最近 24 個月", len(c["2330"]) == 24 and min(c["2330"]) == "2024-11", (len(c["2330"]), min(c["2330"])))
    check("1101 9/30 停牌：9 月不收（月中 09-15 不冒充月底）", "2026-09" not in c.get("1101", {}) and c["1101"].get("2026-10") == 31.0, c.get("1101"))
    check("2454 9/30 收盤缺：9 月不收、不補假值", "2026-09" not in c.get("2454", {}) and c["2454"].get("2026-10") == 1500.0, c.get("2454"))
    check("price_history 沒有的舊代號 8888 已累積月份保留", c.get("8888") == {"2026-08": 50.0}, c.get("8888"))
    check("last_trading_day＝2026-10-29、partial_month＝2026-10", doc["meta"]["last_trading_day"] == "2026-10-29" and doc["meta"]["partial_month"] == "2026-10", doc["meta"])

    print("情境二：內容沒變不重寫")
    before = out.read_text(encoding="utf-8")
    mt = out.stat().st_mtime_ns
    rc, err = run(out, FakePHS(p))
    check("重跑內容相同、檔案沒被重寫", rc == 0 and out.read_text(encoding="utf-8") == before and out.stat().st_mtime_ns == mt)

    print("情境三：月份已結束 → partial_month＝None")
    p3 = market()
    for rows in p3.values():
        rows.pop()  # 只到 9 月
    out3 = base / "o3.json"
    rc, err = run(out3, FakePHS(p3))
    d3 = json.loads(out3.read_text(encoding="utf-8"))
    check("最後交易日在上個月 → partial_month 是 None", d3["meta"]["partial_month"] is None and d3["meta"]["last_trading_day"] == "2026-09-30", d3["meta"])

    sentinel = json.dumps({"meta": {}, "closes": {"2330": {"2025-01": 1.0}}})

    print("情境四：price_history 讀不到 → 既有檔不動")
    out4 = base / "o4.json"
    out4.write_text(sentinel, encoding="utf-8")
    rc, err = run(out4, FakePHS(exc=OSError("沒有檔")))
    check("讀不到 price_history 不拋例外、既有檔不動", err is None and out4.read_text(encoding="utf-8") == sentinel, (rc, err))

    print("情境五：既有 monthly_close.json 讀不出來 → 不覆寫已累積月份")
    out5 = base / "o5.json"
    out5.write_text("<<<<<<< HEAD\n" + sentinel, encoding="utf-8")
    rc, err = run(out5, FakePHS(market()))
    check("既有檔損壞不拋未處理例外", err is None, err)
    check("既有檔損壞時原檔不動（不用只剩近幾個月的新檔蓋掉）", out5.read_text(encoding="utf-8").startswith("<<<<<<< HEAD"))

    print("情境六：既有檔不存在 → 正常建立")
    out6 = base / "o6.json"
    rc, err = run(out6, FakePHS(market()))
    check("首次建立 rc=0、有 520 檔", rc == 0 and out6.exists() and len(json.loads(out6.read_text(encoding="utf-8"))["closes"]) == 520, (rc, err))

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
