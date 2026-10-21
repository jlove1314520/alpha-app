# -*- coding: utf-8 -*-
"""收件匣 013（2026-10-22）自測：DevQueue 不再被「自己」逼讓路，但別人中途改檔仍讓路。

1. _running_cmdlines() 不含本程序自己的命令列（本程式名在 PENDING_QUEUE.md 寫手名單裡，以前永遠命中）。
2. 暫存 git repo 端到端：mark_blocked 式改動＋記雜湊 → _recent_real_dirty_reason() 回 None（不讓路）；
   之後任何人再改一個字 → 回讓路理由；沒有寫入紀錄 → 讓路；紀錄壞掉 → 讓路（fail safe）。
跑法：python scripts/selftest_dev_queue_self_yield.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import dev_queue_runner as D  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


# 1. 自己不算
me = " ".join(sys.argv).lower()
cmds = D._running_cmdlines() or []
check("1 執行中程序清單不含自己", not any("selftest_dev_queue_self_yield" in c for c in cmds), f"（{len(cmds)} 筆）")

# 2. 端到端
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    git = lambda *a: subprocess.run(["git", "-C", td, *a], capture_output=True, text=True, check=True)
    git("init", "-q")
    git("config", "user.email", "selftest@example.invalid")
    git("config", "user.name", "selftest")
    q = root / "PENDING_QUEUE.md"
    q.write_text("# 佇列\n- [ ] **甲 第一項**\n- [ ] **乙 第二項**\n", encoding="utf-8", newline="\n")
    git("add", "PENDING_QUEUE.md")
    git("commit", "-q", "-m", "init")
    D.ROOT, D.QUEUE = root, q
    D.RUNNER_WRITE = root / ".runner_write.json"
    D.DIRTY_SEEN = root / ".dirty_seen.json"

    q.write_text("# 佇列\n- [!] **甲 第一項**　**⛔ 自走中止**：測試\n- [ ] **乙 第二項**\n", encoding="utf-8", newline="\n")
    check("2a 沒有寫入紀錄 → 讓路", D._recent_real_dirty_reason() is not None)

    D._record_runner_write("PENDING_QUEUE.md")
    os.utime(q, None)  # 模擬 autostash 刷新修改時間
    r = D._recent_real_dirty_reason()
    check("2b 只有守門員自己的 - [!] → 不讓路", r is None, str(r or ""))

    q.write_text(q.read_text(encoding="utf-8") + "- [ ] **丙 互動視窗正在寫**\n", encoding="utf-8", newline="\n")
    q.write_text(q.read_text(encoding="utf-8").replace("乙 第二項", "乙 第二項（改）"), encoding="utf-8", newline="\n")
    r = D._recent_real_dirty_reason()
    check("2c 之後有人改既有行 → 讓路", r is not None, (r or "")[:60])

    D.RUNNER_WRITE.write_text("{壞掉", encoding="utf-8")
    check("2d 寫入紀錄壞掉 → 讓路（fail safe）", D._recent_real_dirty_reason() is not None)

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
