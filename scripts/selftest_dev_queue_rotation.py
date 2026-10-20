# -*- coding: utf-8 -*-
"""先.一二二-6 自測：分批項輪替（不改真實佇列／狀態檔，全用暫存）。"""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dev_queue_runner as D  # noqa: E402

res = []
def check(n, ok):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n)

tmp = Path(tempfile.mkdtemp())
D.STATE = tmp / "state.json"
lines = ["- [ ] **甲 V1 補抓** 分批續跑，每批 30 檔", "- [ ] **乙 一般項目** 做事"]
D._lines = lambda: lines
D._explicit_order = lambda: []
D._yield_report = lambda l: []
D._save_state({})
check("首輪取檔案第一項（分批）", "甲" in D.find_next()[1])
D._note_dispatch(lines[0])
check("上輪是分批→改拿乙", "乙" in D.find_next()[1])
D._note_dispatch(lines[1])
check("上輪非分批→回到甲", "甲" in D.find_next()[1])
D._note_dispatch(lines[0])
lines[:] = [lines[0]]
check("只剩分批項→仍回頭做它", "甲" in D.find_next()[1])
orig = D._find_next_base
def boom(*a, **k):
    if a or k: raise RuntimeError("x")
    return orig()
D._find_next_base = boom
lines[:] = ["- [ ] **甲 V1 補抓** 分批續跑", "- [ ] **乙 一般項目** 做事"]
check("輪替自身失敗→降級回原結果不拋例外", "甲" in D.find_next()[1])
sys.exit(0 if all(res) else 1)
