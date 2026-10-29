"""自測：上櫃次日漲跌停價本機歸檔 `scripts/archive_tpex_limit_next.py`（先.一三五-1bn）。

`versions()` 換成合成版本清單、`OUT_DIR` 換暫存目錄：零外部請求、不讀 git、不動真實 research/data/。
模擬 Q／R（paper_17／18）的官方漲跌停判斷讀這個歸檔，這裡確認：同日取最新版、已存在不覆寫、
壞版本略過不中斷、資料日格式不對的版本不會寫到歸檔目錄以外。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import archive_tpex_limit_next as A  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def ver(date, up=10.0, rows=True):
    doc = {"data_date": date, "n": 1}
    if rows:
        doc["rows"] = {"6488": [up, up * 0.8]}
    return json.dumps(doc)


def run(vers, out_dir):
    A.versions = lambda: vers
    A.OUT_DIR = out_dir
    return A.main()


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    out = base / "archive"

    print("情境一：同一資料日多版本 → 取最新（清單最前面）那一版")
    rc = run([("worktree", ver("2026-10-29", 11.0)), ("aaaaaaaaaa", ver("2026-10-29", 10.0)),
              ("bbbbbbbbbb", ver("2026-10-28", 9.0))], out)
    d29 = json.loads((out / "2026-10-29.json").read_text(encoding="utf-8"))
    check("exit 0", rc == 0, rc)
    check("10-29 取 worktree 版", d29["rows"]["6488"][0] == 11.0 and d29["archived_from"] == "worktree", d29)
    check("10-28 有寫", (out / "2026-10-28.json").exists())

    print("情境二：已存在的日期不覆寫")
    run([("cccccccccc", ver("2026-10-29", 99.0))], out)
    d29b = json.loads((out / "2026-10-29.json").read_text(encoding="utf-8"))
    check("10-29 仍是 11.0", d29b["rows"]["6488"][0] == 11.0, d29b)

    print("情境三：壞版本略過、不中斷後面的版本")
    rc = run([("bad1", "{not json"), ("bad2", ver("2026-10-27", rows=False)), ("bad3", ver("")),
              ("bad4", json.dumps(["list"])), ("good", ver("2026-10-26", 8.0))], out)
    check("exit 0", rc == 0, rc)
    check("壞版本都沒寫檔", sorted(p.name for p in out.iterdir()) ==
          ["2026-10-26.json", "2026-10-28.json", "2026-10-29.json"], sorted(p.name for p in out.iterdir()))

    print("情境四：資料日格式不對（含路徑字元）→ 當壞版本，不寫到歸檔目錄以外、不中斷")
    try:
        rc = run([("weird1", ver("2026/10/25")), ("weird2", ver("../escape")), ("weird3", ver(20261024)),
                  ("good", ver("2026-10-23", 7.0))], out)
        crashed = None
    except Exception as e:  # noqa: BLE001
        rc, crashed = None, e
    check("沒有拋例外", crashed is None, repr(crashed))
    check("exit 0", rc == 0, rc)
    check("歸檔目錄外沒有多出檔案", not (base / "escape.json").exists())
    check("後面的好版本照寫", (out / "2026-10-23.json").exists())
    check("歸檔目錄只有 YYYY-MM-DD.json", all(len(p.stem) == 10 for p in out.iterdir()),
          sorted(p.name for p in out.iterdir()))

    print("情境五：沒有任何版本 → exit 0、建目錄")
    out2 = base / "empty"
    check("exit 0", run([], out2) == 0)
    check("目錄已建立", out2.is_dir())

print(f"\n結果：{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
