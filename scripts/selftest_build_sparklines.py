"""自測：全市場走勢線 `.github/scripts/build_sparklines.py`（先.一三五-1cd）。

`PRICE_HISTORY_PATH`／`OUT_PATH` 換成暫存檔：零外部請求、不讀也不動真實 data/。
App 自選股／榜單走勢線唯一來源，這裡確認：最多切 20 天、順序舊到新、缺價（None／0／NaN）不補假值、
單日列不輸出、落後股票照常輸出並記 stale_dates、讀不到來源／來源損壞／來源是空的都不覆寫既有輸出。
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
_spec = importlib.util.spec_from_file_location("build_sparklines", ROOT / ".github" / "scripts" / "build_sparklines.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
B.PHS._read.__defaults__ = (1,)  # 損壞情境不要重試 5 次空等

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def days(n: int, start: int = 1) -> list[str]:
    return [f"2026-10-{d:02d}" for d in range(start, start + n)]


def run(src: Path, out: Path):
    B.PRICE_HISTORY_PATH = src
    B.OUT_PATH = out
    try:
        B.main()
        return 0
    except SystemExit as e:
        return e.code if e.code is not None else 0


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    src = base / "price_history.json"
    out = base / "sparklines.json"

    d25 = days(25)
    prices = {
        # 上市、25 天 → 只取最後 20 天
        "2330": [{"date": d, "close": 1000.0 + i} for i, d in enumerate(d25)],
        # 上櫃代號、停牌缺日（中間少 10-10～10-14）、末日同最大日
        "6488": [{"date": d, "close": 500.0 + i} for i, d in enumerate(d25) if not ("2026-10-10" <= d <= "2026-10-14")],
        # 價格 None／0（no_trade）／NaN 夾在中間
        "3008": [{"date": d, "close": (None if i == 21 else 0 if i == 22 else float("nan") if i == 23 else 2000.0 + i)}
                 for i, d in enumerate(d25)],
        # 單日列 → 畫不出線，不輸出
        "9999": [{"date": "2026-10-25", "close": 10.0}],
        # 空列
        "8888": [],
        # 落後（最後一筆 10-20）→ 照常輸出、記 stale_dates
        "1101": [{"date": d, "close": 30.0 + i} for i, d in enumerate(days(20))],
    }
    src.write_text(json.dumps({"meta": {}, "prices": prices}), encoding="utf-8")

    print("情境一：正常切出")
    rc = run(src, out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    sp = doc["sparklines"]
    check("exit 0", rc == 0, rc)
    check("2330 只取 20 天", len(sp["2330"]) == 20, len(sp.get("2330", [])))
    check("2330 舊到新、最後一點＝最後收盤", sp["2330"][0] == 1005.0 and sp["2330"][-1] == 1024.0, sp["2330"][:2])
    check("2330 遞增（順序沒反）", sp["2330"] == sorted(sp["2330"]))
    check("6488 上櫃代號有輸出、停牌缺日不補（20 列裡只 20 筆實際列）",
          sp.get("6488") == [500.0 + i for i, d in enumerate(d25) if not ("2026-10-10" <= d <= "2026-10-14")][-20:],
          sp.get("6488"))
    check("3008 缺價不補假值（None／0／NaN 被丟掉、不填前值）",
          sp.get("3008") == [2000.0 + i for i in range(5, 25) if i not in (21, 22, 23)], sp.get("3008"))
    check("9999 單日列不輸出", "9999" not in sp)
    check("8888 空列不輸出", "8888" not in sp)
    check("略過數＝2", doc["meta"]["skipped_too_short"] == 2, doc["meta"])
    check("data_asof＝最大日期", doc["meta"]["data_asof"] == "2026-10-25", doc["meta"].get("data_asof"))
    check("1101 落後照常輸出", len(sp.get("1101", [])) == 20)
    check("stale_dates 只記 1101", doc["stale_dates"] == {"1101": "2026-10-20"}, doc["stale_dates"])
    check("輸出值全是正有限數", all(isinstance(v, float) and v == v and v > 0 for a in sp.values() for v in a))
    good = out.read_text(encoding="utf-8")

    print("情境二：來源不存在 → 非零退出、不覆寫")
    rc = run(base / "nope.json", out)
    check("非零退出", rc not in (0, None), rc)
    check("既有輸出未被改", out.read_text(encoding="utf-8") == good)

    print("情境三：來源 JSON 損壞 → 非零退出（不是未處理例外）、不覆寫")
    bad = base / "bad" / "price_history.json"
    bad.parent.mkdir()
    bad.write_text('{"meta": {}, "prices": {"2330": [', encoding="utf-8")
    try:
        rc = run(bad, out)
        crashed = None
    except Exception as e:  # noqa: BLE001
        rc, crashed = None, e
    check("沒有未處理例外", crashed is None, repr(crashed))
    check("非零退出", rc not in (0, None), rc)
    check("既有輸出未被改", out.read_text(encoding="utf-8") == good)

    print("情境四：來源 prices 為空／全都畫不出線 → 非零退出、不寫空檔")
    for name, pr in (("空 prices", {}), ("全單日列", {"2330": [{"date": "2026-10-25", "close": 1.0}]})):
        empty = base / name / "price_history.json"
        empty.parent.mkdir()
        empty.write_text(json.dumps({"meta": {}, "prices": pr}), encoding="utf-8")
        rc = run(empty, out)
        check(f"{name}：非零退出", rc not in (0, None), rc)
        check(f"{name}：既有輸出未被改", out.read_text(encoding="utf-8") == good)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
