# -*- coding: utf-8 -*-
"""收件匣 034（先.一三五-1fr-a）：刪除 10/31 盤點過、確認沒有獨有內容的殘留 git stash。給總司令本人執行一次。

刪之前每一筆都重跑一次盤點（scripts/inventory_autostash_residual.py 的 classify），跟已逐行核對過的
快照 research/data/autostash_residual_20261101.json 比：「要人看」的檔（unique／missing）名單與獨有行數
是快照的子集才刪；多出任何一檔或行數變了 → 跳過那一筆並印出來。用雜湊找位置、刪前再確認一次是同一筆。
刪掉的 commit ID 清單在 research/data/stash_residual_20261031.txt，git 清理（gc）之前仍可救回。
用法：python scripts/drop_autostash_residual.py　（加 --dry 只比對、不刪）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import inventory_autostash_residual as inv  # noqa: E402

SNAP = ROOT / "research" / "data" / "autostash_residual_20261101.json"
LOCK = ROOT / "research" / "git_op_lock.py"


def _g(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main() -> int:
    snap = {r["stash"]: r for r in json.loads(SNAP.read_text(encoding="utf-8"))}
    r = subprocess.run([sys.executable, str(LOCK), "acquire"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("git 鎖被其他排程占用，請過一兩分鐘再跑一次")
        return 1
    m = re.search(r"token=(\w+)", r.stdout or "")
    tok = m.group(1) if m else None
    done, skip = [], []
    print(f"開始逐筆檢查 {len(snap)} 筆（含上千個檔的那筆要好幾分鐘，期間會占住 git 鎖，請等它跑完、不要關視窗）", flush=True)
    try:
        for i, (h, row) in enumerate(snap.items(), 1):
            print(f"  [{i}/{len(snap)}] 檢查 {h[:10]} …", flush=True)
            hashes = _g("stash", "list", "--format=%H").stdout.split()
            if h not in hashes:
                print(f"  已不在清單：{h[:10]}")
                continue
            ci = row["at"]
            names = [n for n in _g("stash", "show", "--name-only", h).stdout.splitlines() if n.strip()]
            look = []
            for n in names:
                c, k = inv.classify(h, ci, n)
                if c in ("unique", "missing"):
                    look.append((n, c, k))
            want = sorted((u["path"], u["class"], u["unique_lines"]) for u in row["needs_look"] if u["class"] in ("unique", "missing"))
            if not set(look) <= set(want):  # 只准變少（例：收件匣 034 起 research/data/paper_*.json 算機器寫檔），多一檔或行數變了就跳過
                skip.append(h)
                print(f"  跳過 {h[:10]}：盤點結果跟已核對的快照不一樣 {sorted(look)} ≠ {want}")
                continue
            if "--dry" in sys.argv:
                done.append(h)
                print(f"  可刪（--dry 未刪）{h[:10]}（{row['at']}，{len(names)} 檔）")
                continue
            ref = f"stash@{{{hashes.index(h)}}}"
            if _g("rev-parse", "-q", "--verify", ref).stdout.strip() != h or _g("stash", "drop", "-q", ref).returncode != 0:
                skip.append(h)
                print(f"  跳過 {h[:10]}：位置剛好變動或刪除失敗")
                continue
            done.append(h)
            print(f"  已刪 {h[:10]}（{row['at']}，{len(names)} 檔）")
    finally:
        subprocess.run([sys.executable, str(LOCK), "release", *(["--token", tok] if tok else [])], cwd=ROOT, capture_output=True)
    print(f"結果：{"可刪" if "--dry" in sys.argv else "刪"} {len(done)} 筆、跳過 {len(skip)} 筆；剩下 stash {len(_g('stash', 'list').stdout.splitlines())} 筆")
    return 0 if not skip else 2


if __name__ == "__main__":
    sys.exit(main())
