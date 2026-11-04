# -*- coding: utf-8 -*-
"""先.一三五-1kc-a（收件匣 039 定案甲）自測：news_events.yml Commit 步驟的 pull/push 迴圈。
從 workflow 取出「for i in 1 2 3 … done」那段，在暫存 repo 跑三種情境：
1. 同檔衝突 → exit 0、印 ::warning::、rebase 已 abort
2. 單純非快轉（別人推了不相干的檔）→ 重試成功、exit 0、遠端有本班 commit
3. 遠端不存在（模擬網路錯）→ exit 1，不吞錯
不碰真 repo、零外部請求。跑法：python scripts/selftest_news_commit_conflict.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
yml = (ROOT / ".github" / "workflows" / "news_events.yml").read_text(encoding="utf-8")
m = re.search(r"^( *)for i in 1 2 3; do\n.*?^\1done\n(?:.*\n){0,2}?\1exit 1\n", yml, re.S | re.M)
if not m:
    print("FAIL 找不到 workflow 裡的重試迴圈")
    sys.exit(1)
loop = "\n".join(ln[len(m.group(1)):] for ln in m.group(0).splitlines()).replace("sleep $((i * 5))", "sleep 0")
BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
fails = []


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def setup(td: Path):
    remote = td / "remote.git"
    git(td, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = td / "seed"
    git(td, "clone", "-q", str(remote), str(seed))
    for d in (seed,):
        git(d, "config", "user.email", "t@example.invalid"); git(d, "config", "user.name", "t")
    (seed / "news.json").write_text("v0\n", encoding="utf-8")
    git(seed, "add", "."); git(seed, "commit", "-q", "-m", "seed"); git(seed, "push", "-q", "origin", "HEAD:main")
    ci = td / "ci"
    git(td, "clone", "-q", str(remote), str(ci))
    git(ci, "config", "user.email", "c@example.invalid"); git(ci, "config", "user.name", "c")
    return remote, seed, ci


def run_loop(ci: Path):
    r = subprocess.run([BASH, "-c", loop], cwd=ci, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    remote, seed, ci = setup(td)
    (seed / "news.json").write_text("local\n", encoding="utf-8"); git(seed, "commit", "-qam", "local"); git(seed, "push", "-q")
    (ci / "news.json").write_text("cloud\n", encoding="utf-8"); git(ci, "commit", "-qam", "cloud")
    rc, out = run_loop(ci)
    clean = not (ci / ".git" / "rebase-merge").exists() and not (ci / ".git" / "rebase-apply").exists()
    check("1 同檔衝突 → exit 0＋警告＋rebase 已 abort", rc == 0 and "::warning::" in out and clean, f"rc={rc}")

with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    remote, seed, ci = setup(td)
    (seed / "other.json").write_text("x\n", encoding="utf-8"); git(seed, "add", "."); git(seed, "commit", "-qm", "other"); git(seed, "push", "-q")
    (ci / "news.json").write_text("cloud\n", encoding="utf-8"); git(ci, "commit", "-qam", "cloud")
    rc, out = run_loop(ci)
    log = git(td, "--git-dir", str(remote), "log", "--format=%s", "main").stdout
    check("2 非快轉 → 重試成功、遠端有本班 commit", rc == 0 and "cloud" in log and "other" in log, f"rc={rc}")

with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    remote, seed, ci = setup(td)
    (ci / "news.json").write_text("cloud\n", encoding="utf-8"); git(ci, "commit", "-qam", "cloud")
    git(ci, "remote", "set-url", "origin", str(td / "no_such_remote.git"))
    rc, out = run_loop(ci)
    check("3 遠端連不到 → exit 1 不吞錯", rc == 1 and "::warning::" not in out, f"rc={rc}")

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
