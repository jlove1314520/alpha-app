#!/usr/bin/env python3
"""先.一三五-1ef：相依套件每週檢查（scripts/check_security_updates.py＋scripts/run_dep_check.py，本機排程 AlphaDepCheck）合成自測。

零外部請求：PyPI 查詢（latest）換假的、REQ／OUT 換暫存檔；run_dep_check 的 subprocess 與 commit_paths 換假的，
不碰真 git、不碰真 data/dependency_status.json。用法：python scripts/selftest_dep_check.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail and not ok else ""))
    if not ok:
        fails.append(name)


import check_security_updates as C  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    C.ROOT = td
    C.REQ = td / "requirements-live.txt"
    C.OUT = td / "dependency_status.json"
    C.REQ.write_text("# 註解\nfastapi==0.1.0\n\nuvicorn==1.0\nrequests>=2\n", encoding="utf-8")

    # 1. parse_pinned 只收 == 釘版、略過註解／空行／>=
    check("parse_pinned 只收 == 釘版", C.parse_pinned() == {"fastapi": "0.1.0", "uvicorn": "1.0"}, str(C.parse_pinned()))

    # 2. 正常：一個落後、一個最新
    C.latest = lambda pkg: ({"fastapi": "0.2.0", "uvicorn": "1.0"}[pkg], None)
    rc = C.main()
    doc = json.loads(C.OUT.read_text(encoding="utf-8"))
    check("正常 exit 0", rc == 0, str(rc))
    check("正常 behind_count=1", doc["behind_count"] == 1, str(doc["behind_count"]))
    check("正常 error_count=0", doc.get("error_count") == 0, str(doc.get("error_count")))

    # 3. 部分失敗：照實記錯誤、仍寫檔
    C.latest = lambda pkg: ("0.2.0", None) if pkg == "fastapi" else (None, "URLError: 假離線")
    rc = C.main()
    doc = json.loads(C.OUT.read_text(encoding="utf-8"))
    row = {r["package"]: r for r in doc["packages"]}
    check("部分失敗 exit 0 且寫檔", rc == 0 and doc.get("error_count") == 1, f"rc={rc} doc={doc.get('error_count')}")
    check("部分失敗 該列 latest=null 帶錯誤、不算落後",
          row["uvicorn"]["latest"] is None and row["uvicorn"]["error"] and row["uvicorn"]["behind"] is False)

    # 4. 全部失敗：不得覆寫舊檔（舊版會寫 behind_count=0，設定頁看起來「全是最新」）
    before = C.OUT.read_text(encoding="utf-8")
    C.latest = lambda pkg: (None, "URLError: 假離線")
    rc = C.main()
    check("全部失敗 exit 非 0", rc != 0, str(rc))
    check("全部失敗 舊檔原封不動", C.OUT.read_text(encoding="utf-8") == before)

    # 5. 找不到 requirements 檔 → exit 2、不寫檔
    C.OUT.unlink()
    C.REQ.unlink()
    rc = C.main()
    check("缺 requirements exit 2 不寫檔", rc == 2 and not C.OUT.exists(), str(rc))

# ── run_dep_check：檢查失敗不提交、成功才提交 ──
fake_g = types.ModuleType("local_git_commit")
calls: list = []
fake_g.commit_paths = lambda paths, msg: calls.append((paths, msg)) or "假提交"
sys.modules["local_git_commit"] = fake_g
import run_dep_check as R  # noqa: E402

orig_run = subprocess.run
try:
    R.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="全部查詢失敗", stderr="")
    rc = R.main()
    check("run_dep_check 檢查失敗 → exit 0 且不提交", rc == 0 and not calls, f"rc={rc} calls={calls}")
    R.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
    rc = R.main()
    check("run_dep_check 檢查成功 → 只提交 dependency_status.json",
          rc == 0 and calls and calls[0][0] == ["data/dependency_status.json"], str(calls))
finally:
    R.subprocess.run = orig_run

print(f"\n{total - len(fails)}/{total} 通過")
sys.exit(1 if fails else 0)
