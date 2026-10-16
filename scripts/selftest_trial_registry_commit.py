# -*- coding: utf-8 -*-
"""先.一〇三-15 自測：試驗登記一律綁程式 commit。不寫帳本（只測 _bind_code_commit 與 dry_run）。

用法：python scripts/selftest_trial_registry_commit.py
"""
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import trial_registry as T  # noqa: E402

res = []


def check(cond, label):
    res.append((bool(cond), label))
    print(("PASS " if cond else "FAIL ") + label)


# ① 已 commit、沒改動的程式 → 回傳短 SHA
clean = "research/adjust.py"
b = T._bind_code_commit([clean], strict=True)
check(len(b["paths"].get(clean, "")) >= 7, f"已 commit 的程式綁到 SHA（{b['paths']}）")

# ② 還沒加入 git 的程式 → 拒絕登記
_fd, _tp = tempfile.mkstemp(suffix=".py", prefix="_selftest_untracked_", dir=ROOT / "research")
import os
os.close(_fd)
tmp = Path(_tp)
try:
    try:
        T._bind_code_commit([str(tmp)], strict=True)
        check(False, "未加入 git 的程式應拒絕登記")
    except ValueError as e:
        check("尚未加入 git" in str(e), "未加入 git 的程式拒絕登記")
    # ③ dry_run（strict=False）只記錄、不擋
    b2 = T._bind_code_commit([str(tmp)], strict=False)
    check(list(b2["paths"].values()) == ["未 commit"], "dry_run 只標「未 commit」不擋")
finally:
    tmp.unlink(missing_ok=True)

# ④ 沒給 code_paths 時用呼叫端腳本（這支自測檔本身）
b3 = T._bind_code_commit(None, strict=False)
check(any(k.endswith("selftest_trial_registry_commit.py") for k in b3["paths"]), f"沒給 code_paths 就綁呼叫端腳本（{b3['paths']}）")

# ⑤ dry_run 的登記列帶「程式 …（SHA）」
tid, row = T.register_trial(track="TW", name="selftest_commit_binding", design="自測", result="自測 n=1",
                            verdict="未結案", notes="自測，不寫帳本", round_note="自測", no_stats_reason="自測",
                            code_paths=[clean], dry_run=True)
check(f"程式 {clean}（" in row, "登記列附上程式與 commit")

ok = all(r[0] for r in res)
print(f"合計 {len(res)} 項，失敗 {sum(1 for r in res if not r[0])}")
sys.exit(0 if ok else 1)
