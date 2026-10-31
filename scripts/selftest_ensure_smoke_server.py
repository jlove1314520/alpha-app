# -*- coding: utf-8 -*-
"""先.一三五-1fg 自測：冒煙伺服器啟動器（ensure_smoke_server.main）。

全部用假的：_fetch／Popen／time.sleep／PID 檔／本機 index.html 換暫存，零外部請求、不真的開埠、不留行程。
用法：python scripts/selftest_ensure_smoke_server.py
"""
import contextlib
import io
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ensure_smoke_server as E  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


spawned = []


class FakePopen:
    def __init__(self, args, **kw):
        spawned.append(args)
        self.pid = 4242


E.subprocess = types.SimpleNamespace(Popen=FakePopen, DETACHED_PROCESS=0, CREATE_NEW_PROCESS_GROUP=0, DEVNULL=None)  # 不動真的 subprocess 模組
E.time = types.SimpleNamespace(sleep=lambda s: None)


def run(fetch_seq):
    """fetch_seq：依序回給 _fetch 的值（用完就一直回最後一個）。回 (exit, stdout+stderr)。"""
    seq = list(fetch_seq)
    E._fetch = lambda port: seq.pop(0) if len(seq) > 1 else seq[0]
    spawned.clear()
    sys.argv = ["ensure_smoke_server.py", "--port", "8799"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = E.main()
    return rc, buf.getvalue()


with tempfile.TemporaryDirectory() as d:
    E.ROOT = Path(d)
    (E.ROOT / "research").mkdir()
    E.PID_FILE = E.ROOT / "research" / ".smoke_server.pid"
    mine = "<html>本 repo</html>".encode("utf-8")
    (E.ROOT / "index.html").write_bytes(mine)

    rc, out = run([mine])
    check("已有伺服器且內容一致 → 沿用 exit 0、不啟動", rc == 0 and not spawned and "沿用" in out)

    rc, out = run(["<html>別份</html>".encode("utf-8")])
    check("已有伺服器但 index.html 不同 → exit 1、不啟動、說明原因", rc == 1 and not spawned and "不同" in out)

    rc, out = run([None, None, mine])
    check("打不通 → 啟動一個並等到回 200 → exit 0", rc == 0 and len(spawned) == 1 and "8799" in spawned[0])
    check("啟動後 PID 寫進 PID 檔", E.PID_FILE.read_text(encoding="utf-8").strip() == "4242")
    check("啟動用 http.server 綁 127.0.0.1", spawned[0][1:3] == ["-m", "http.server"] and "127.0.0.1" in spawned[0])

    rc, out = run([None])
    check("啟動後 10 秒內仍打不通 → exit 1", rc == 1 and len(spawned) == 1 and "打不通" in out)

    (E.ROOT / "index.html").unlink()
    rc, out = run([mine])
    check("本機 index.html 讀不到 → 只警告、照舊沿用 exit 0", rc == 0 and not spawned and "warn" in out)

# 真的 _fetch：打一個不會有人聽的埠要回 None、不拋例外
import importlib  # noqa: E402
E2 = importlib.reload(E)
check("真 _fetch 對沒人聽的埠回 None 不拋例外", E2._fetch(1) is None)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(1 if False in results else 0)
