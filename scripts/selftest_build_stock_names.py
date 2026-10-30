"""自測：搜尋用名稱清單 `scripts/build_stock_names.py`（先.一三五-1cs）。

`DATA`／`OUT` 換成暫存目錄，零外部請求、不讀也不動真實 data/。
確認：台股只取名稱與產業且濾掉權證、美股兩來源合併去重（SIC 名稱與產業優先）、內容沒變不重寫、
台股來源讀不到不覆寫、美股任一來源讀不到時美股沿用上一版（不寫成殘缺或空清單）。
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
_spec = importlib.util.spec_from_file_location("build_stock_names", ROOT / "scripts" / "build_stock_names.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


COMP = {"companies": {
    "2330": {"name": "台積電", "industry": "半導體業", "website": "https://x"},
    "0050": {"name": "元大台灣50"},
    "00878": {"name": "國泰永續高股息", "industry": "ETF"},
    "030001": {"name": "某權證"},  # 6 碼純數字＝權證，濾掉
    "123": {"name": "太短"},
    "9999": {"name": ""},
}}
USF = {"financials": {"AAPL": {"name": "Apple Inc. Common Stock"}, "TSM": {"name": "Taiwan Semi"}, "X": {}}}
SIC = {"tickers": {"TSM": {"entity_name": "TAIWAN SEMICONDUCTOR MFG", "sic_description": "Semiconductors"},
                   "NVDA": {"entity_name": "NVIDIA CORP"}}}


def setup(d: Path, comp=COMP, usf=USF, sic=SIC) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name, doc in (("company_info.json", comp), ("us_financials.json", usf), ("us_sic.json", sic)):
        p = d / name
        if doc is None:
            p.unlink(missing_ok=True)
        elif isinstance(doc, str):
            p.write_text(doc, encoding="utf-8")
        else:
            p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def run(d: Path):
    B.DATA = d
    B.OUT = d / "stock_names.json"
    B.FAILED.clear()
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    d = base / "d"

    print("情境一：正常產生")
    setup(d)
    rc, err = run(d)
    check("rc=0 不拋例外", rc == 0 and err is None, (rc, err))
    doc = json.loads((d / "stock_names.json").read_text(encoding="utf-8"))
    check("台股：只留 4～6 碼且非 6 碼純數字、有名稱的（0050／00878／2330）", [r[0] for r in doc["tw"]] == ["0050", "00878", "2330"], doc["tw"])
    check("台股：只取 [代號, 名稱, 產業]，沒產業給空字串", doc["tw"][2] == ["2330", "台積電", "半導體業"] and doc["tw"][0] == ["0050", "元大台灣50", ""], doc["tw"])
    us = {r[0]: r for r in doc["us"]}
    check("美股兩來源合併去重：AAPL／NVDA／TSM 各一列", sorted(us) == ["AAPL", "NVDA", "TSM"] and len(doc["us"]) == 3, doc["us"])
    check("SEC 名稱去掉 Common Stock 尾巴", us["AAPL"][1] == "Apple Inc.", us["AAPL"])
    check("同代號以 SIC 名稱與產業為準", us["TSM"] == ["TSM", "TAIWAN SEMICONDUCTOR MFG", "Semiconductors"], us["TSM"])
    check("meta 計數正確", doc["meta"]["tw_count"] == 3 and doc["meta"]["us_count"] == 3, doc["meta"])

    print("情境二：內容沒變不重寫")
    mt = (d / "stock_names.json").stat().st_mtime_ns
    before = (d / "stock_names.json").read_text(encoding="utf-8")
    rc, err = run(d)
    check("重跑檔案沒被重寫", rc == 0 and (d / "stock_names.json").stat().st_mtime_ns == mt and (d / "stock_names.json").read_text(encoding="utf-8") == before)

    print("情境三：台股來源讀不到 → 不覆寫")
    setup(d, comp="{壞掉")
    rc, err = run(d)
    check("台股來源損壞不拋例外、既有檔不動", err is None and (d / "stock_names.json").read_text(encoding="utf-8") == before, (rc, err))
    setup(d, comp=None)
    rc, err = run(d)
    check("台股來源不存在不拋例外、既有檔不動", err is None and (d / "stock_names.json").read_text(encoding="utf-8") == before, (rc, err))

    print("情境四：美股兩來源都讀不到 → 美股沿用上一版、台股照常更新")
    comp2 = json.loads(json.dumps(COMP))
    comp2["companies"]["2454"] = {"name": "聯發科", "industry": "半導體業"}
    setup(d, comp=comp2, usf=None, sic="<<<<<<< HEAD")
    rc, err = run(d)
    doc4 = json.loads((d / "stock_names.json").read_text(encoding="utf-8"))
    check("美股沿用上一版 3 檔（不寫成空清單）", err is None and doc4["us"] == doc["us"] and doc4["meta"]["us_count"] == 3, doc4.get("us"))
    check("台股照常更新（新增 2454）", "2454" in [r[0] for r in doc4["tw"]], doc4["tw"])

    print("情境五：美股只有一個來源讀不到 → 也沿用上一版（不寫殘缺清單）")
    setup(d, usf=USF, sic=None)
    rc, err = run(d)
    doc5 = json.loads((d / "stock_names.json").read_text(encoding="utf-8"))
    check("SIC 讀不到：美股沿用上一版（NVDA 不消失）", err is None and "NVDA" in [r[0] for r in doc5["us"]], doc5.get("us"))

    print("情境六：沒有上一版時美股來源讀不到 → 照現有寫（台股不受影響）")
    d6 = base / "d6"
    setup(d6, usf=None, sic=None)
    rc, err = run(d6)
    doc6 = json.loads((d6 / "stock_names.json").read_text(encoding="utf-8"))
    check("無上一版：台股照寫、美股空", rc == 0 and len(doc6["tw"]) == 3 and doc6["us"] == [], doc6)

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
