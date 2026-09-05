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


def acquire(name: str = DEFAULT_LOCK_NAME) -> bool:
    lock_path = _lock_path(name)
    if lock_path.exists():
        try:
            pid_str, ts_str = lock_path.read_text(encoding="utf-8").strip().split("|", 1)
            age_minutes = (time.time() - float(ts_str)) / 60.0
        except (ValueError, OSError):
            age_minutes = STALE_MINUTES + 1  # unreadable/corrupt lock file -- treat as stale, don't wedge forever
            pid_str, ts_str = "unknown", "unknown"
        if age_minutes < STALE_MINUTES:
            print(f"LOCK_HELD by {pid_str} since {ts_str} ({age_minutes:.1f} min ago)")
            return False
        print(f"LOCK_STALE (held by {pid_str}, {age_minutes:.1f} min old) -- recovering")
    lock_path.write_text(f"{os.getpid()}|{time.time()}", encoding="utf-8")
    print("LOCK_ACQUIRED")
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
