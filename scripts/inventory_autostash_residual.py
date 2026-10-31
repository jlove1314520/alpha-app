"""先.一三五-1fr：git stash 殘留盤點（唯讀，不 drop、不改任何檔）。

10/23 清空 56 筆後又累積的 autostash，逐筆逐檔判定：
- same：stash 版本與目前工作樹相同
- superseded：機器寫檔（dev_queue_runner.MACHINE_WRITTEN），且 stash 時間之後 HEAD 有 commit 動過該檔
- lines_kept：人寫的檔，stash 版本每一行都還在目前工作樹（只是被加註／移位）
- unique：人寫的檔有 stash 獨有行（列出行數，要人看）
- machine_stale：機器寫檔但 stash 之後沒有 commit 動過（少見，列出來）
- missing：目前工作樹沒有這個檔
用法：python scripts/inventory_autostash_residual.py [--json 輸出路徑]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _g(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True)


def _machine(path: str) -> bool:
    try:
        from dev_queue_runner import MACHINE_WRITTEN  # noqa: PLC0415
        return any(p.match(path) for p in MACHINE_WRITTEN)
    except Exception:  # noqa: BLE001
        return path.startswith("data/")


def classify(stash: str, stash_ts: str, path: str) -> tuple[str, int]:
    """回傳 (類別, 獨有行數)。"""
    blob = _g("show", f"{stash}:{path}")
    if blob.returncode != 0:
        return "deleted_in_stash", 0
    cur_p = ROOT / path
    if not cur_p.exists():
        return "missing", 0
    cur = cur_p.read_bytes()
    if blob.stdout == cur:
        return "same", 0
    if _machine(path):
        later = _g("log", "-1", "--format=%H", f"--since={stash_ts}", "HEAD", "--", path).stdout.strip()
        return ("superseded" if later else "machine_stale"), 0
    try:
        old = blob.stdout.decode("utf-8").splitlines()
        now = set(cur.decode("utf-8").splitlines())
    except UnicodeDecodeError:
        return "unique", -1
    miss = [ln for ln in old if ln.strip() and ln not in now]
    return ("lines_kept" if not miss else "unique"), len(miss)


def main() -> int:
    out = None
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
    lines = _g("stash", "list", "--format=%H|%ci|%gd|%gs").stdout.decode("utf-8").splitlines()
    report = []
    for ln in lines:
        h, ts, ref, subj = ln.split("|", 3)
        names = _g("stash", "show", "--name-only", h).stdout.decode("utf-8").split("\n")
        names = [n for n in names if n]
        cnt: dict[str, int] = {}
        uniq = []
        for n in names:
            c, k = classify(h, ts, n)
            cnt[c] = cnt.get(c, 0) + 1
            if c in ("unique", "machine_stale", "missing"):
                uniq.append({"path": n, "class": c, "unique_lines": k})
        report.append({"ref": ref, "stash": h, "at": ts, "subject": subj, "files": len(names),
                       "counts": cnt, "needs_look": uniq})
        print(f"{ref} {ts} {subj}：{len(names)} 檔 {cnt}")
        for u in uniq:
            print(f"    ⚠ {u['class']} {u['path']} 獨有行 {u['unique_lines']}")
    if out:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
