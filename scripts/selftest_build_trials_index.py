"""自測：研究透明度試驗索引 `.github/scripts/build_trials_index.py`（先.一三五-1cn）。

假 `TRIALS_LEDGER.md` 與輸出檔都換成暫存路徑（`selection_bias_ledger.LEDGER` 一併指過去）：零外部請求、不讀也不動真實帳本與 data/。
守住先.八十-3／先.一〇三-15 修過的行為：只收「第一欄純數字＋第二欄日期」的列（FDR 排名表不收）、`\\|` 還原不位移、
判定欄以判定字開頭（備註散文提到別筆 FAIL 不誤判）、共用編號給 uid、事前登記併入結果列、count 與總 N 不等時不寫檔非零退出、
帳本讀不到或解析不出任何列時不覆寫既有輸出。
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
_spec = importlib.util.spec_from_file_location("build_trials_index", ROOT / ".github" / "scripts" / "build_trials_index.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)  # 會把 research/ 放進 sys.path
import selection_bias_ledger as S  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


LEDGER_OK = """# 試驗帳本（假）

| # | 日期 | 軌 | 名稱 | 結果 | 判定 | 備註 |
|---|---|---|---|---|---|---|
| 1 | 2026-09-01 | TW | f_alpha_one | ret 1% | **FAIL** | 無 |
| 2 | 2026-09-02 | TW | f_pipe \\| name | ret 2% | **PASS** | 備註提到別筆 FAIL |
| 3 | 2026-09-03 | US | f_us_three | ret 3% | **FRAMEWORK_CHECK** | 框架驗證 |
| 4 | 2026-09-04 | TW | prereg_four | 事前登記 | **未結案** | 等結果 |
| 5 | 2026-09-05 | TW | f_five_result | 事前登記 #4 結果 | **FAIL** | 依事前登記 #4 |
| 2 | 2026-09-06 | TW | f_dup_two | ret | **CHEAP_PASS** | 共用編號 |

## FDR 重新評分對照表

| 排名 | 試驗 | 名稱 | 新判定 |
|---|---|---|---|
| 1 | #2 | f_pipe | PASS |
| 2 | #1 | f_alpha_one | FAIL |
"""


def run(ledger: Path, out: Path):
    B.LEDGER = ledger
    B.OUT = out
    S.LEDGER = ledger
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：正常帳本（含 FDR 排名表、\\| 跳脫、備註散文 FAIL、框架驗證列、事前登記、共用編號）")
    led = base / "ledger1.md"
    led.write_text(LEDGER_OK, encoding="utf-8")
    out = base / "trials_index.json"
    rc, err = run(led, out)
    check("正常結束 rc=0", rc == 0 and err is None, (rc, err))
    doc = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    rows = doc.get("rows", [])
    check("只收 6 列試驗（FDR 排名表 2 列不收）", doc.get("rows_listed") == 6 and len(rows) == 6, doc.get("rows_listed"))
    byuid = {r["uid"]: r for r in rows}
    r2 = byuid.get("2-1", {})
    check("\\| 還原成 | 且名稱不截斷", r2.get("name") == "f_pipe | name", r2.get("name"))
    check("\\| 之後欄位不位移：軌別仍是 TW", r2.get("track") == "TW", r2.get("track"))
    check("判定欄取粗體開頭那欄（備註提到 FAIL 不誤判）＝PASS", r2.get("verdict") == "PASS", r2.get("verdict"))
    check("日期欄照抄", r2.get("date") == "2026-09-02", r2.get("date"))
    check("共用編號 #2 兩列都保留、uid 2-1／2-2", "2-1" in byuid and "2-2" in byuid and byuid["2-2"].get("verdict") == "CHEAP_PASS", sorted(byuid))
    check("dup_ids＝[2]", doc.get("dup_ids") == [2], doc.get("dup_ids"))
    check("框架驗證列 counted=false", byuid.get("3", {}).get("counted") is False, byuid.get("3"))
    check("事前登記 #4 併入 #5（counted=false、merged_into=5）",
          byuid.get("4", {}).get("counted") is False and byuid.get("4", {}).get("merged_into") == 5, byuid.get("4"))
    check("merged_prereg＝{'4': 5}", doc.get("merged_prereg") == {"4": 5}, doc.get("merged_prereg"))
    # 6 列 −1 框架驗證 −1 事前登記併入 ＝ 4
    check("count＝總 N＝4", doc.get("count") == 4, doc.get("count"))
    _n_rows, n_ref, _m = B.ledger_total()
    check("count 與 selection_bias_ledger 總 N 相同", doc.get("count") == n_ref, (doc.get("count"), n_ref))
    check("排序：編號新到舊", [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True), [r["id"] for r in rows])
    check("帶非投資建議聲明與來源", doc.get("disclaimer") and doc.get("source") == "research/TRIALS_LEDGER.md", doc.get("disclaimer"))

    print("情境二：列數與總 N 對不上 → 不寫檔、非零退出")
    sentinel = '{"keep": "上一份"}'
    out2 = base / "out2.json"
    out2.write_text(sentinel, encoding="utf-8")
    real_total = B.ledger_total
    B.ledger_total = lambda: (99, 99, {})  # 帳本試驗列數不同
    rc, err = run(led, out2)
    check("列數不等 rc≠0 且沒拋例外", rc not in (0, None) and err is None, (rc, err))
    check("列數不等時既有輸出不動", out2.read_text(encoding="utf-8") == sentinel)
    B.ledger_total = lambda: (6, 5, {4: 5})  # 列數相同、總 N 不同
    rc, err = run(led, out2)
    check("總 N 不等 rc≠0 且沒拋例外", rc not in (0, None) and err is None, (rc, err))
    check("總 N 不等時既有輸出不動", out2.read_text(encoding="utf-8") == sentinel)
    B.ledger_total = real_total

    print("情境三：帳本不存在 → 不拋未處理例外、不覆寫既有輸出")
    out3 = base / "out3.json"
    out3.write_text(sentinel, encoding="utf-8")
    rc, err = run(base / "no_such_ledger.md", out3)
    check("帳本不存在 rc≠0 且沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("帳本不存在時既有輸出不動", out3.read_text(encoding="utf-8") == sentinel)

    print("情境四：帳本只有表頭、沒有任何試驗列 → 不用空清單覆寫")
    led4 = base / "ledger4.md"
    led4.write_text("# 空帳本\n\n| # | 日期 | 軌 | 名稱 | 結果 | 判定 | 備註 |\n|---|---|---|---|---|---|---|\n", encoding="utf-8")
    out4 = base / "out4.json"
    out4.write_text(sentinel, encoding="utf-8")
    rc, err = run(led4, out4)
    check("空帳本 rc≠0 且沒拋例外", rc not in (0, None) and err is None, (rc, err))
    check("空帳本時既有輸出不動", out4.read_text(encoding="utf-8") == sentinel)

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
