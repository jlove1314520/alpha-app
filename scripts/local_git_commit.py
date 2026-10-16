# -*- coding: utf-8 -*-
"""先.八十-11（2026-10-12）：本機排程「只提交自己的產出檔」共用流程。

與三支 wrapper（run-*-cycle.ps1）同一套結案.一 方案甲＋丙：搶 research/git_op_lock.py → commit（pathspec，只收指定檔）
→ pull --rebase --autostash → push 前偵測字面衝突標記（有就跳過 push 並回報）→ push → 放鎖。
鎖被別人持有就整輪跳過、留給下一輪（不排隊）。自身任何失敗只回傳原因字串，不拋例外（十二節）。

2026-10-13 修正（事故）：10-13 04:42 新聞補班的 pull --rebase 撞到雲端同時更新的 events.json 而停在 rebase 中，
舊版只偵測到衝突標記就返回，**把 repo 留在 rebase 進行中（detached HEAD）**，之後 3 小時所有排程都提交到
detached HEAD、push 全失敗。現在：①開始前若 repo 已在 rebase 中就什麼都不做；②pull 失敗或之後仍在 rebase 中
一律 `git rebase --abort` 還原；③drop_on_conflict=True（新聞補班用）時，衝突就撤銷本輪自己剛做的那個 commit
（只在 HEAD 確實是本輪 commit 時）並把產出檔還原成 HEAD 版本——雲端已有較新的同一份資料，本機這輪作廢。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "research" / "git_op_lock.py"
GITDIR = ROOT / ".git"


def _g(*a, timeout=180):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def rebase_in_progress() -> bool:
    return (GITDIR / "rebase-merge").exists() or (GITDIR / "rebase-apply").exists()


def _restore_failed_autostash(stash_before: str) -> str:
    """先.一〇三-14v（2026-10-16 事故）：pull --autostash 套回失敗時，git 把「別的排程／互動視窗」尚未 commit 的修改
    整包留在 stash（`Your changes are safe in the stash`，exit 0），工作目錄留下衝突標記或被清回 HEAD。10:05 新聞補班就這樣
    吃掉 DevQueue 剛重產的 research*.json 與 by_code。

    這裡偵測 refs/stash 換了新的 autostash，就逐檔取回：只取回「遠端這次沒動到」的檔（stash 基底版＝目前 HEAD 版），
    遠端有更新的檔保留遠端版（那正是套回衝突的原因，舊的機器產出以遠端為準）。stash 本身不刪（不可逆，留給人工）。
    自身任何失敗只回傳原因字串（十二節）。"""
    try:
        after = _g("rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
        if not after or after == stash_before:
            return ""
        if "autostash" not in _g("log", "-1", "--format=%gs", "-g", "refs/stash").stdout:
            return ""
        names = [n for n in _g("stash", "show", "--name-only", after).stdout.splitlines() if n.strip()]
        back, kept = [], []
        for n in names:
            if _g("diff", "--quiet", f"{after}^1", "HEAD", "--", n).returncode == 0:
                if _g("checkout", "-q", after, "--", n).returncode == 0:
                    _g("reset", "-q", "--", n)
                    back.append(n)
                    continue
            kept.append(n)
            _g("checkout", "-q", "HEAD", "--", n)  # 套回失敗會留衝突標記（UU），改回遠端版；本機版仍在 stash
        msg = f"autostash 套回失敗：已取回 {len(back)} 檔、遠端較新保留遠端版 {len(kept)} 檔（{', '.join(kept)[:200]}）；stash 未刪"
        print(f"[local_git_commit] {msg}", file=sys.stderr)
        return msg
    except Exception as e:  # noqa: BLE001
        print(f"[local_git_commit] 警告：autostash 取回失敗（{type(e).__name__}: {e}），stash 仍保留", file=sys.stderr)
        return ""


def pull_autostash_safe(timeout=180):
    """先.一〇三-14w：給自己呼叫 `pull --rebase --autostash` 的其他排程用；套回失敗時一樣取回別人未提交的檔。"""
    before = _g("rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    r = _g("pull", "-q", "--rebase", "--autostash", timeout=timeout)
    _restore_failed_autostash(before)
    return r


def pull_or_abort(timeout=180) -> int:
    """先.一〇三-14w 第 2 批：給 .ps1 用的 `python scripts/local_git_commit.py pull`。
    pull 成功回 0；失敗（或停在 rebase 中）就 abort，abort 套回 autostash 失敗一樣取回，回 1。"""
    before = _g("rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    r = pull_autostash_safe(timeout=timeout)
    if r.returncode == 0 and not rebase_in_progress():
        return 0
    _g("rebase", "--abort")
    _restore_failed_autostash(before)
    return 1


def commit_paths(paths: list[str], msg: str, drop_on_conflict: bool = False) -> str:
    if rebase_in_progress():
        return "repo 正在 rebase 中（別的程序留下的），本輪不動，留給人工或下一輪"
    try:
        r = subprocess.run([sys.executable, str(LOCK), "acquire"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if r.returncode != 0:
            return "鎖被其他排程持有，本輪跳過"
        m = re.search(r"token=(\w+)", r.stdout or "")  # 先.八十一-34：持有者憑證，release 時帶回
        tok = m.group(1) if m else None
    except Exception as e:  # noqa: BLE001
        return f"取鎖失敗（{type(e).__name__}），本輪跳過"
    try:
        existing = [p for p in paths if (ROOT / p).exists()]
        if not existing:
            return "沒有產出檔"
        _g("add", "--", *existing)
        if _g("diff", "--cached", "--quiet", "--", *existing).returncode == 0:
            return "沒有變更"
        c = _g("commit", "-q", "-m", msg, "--", *existing)
        if c.returncode != 0:
            return "commit 失敗：" + (c.stderr or c.stdout)[-200:]
        mine = _g("rev-parse", "HEAD").stdout.strip()
        stash_before = _g("rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
        pl = _g("pull", "-q", "--rebase", "--autostash")
        _restore_failed_autostash(stash_before)
        if pl.returncode != 0 or rebase_in_progress():
            _g("rebase", "--abort")
            _restore_failed_autostash(stash_before)  # abort 時才套回 autostash，套回失敗一樣要取回
            if drop_on_conflict and _g("rev-parse", "HEAD").stdout.strip() == mine:
                _g("reset", "-q", "--soft", "HEAD~1")
                _g("reset", "-q", "--", *existing)
                _g("checkout", "-q", "HEAD", "--", *[p for p in existing if _g("ls-files", "--error-unmatch", p).returncode == 0])
                return "pull 與遠端衝突：已 abort，並作廢本機這輪（產出檔還原成 HEAD 版本）"
            return "pull 與遠端衝突：已 abort（commit 留在本機，下一輪再試）"
        marks = _g("grep", "-l", "^<<<<<<< ")
        if marks.returncode == 0 and marks.stdout.strip():
            return "已 commit，但偵測到衝突標記，跳過 push：" + marks.stdout.strip().replace("\n", ", ")[:200]
        p = _g("push", "-q")
        return "已 commit 並 push" if p.returncode == 0 else "已 commit，push 失敗（留給下一輪）"
    except Exception as e:  # noqa: BLE001
        try:
            if rebase_in_progress():
                _g("rebase", "--abort")
        except Exception:  # noqa: BLE001
            pass
        return f"提交流程失敗（{type(e).__name__}: {e}）"
    finally:
        try:
            subprocess.run([sys.executable, str(LOCK), "release", *(["--token", tok] if tok else [])], cwd=ROOT, capture_output=True, timeout=60)
        except Exception:  # noqa: BLE001
            pass


def last_commit_age_min(path: str) -> float | None:
    """該檔最後一次 commit 距今幾分鐘；從沒 commit 過回 None。"""
    import time
    r = _g("log", "-1", "--format=%ct", "--", path, timeout=60)
    s = (r.stdout or "").strip()
    return (time.time() - int(s)) / 60 if s.isdigit() else None


if __name__ == "__main__":
    # .ps1 呼叫：python scripts/local_git_commit.py pull → 0＝成功、1＝pull 失敗已 abort；其他退出碼（含 python 起不來）由 .ps1 退回原本的 git pull（十二節）
    if sys.argv[1:2] == ["pull"]:
        try:
            sys.exit(pull_or_abort())
        except Exception as e:  # noqa: BLE001
            print(f"[local_git_commit] 警告：pull 取回流程失敗（{type(e).__name__}: {e}）", file=sys.stderr)
            sys.exit(2)
    print("用法：python scripts/local_git_commit.py pull", file=sys.stderr)
    sys.exit(2)
