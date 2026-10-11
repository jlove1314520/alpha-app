# -*- coding: utf-8 -*-
"""先.六十九-2 自測：scripts/shell_version.py（外殼版本號只在真變動時更新、趕工期間每小時最多發布一次、不掃進別人的修改）。
全程在暫存 git repo 裡跑（ALPHA_SHELL_ROOT 指過去），不碰真 repo、不推送。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


tmp = Path(tempfile.mkdtemp())
env = dict(os.environ, ALPHA_SHELL_ROOT=str(tmp), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
env.pop("ALPHA_CYCLE_ID", None)


def git(*a, e=None):
    return subprocess.run(["git", "-C", str(tmp), *a], capture_output=True, text=True, encoding="utf-8", env=e or env)


def sv(*a, e=None):
    return subprocess.run([sys.executable, str(HERE / "shell_version.py"), *a], capture_output=True, text=True, encoding="utf-8", env=e or env)


def commit(msg, e=None):
    # 模擬 pre-commit：先跑 hook 再 commit（hook 只改暫存區）
    h = sv("hook", e=e)
    c = git("commit", "-q", "-m", msg, e=e)
    return h.stdout + h.stderr, c.returncode


def ver(path, rev="HEAD"):
    t = git("show", f"{rev}:{path}").stdout
    import re
    m = re.search(r"APP_VERSION='([^']*)'|CACHE = 'alpha-v([^']*)'|app\.js\?v=([0-9.-]+)", t)
    return next(g for g in m.groups() if g) if m else None


def state():
    try:
        return json.loads((tmp / "research" / ".shell_release.json").read_text(encoding="utf-8"))
    except OSError:
        return {}


try:
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp / "research").mkdir()
    (tmp / "index.html").write_text("<link href=\"app.css?v=2026-01-01.0000\">\n<script src=\"app.js?v=2026-01-01.0000\"></script>\n<p>a</p>\n", encoding="utf-8")
    (tmp / "app.js").write_text("const APP_VERSION='2026-01-01.0000';\nfunction a(){return 1}\n", encoding="utf-8")
    (tmp / "sw.js").write_text("const CACHE = 'alpha-v2026-01-01.0000';\n", encoding="utf-8")
    (tmp / "app.css").write_text("body{}\n", encoding="utf-8")
    (tmp / "PENDING_QUEUE.md").write_text("# q\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "init")

    # ① 只改版本戳 → 不更新
    (tmp / "app.js").write_text("const APP_VERSION='2026-02-02.0202';\nfunction a(){return 1}\n", encoding="utf-8")
    git("add", "app.js")
    out, _ = commit("stamp only")
    check("①只改版本戳：版本號不更新、印出說明", "只有版本戳字樣變動" in out and ver("sw.js") == "2026-01-01.0000")

    # ② 真的改外殼（非趕工）→ 立即更新三處版本戳
    (tmp / "app.js").write_text("const APP_VERSION='2026-02-02.0202';\nfunction a(){return 2}\n", encoding="utf-8")
    git("add", "app.js")
    out, _ = commit("real change")
    v2 = ver("sw.js")
    check(f"②真變動：sw.js／app.js／index.html 同步更新為 {v2}", v2 != "2026-01-01.0000" and ver("app.js") == v2 and ver("index.html") == v2)
    check("②工作目錄同步、沒有殘留未提交", git("status", "--porcelain").stdout.strip() in ("", "?? research/"))

    # ③ 不掃進別人的修改：app-market.js 與 app.js 有別人的未暫存修改，只暫存 app.css
    (tmp / "app-market.js").write_text("// 別人的半成品\n", encoding="utf-8")
    git("add", "app-market.js")
    git("commit", "-q", "-m", "add module", e=dict(env, ALPHA_SHELL_RELEASING="1"))
    (tmp / "app-market.js").write_text("// 別人的半成品 v2（未暫存）\n", encoding="utf-8")
    with open(tmp / "app.js", "a", encoding="utf-8") as f:
        f.write("// 別人在 app.js 的未暫存修改\n")
    (tmp / "app.css").write_text("body{color:red}\n", encoding="utf-8")
    git("add", "app.css")
    out, _ = commit("css")
    files = set(git("show", "--name-only", "--format=", "HEAD").stdout.split())
    check(f"③只 commit 暫存的 app.css＋版本戳（{sorted(files)}），別人的未暫存修改不被掃進來",
          "app-market.js" not in files and "別人在 app.js" not in git("show", "HEAD:app.js").stdout)
    check("③別人的未暫存修改仍留在工作目錄", "未暫存" in (tmp / "app-market.js").read_text(encoding="utf-8")
          and "別人在 app.js" in (tmp / "app.js").read_text(encoding="utf-8"))
    git("checkout", "--", "app.js", "app-market.js")

    # ④ 趕工＋DevQueue commit＋距上次發布 <60 分 → 延後
    ce = dict(env, ALPHA_CYCLE_ID="TEST", ALPHA_SHELL_CRUNCH="1")
    before = ver("sw.js")
    (tmp / "index.html").write_text((tmp / "index.html").read_text(encoding="utf-8") + "<p>b</p>\n", encoding="utf-8")
    git("add", "index.html")
    out, rc = commit("devqueue shell change", e=ce)
    check("④趕工中 DevQueue 外殼 commit：照常 commit、版本號不動、記待發布", rc == 0 and ver("sw.js") == before and state().get("pending") is True and "延後發布" in out)
    # 互動視窗（無 ALPHA_CYCLE_ID）即使在趕工也立即發布
    (tmp / "app.css").write_text("body{color:blue}\n", encoding="utf-8")
    git("add", "app.css")
    ie = dict(env, ALPHA_SHELL_CRUNCH="1")
    out, _ = commit("interactive change", e=ie)
    check("④互動視窗的外殼 commit 不延後（立即更新版本號、清除待發布）", ver("sw.js") != before and state().get("pending") is False)

    # ⑤ release：再累積一次待發布 → 不滿 60 分不發布 → 改成 61 分前 → 發布並單獨 commit
    (tmp / "index.html").write_text((tmp / "index.html").read_text(encoding="utf-8") + "<p>c</p>\n", encoding="utf-8")
    git("add", "index.html")
    commit("devqueue 2", e=ce)
    v_hold = ver("sw.js")
    r = sv("release", e=ce)
    check("⑤release：不滿 60 分不發布", "不滿 60 分鐘" in r.stdout and ver("sw.js") == v_hold)
    st = state()
    st["last_release"] = time.time() - 61 * 60
    (tmp / "research" / ".shell_release.json").write_text(json.dumps(st), encoding="utf-8")
    r = sv("release", e=ce)
    msg = git("log", "-1", "--format=%s").stdout
    check(f"⑤release：滿 60 分→蓋戳單獨 commit（{msg.strip()[:30]}…）", "已發布外殼版本" in r.stdout and ver("sw.js") != v_hold and "App 外殼發布" in msg
          and set(git("show", "--name-only", "--format=", "HEAD").stdout.split()) <= {"index.html", "app.js", "sw.js"})
    check("⑤發布後狀態清除待發布", state().get("pending") is False)
    # 暫存區有別人的東西 → 延後
    st = state(); st.update(pending=True, last_release=time.time() - 2 * 3600)
    (tmp / "research" / ".shell_release.json").write_text(json.dumps(st), encoding="utf-8")
    (tmp / "PENDING_QUEUE.md").write_text("# q2\n", encoding="utf-8")
    git("add", "PENDING_QUEUE.md")
    r = sv("release", e=ce)
    check("⑤暫存區有別人的變動 → 不發布、不混進別人的 commit", "暫存區有其他人的變動" in r.stdout)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
