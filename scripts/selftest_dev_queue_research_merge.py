# -*- coding: utf-8 -*-
"""先.一二七-A 自測：研究軌併入 DevQueue（不改真實佇列／狀態檔／提示詞檔，全用暫存）。"""
import os, sys, tempfile
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
D.PROMPT_OUT = tmp / "prompt.txt"
lines = ["- [ ] **甲 改核心檔** （互動視窗執行；動 research/adjust.py）",
         "- [ ] **乙 假說單發** [研究] 寫 PREREG",
         "- [ ] **丙 畫面修正** [產品] 改按鈕"]
D._lines = lambda: lines
D._explicit_order = lambda: []
D._yield_report = lambda l: []
D._save_state({})
check("併入後：研究類會被取件（跳過互動視窗類）", "乙" in D.find_next()[1])
check("互動視窗類仍永遠跳過", D._skip_classes() == ("互動視窗",))
D.RESEARCH_MERGED_INTO_DEVQUEUE = False
check("旗標關閉→還原舊行為跳過研究類", "丙" in D.find_next()[1])
D.RESEARCH_MERGED_INTO_DEVQUEUE = True
# 提示詞
for f in ("guard_precheck", "approval_precheck", "eligible_precheck", "_report_order_tag_mismatches"):
    setattr(D, f, lambda: None)
D._order_marker_ambiguity = lambda: None
os.environ.pop("ALPHA_DEVQUEUE_CRUNCH", None)
rc = D.build_prompt()
p = D.PROMPT_OUT.read_text(encoding="utf-8")
check("研究類提示詞：研究帽＋事前登記＋核心檔案禁改", rc == 0 and "本輪帽子：研究／驗證" in p
      and "register_trial()" in p and "research/adjust.py" in p and "只接[研究]類" in p)
lines[:] = [lines[2]]
D._save_state({})
D.build_prompt()
p = D.PROMPT_OUT.read_text(encoding="utf-8")
check("開發類提示詞：開發帽、不帶研究紀律", "本輪帽子：開發／維運" in p and "register_trial()" not in p)
check("補件規則含⑤研究候選與常規.補件順序", "GRAVEYARD_AUTOPSY" in p and "常規.補件順序" in p)
lines[:] = ["- [ ] **甲 改核心檔** （互動視窗執行；動 research/adjust.py）"]
check("只剩互動視窗類→find_next 回 None", D.find_next() is None)
sys.exit(0 if all(res) else 1)
