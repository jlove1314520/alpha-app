"""自測：ADR 溢價 `.github/scripts/compute_adr_premium.py`（先.一三五-1cf）。

`DATA_DIR`／`OUT_PATH` 換成暫存目錄：零外部請求、不讀也不動真實 data/。
App 市場頁 ADR 溢價卡唯一來源，這裡確認：溢價公式、各檔缺價／缺匯率只略過該檔並記原因（不補假值）、
台股收盤 0（無成交）不除以零崩潰、各列帶三邊日期、四檔全算不出來時不覆寫既有輸出。
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
_spec = importlib.util.spec_from_file_location("compute_adr_premium", ROOT / ".github" / "scripts" / "compute_adr_premium.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def setup(d: Path, us=None, tw=None, fx=None) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name, doc in (("quotes_us.json", us), ("quotes_all_tw.json", tw), ("fx.json", fx)):
        if doc is not None:
            (d / name).write_text(json.dumps(doc), encoding="utf-8")


def run(d: Path, out: Path):
    A.DATA_DIR = d
    A.OUT_PATH = out
    try:
        A.main()
        return 0, None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    out = base / "adr_premium.json"

    print("情境一：四檔齊全＋UMC 缺台股價、CHT 台股收盤 0（無成交）")
    d1 = base / "d1"
    setup(d1,
          us={"quotes": {"TSM": {"price": 200.0, "quote_time": "2026-10-29T16:00"}, "UMC": {"price": 8.0},
                         "ASX": {"price": 10.0}, "CHT": {"price": 40.0}}},
          tw={"quotes": {"2330": {"close": 1200.0, "as_of": "2026-10-29"}, "3711": {"close": 160.0, "date": "2026-10-29"},
                         "2412": {"close": 0}}},
          fx={"usd_twd": {"rate": 32.0, "date": "2026-10-29"}})
    rc, err = run(d1, out)
    check("沒有未處理例外（收盤 0 不除以零）", err is None, repr(err))
    check("exit 0", rc == 0, rc)
    doc = json.loads(out.read_text(encoding="utf-8"))
    rows = doc["rows"]
    tsm = rows.get("TSM", {})
    check("TSM 推算台股價＝200×32÷5＝1280", tsm.get("implied_tw_price") == 1280.0, tsm)
    check("TSM 溢價＝(1280−1200)÷1200×100", abs(tsm.get("premium_pct", 0) - 6.667) < 1e-9, tsm.get("premium_pct"))
    check("ASX 比率 2：10×32÷2＝160 → 溢價 0", rows.get("ASX", {}).get("premium_pct") == 0.0, rows.get("ASX"))
    check("TSM 帶三邊日期", tsm.get("us_quote_time") == "2026-10-29T16:00" and tsm.get("tw_quote_date") == "2026-10-29"
          and tsm.get("fx_date") == "2026-10-29", tsm)
    check("ASX 台股日期用 date 欄回退", rows.get("ASX", {}).get("tw_quote_date") == "2026-10-29")
    check("UMC 缺台股價 → 不輸出、記原因", "UMC" not in rows and any(e["ticker"] == "UMC" for e in doc["errors"]))
    check("CHT 收盤 0 → 不輸出、記原因", "CHT" not in rows and any(e["ticker"] == "CHT" for e in doc["errors"]))
    good = out.read_text(encoding="utf-8")

    print("情境二：匯率缺 → 全部算不出來 → 非零退出、不覆寫")
    d2 = base / "d2"
    setup(d2, us={"quotes": {"TSM": {"price": 200.0}}}, tw={"quotes": {"2330": {"close": 1200.0}}}, fx={"usd_twd": {}})
    rc, err = run(d2, out)
    check("沒有未處理例外", err is None, repr(err))
    check("非零退出", rc not in (0, None), rc)
    check("既有輸出未被改", out.read_text(encoding="utf-8") == good)

    print("情境三：三個輸入檔都不存在／損壞 → 非零退出、不覆寫")
    d3 = base / "d3"
    d3.mkdir()
    (d3 / "fx.json").write_text("{壞掉", encoding="utf-8")
    rc, err = run(d3, out)
    check("沒有未處理例外", err is None, repr(err))
    check("非零退出", rc not in (0, None), rc)
    check("既有輸出未被改", out.read_text(encoding="utf-8") == good)

    print("情境四：價格是字串／負數／NaN 不當成有效價")
    d4 = base / "d4"
    setup(d4, us={"quotes": {"TSM": {"price": "200"}, "UMC": {"price": -1}, "ASX": {"price": float("nan")},
                             "CHT": {"price": 40.0}}},
          tw={"quotes": {"2412": {"close": 128.0}}}, fx={"usd_twd": {"rate": 32.0}})
    rc, err = run(d4, out)
    doc4 = json.loads(out.read_text(encoding="utf-8"))
    check("沒有未處理例外", err is None, repr(err))
    check("只剩 CHT", sorted(doc4["rows"]) == ["CHT"], sorted(doc4["rows"]))
    check("CHT 比率 10：40×32÷10＝128 → 溢價 0", doc4["rows"]["CHT"]["premium_pct"] == 0.0)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
