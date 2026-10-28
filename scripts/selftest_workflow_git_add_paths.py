# -*- coding: utf-8 -*-
"""先.一四〇-2（2026-10-29）：workflow「git add」路徑存在性自測（防 先.一四〇-1z 再發）。
先.一四〇-1z 根因：market.yml 大清單 `git add -A a b c …` 裡只要有一個路徑不在工作目錄
（只有特定班次才建立的資料夾、沒資料就不寫的檔），git 就 `fatal: pathspec … did not match`
exit 128，整批資料都不 commit。
本自測（零外部請求）解析 .github/workflows/*.yml 每個沒有 `|| true` 保護的「git add」指令，
逐一 `git ls-files --error-unmatch` 路徑；不在 repo 的列 FAIL（修法：改成獨立一行
`git add -A -- 路徑 2>/dev/null || true`）。含 `$` 變數的路徑無法靜態判斷，略過不檢。
另外自測檢查器本身：餵假 workflow 文字，確認會抓到不存在路徑、會略過有保護的行。
用法：python scripts/selftest_workflow_git_add_paths.py
"""
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 「git add」出現在指令開頭，或 ; && do then 之後（for 迴圈裡那種）
GIT_ADD_RE = re.compile(r"(?:^|[;&]\s*|\bdo\s+|\bthen\s+)git add\b(.*)")


def unprotected_paths(text: str) -> list[tuple[int, str]]:
    """回傳 (行號, 路徑)：沒有 `|| true` 保護的 git add 指令中的每個路徑。"""
    out = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = GIT_ADD_RE.search(line)
        if not m:
            continue
        if "|| true" in line:
            continue
        rest = m.group(1).split(";")[0].split("&&")[0]
        try:
            toks = shlex.split(rest)
        except ValueError:
            toks = rest.split()
        for t in toks:
            if t.startswith("-") or "$" in t or t.startswith(("2>", ">")):
                continue
            out.append((no, t))
    return out


def tracked(path: str) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


res = []
fake = (
    "  run: |\n"
    "    # git add data/註解裡的不算.json\n"
    "    git add -- data/schema_guard/x.json 2>/dev/null || true\n"
    "    git add -A data/STATUS.json data/__不存在__/\n"
    "    for f in a b; do git add -f research/data/$f 2>/dev/null || true; done\n"
)
got = unprotected_paths(fake)
res.append(("檢查器只抓沒保護那行的兩個路徑", got == [(4, "data/STATUS.json"), (4, "data/__不存在__/")]))
res.append(("檢查器判斷：存在的路徑通過", tracked("data/STATUS.json")))
res.append(("檢查器判斷：不存在的路徑會被抓到", not tracked("data/__不存在__/")))

violations = []
n_checked = 0
for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    for no, p in unprotected_paths(wf.read_text(encoding="utf-8")):
        n_checked += 1
        if not tracked(p):
            violations.append(f"{wf.name}:{no} {p}")
res.append((f"所有 workflow 沒保護的 git add 路徑都已在 repo（檢查 {n_checked} 個）", not violations and n_checked > 0))

for name, ok in res:
    print(("PASS " if ok else "FAIL ") + name)
for v in violations:
    print(f"  不在 repo：{v}（改成獨立一行 git add -A -- 路徑 2>/dev/null || true）")
sys.exit(0 if all(ok for _, ok in res) else 1)
