# -*- coding: utf-8 -*-
"""先.八十-11（2026-10-12）：本機排程「只提交自己的產出檔」共用流程。

與三支 wrapper（run-*-cycle.ps1）同一套結案.一 方案甲＋丙：搶 research/git_op_lock.py → commit（pathspec，只收指定檔）
→ pull --rebase --autostash → push 前偵測字面衝突標記（有就跳過 push 並回報）→ push → 放鎖。
鎖被別人持有就整輪跳過、留給下一輪（不排隊）。自身任何失敗只回傳原因字串，不拋例外（十二節）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "research" / "git_op_lock.py"


def _g(*a, timeout=180):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def commit_paths(paths: list[str], msg: str) -> str:
    try:
        if subprocess.run([sys.executable, str(LOCK), "acquire"], cwd=ROOT, capture_output=True, timeout=60).returncode != 0:
            return "鎖被其他排程持有，本輪跳過"
    except Exception as e:  # noqa: BLE001
        return f"取鎖失敗（{type(e).__name__}），本輪跳過"
    try:
        existing = [p for p in paths if (ROOT / p).exists()]
        if not existing:
            return "沒有產出檔"
        _g("add", "--", *existing)
        if _g("diff", "--cached", "--quiet", "--", *existing).returncode == 0:
            return "沒有變更"
        c = _g("commit", "-q", "-m", msg, "--", *existing)
        if c.returncode != 0:
            return "commit 失敗：" + (c.stderr or c.stdout)[-200:]
        _g("pull", "-q", "--rebase", "--autostash")
        marks = _g("grep", "-l", "^<<<<<<< ")
        if marks.returncode == 0 and marks.stdout.strip():
            return "已 commit，但偵測到衝突標記，跳過 push：" + marks.stdout.strip().replace("\n", ", ")[:200]
        p = _g("push", "-q")
        return "已 commit 並 push" if p.returncode == 0 else "已 commit，push 失敗（留給下一輪）"
    except Exception as e:  # noqa: BLE001
        return f"提交流程失敗（{type(e).__name__}: {e}）"
    finally:
        try:
            subprocess.run([sys.executable, str(LOCK), "release"], cwd=ROOT, capture_output=True, timeout=60)
        except Exception:  # noqa: BLE001
            pass


def last_commit_age_min(path: str) -> float | None:
    """該檔最後一次 commit 距今幾分鐘；從沒 commit 過回 None。"""
    import time
    r = _g("log", "-1", "--format=%ct", "--", path, timeout=60)
    s = (r.stdout or "").strip()
    return (time.time() - int(s)) / 60 if s.isdigit() else None
