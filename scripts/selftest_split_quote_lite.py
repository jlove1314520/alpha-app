"""自測：首頁小檔拆檔 `scripts/split_quote_lite.py`（先.一三五-1cy）。

`ROOT`／`DATA`／`OUT_DIR`／`SHARD_DIR` 換成暫存目錄：零外部請求、不動真實 data/。
確認：熱門代號拆單檔、其餘進前兩碼（00 開頭前三碼）分片，內容與三份來源原樣一致；
某份來源沒有這一檔就不放那個欄位；內容沒變不重寫；不再熱門／不在來源的檔會移除；
三份來源任一份讀不到／損壞／缺欄位 → 不寫、不刪、不覆寫既有小檔，且失敗由 `__main__` 包裝降級成警告（exit 0）。
另印出觀察（不計成敗）：自選股代號已不在任何來源時，其單檔是否被保留。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "split_quote_lite.py"
_spec = importlib.util.spec_from_file_location("split_quote_lite", SCRIPT)
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


SPARKS = {"2330": [1, 2, 3], "2317": [4, 5], "0050": [6], "00878": [7], "TAIEX": [8], "1101": [9]}
QUOTES = {"2330": {"c": 1000}, "2317": {"c": 200}, "0050": {"c": 190}, "00878": {"c": 22}, "TAIEX": {"c": 23000},
          "6505": {"c": 50}}
COMPS = {"2330": {"name": "台積電"}, "2317": {"name": "鴻海"}, "0050": {"name": "元大台灣50"}, "6505": {"name": "台塑化"},
         "1101": {"name": ""}}


def setup(root: Path, sp=None, qa=None, ci=None, watch=("2330",), raw: dict | None = None) -> None:
    B.ROOT = root
    B.DATA = root / "data"
    B.OUT_DIR = B.DATA / "quote_lite"
    B.SHARD_DIR = B.OUT_DIR / "p"
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir(parents=True, exist_ok=True)
    docs = {
        "sparklines.json": {"meta": {"data_asof": "2026-10-29"}, "sparklines": SPARKS if sp is None else sp,
                            "stale_dates": {"2317": "2026-10-20"}},
        "quotes_all_tw.json": {"quotes": QUOTES if qa is None else qa},
        "company_info.json": {"companies": COMPS if ci is None else ci},
    }
    for name, d in docs.items():
        p = root / "data" / name
        if raw and name in raw:
            if raw[name] is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_text(raw[name], encoding="utf-8")
        else:
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (root / "research" / ".live_watchlist.json").write_text(json.dumps({"codes": list(watch)}), encoding="utf-8")
    (root / "data" / "picks_ledger.json").write_text(json.dumps(
        {"snapshots": [{"snapshot_date": date.today().isoformat(), "picks": [{"code": "2317"}]}]}), encoding="utf-8")


def run():
    try:
        return B.main(), None
    except Exception as e:  # 交給 __main__ 包裝處理
        return None, e


def rd(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def snapshot(d: Path) -> dict:
    return {str(f.relative_to(d)): (f.read_text(encoding="utf-8"), f.stat().st_mtime) for f in sorted(d.rglob("*.json"))} if d.exists() else {}


with tempfile.TemporaryDirectory() as td:
    r = Path(td)

    print("情境一：正常拆檔（熱門單檔＋分片）")
    setup(r)
    rc, err = run()
    check("exit 0、無例外", rc == 0 and err is None, (rc, err))
    singles = {f.stem for f in B.OUT_DIR.glob("*.json")}
    check("熱門＝自選股 2330＋近 30 日進榜 2317＋白名單 0050＋指數 TAIEX", singles == {"2330", "2317", "0050", "TAIEX"}, singles)
    shards = {f.stem for f in B.SHARD_DIR.glob("*.json")}
    check("非熱門進分片：00878→008、6505→65、1101→11", shards == {"008", "65", "11"}, shards)
    check("2330 單檔內容＝三份來源原樣",
          rd(B.OUT_DIR / "2330.json") == {"asof": "2026-10-29", "s": [1, 2, 3], "a": {"c": 1000}, "n": "台積電"})
    check("2317 帶 stale_dates 的 sd", rd(B.OUT_DIR / "2317.json").get("sd") == "2026-10-20")
    check("TAIEX 沒有公司名 → 不放 n 欄（不寫成空）", "n" not in rd(B.OUT_DIR / "TAIEX.json") and rd(B.OUT_DIR / "TAIEX.json")["a"] == {"c": 23000})
    s65 = rd(B.SHARD_DIR / "65.json")
    check("6505 沒有走勢 → 分片不放 s 欄", s65 == {"6505": {"asof": "2026-10-29", "a": {"c": 50}, "n": "台塑化"}}, s65)
    s11 = rd(B.SHARD_DIR / "11.json")
    check("1101 沒報價、公司名空字串 → 只有 asof＋s", s11 == {"1101": {"asof": "2026-10-29", "s": [9]}}, s11)
    check("00878 分片內容一致", rd(B.SHARD_DIR / "008.json") == {"00878": {"asof": "2026-10-29", "s": [7], "a": {"c": 22}}})
    check("沒有殘留 .tmp", not list(B.OUT_DIR.rglob("*.tmp")))

    print("情境二：內容沒變不重寫")
    old_t = 1_700_000_000
    allf = list(B.OUT_DIR.rglob("*.json"))
    for f in allf:
        os.utime(f, (old_t, old_t))
    run()
    check("再跑一次：所有小檔都不重寫", all(abs(f.stat().st_mtime - old_t) < 1 for f in allf))

    print("情境三：不再熱門／不在來源 → 移除")
    qa = dict(QUOTES)
    del qa["6505"]
    ci = dict(COMPS)
    del ci["6505"]
    setup(r, qa=qa, ci=ci, watch=())
    run()
    check("2330 不再是自選股 → 單檔移除、改進分片 23", not (B.OUT_DIR / "2330.json").exists()
          and "2330" in rd(B.SHARD_DIR / "23.json"))
    check("6505 不在任何來源 → 分片 65 移除", not (B.SHARD_DIR / "65.json").exists())

    print("情境四：任一份來源讀不到／損壞／缺欄位 → 不寫不刪不覆寫")
    setup(r)
    run()
    base = snapshot(B.OUT_DIR)
    cases = [
        ("sparklines 不存在", {"raw": {"sparklines.json": None}}),
        ("quotes_all_tw 不存在", {"raw": {"quotes_all_tw.json": None}}),
        ("company_info 不存在", {"raw": {"company_info.json": None}}),
        ("sparklines 損壞", {"raw": {"sparklines.json": "{"}}),
        ("quotes_all_tw 空檔", {"raw": {"quotes_all_tw.json": ""}}),
        ("company_info 頂層陣列", {"raw": {"company_info.json": "[1]"}}),
        ("sparklines 空物件", {"sp": {}}),
        ("quotes 空物件", {"qa": {}}),
        ("companies 是陣列", {"raw": {"company_info.json": json.dumps({"companies": [1]})}}),
        ("quotes 是陣列", {"raw": {"quotes_all_tw.json": json.dumps({"quotes": [1]})}}),
    ]
    for label, kw in cases:
        setup(r, **kw)
        rc, err = run()
        after = snapshot(B.OUT_DIR)
        check(f"{label}：既有小檔原封不動", after == base, (label, set(base) ^ set(after)))
        check(f"{label}：回 0 或拋例外交給 __main__ 包裝", rc == 0 or err is not None, (rc, err))

    print("情境五：__main__ 包裝把例外降級成警告（exit 0）")
    src = SCRIPT.read_text(encoding="utf-8")
    tail = src[src.index('if __name__ == "__main__":'):]
    setup(r, raw={"sparklines.json": "{"})
    ns = dict(vars(B))
    ns["__name__"] = "__main__"
    try:
        exec(compile("\n" + tail, str(SCRIPT), "exec"), ns)
        rc = "沒有呼叫 sys.exit"
    except SystemExit as e:
        rc = e.code
    except Exception as e:  # noqa: BLE001
        rc = f"未處理例外 {type(e).__name__}"
    check("損壞輸入經 __main__ 包裝 → exit 0", rc == 0, rc)
    check("包裝後既有小檔仍原封不動", snapshot(B.OUT_DIR) == base)

    print("觀察（不計成敗）：自選股代號已不在任何來源")
    sp = dict(SPARKS)
    del sp["2330"]
    qa = dict(QUOTES)
    del qa["2330"]
    ci = dict(COMPS)
    del ci["2330"]
    setup(r, sp=sp, qa=qa, ci=ci, watch=("2330",))
    run()
    kept = (B.OUT_DIR / "2330.json").exists()
    print(f"  · 2330 單檔{'仍保留（舊價格留著，與 docstring「已不在任何來源裡的代號…刪掉單檔」不一致）' if kept else '已移除'}")

    print("情境：company_info 的 companies 是空物件（先.一三五-1dd）")
    setup(r)
    run()
    before = snapshot(B.OUT_DIR)
    setup(r, ci={})
    rc, err = run()
    check("companies 空 → 中止、無例外", rc == 0 and err is None, (rc, err))
    check("companies 空 → 既有小檔原封不動（公司名不被整批拿掉）",
          snapshot(B.OUT_DIR) == before and "n" in rd(B.OUT_DIR / "0050.json"))

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
