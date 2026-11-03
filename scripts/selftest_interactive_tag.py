# -*- coding: utf-8 -*-
"""先.八十一-46（2026-10-13）：「（互動視窗執行）」專屬標記在各自走軌道都被排除的自測。

① DevQueue：scripts/dev_queue_runner.py 的 INLINE_INTERACTIVE_TAG 對下列樣本判定正確
   （標題含星號、含括號也要判成互動視窗專屬；「（互動視窗或DevQueue皆可）」不算）。
② HypothesisQueue／Marathon：兩份 continuation prompt 都寫了「互動視窗專屬」規則（2026-10-13 12:05 HypothesisQueue
   代做了互動視窗專屬的先.八十一-42，根因就是 prompt 只排除「〔互動視窗執行中〕」標記）。
用法：python scripts/selftest_interactive_tag.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dev_queue_runner as D  # noqa: E402

SAMPLES = [
    ("- [ ] **先.八十一-42 過期一次性排程 5 支（Alpha*）**（互動視窗執行）", True),
    ("- [ ] **先.八十一-18 scores*_list 落地驗證**（互動視窗執行）", True),
    ("- [ ] **評.B-2 單發**（互動視窗執行中 2026-10-13 10:00）", True),
    ("- [ ] **常備.開發-99 某項**（互動視窗或DevQueue皆可）", False),
    ("- [ ] **常備.開發-98 某項**", False),
    # 2026-11-04（DevQueue cycle 20261104-033101）：代號與「（互動視窗」之間夾 [產品]／[研究] 標籤
    ("- [ ] **先.一四八-3 P2 首頁** [產品]（互動視窗執行；已定案）", True),
    ("- [ ] **先.一四七-1 草稿** [研究]（DevQueue 可執行）", False),
]
res = []
for line, want in SAMPLES:
    got = bool(D.INLINE_INTERACTIVE_TAG.search(line))
    res.append((f"DevQueue 判定：{line[:40]}… → {'互動視窗專屬' if want else '可接'}", got == want))
# item_class 必須讓互動視窗註記優先於 [產品] 標籤（原本先比對 [產品] 回傳「產品」，被 DevQueue 接走）
_c = D.item_class("- [ ] **先.一四八-3 P2 首頁** [產品]（互動視窗執行；已定案）")
res.append((f"item_class：[產品]（互動視窗執行 → {_c}（應為互動視窗）", _c == "互動視窗"))
for name in ("HYPOTHESIS_QUEUE_CONTINUATION_PROMPT.txt", "MARATHON_CONTINUATION_PROMPT.txt"):
    txt = (ROOT / "research" / name).read_text(encoding="utf-8")
    res.append((f"{name} 有「互動視窗專屬」規則", "互動視窗專屬" in txt and "（互動視窗執行" in txt))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
