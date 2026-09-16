# -*- coding: utf-8 -*-
"""稽核管線自檢（2026-09-17 總司令裁示【記一筆】：監控工具自己也要被監控）。

**為什麼需要這支**：2026-09-10 commit `52ab79a7` 誤刪 `data_audit.py` 的
`TWSE_COMPANY` 常數，導致 `build_listed_universe.py` 第一步就
`ImportError`，`audit.yml` 連續一週（09-10~09-17）每次觸發都全滅——
但 `data/audit_report.json` 本身完全沒有留下任何紀錄，因為
`data_audit.py` 根本沒機會跑到寫檔那一步，只有去查 `gh run list` 才看
得到。稽核本來是用來抓別人靜默停擺的，結果自己靜默停擺卻沒有任何機制
記錄下來——這支就是補這個盲點。

**設計原則：極簡，只用標準函式庫，不 import 任何專案自己的模組去做
「檢查」**——如果連自我檢查都要 import 專案模組，那個模組壞掉時自我
檢查本身也會一起死，等於沒做。改用 `subprocess` 開一個乾淨的
`python -c` 子行程去試 import，子行程掛掉不會拖累這支腳本本身，
也不會拖累外層 workflow 繼續跑後面的步驟（`main()` 永遠 exit 0）。

**用法**：`python scripts/audit_preflight.py`，放在 `audit.yml` 最前面、
`build_listed_universe.py` 之前執行。結果寫進 `data/audit_report.json`
固定的 `self_check` 欄位（跟 `local_task_health` 同一套「讀出來只改
自己的 key」手法，不覆蓋其他稽核結果）。

**維護提醒**：`CHECKS` 列的是後面幾支腳本實際會用到的 import／常數——
那幾支腳本的 import 來源改了，這裡要跟著更新，否則會出現「自我檢查
過關，但實際腳本還是 ImportError」的假陽性。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "audit_report.json"
TZ = timezone(timedelta(hours=8))

CHECKS = [
    ("build_listed_universe.py 所需 import/常數",
     "import sys; sys.path.insert(0,'scripts'); "
     "from data_audit import TPEX_QUOTES, TWSE_COMPANY, TWSE_STOCK_DAY_ALL, "
     "is_stock_code, make_session, num"),
    ("prune_delisted.py 可以 import",
     "import sys; sys.path.insert(0,'scripts'); import prune_delisted"),
    ("data_audit.py 可以 import",
     "import sys; sys.path.insert(0,'scripts'); import data_audit"),
]


def run_check(label: str, code: str) -> dict:
    try:
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
        ok = p.returncode == 0
        return {"label": label, "ok": ok, "error": "" if ok else (p.stderr or "").strip()[-500:]}
    except Exception as e:  # noqa: BLE001
        return {"label": label, "ok": False, "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    now = datetime.now(TZ)
    results = [run_check(label, code) for label, code in CHECKS]
    all_ok = all(r["ok"] for r in results)

    try:
        doc = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    except (OSError, json.JSONDecodeError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    doc["self_check"] = {
        "checked_at": now.isoformat(),
        "ok": all_ok,
        "checks": results,
        "note": "audit.yml 每次執行最前面跑，確認後面幾支腳本要用到的 import/常數"
                "撈得到——2026-09-10~17 因 data_audit.py 誤刪 TWSE_COMPANY 導致"
                "build_listed_universe.py 連續一週 ImportError 全滅，但"
                "audit_report.json 本身完全沒有任何紀錄，只能靠 gh run list 才查得到，"
                "這個欄位就是補這個盲點。",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in results:
        print(("OK " if r["ok"] else "FAIL ") + r["label"] + (f"：{r['error']}" if not r["ok"] else ""))
    if not all_ok:
        print("::error::稽核管線自檢失敗，後面步驟可能會 ImportError")
    return 0  # 自檢本身不擋住 workflow——就算真的壞了，也要讓後面步驟照跑，
    # 該失敗的地方自然會失敗，這支只負責留下紀錄。


if __name__ == "__main__":
    raise SystemExit(main())
