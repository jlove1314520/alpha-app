# -*- coding: utf-8 -*-
"""先.一三五-1kk（2026-11-05）自測：_restore_failed_autostash 批次版與舊逐檔版判定一致、耗時下降。

暫存 bare origin＋兩個 clone，不碰真 repo、不發推播：
1. 本機 1,000 檔未提交修改（含 3 檔刪除、檔名含空白），遠端同時改了其中 60 檔＋另外 40 檔、刪 2 檔，
   本機 pull --rebase --autostash 套回失敗留下 autostash；之後別的寫入者又把 25 檔寫成更新版。
2. 把整個 repo 複製成兩份，一份跑舊版 _classify_restore_per_file、一份跑新版 _classify_restore_batch：
   back／kept／newer 三組名單逐檔一致、兩份工作樹每個檔內容一致、`git status --porcelain` 一致、
   暫存區（diff --cached）一致，且已取回的檔都已撤出暫存區（git 部分套回時會自己 add，別人 commit 會夾帶）。
3. 新版耗時明顯低於舊版（要求 < 舊版 1/3）。
4. 新版判定出錯（cat-file 起不來）時 _restore_failed_autostash 退回逐檔，不拋例外。
跑法：python scripts/selftest_autostash_restore_batch.py
"""
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import local_git_commit as G  # noqa: E402

sys.modules["cc_push"] = types.SimpleNamespace(_send=lambda t, b, k: {"ok": 1})
fails = []
N = 1000


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, encoding="utf-8")


def fname(i):
    return f"data/ev/{i:04d}.json" if i % 97 else f"data/ev/with space {i:04d}.json"


def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", newline="\n")


def snapshot(repo: Path):
    files = {}
    for p in sorted((repo / "data").rglob("*")):
        if p.is_file():
            files[p.relative_to(repo).as_posix()] = p.read_bytes()
    st = git(repo, "status", "--porcelain").stdout
    cached = git(repo, "diff", "--cached", "--name-status").stdout
    return files, st, cached


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    origin, a, b = td / "origin.git", td / "a", td / "b"
    git(td, "init", "-q", "--bare", "-b", "main", str(origin))
    git(td, "clone", "-q", str(origin), str(a))
    git(a, "config", "user.email", "t@example.invalid"); git(a, "config", "user.name", "t")
    git(a, "checkout", "-q", "-b", "main")
    for i in range(N + 50):
        w(a / fname(i), f'{{"i": {i}, "v": 0}}\n')
    git(a, "add", "-A"); git(a, "commit", "-q", "-m", "init"); git(a, "push", "-q", "-u", "origin", "main")
    git(td, "clone", "-q", str(origin), str(b))
    git(b, "config", "user.email", "t@example.invalid"); git(b, "config", "user.name", "t")
    remote_mod = list(range(0, 600, 10)) + list(range(1005, 1045))  # 60 檔與本機重疊＋40 檔本機沒動
    for i in remote_mod:
        w(b / fname(i), f'{{"i": {i}, "v": "remote"}}\n')
    for i in (3, 1046):
        (b / fname(i)).unlink()
    git(b, "add", "-A"); git(b, "commit", "-q", "-m", "remote"); git(b, "push", "-q")

    for i in range(N):
        if i in (7, 11, 500):
            (a / fname(i)).unlink()  # 本機未提交的刪除
        else:
            w(a / fname(i), f'{{"i": {i}, "v": "local"}}\n')
    before = git(a, "rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    pl = git(a, "pull", "-q", "--rebase", "--autostash")
    after = git(a, "rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    subj = git(a, "log", "-1", "--format=%gs", "-g", "refs/stash").stdout
    check("0 情境成立：留下 autostash", bool(after) and after != before and "autostash" in subj, (pl.stderr or "")[-160:])
    for i in range(700, 725):  # stash 之後別的寫入者寫了更新版
        w(a / fname(i), f'{{"i": {i}, "v": "newer"}}\n')

    a1, a2 = td / "a1", td / "a2"
    shutil.copytree(a, a1)
    shutil.copytree(a, a2)
    names = [n for n in git(a, "stash", "show", "--name-only", after).stdout.splitlines() if n.strip()]
    check("0b stash 檔數", len(names) >= N, str(len(names)))

    G.ROOT, G.GITDIR = a1, a1 / ".git"
    t0 = time.perf_counter()
    r_old = G._classify_restore_per_file(after, names)
    t_old = time.perf_counter() - t0
    G.ROOT, G.GITDIR = a2, a2 / ".git"
    t0 = time.perf_counter()
    r_new = G._classify_restore_batch(after, names)
    t_new = time.perf_counter() - t0
    G.ROOT, G.GITDIR = a1, a1 / ".git"
    G._unstage(r_old[0] + r_old[2])
    G.ROOT, G.GITDIR = a2, a2 / ".git"
    G._unstage(r_new[0] + r_new[2])
    for k, lab in enumerate(("back", "kept", "newer")):
        o, n = r_old[k], r_new[k]
        check(f"1{'abc'[k]} {lab} 名單一致", o == n, f"舊 {len(o)}／新 {len(n)}；差 {sorted(set(o) ^ set(n))[:5]}")
    s1, s2 = snapshot(a1), snapshot(a2)
    diff_files = [k for k in set(s1[0]) | set(s2[0]) if s1[0].get(k) != s2[0].get(k)]
    check("2a 兩份工作樹每個檔內容一致", not diff_files, str(diff_files[:5]))
    check("2b git status 一致", s1[1] == s2[1], "")
    check("2c 暫存區一致（新版不會把 stash 版留在暫存區）", s1[2] == s2[2], repr(s2[2][:160]))
    staged = {ln.split("	", 1)[-1] for ln in s2[2].splitlines()}
    check("2d 已取回與工作樹較新的檔都不在暫存區（_unstage）", not staged & set(r_new[0] + r_new[2]), str(sorted(staged & set(r_new[0] + r_new[2]))[:5]))
    check("3 耗時明顯下降（< 舊版 1/3）", t_new < t_old / 3, f"舊 {t_old:.1f}s／新 {t_new:.1f}s")
    print(f"   back {len(r_new[0])}、kept {len(r_new[1])}、newer {len(r_new[2])}；舊 {t_old:.1f}s → 新 {t_new:.1f}s")

    # 4. 批次判定出錯 → 退回逐檔，不拋例外
    a3 = td / "a3"
    shutil.copytree(a, a3)
    G.ROOT, G.GITDIR = a3, a3 / ".git"
    G.AUTOSTASH_LOG = a3 / "autostash_failures.jsonl"
    G.AUTOSTASH_ALERT_STATE = a3 / ".autostash_alert_state.json"
    orig = G._cat_blobs
    G._cat_blobs = lambda specs, timeout=300: (_ for _ in ()).throw(RuntimeError("模擬 cat-file 起不來"))
    try:
        msg = G._restore_failed_autostash(before)
        ok4 = f"已取回 {len(r_old[0])} 檔" in msg
    except Exception as e:  # noqa: BLE001
        ok4, msg = False, f"拋例外 {e}"
    G._cat_blobs = orig
    check("4 批次出錯退回逐檔、結果同舊版", ok4, msg[:120])

print("\n結果：" + ("全部通過" if not fails else f"FAIL {len(fails)} 項：{fails}"))
sys.exit(1 if fails else 0)
