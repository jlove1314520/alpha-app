"""File-based lock coordinating git commit->pull->push sequences across the
three independent local wrapper scripts (run-marathon-cycle.ps1 /
run-dev-queue-cycle.ps1 / run-hypothesis-queue-cycle.ps1), each on its own
Task Scheduler cadence (15~30 min), none aware of the others.

2026-09-23 total司令裁示【修正兩個系統性錯誤＋兩件待審閱結案】結案.一
方案甲（見 `PENDING_QUEUE.md`「2026-09-23【維運.git衝突根因】」章節）：
round607 的衝突根因是三支 wrapper 各自獨立呼叫 `git pull --rebase
--autostash` 收尾，`--autostash` 會連同「別的 wrapper/session 留下的
未commit修改」一起暫存，若同時遠端也有變動，`stash pop` 衝突時不會設
`rebase-merge`/`MERGE_HEAD` 狀態，只留下字面衝突標記——正是round607
觀察到的異常。這支鎖確保同一時刻只有一支 wrapper 在做
commit->pull->push 這段收尾，直接消除「兩個 autostash 同時發生」的
競爭條件本身，是根治不是繞過。

跟 `marathon_lock.py` 的差異：那支鎖的是「整輪 claude -p session」
（可能長達 25~60 分鐘），這支鎖的只是 git 收尾這幾秒到幾十秒的操作，
陳舊門檻（`STALE_MINUTES`）遠比 marathon 鎖短——正常情況下不該有任何
一次 git 操作卡超過 5 分鐘，卡超過就代表持鎖的行程已經死掉，5 分鐘後
自動視為陳舊可回收，不會永久卡死其他 wrapper。

用法（PowerShell 呼叫端，見三支 .ps1 的 git 收尾段落）：
    python research/git_op_lock.py acquire
      # exit 0 + "LOCK_ACQUIRED" if free
      # exit 1 + "LOCK_HELD by <pid> since <ts>" if held by someone else
    python research/git_op_lock.py release
      # always exit 0（釋放一把已經是空的鎖不是錯誤）

鎖檔（`.git_op.lock`，跟 `.marathon.lock` 同一層、同樣 gitignored，
是暫態本機狀態不是專案歷史）格式：`pid|unix_ts`。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

STALE_MINUTES = 5  # 見模組docstring：git commit->pull->push正常應在數十秒內完成，
# 5分鐘是遠高於正常耗時的保守上限，卡超過代表持鎖行程已死，不是還在正常工作。

LOCK_PATH = Path(__file__).parent / ".git_op.lock"  # gitignored，暫態本機狀態


def _read_lock() -> tuple[str, float]:
    try:
        pid_str, ts_str = LOCK_PATH.read_text(encoding="utf-8").strip().split("|")
        return pid_str, float(ts_str)
    except (ValueError, IndexError, OSError):
        return "unknown", 0.0


def acquire() -> bool:
    if LOCK_PATH.exists():
        pid_str, ts = _read_lock()
        age_minutes = (time.time() - ts) / 60.0 if ts else STALE_MINUTES + 1
        if age_minutes < STALE_MINUTES:
            print(f"LOCK_HELD by {pid_str} since {ts} ({age_minutes:.1f} min ago)")
            return False
        print(f"LOCK_STALE (held by {pid_str}, {age_minutes:.1f} min old) -- recovering")
    LOCK_PATH.write_text(f"{os.getpid()}|{time.time()}", encoding="utf-8")
    print("LOCK_ACQUIRED")
    return True


def release() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass  # 已經是空的，不是錯誤——跟marathon_lock.py同一種設計
    print("LOCK_RELEASED")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "acquire":
        sys.exit(0 if acquire() else 1)
    elif cmd == "release":
        release()
        sys.exit(0)
    else:
        print("usage: python git_op_lock.py [acquire|release]")
        sys.exit(2)
