# -*- coding: utf-8 -*-
"""先.一三一-1（2026-10-22，收件匣 015）自測：pull --rebase --autostash 套回失敗時不再靜默、不拿舊 stash 蓋掉新資料。

暫存 bare origin＋兩個 clone，不碰真 repo、不發推播（cc_push._send 換成記錄器）：
1. 遠端改了 X、本機未提交也改了 X 與 Y → pull_autostash_safe()：X 保留遠端版、Y 取回本機版、stash 保留、
   寫一行 autostash_failures.jsonl、推一次 cc_stuck。
2. stash 之後工作樹又被別人寫成更新版 W2 → _restore_failed_autostash() 保留 W2（列在 kept_worktree_newer）。
3. 6 小時內第二次失敗：照寫紀錄、不再推播。
（先.一三一-3）2c：只有「工作樹較新」→ 沒有獨有內容，自動刪這筆 stash、不推播；
4. 機器寫檔（data/m.json）遠端較新 → 自動刪 stash、不推播；人寫的檔（情境 1 的 X.txt）遠端較新 → 保留 stash＋推播。
跑法：python scripts/selftest_autostash_restore.py
"""
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import local_git_commit as G  # noqa: E402

fails, pushes = [], []
sys.modules["cc_push"] = types.SimpleNamespace(_send=lambda t, b, k: pushes.append((t, k)) or {"ok": 1})


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, encoding="utf-8")


def w(p: Path, s: str):
    p.write_text(s, encoding="utf-8", newline="\n")


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    origin, a, b = td / "origin.git", td / "a", td / "b"
    git(td, "init", "-q", "--bare", "-b", "main", str(origin))
    git(td, "clone", "-q", str(origin), str(a))
    for c in (a,):
        git(c, "config", "user.email", "t@example.invalid"); git(c, "config", "user.name", "t")
        git(c, "checkout", "-q", "-b", "main")
    (a / "research").mkdir()
    (a / "data").mkdir()
    for f, s in (("X.txt", "x0\n"), ("Y.txt", "y0\n"), ("Z.txt", "z0\n"), ("W.txt", "w0\n"), ("data/m.json", "m0\n")):
        w(a / f, s)
    git(a, "add", "-A"); git(a, "commit", "-q", "-m", "init"); git(a, "push", "-q", "-u", "origin", "main")
    git(td, "clone", "-q", str(origin), str(b))
    git(b, "config", "user.email", "t@example.invalid"); git(b, "config", "user.name", "t")
    w(b / "X.txt", "x-remote\n"); git(b, "commit", "-q", "-am", "remote X"); git(b, "push", "-q")

    G.ROOT, G.GITDIR = a, a / ".git"
    G.AUTOSTASH_LOG = a / "research" / "autostash_failures.jsonl"
    G.AUTOSTASH_ALERT_STATE = a / "research" / ".autostash_alert_state.json"

    # 1. 遠端衝突
    w(a / "Z.txt", "z-local-committed\n"); git(a, "commit", "-q", "-am", "local Z")
    w(a / "X.txt", "x-local-uncommitted\n"); w(a / "Y.txt", "y-local-uncommitted\n")
    G.pull_autostash_safe()
    check("1a X 保留遠端版", (a / "X.txt").read_text(encoding="utf-8") == "x-remote\n", repr((a / "X.txt").read_text(encoding="utf-8")))
    check("1b Y 取回本機未提交版", (a / "Y.txt").read_text(encoding="utf-8") == "y-local-uncommitted\n")
    check("1c stash 保留（不刪）", bool(git(a, "stash", "list").stdout.strip()))
    log = [json.loads(l) for l in G.AUTOSTASH_LOG.read_text(encoding="utf-8").splitlines()] if G.AUTOSTASH_LOG.exists() else []
    check("1d 寫一行失敗紀錄", len(log) == 1 and "X.txt" in log[0]["kept_remote"] and "Y.txt" in log[0]["restored"], str(log)[:160])
    check("1e 推一次 cc_stuck", len(pushes) == 1 and pushes[0][1] == "cc_stuck", str(pushes))

    # 2. stash 之後工作樹被寫成更新版
    git(a, "checkout", "-q", "--", "Y.txt"); git(a, "reset", "-q", "--hard")
    before = git(a, "rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    w(a / "W.txt", "w-at-stash\n")
    sha = git(a, "stash", "create").stdout.strip()
    git(a, "stash", "store", "-m", "autostash", sha)
    w(a / "W.txt", "w-newer-after-stash\n")
    G._restore_failed_autostash(before)
    check("2a 工作樹的更新版 W 沒被舊 stash 蓋掉", (a / "W.txt").read_text(encoding="utf-8") == "w-newer-after-stash\n")
    log = [json.loads(l) for l in G.AUTOSTASH_LOG.read_text(encoding="utf-8").splitlines()]
    check("2b 紀錄列在 kept_worktree_newer", len(log) == 2 and "W.txt" in log[1]["kept_worktree_newer"], str(log[-1])[:160])
    check("2c 只有工作樹較新 → 自動刪這筆 stash", sha not in git(a, "stash", "list", "--format=%H").stdout and log[1].get("stash_dropped") is True,
          str(log[-1].get("drop_reason")))
    check("3 不再推播（六小時內／已自動清除）", len(pushes) == 1, str(pushes))

    # 4. 機器寫檔遠端較新 → 自動刪、不推
    git(a, "stash", "clear"); git(a, "reset", "-q", "--hard")
    git(b, "pull", "-q"); w(b / "data" / "m.json", "m-remote\n"); git(b, "commit", "-q", "-am", "remote m"); git(b, "push", "-q")
    w(a / "Z.txt", "z-local-2\n"); git(a, "commit", "-q", "-am", "local Z2")
    w(a / "data" / "m.json", "m-local-uncommitted\n")
    G.AUTOSTASH_ALERT_STATE.unlink(missing_ok=True)
    G.pull_autostash_safe()
    log = [json.loads(l) for l in G.AUTOSTASH_LOG.read_text(encoding="utf-8").splitlines()]
    check("4a 機器寫檔遠端較新 → 保留遠端版、自動刪 stash", (a / "data" / "m.json").read_text(encoding="utf-8") == "m-remote\n"
          and log[-1].get("stash_dropped") is True and not git(a, "stash", "list").stdout.strip(), str(log[-1])[:200])
    check("4b 自動清除不推播", len(pushes) == 1, str(pushes))
    check("4c 情境 1（人寫的 X.txt 遠端較新）當時有保留 stash", log[0].get("stash_dropped") is False, str(log[0].get("drop_reason")))

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
