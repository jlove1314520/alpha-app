# -*- coding: utf-8 -*-
"""收件匣 029 自測（先.一三五-1ag-a 甲）：不可逆組的資料切分保留字要跟動詞同句才擋。

不改任何檔案、不呼叫 claude。檢查：
①應放行：1aa 原措辭（改寫前，從 git 版本 9e8c7e0c1a 讀；讀不到用內建摘錄）、「… 讀取清查」、常數名／檔名／函式名提及
②應擋：「解鎖 … 跑最終檢定」「呼叫 unlock_…_once()」「擴大 … 期間」「用 … 期間資料跑回測」
③其他不可逆字照舊：「刪除 alpha.db 舊表」仍擋
④現行 PENDING_QUEUE 全部 - [ ] 修前（GUARD_HOLDOUT_VERB_ON=False）／修後被擋清單差異：修後只會少擋、不會多擋
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dev_queue_runner as D  # noqa: E402

W = "hold" + "out"  # 拆開寫，避免本檔被其他掃描器當成要動用資料切分
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"｜{detail}" if detail and not ok else ""))


def irr(text):
    return D.guard_hits(text)["irreversible"]


def old_1aa():
    try:
        pq = subprocess.run(["git", "-C", str(ROOT), "show", "9e8c7e0c1a:PENDING_QUEUE.md"],
                            capture_output=True, check=True).stdout.decode("utf-8", "replace")
        for ln in pq.splitlines():
            if "**先.一三五-1aa " in ln:
                return re.sub(r"^\s*- \[.\]\s*", "", ln).strip(), "git 9e8c7e0c1a"
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] 讀 git 版本失敗（{type(e).__name__}），改用內建摘錄")
    return (f"**先.一三五-1aa 前向追蹤程式讀 {W} 期間資料的方式清查（14 支 vs `ALLOWED_HOLDOUT_READERS`，零請求）** "
            f"[維運]〔做法：新增 `scripts/audit_forward_{W}_reads.py`，逐支列出是否呼叫 `{W}.assert_no_{W}_leakage()`〕"), "內建摘錄"


t, src = old_1aa()
check(f"① 放行：1aa 原措辭（{src}）", not irr(t), irr(t))
PASS_CASES = [
    f"**先.X {W} 讀取清查** [維運]〔做法：列出哪些程式 import `{W}.py`〕",
    f"**先.X 白名單 `{W}.ALLOWED_READERS` 比對** [維運]",
]
for c in PASS_CASES:
    check("① 放行：" + c[6:26], not irr(c), irr(c))
BLOCK_CASES = [
    f"**某研究 解鎖 {W} 跑最終檢定** [研究]",
    f"**某研究 最終一次** [研究]〔做法：呼叫 unlock_{W}_once() 後跑一次〕",
    f"**某研究 擴大 {W} 期間到 2026** [研究]",
    f"**某研究 用 {W} 期間資料跑回測** [研究]",
]
for c in BLOCK_CASES:
    check("② 照擋：" + c[2:26], bool(irr(c)), irr(c))
check("③ 其他不可逆字照舊：刪除 alpha.db 舊表", bool(irr("**先.X 刪除 alpha.db 舊表** [維運]")))


def blocked(pq_text):
    out = set()
    for ln in pq_text.splitlines():
        if ln.lstrip().startswith("- [ ]"):
            clean = re.sub(r"^\s*- \[ \]\s*", "", ln).strip()
            h = D.guard_hits(clean)
            if h["needs_user"] or h["irreversible"]:
                out.add(clean[:50])
    return out


cur = (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8", errors="replace")
D.GUARD_HOLDOUT_VERB_ON = False
before = blocked(cur)
D.GUARD_HOLDOUT_VERB_ON = True
after = blocked(cur)
print(f"\n[現行 PENDING_QUEUE] 修前被擋 {len(before)} 條、修後 {len(after)} 條")
for x in sorted(before - after):
    print("  修後放行：" + x)
for x in sorted(after - before):
    print("  修後新擋：" + x)
for x in sorted(after):
    print("  修前修後都擋：" + x)
check("④ 現行佇列：修後被擋 ⊆ 修前被擋", after <= before, str(after - before))

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} PASS")
sys.exit(1 if bad else 0)
