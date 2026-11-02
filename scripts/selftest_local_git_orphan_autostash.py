# -*- coding: utf-8 -*-
"""先.一三五-1hq 自測：`.git/rebase-merge/` 只剩 autostash（11/02 10:45 事故形狀）時，
local_git_commit.abort_rebase() 要能保存 stash、把目錄搬走（不刪）；真的 rebase 停在一半時不得動目錄。
全部在暫存 repo 進行，不碰真 repo。用法：python scripts/selftest_local_git_orphan_autostash.py → 全過 exit 0。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_git_commit as G  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"（{extra}）" if extra else ""))


def git(repo, *a):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    G.ROOT = repo
    G.GITDIR = repo / ".git"

    # 情境 1：只剩 autostash
    (repo / "a.txt").write_text("a\ndirty\n", encoding="utf-8")
    h = git(repo, "stash", "create").stdout.strip()
    git(repo, "checkout", "-q", "--", "a.txt")
    d = repo / ".git" / "rebase-merge"
    d.mkdir()
    (d / "autostash").write_text(h + "\n", encoding="utf-8")
    note = G.abort_rebase()
    check("只剩 autostash：目錄已不在原位", not d.exists(), note)
    check("只剩 autostash：rebase_in_progress() 為假", not G.rebase_in_progress())
    check("只剩 autostash：stash 清單有這筆", h in git(repo, "stash", "list", "--format=%H").stdout.split())
    stale = list((repo / ".git").glob("rebase-merge.stale-*"))
    check("只剩 autostash：目錄搬到 .git 內備份名（不是刪除）", len(stale) == 1 and (stale[0] / "autostash").exists())
    check("回報字串說明了處理方式", "已存成 stash" in note, note)

    # 情境 2：再跑一次（stash 已在清單）不重複 store
    d.mkdir()
    (d / "autostash").write_text(h + "\n", encoding="utf-8")
    n_before = len(git(repo, "stash", "list").stdout.splitlines())
    G.abort_rebase()
    check("同一筆 autostash 不重複存", len(git(repo, "stash", "list").stdout.splitlines()) == n_before)

    # 情境 3：有其他狀態檔（像真的 rebase 停在一半）→ 不動
    d.mkdir(exist_ok=True)
    (d / "autostash").write_text(h + "\n", encoding="utf-8")
    (d / "head-name").write_text("refs/heads/main\n", encoding="utf-8")
    (d / "onto").write_text(h + "\n", encoding="utf-8")
    r = G.recover_orphan_autostash_dir()
    check("有 head-name 等狀態檔：目錄不動", d.exists() and (d / "head-name").exists(), r or "空字串")
    import shutil
    shutil.rmtree(d)

    # 情境 4：雜湊無效 → 不動、不拋例外
    d.mkdir()
    (d / "autostash").write_text("not-a-hash\n", encoding="utf-8")
    r = G.recover_orphan_autostash_dir()
    check("雜湊無效：目錄不動", d.exists(), r)
    shutil.rmtree(d)

    # 情境 5：沒有殘留 → 空字串
    check("沒有殘留：回空字串", G.recover_orphan_autostash_dir() == "")

print("ALL PASS" if ok else "SOME FAIL")
sys.exit(0 if ok else 1)
