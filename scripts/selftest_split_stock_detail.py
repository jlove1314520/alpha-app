"""自測：個股明細拆檔 `scripts/split_stock_detail.py`（先.一三五-1cx）。

`SRC`／`OUT_DIR`／`EPS_OUT` 換成暫存目錄：零外部請求、不動真實 data/。
確認：每檔小檔內容與整份 stocks[代號] 相同、權證與非法代號不輸出、EPS 摘要只取最後四季、
內容沒變不重寫、整份讀不出來（不存在／損壞／頂層不是物件／stocks 空或型別錯）不刪不清空既有小檔、
且失敗由 `__main__` 包裝降級成警告（exit 0）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "split_stock_detail.py"
_spec = importlib.util.spec_from_file_location("split_stock_detail", SCRIPT)
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


def quarters(n: int) -> list:
    return [{"year": 2025 + i // 4, "quarter": i % 4 + 1, "eps": 1.0 + i, "revenue": 100 + i} for i in range(n)]


STOCKS = {
    "2330": {"name": "台積電", "financials": {"quarters": quarters(6)}, "per": 20.5},
    "0050": {"name": "元大台灣50", "price": [1, 2, 3]},
    "00878": {"name": "國泰永續高股息"},
    "031234": {"name": "某權證"},
    "a/b": {"name": "非法代號"},
    "9999": "不是物件",
}


def setup(root: Path, raw: str | None) -> None:
    B.SRC = root / "stock_detail.json"
    B.OUT_DIR = root / "stock_detail"
    B.EPS_OUT = root / "stock_detail_eps.json"
    if raw is None:
        if B.SRC.exists():
            B.SRC.unlink()
    else:
        B.SRC.write_text(raw, encoding="utf-8")


def run() -> tuple[int | None, Exception | None]:
    try:
        return B.main(), None
    except Exception as e:  # 交給 __main__ 包裝處理；這裡只記下來
        return None, e


def snapshot(d: Path) -> dict:
    return {f.name: (f.read_text(encoding="utf-8"), f.stat().st_mtime) for f in sorted(d.glob("*.json"))} if d.exists() else {}


with tempfile.TemporaryDirectory() as td:
    r = Path(td)
    doc = {"meta": {"generated_at": "2026-10-30T09:00:00+08:00"}, "stocks": STOCKS}

    print("情境一：正常拆檔")
    setup(r, json.dumps(doc, ensure_ascii=False))
    rc, err = run()
    check("exit 0、無例外", rc == 0 and err is None, (rc, err))
    files = {f.stem for f in B.OUT_DIR.glob("*.json")}
    check("只輸出合法非權證代號", files == {"2330", "0050", "00878"}, files)
    same = all(json.loads((B.OUT_DIR / f"{c}.json").read_text(encoding="utf-8")) == STOCKS[c] for c in ("2330", "0050", "00878"))
    check("每檔內容與整份 stocks[代號] 相同", same)
    check("沒有殘留 .tmp", not list(B.OUT_DIR.glob("*.tmp")))
    eps = json.loads(B.EPS_OUT.read_text(encoding="utf-8"))
    q = eps["stocks"]["2330"]["financials"]["quarters"]
    check("EPS 摘要只取最後四季、只留 year/quarter/eps",
          q == [{"year": x["year"], "quarter": x["quarter"], "eps": x["eps"]} for x in quarters(6)[-4:]], q)
    check("EPS 摘要只收有季資料的股票、count 正確", set(eps["stocks"]) == {"2330"} and eps["meta"]["count"] == 1, eps["meta"])
    check("EPS 摘要帶來源 generated_at", eps["meta"]["generated_at"] == "2026-10-30T09:00:00+08:00")

    print("情境二：內容沒變不重寫、有變才重寫")
    old_t = 1_700_000_000
    for f in list(B.OUT_DIR.glob("*.json")) + [B.EPS_OUT]:
        os.utime(f, (old_t, old_t))
    run()
    unchanged = all(abs(f.stat().st_mtime - old_t) < 1 for f in list(B.OUT_DIR.glob("*.json")) + [B.EPS_OUT])
    check("再跑一次：小檔與 EPS 摘要都不重寫", unchanged)
    doc2 = json.loads(json.dumps(doc))
    doc2["stocks"]["0050"]["price"] = [9]
    setup(r, json.dumps(doc2, ensure_ascii=False))
    run()
    check("0050 有變：重寫且內容更新", (B.OUT_DIR / "0050.json").stat().st_mtime > old_t + 1
          and json.loads((B.OUT_DIR / "0050.json").read_text(encoding="utf-8")) == {"name": "元大台灣50", "price": [9]})
    check("2330 沒變：不重寫", abs((B.OUT_DIR / "2330.json").stat().st_mtime - old_t) < 1)

    print("情境三：來源少了某檔 → 不刪舊檔")
    doc3 = json.loads(json.dumps(doc2))
    del doc3["stocks"]["00878"]
    setup(r, json.dumps(doc3, ensure_ascii=False))
    run()
    check("00878 舊小檔保留", (B.OUT_DIR / "00878.json").exists())

    print("情境四：整份讀不出來 → 不刪不清空既有小檔")
    base = snapshot(B.OUT_DIR)
    eps_before = B.EPS_OUT.read_text(encoding="utf-8")
    for label, raw in [("不存在", None), ("損壞 JSON", "{"), ("空檔", ""), ("頂層是陣列", "[1]"),
                       ("stocks 空物件", json.dumps({"stocks": {}})), ("沒有 stocks", json.dumps({"meta": {}})),
                       ("stocks 是陣列", json.dumps({"stocks": [1, 2]}))]:
        setup(r, raw)
        rc, err = run()
        after = snapshot(B.OUT_DIR)
        check(f"{label}：既有小檔原封不動", after == base, (label, set(base) ^ set(after)))
        check(f"{label}：EPS 摘要沒被改寫", B.EPS_OUT.read_text(encoding="utf-8") == eps_before)
        check(f"{label}：回 0 或拋例外交給 __main__ 包裝", rc == 0 or err is not None, (rc, err))

    print("情境五：__main__ 包裝把例外降級成警告（exit 0）")
    src = SCRIPT.read_text(encoding="utf-8")
    tail = src[src.index('if __name__ == "__main__":'):]
    check("__main__ 包 try/except、except 內 sys.exit(0)",
          "try:" in tail and "except Exception" in tail and "sys.exit(0)" in tail.split("except Exception", 1)[1])
    setup(r, "{")
    ns = dict(vars(B))
    ns["__name__"] = "__main__"
    code = compile("\n" + tail, str(SCRIPT), "exec")
    try:
        exec(code, ns)
        rc = "沒有呼叫 sys.exit"
    except SystemExit as e:
        rc = e.code
    except Exception as e:  # noqa: BLE001
        rc = f"未處理例外 {type(e).__name__}"
    check("損壞輸入經 __main__ 包裝 → exit 0", rc == 0, rc)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
