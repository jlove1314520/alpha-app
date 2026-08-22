"""File-based lock preventing two marathon cycles (headless `claude -p`
invocations, launched every 30 min by Windows Task Scheduler) from running
concurrently -- e.g. if one cycle runs long and the next fires before it's
done. Not a distributed lock, not thread-safe against true concurrency --
just enough to stop the specific failure mode this project actually has
(a scheduled task firing every 30 min, each invocation a full agentic
session that could in principle run long).

Usage (see MARATHON_PROTOCOL.md section 0):
    python marathon_lock.py acquire   # exit 0 + "LOCK_ACQUIRED" if free
                                       # exit 1 + "LOCK_HELD by <pid> since <ts>" if held
    python marathon_lock.py release   # always exits 0 (releasing an
                                       # already-free lock is not an error)

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

LOCK_PATH = Path(__file__).parent / ".marathon.lock"  # gitignored -- transient local state, not project history
STALE_MINUTES = 25  # a cycle is scheduled every 30 min; a lock older than this almost certainly means
# the process that created it died without releasing -- not a deliberate long-running cycle.


def acquire() -> bool:
    if LOCK_PATH.exists():
        try:
            pid_str, ts_str = LOCK_PATH.read_text(encoding="utf-8").strip().split("|", 1)
            age_minutes = (time.time() - float(ts_str)) / 60.0
        except (ValueError, OSError):
            age_minutes = STALE_MINUTES + 1  # unreadable/corrupt lock file -- treat as stale, don't wedge forever
            pid_str, ts_str = "unknown", "unknown"
        if age_minutes < STALE_MINUTES:
            print(f"LOCK_HELD by {pid_str} since {ts_str} ({age_minutes:.1f} min ago)")
            return False
        print(f"LOCK_STALE (held by {pid_str}, {age_minutes:.1f} min old) -- recovering")
    LOCK_PATH.write_text(f"{os.getpid()}|{time.time()}", encoding="utf-8")
    print("LOCK_ACQUIRED")
    return True


def release() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass  # already free -- not an error, releasing a non-held lock is a no-op by design
    print("LOCK_RELEASED")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "acquire":
        sys.exit(0 if acquire() else 1)
    elif cmd == "release":
        release()
        sys.exit(0)
    else:
        print("usage: python marathon_lock.py [acquire|release]")
        sys.exit(2)
