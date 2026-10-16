# -*- coding: utf-8 -*-
"""先.一〇六（2026-10-16 總司令裁示）：內部人持股轉讓紀錄的舊 v1 姓名雜湊清空。一次性、可重跑（冪等）。

做法（不用猜，全部從 git log 查）：
1. 每筆紀錄依新編號規則（fetch_insider_transfer_tw.record_id，不含姓名雜湊）重算 id，檢查沒有重複、筆數不變。
2. 走過 data/insider_transfer_tw_history.json 的每一個歷史版本（git log --reverse），找每筆第一次出現的 commit。
   那個 commit 若是 HMAC 程式（先.一〇三-19，commit 5dd30bb118）的後代 → 是 HMAC 上線後的班次寫的 → "hmac-sha256-v2"；
   否則 → "v1"。（實際分界＝10/16 05:43 班，run 38826167660，commit a99e9f96ee。）
3. v1 紀錄：name_hash／transferee_hash 改 null、hash_scheme 改 "v1-cleared"，其他欄位一律不動。
4. meta.note 加「10/16 以前的姓名雜湊已清空（舊算法可被比對）；git 歷史不改寫。」

不改寫 git 歷史、不碰 HMAC 金鑰、不讀 INSIDER_HASH_KEY。
用法：python scripts/migrate_insider_hash_v1_clear.py [--dry-run]
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援 reconfigure 時照舊輸出
    pass

ROOT = Path(__file__).resolve().parent.parent
REL = "data/insider_transfer_tw_history.json"
PATH = ROOT / REL
HMAC_CODE_COMMIT = "5dd30bb118"  # 先.一〇三-19：姓名雜湊改 HMAC 的程式 commit

spec = importlib.util.spec_from_file_location("fit", ROOT / ".github" / "scripts" / "fetch_insider_transfer_tw.py")
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def first_seen() -> dict[str, str]:
    """新編號 → 第一次出現的 commit（完整 SHA）。"""
    out: dict[str, str] = {}
    log = git("log", "--reverse", "--format=%H", "--", REL).stdout.decode().split()
    for h in log:
        doc = json.loads(git("show", f"{h}:{REL}").stdout.decode("utf-8"))
        for r in doc.get("records") or []:
            out.setdefault(fit.record_id(r), h)
    return out


def after_hmac(commit: str) -> bool:
    return git("merge-base", "--is-ancestor", HMAC_CODE_COMMIT, commit).returncode == 0


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    recs = doc["records"]
    n_before = len(recs)
    new_ids = [fit.record_id(r) for r in recs]
    dup = sum(c - 1 for c in Counter(new_ids).values() if c > 1)
    print(f"改動前 {n_before} 筆；新編號規則下重複 {dup} 筆")
    if dup:
        print("有重複，停止（裁示：筆數不能變）")
        return 1

    seen = first_seen()
    cache: dict[str, bool] = {}
    out, tally = [], Counter()
    for r, nid in zip(recs, new_ids):
        r = dict(r, id=nid)
        if r.get("hash_scheme") == "v1-cleared":
            pass  # 已清過（重跑）
        else:
            c = seen.get(nid)
            if c is None:
                print(f"找不到 {nid}（{r.get('code')} {r.get('report_date')}）第一次出現的 commit，停止，不猜")
                return 1
            if c not in cache:
                cache[c] = after_hmac(c)
            if cache[c]:
                r["hash_scheme"] = "hmac-sha256-v2"
            else:
                r["name_hash"] = None
                r["transferee_hash"] = None
                r["hash_scheme"] = "v1-cleared"
        tally[r["hash_scheme"]] += 1
        out.append(r)
    print("第一次出現的 commit：", dict(Counter(seen[i][:10] for i in new_ids)))
    print("分類：", dict(tally))
    assert len(out) == n_before

    doc["records"] = out
    meta = doc.setdefault("meta", {})
    meta["record_count"] = len(out)
    if fit.V1_CLEARED_NOTE not in (meta.get("note") or ""):
        meta["note"] = (meta.get("note") or "") + fit.V1_CLEARED_NOTE
    print(f"改動後 {len(out)} 筆")
    if dry:
        print("--dry-run：不寫檔")
        return 0
    PATH.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
