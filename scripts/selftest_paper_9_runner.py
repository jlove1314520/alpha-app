# -*- coding: utf-8 -*-
"""自測：模擬 I 本機排程啟動程式（scripts/run_paper_9.py，AlphaPaper9）（先.一三五-1ej）。

tracker／local_git_commit／subprocess.run 全換假的，不跑真的 step()、不 git add、不 commit，零外部請求；
ROOT 換暫存目錄。只測啟動程式的錯誤隔離與提交清單，不測模擬 I 判定規則（那在 selftest_paper_forward_common.py）。
"""
from __future__ import annotations

import io
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import run_paper_9 as R  # noqa: E402

fails = []


def chk(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def setup(td: Path, step, commit, ledger_exists: bool):
    calls = {"step": 0, "add": [], "commit": []}
    T = types.ModuleType("paper_9_breakout_tracker")

    def _step():
        calls["step"] += 1
        return step()
    T.step = _step
    G = types.ModuleType("local_git_commit")

    def _commit(paths, msg, **k):
        calls["commit"].append((list(paths), msg))
        return commit()
    G.commit_paths = _commit
    sys.modules["paper_9_breakout_tracker"] = T
    sys.modules["local_git_commit"] = G
    R.ROOT = td
    if ledger_exists:
        (td / "research" / "data").mkdir(parents=True, exist_ok=True)
        (td / R.LEDGER).write_text("", encoding="utf-8")
    R.subprocess = types.SimpleNamespace(run=lambda args, **k: calls["add"].append(args))
    return calls


def run():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = R.main()
    return rc, buf.getvalue()


with tempfile.TemporaryDirectory() as a:
    c = setup(Path(a), lambda: {"status": "NOT_STARTED"}, lambda: "nothing to commit", False)
    rc, out = run()
    chk("1 起跑前 NOT_STARTED、帳本不存在 -> exit 0、不 git add -f、仍呼叫 commit_paths", rc == 0 and c["add"] == [] and len(c["commit"]) == 1)
    chk("1b 提交清單只有摘要＋帳本兩檔", c["commit"][0][0] == ["data/paper_9.json", "research/data/paper_9_log.jsonl"])
    chk("1c 訊息含「非投資建議」", "非投資建議" in c["commit"][0][1])
with tempfile.TemporaryDirectory() as a:
    c = setup(Path(a), lambda: {"status": "OK"}, lambda: "committed", True)
    rc, out = run()
    chk("2 帳本存在 -> git add -f 只加帳本一檔", rc == 0 and len(c["add"]) == 1 and c["add"][0][-1] == "research/data/paper_9_log.jsonl" and "-f" in c["add"][0])


def boom():
    raise ValueError("合成 step 失敗")


with tempfile.TemporaryDirectory() as a:
    c = setup(Path(a), boom, lambda: "x", True)
    rc, out = run()
    chk("3 step 拋例外 -> exit 0、印 [warn]、不提交也不 add", rc == 0 and "[warn]" in out and c["commit"] == [] and c["add"] == [])


def cboom():
    raise RuntimeError("合成 commit 失敗")


with tempfile.TemporaryDirectory() as a:
    c = setup(Path(a), lambda: {"status": "OK"}, cboom, False)
    rc, out = run()
    chk("4 commit 拋例外 -> exit 0、印「下一輪再試」", rc == 0 and "下一輪再試" in out)
with tempfile.TemporaryDirectory() as a:
    c = setup(Path(a), lambda: {"note": "含 emoji ✓ 與中文"}, lambda: "ok", False)
    rc, out = run()
    chk("5 step 結果含非 ASCII -> 照印不崩潰", rc == 0 and "✓" in out)

print("ALL PASS" if not fails else "FAILED: " + str(fails))
sys.exit(1 if fails else 0)
