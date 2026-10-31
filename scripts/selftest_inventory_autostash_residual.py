# -*- coding: utf-8 -*-
"""自測：git stash 殘留盤點工具（先.一三五-1fu）——零外部請求、不碰本 repo 的 stash。

在暫存目錄建一個獨立 git repo，造出 6 種情境的 stash，monkeypatch `inv.ROOT` 與 `inv._machine`，
確認 classify()／main() 的分類：
  same／superseded／machine_stale／lines_kept／unique（含獨有行數）／deleted_in_stash／missing，
另確認 main() 只讀不寫：跑完後暫存 repo 的 stash 筆數與工作樹內容不變。
用法：python scripts/selftest_inventory_autostash_residual.py
"""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import inventory_autostash_residual as inv  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def git(repo, *a):
    r = subprocess.run(["git", *a], cwd=repo, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(a)}：{r.stderr.decode('utf-8', 'replace')}")
    return r.stdout.decode("utf-8", "replace").strip()


def w(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


with tempfile.TemporaryDirectory() as td:
    repo = Path(td)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "selftest@example.invalid")
    git(repo, "config", "user.name", "selftest")
    git(repo, "config", "commit.gpgsign", "false")
    files = {
        "data/same.json": "{}\n",
        "data/super.json": "v1\n",
        "data/stale.json": "v1\n",
        "notes/kept.md": "甲\n乙\n",
        "notes/uniq.md": "甲\n乙\n",
        "notes/gone.md": "x\n",
        "notes/del.md": "y\n",
    }
    for k, v in files.items():
        w(repo, k, v)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    time.sleep(1.2)  # --since 含當秒，init commit 不得與 stash 同秒

    # stash 內容：每檔各改成對應情境
    w(repo, "data/same.json", "{\"a\":1}\n")      # 之後工作樹會改成一樣 → same
    w(repo, "data/super.json", "v2-stash\n")      # 之後 HEAD 有 commit 動過 → superseded
    w(repo, "data/stale.json", "v2-stash\n")      # 之後沒 commit 動過 → machine_stale
    w(repo, "notes/kept.md", "甲\n乙\n")         # 先不動，下面加一行再 stash
    w(repo, "notes/kept.md", "甲\n")              # stash 版本只有「甲」，工作樹之後仍有 → lines_kept
    w(repo, "notes/uniq.md", "甲\n獨有一\n獨有二\n")  # 兩行獨有 → unique 2
    w(repo, "notes/gone.md", "x2\n")              # 之後工作樹刪掉 → missing
    (repo / "notes/del.md").unlink()              # stash 內刪除 → deleted_in_stash
    git(repo, "stash", "push", "-q", "-m", "autostash-selftest")
    time.sleep(1.2)  # --since 精度為秒，避免 stash 與後續 commit 同秒
    w(repo, "data/super.json", "v3-later\n")
    git(repo, "add", "data/super.json")
    git(repo, "commit", "-q", "-m", "later machine commit")
    w(repo, "data/same.json", "{\"a\":1}\n")
    (repo / "notes/gone.md").unlink()

    inv.ROOT = repo
    inv._machine = lambda p: p.startswith("data/")
    h = git(repo, "stash", "list", "--format=%H")
    ts = git(repo, "stash", "list", "--format=%ci")

    exp = {
        "data/same.json": ("same", 0),
        "data/super.json": ("superseded", 0),
        "data/stale.json": ("machine_stale", 0),
        "notes/kept.md": ("lines_kept", 0),
        "notes/uniq.md": ("unique", 2),
        "notes/gone.md": ("missing", 0),
        "notes/del.md": ("deleted_in_stash", 0),
    }
    for path, want in exp.items():
        got = inv.classify(h, ts, path)
        check(f"classify {path} → {want[0]}", got == want, f"得到 {got}")

    # 非 UTF-8 人寫檔 → unique、-1
    w(repo, "notes/bin.md", "z\n")
    git(repo, "add", "notes/bin.md")
    git(repo, "commit", "-q", "-m", "bin")
    (repo / "notes/bin.md").write_bytes(b"\xff\xfe\x00bad\n")
    git(repo, "stash", "push", "-q", "-m", "autostash-bin", "--", "notes/bin.md")  # 只收這檔，不帶走前面情境
    (repo / "notes/bin.md").write_bytes(b"other\n")
    h2 = git(repo, "stash", "list", "-1", "--format=%H")
    ts2 = git(repo, "stash", "list", "-1", "--format=%ci")
    got = inv.classify(h2, ts2, "notes/bin.md")
    check("classify 非 UTF-8 人寫檔 → unique／-1", got == ("unique", -1), f"得到 {got}")

    before_list = git(repo, "stash", "list", "--format=%H")
    before_tree = {p.relative_to(repo).as_posix(): p.read_bytes()
                   for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}
    out = repo.parent / f"inv_selftest_{int(time.time())}.json"
    sys.argv = ["x", "--json", str(out)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = inv.main()
    check("main() exit 0", rc == 0)
    try:
        rep = json.loads(out.read_text(encoding="utf-8"))
    finally:
        out.unlink(missing_ok=True)
    check("main() 兩筆 stash 都有報告", len(rep) == 2, f"{len(rep)}")
    first = next((r for r in rep if r["subject"].endswith("autostash-selftest")), None)
    check("main() 第一筆 counts 正確", first is not None and first["counts"] == {
        "same": 1, "superseded": 1, "machine_stale": 1, "lines_kept": 1,
        "unique": 1, "missing": 1, "deleted_in_stash": 1}, f"{first and first['counts']}")
    needs = sorted((u["path"], u["class"]) for u in (first or {}).get("needs_look", []))
    check("main() needs_look 只列 unique／machine_stale／missing", needs == [
        ("data/stale.json", "machine_stale"), ("notes/gone.md", "missing"), ("notes/uniq.md", "unique")],
        f"{needs}")
    after_tree = {p.relative_to(repo).as_posix(): p.read_bytes()
                  for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}
    check("main() 唯讀：stash 筆數不變", git(repo, "stash", "list", "--format=%H") == before_list)
    check("main() 唯讀：工作樹不變", before_tree == after_tree)

print(f"\n{'全過' if not FAILS else f'{len(FAILS)} 項 FAIL'}")
sys.exit(1 if FAILS else 0)
