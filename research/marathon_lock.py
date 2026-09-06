"""File-based lock preventing two marathon cycles (headless `claude -p`
invocations, launched every 30 min by Windows Task Scheduler) from running
concurrently -- e.g. if one cycle runs long and the next fires before it's
done. Not a distributed lock, not thread-safe against true concurrency --
just enough to stop the specific failure mode this project actually has
(a scheduled task firing every 30 min, each invocation a full agentic
session that could in principle run long).

Usage (see MARATHON_PROTOCOL.md section 0):
    python marathon_lock.py acquire            # default lock (TW/US/FUT three-track marathon)
    python marathon_lock.py acquire --name X   # named lock for an independent track
                                                # (2026-09-01: added for the hypothesis-queue
                                                # track, HYPOTHESIS_QUEUE_PROTOCOL.md, so it
                                                # doesn't contend with the three-track lock --
                                                # the two run on independent schedules and must
                                                # not block each other)
      # exit 0 + "LOCK_ACQUIRED" if free
      # exit 1 + "LOCK_HELD by <pid> since <ts>" if held
    python marathon_lock.py release [--name X]  # always exits 0 (releasing an
                                                 # already-free lock is not an error)

Lock file format (2026-09-05): `pid|unix_ts|cycle_id`. cycle_id comes from env ALPHA_CYCLE_ID,
set by run-marathon-cycle.ps1, so the launcher's finally block can release *only its own* lock.

Stale-lock recovery: a lock older than STALE_MINUTES is treated as free --
the process that held it almost certainly crashed or was killed without
reaching its own release() call (headless agent sessions have no guaranteed
cleanup path), and refusing to ever recover would permanently wedge the
marathon after a single bad cycle.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DEFAULT_LOCK_NAME = "marathon"  # unchanged default -- existing TW/US/FUT track keeps using .marathon.lock
STALE_MINUTES = 27  # 2026-09-05: run-marathon-cycle.ps1 hard-kills a cycle at 25 min, so a lock older than
# 27 min can only belong to a cycle that is already dead (killed by budget/timeout before reaching release()).
# It used to be 25 while real cycles ran up to 27.8 min -> the *next* cycle stole the lock from a cycle that was
# still alive and both wrote the same state files. Keep this strictly greater than the ps1 $MaxMinutes.


def _lock_path(name: str) -> Path:
    filename = ".marathon.lock" if name == DEFAULT_LOCK_NAME else f".{name}.lock"
    return Path(__file__).parent / filename  # gitignored -- transient local state, not project history


def _read_lock(lock_path: Path) -> tuple[str, float, str]:
    """回傳 (pid, ts, cycle_id)。2026-09-05 起鎖檔是三欄 `pid|ts|cycle_id`；舊的兩欄格式仍讀得動
    （cycle_id 給 "unknown"）。讀不動就回傳 ts=0 讓呼叫端視為陳舊，不要永遠卡死。"""
    try:
        parts = lock_path.read_text(encoding="utf-8").strip().split("|")
        pid_str, ts_str = parts[0], parts[1]
        cycle_id = parts[2] if len(parts) > 2 else "unknown"
        return pid_str, float(ts_str), cycle_id
    except (ValueError, IndexError, OSError):
        return "unknown", 0.0, "unknown"


def _stale_minutes_for(name: str) -> int:
    """每條軌道的陳舊門檻要比它自己的 wall-clock 上限大。

    2026-09-06（自走一）：開發佇列軌（devqueue）每輪上限 60 分鐘，用預設的 27 分鐘
    會讓還在跑的那一輪被下一輪搶走鎖——馬拉松就是踩過這個坑才把門檻訂成「必須嚴格
    大於 ps1 的 MaxMinutes」。這裡照同一條規則給 devqueue 一個自己的值（62 > 60）。
    """
    return {"devqueue": 62}.get(name, STALE_MINUTES)


def acquire(name: str = DEFAULT_LOCK_NAME) -> bool:
    lock_path = _lock_path(name)
    stale_minutes = _stale_minutes_for(name)
    # 2026-09-05：cycle_id 由 run-marathon-cycle.ps1 用環境變數傳進來，寫進鎖檔第三欄，
    # 讓 ps1 的 finally 能精確判斷「這把鎖是不是我這輪的」——舊版用時間戳猜，兩輪重疊時
    # 會誤釋放另一輪還在用的鎖（驗收實測到，見 PROPOSAL_2026-09-05_marathon_process_hardening.md）。
    cycle_id = os.environ.get("ALPHA_CYCLE_ID", "unknown")
    if lock_path.exists():
        pid_str, ts, holder_cycle = _read_lock(lock_path)
        age_minutes = (time.time() - ts) / 60.0 if ts else stale_minutes + 1
        if age_minutes < stale_minutes:
            print(f"LOCK_HELD by {pid_str} (cycle {holder_cycle}) since {ts} ({age_minutes:.1f} min ago)")
            return False
        print(f"LOCK_STALE (held by {pid_str}, cycle {holder_cycle}, {age_minutes:.1f} min old) -- recovering")
    lock_path.write_text(f"{os.getpid()}|{time.time()}|{cycle_id}", encoding="utf-8")
    print(f"LOCK_ACQUIRED (cycle {cycle_id})")
    return True


def release(name: str = DEFAULT_LOCK_NAME) -> None:
    try:
        _lock_path(name).unlink()
    except FileNotFoundError:
        pass  # already free -- not an error, releasing a non-held lock is a no-op by design
    print("LOCK_RELEASED")


def _parse_name(argv: list[str]) -> str:
    if "--name" in argv:
        idx = argv.index("--name")
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return DEFAULT_LOCK_NAME


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    lock_name = _parse_name(sys.argv[2:])
    if cmd == "acquire":
        sys.exit(0 if acquire(lock_name) else 1)
    elif cmd == "release":
        release(lock_name)
        sys.exit(0)
    else:
        print("usage: python marathon_lock.py [acquire|release] [--name LOCK_NAME]")
        sys.exit(2)
