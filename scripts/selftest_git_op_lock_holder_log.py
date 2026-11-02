# -*- coding: utf-8 -*-
"""先.一三五-1hu（2026-11-02）：git_op_lock acquire 被擋時記下持有者——合成自測（只用暫存目錄，不碰真的鎖檔與 log）。
① 空鎖→ACQUIRED、不記 log，鎖檔第 4 欄有 ppid／argv0
② 被持有→回 False（CLI exit 1）、log 多一行 LOCK_HELD 含 holder_pid／age／holder／caller
③ log 目錄不可寫（路徑指到不存在的目錄）→ 仍照常回 LOCK_HELD、不丟例外
④ 舊 2／3 欄鎖檔照讀：被擋且 holder=unknown；token release 照常
用法：python scripts/selftest_git_op_lock_holder_log.py
"""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location("git_op_lock", ROOT / "research" / "git_op_lock.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
d = Path(tempfile.mkdtemp())
L.LOCK_PATH, L.LEGACY_LOG = d / ".git_op.lock", d / "git_op_lock.log"


def run(f, *a):
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        r = f(*a)
    return r, b.getvalue().strip()


def log_lines():
    return L.LEGACY_LOG.read_text(encoding="utf-8").splitlines() if L.LEGACY_LOG.exists() else []


res = []
ok, out = run(L.acquire)
parts = L.LOCK_PATH.read_text(encoding="utf-8").split("|")
res.append(("①空鎖→ACQUIRED", ok and "LOCK_ACQUIRED" in out))
res.append(("①不記 log", log_lines() == []))
res.append(("①鎖檔第 4 欄有 ppid／argv0", len(parts) == 4 and parts[3].startswith(f"ppid={os.getppid()};argv0=")))

ok2, out2 = run(L.acquire)
lines = log_lines()
res.append(("②被持有→False", not ok2 and "LOCK_HELD" in out2))
res.append(("②log 多一行 LOCK_HELD", len(lines) == 1 and "LOCK_HELD" in lines[0]
            and f"holder_pid={os.getpid()}" in lines[0] and " age=" in lines[0]
            and "holder=ppid=" in lines[0] and "caller_ppid=" in lines[0]))

# CLI 路徑：用子行程跑一份指向同一暫存鎖檔的副本，確認 exit 1
cli = d / "git_op_lock.py"
cli.write_text((ROOT / "research" / "git_op_lock.py").read_text(encoding="utf-8"), encoding="utf-8")
p = subprocess.run([sys.executable, str(cli), "acquire"], capture_output=True, text=True, encoding="utf-8", errors="replace")
res.append(("②CLI 被擋 exit 1 且記 log", p.returncode == 1 and "LOCK_HELD" in p.stdout and len(log_lines()) == 2))

L.LEGACY_LOG = d / "no_such_dir" / "sub" / "git_op_lock.log"
try:
    ok3, out3 = run(L.acquire)
    res.append(("③log 不可寫仍回 LOCK_HELD", not ok3 and "LOCK_HELD" in out3 and not L.LEGACY_LOG.exists()))
except Exception as e:  # noqa: BLE001
    res.append((f"③log 不可寫丟例外：{e!r}", False))
L.LEGACY_LOG = d / "git_op_lock.log"

for old in (f"12345|{time.time()}", f"12345|{time.time()}|abcdabcdabcdabcd"):
    L.LOCK_PATH.write_text(old, encoding="utf-8")
    n0 = len(log_lines())
    ok4, out4 = run(L.acquire)
    last = log_lines()[-1] if log_lines() else ""
    res.append((f"④舊 {len(old.split('|'))} 欄鎖檔照讀被擋", not ok4 and "LOCK_HELD by 12345" in out4
                and len(log_lines()) == n0 + 1 and "holder=unknown" in last))
run(L.release, "abcdabcdabcdabcd")
res.append(("④舊 3 欄 token release 照常", not L.LOCK_PATH.exists()))

L.LOCK_PATH.write_text("999|1.0|t|ppid=1;argv0=x", encoding="utf-8")  # 陳舊鎖：回收、不記 LOCK_HELD
n0 = len(log_lines())
ok5, out5 = run(L.acquire)
res.append(("陳舊鎖照舊回收、不記 LOCK_HELD", ok5 and "LOCK_STALE" in out5 and len(log_lines()) == n0))

fail = 0
for name, good in res:
    print(("PASS " if good else "FAIL ") + name)
    fail += 0 if good else 1
print(f"合計 {len(res)} 項，失敗 {fail}")
sys.exit(1 if fail else 0)
