"""先.一三五-1hq-a 自測：check_external_connectivity.check_rebase_residue_alerts()。
只在暫存目錄造假的 .git/rebase-merge，不碰真 repo。執行：python scripts/selftest_rebase_residue_alert.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import check_external_connectivity as cec  # noqa: E402

fails = 0


def ok(name: str, cond: bool) -> None:
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    git = t / ".git"
    git.mkdir()
    lock = t / ".git_op.lock"
    now = time.time()

    ok("1 沒有 rebase 目錄 → 不告警", cec.check_rebase_residue_alerts(git, lock, now) == [])

    rm = git / "rebase-merge"
    rm.mkdir()
    (rm / "autostash").write_text("x", encoding="utf-8")
    os.utime(rm, (now - 10 * 60, now - 10 * 60))
    ok("2 殘留 10 分鐘 → 不告警", cec.check_rebase_residue_alerts(git, lock, now) == [])

    os.utime(rm, (now - 45 * 60, now - 45 * 60))
    r = cec.check_rebase_residue_alerts(git, lock, now)
    ok("3 殘留 45 分鐘、無鎖 → 告警 1 則且列出內容", len(r) == 1 and "rebase-merge" in r[0] and "autostash" in r[0])

    lock.write_text(f"1234|{now - 5 * 60}|tok|x", encoding="utf-8")
    ok("4 有人持鎖 5 分鐘 → 不告警", cec.check_rebase_residue_alerts(git, lock, now) == [])

    lock.write_text(f"1234|{now - 60 * 60}|tok|x", encoding="utf-8")
    ok("5 鎖已持 60 分鐘（視為無活持鎖者）→ 告警", len(cec.check_rebase_residue_alerts(git, lock, now)) == 1)

    lock.write_text("壞掉的鎖檔", encoding="utf-8")
    os.utime(lock, (now - 2 * 60, now - 2 * 60))
    ok("6 鎖檔格式壞、mtime 2 分鐘 → 用 mtime 判斷、不告警", cec.check_rebase_residue_alerts(git, lock, now) == [])
    lock.unlink()

    ra = git / "rebase-apply"
    ra.mkdir()
    os.utime(ra, (now - 40 * 60, now - 40 * 60))
    ok("7 兩種目錄都殘留 → 告警 2 則", len(cec.check_rebase_residue_alerts(git, lock, now)) == 2)

    ok("8 .git 不是目錄（worktree 檔）→ 不告警", cec.check_rebase_residue_alerts(t / "nope", lock, now) == [])

    # 9 看守自己壞掉：傳入會讓內部拋例外的參數 → 只印警告、回空清單，不往外拋
    try:
        r = cec.check_rebase_residue_alerts(git, lock, "不是數字")  # type: ignore[arg-type]
        ok("9 看守自身例外 → fail open 回空清單", r == [])
    except Exception as e:  # noqa: BLE001
        ok(f"9 看守自身例外不得外溢（實際拋出 {type(e).__name__}）", False)

# 10 主流程照跑：main() 的 task_stalls 串接裡確實呼叫這支（靜態檢查，不真的跑網路自檢）
src = Path(cec.__file__).read_text(encoding="utf-8")
ok("10 已併入 main() 的 task_stalls", "+ check_rebase_residue_alerts())" in src)

print(f"\n{10 - fails}/10 通過")
sys.exit(1 if fails else 0)
