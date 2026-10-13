# -*- coding: utf-8 -*-
"""先.八十一-34（2026-10-13）：git_op_lock 持有者憑證自測（只用暫存目錄的鎖檔，不碰真的 research/.git_op.lock）。
① acquire 拿到 token ② 第二次 acquire 被擋 ③ 錯 token 的 release 不刪鎖（LOCK_NOT_OWNER）④ 對 token 才刪
⑤ 不帶 token（相容期）照舊刪、並記 legacy log ⑥ 舊格式鎖檔（無 token）帶 token release 仍可刪。
用法：python scripts/selftest_git_op_lock.py
"""
import contextlib
import importlib.util
import io
import sys
import tempfile
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


res = []
ok, out = run(L.acquire)
tok = out.split("token=")[1] if "token=" in out else ""
res.append(("①acquire 拿到 token", ok and len(tok) == 16))
ok2, _ = run(L.acquire)
res.append(("②第二次 acquire 被擋", not ok2))
_, o3 = run(L.release, "0" * 16)
res.append(("③錯 token 不刪鎖", L.LOCK_PATH.exists() and "LOCK_NOT_OWNER" in o3))
run(L.release, tok)
res.append(("④對 token 刪鎖", not L.LOCK_PATH.exists()))
run(L.acquire)
run(L.release, None)
res.append(("⑤不帶 token 相容刪鎖並記 log", not L.LOCK_PATH.exists() and "legacy" in L.LEGACY_LOG.read_text(encoding="utf-8")))
L.LOCK_PATH.write_text("123|9999999999", encoding="utf-8")
run(L.release, "abc")
res.append(("⑥舊格式鎖檔帶 token 可刪", not L.LOCK_PATH.exists()))
for n, p in res:
    print(("PASS " if p else "FAIL ") + n)
bad = sum(1 for _, p in res if not p)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
