# -*- coding: utf-8 -*-
"""先.八十-11 自測：本機心跳提交（commit_local_heartbeats.py）與新聞本機補班（news_local_fallback.py）的判斷邏輯。
全程替換 git／子行程／提交函式，不碰真的 repo、不連網。
①心跳：上次提交 <60 分鐘 → 不提交；≥60 分鐘或從沒提交 → 只提交該工作自己的產出檔
②新聞：雲端 news.json 20 分鐘前更新 → 不跑任何步驟；90 分鐘沒更新 → 依 workflow 順序跑 5 步、只提交 workflow 的產出檔
③新聞：第一步（抓新聞）失敗 → 不提交
④（2026-10-13 事故回歸）真的 git：兩個 clone 同時改同一檔 → commit_paths(drop_on_conflict=True) 不得留下 rebase 進行中、本輪 commit 作廢、檔案還原
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import commit_local_heartbeats as H  # noqa: E402
import local_git_commit as G  # noqa: E402
import news_local_fallback as N  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


calls = []
saved = (G.last_commit_age_min, G.commit_paths, N.origin_age_min, N.subprocess.run, N.log, sys.argv)
try:
    G.commit_paths = lambda paths, msg, **kw: (calls.append(("commit", tuple(paths))), "已 commit 並 push")[1]
    N.log = lambda m: None
    # ① 心跳節流
    G.last_commit_age_min = lambda p: 15.0
    sys.argv = ["x", "connectivity"]; H.main()
    check("①上次提交 15 分鐘前 → 不提交", not calls)
    G.last_commit_age_min = lambda p: 75.0
    H.main()
    check("①75 分鐘 → 只提交連通性監測自己的檔", calls == [("commit", ("research/external_connectivity.jsonl", "research/connectivity_check.log"))])
    calls.clear(); G.last_commit_age_min = lambda p: None; sys.argv = ["x", "probe"]; H.main()
    check("①從沒提交過 → 提交探測檔", calls and calls[0][1][0] == "research/twse_publish_probe.jsonl")
    # ② 新聞補班
    ran = []

    class R:
        def __init__(self, rc): self.returncode, self.stdout, self.stderr = rc, "", ""

    def fake_run(args, **kw):
        ran.append(args[1] if len(args) > 1 else args[0])
        return R(0)
    N.subprocess.run = fake_run
    calls.clear(); ran.clear(); N.origin_age_min = lambda: 20.0; N.main()
    check("②雲端 20 分鐘前更新 → 不跑任何步驟、不提交", not ran and not calls)
    calls.clear(); ran.clear(); N.origin_age_min = lambda: 90.0; N.main()
    want = [s[0][0] for s in N.STEPS]
    check(f"②雲端 90 分鐘沒更新 → 依序跑 5 步＋schema 守門（{len(ran)} 個）", ran[:5] == want and "scripts/data_schema_guard.py" in ran)
    check("②只提交 workflow 本來就提交的產出檔", calls and set(calls[0][1]) == set(N.OUTPUTS))
    # ③ 第一步失敗
    def fail_first(args, **kw):
        ran.append(args[1]); return R(1 if args[1] == N.STEPS[0][0][0] else 0)
    N.subprocess.run = fail_first
    calls.clear(); ran.clear(); N.main()
    check("③抓新聞失敗 → 不提交", not calls and ran == [N.STEPS[0][0][0]])
finally:
    G.last_commit_age_min, G.commit_paths, N.origin_age_min, N.subprocess.run, N.log, sys.argv = saved

# ④ 真 git 衝突回歸（暫存目錄的 bare origin＋兩個 clone）
import shutil, subprocess, tempfile, importlib
tmp = Path(tempfile.mkdtemp())
try:
    run = lambda cwd, *a: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    run(tmp, "init", "-q", "--bare", "origin.git")
    for name in ("a", "b"):
        run(tmp, "clone", "-q", str(tmp / "origin.git"), name)
        run(tmp / name, "config", "user.email", "t@t"); run(tmp / name, "config", "user.name", "t")
    (tmp / "a" / "f.json").write_text("1\n"); run(tmp / "a", "add", "f.json"); run(tmp / "a", "commit", "-qm", "init"); run(tmp / "a", "push", "-q", "origin", "HEAD")
    run(tmp / "b", "pull", "-q", "origin", "HEAD")
    br = run(tmp / "a", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    run(tmp / "b", "checkout", "-q", br) ; run(tmp / "b", "branch", "-q", "--set-upstream-to", f"origin/{br}")
    (tmp / "a" / "f.json").write_text("2-cloud\n"); run(tmp / "a", "commit", "-qam", "cloud"); run(tmp / "a", "push", "-q", "origin", "HEAD")
    (tmp / "b" / "research").mkdir()
    (tmp / "b" / "research" / "git_op_lock.py").write_text("import sys\nprint('LOCK_ACQUIRED')\n")
    (tmp / "b" / "f.json").write_text("2-local\n")
    G2 = importlib.reload(G)
    G2.ROOT, G2.GITDIR, G2.LOCK = tmp / "b", tmp / "b" / ".git", tmp / "b" / "research" / "git_op_lock.py"
    head0 = run(tmp / "b", "rev-parse", "HEAD").stdout.strip()
    msg = G2.commit_paths(["f.json"], "local", drop_on_conflict=True)
    check(f"④衝突時不留下 rebase 進行中（{msg}）", not G2.rebase_in_progress())
    check("④本輪 commit 作廢、HEAD 回到原點、檔案還原 HEAD 版本",
          run(tmp / "b", "rev-parse", "HEAD").stdout.strip() == head0 and (tmp / "b" / "f.json").read_text() == "1\n")
    check("④仍在分支上（不是 detached HEAD）", run(tmp / "b", "symbolic-ref", "-q", "HEAD").returncode == 0)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
