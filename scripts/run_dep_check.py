# -*- coding: utf-8 -*-
"""先.八十一-14（2026-10-13）：每週相依套件檢查的排程入口（AlphaDepCheck，週一 08:00）。

根因：排程原本只跑 scripts/check_security_updates.py，它寫 data/dependency_status.json 但**從不 commit／push**，
所以設定頁（讀 GitHub Pages 上的檔）一直停在 9/28 那次手動提交的版本，之後每週都有跑卻沒發布。
這支先跑檢查，再用 scripts/local_git_commit.commit_paths 只提交這一個檔（取鎖、pathspec、pull --rebase、push）。
自身失敗只印原因、exit 0（十二節）。用法：python scripts/run_dep_check.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import local_git_commit as G  # noqa: E402

OUT = "data/dependency_status.json"


def main() -> int:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_security_updates.py")], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    print((r.stdout or "")[-800:], (r.stderr or "")[-400:])
    if r.returncode != 0:
        print(f"檢查失敗（exit {r.returncode}），不提交")
        return 0
    print("提交：" + G.commit_paths([OUT], "相依套件每週檢查 data/dependency_status.json（AlphaDepCheck，先.八十一-14）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
