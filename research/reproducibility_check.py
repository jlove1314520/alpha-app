# -*- coding: utf-8 -*-
"""reproducibility_check.py — 批次確認`TRIALS_LEDGER.md`裡登記過結果的
腳本，現在還能不能被`import`（2026-09-20總司令裁示【Q4前視與#23無法
重現】二.3新增，是`#23`從2026-09-03壞到現在都沒人發現的根本預防）。

**背景**：`piotroski_fscore_sanity.py`（`TRIALS_LEDGER.md`#93）與
`piotroski_fscore_gate_v1.py`（#94）自2026-09-03首次commit起就
`import`一個`pit.py`從未定義過的函式，兩支腳本從那天起就無法執行，
但沒有任何機制發現這件事，直到今天（2026-09-20）研究財報原子庫的
PIT機制時才意外撞見。**登記過的結果，要有機器定期確認它還跑得動**，
這支腳本就是那個機器。

**設計原則（安全考量，務必遵守）**：
1. **只檢查`import`，不執行`main()`**——很多被檢查的腳本頂層就有
   會發真實網路請求的程式碼（例如已停用的MOPS client會在頂層流程裡
   呼叫，一`import`就觸發，這正是它們被停用後仍要用`PermissionError`
   卡住而不是整支刪除的理由——擋在請求真正送出之前）。**每個檢查都
   用獨立子行程＋短逾時**（預設10秒），限制任何頂層副作用的影響範圍，
   不是徹底消除風險（子行程逾時前仍可能已經送出少量真實請求），但
   遠比讓它跑到底安全。
2. **區分「被合規/安全防呆擋下」跟「真的壞掉」**：`PermissionError`
   （`net_guard.py`/既有MOPS client的硬性防呆）代表機制正常運作
   （這支腳本被正確地擋住了，不是壞掉），不列入「需要修的項目」；
   `ImportError`/`ModuleNotFoundError`/`AttributeError`才是需要
   關注的真bug（正是`#23`那種dangling import）。
3. **只檢查`research/`裡確實存在的檔案**——`TRIALS_LEDGER.md`裡提到
   的`.py`檔名，很多是舊版重構後已經改名或整併掉的，本檔案裡找不到
   對應檔案的一律標`FILE_NOT_FOUND`，不當成錯誤（可能是合理的歷史
   演進，不是本次檢查的目標）。

用法：
    python research/reproducibility_check.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:  # Windows cp950主控台印不出特殊符號時降級，不崩潰（見CLAUDE.md第十二節）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).parent
TRIALS_LEDGER = ROOT / "TRIALS_LEDGER.md"
OUT_PATH = ROOT / "reproducibility_check_result.json"
TIMEOUT_SECONDS = 10

_PY_NAME_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.py\b")


def find_ledger_script_names() -> list[str]:
    """從TRIALS_LEDGER.md掃出所有`xxx.py`字面提及，去重、排序。"""
    text = TRIALS_LEDGER.read_text(encoding="utf-8")
    names = sorted(set(_PY_NAME_RE.findall(text)))
    return names


def check_one(module_name: str) -> dict:
    script_path = ROOT / f"{module_name}.py"
    if not script_path.exists():
        return {"module": module_name, "status": "FILE_NOT_FOUND"}

    code = f"import sys; sys.path.insert(0, r'{ROOT}'); import {module_name}"
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS, cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"module": module_name, "status": "TIMEOUT",
                "note": f"{TIMEOUT_SECONDS}秒內未完成import，可能頂層有重度/網路操作，"
                        f"需要人工檢查是否應該加`if __name__ == '__main__':`保護"}

    if result.returncode == 0:
        return {"module": module_name, "status": "OK"}

    stderr = result.stderr.strip()
    last_line = stderr.splitlines()[-1] if stderr else ""
    if "PermissionError" in stderr:
        return {"module": module_name, "status": "BLOCKED_BY_GUARD",
                "note": "被net_guard/既有合規防呆正確擋下，不是bug", "detail": last_line}
    if any(err in stderr for err in ("ImportError", "ModuleNotFoundError", "AttributeError", "NameError")):
        return {"module": module_name, "status": "IMPORT_ERROR",
                "note": "真的壞了，需要修——這正是#23那種dangling import的同類問題",
                "detail": last_line}
    return {"module": module_name, "status": "OTHER_ERROR", "detail": last_line}


def main() -> int:
    names = find_ledger_script_names()
    print(f"從TRIALS_LEDGER.md掃出{len(names)}個候選腳本名稱，逐一檢查import...")

    results = []
    for i, name in enumerate(names):
        r = check_one(name)
        results.append(r)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(names)}")

    by_status: dict[str, list[dict]] = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)

    print("\n=== 結果摘要 ===")
    for status in ("OK", "BLOCKED_BY_GUARD", "FILE_NOT_FOUND", "TIMEOUT", "IMPORT_ERROR", "OTHER_ERROR"):
        items = by_status.get(status, [])
        print(f"{status}: {len(items)}")

    broken = by_status.get("IMPORT_ERROR", []) + by_status.get("OTHER_ERROR", [])
    if broken:
        print(f"\n⚠️ 需要修的項目（{len(broken)}個）：")
        for r in broken:
            print(f"  {r['module']}.py — {r['status']}：{r.get('detail', '')}")
    else:
        print("\n沒有發現新的dangling import（除了已經修好的#23）。")

    OUT_PATH.write_text(json.dumps({
        "checked_at": None,  # 由呼叫端或audit_preflight填,這支本身不依賴系統時間避免時區混淆
        "n_checked": len(names),
        "by_status_count": {k: len(v) for k, v in by_status.items()},
        "broken": broken,
        "all_results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存：{OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
