# -*- coding: utf-8 -*-
"""sync_continuation_prompts.py — 把`research/queue_depth_config.py`的
門檻數字同步進兩份靜態prompt檔（2026-09-20總司令裁示【Q4前視與#23無法
重現】四）。

**問題背景**：`MARATHON_CONTINUATION_PROMPT.txt`/`HYPOTHESIS_QUEUE_
CONTINUATION_PROMPT.txt`是外部排程器（Windows工作排程器）直接讀取的
靜態文字檔，無法在「被讀取的當下」動態import Python常數——過去這兩份
檔案跟`CLAUDE.md`/`scripts/dev_queue_runner.py`各自硬寫「門檻12、
補到20」這兩個數字，2026-09-19門檻從5改12時只更新了部分位置，導致
兩份靜態prompt停留在舊版整整5輪都沒被發現。

**解法**：兩份`.txt`檔裡用`<!-- QUEUE_DEPTH_BEGIN -->`/
`<!-- QUEUE_DEPTH_END -->`標記出佇列深度檢查那一段，這支腳本用
`queue_depth_config.py`的常數重新產生該段落並取代——**改門檻只要改
`queue_depth_config.py`一個地方，再跑這支腳本，兩份prompt檔就會同步**，
不需要手動編輯三個地方。

用法：
    python research/sync_continuation_prompts.py          # 執行同步
    python research/sync_continuation_prompts.py --check  # 只檢查是否同步，不寫檔（給audit_preflight用）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from queue_depth_config import MIN_QUEUE_DEPTH, TARGET_QUEUE_DEPTH

ROOT = Path(__file__).parent
BEGIN_MARKER = "<!-- QUEUE_DEPTH_BEGIN -->"
END_MARKER = "<!-- QUEUE_DEPTH_END -->"

TARGET_FILES = [
    ROOT / "MARATHON_CONTINUATION_PROMPT.txt",
    ROOT / "HYPOTHESIS_QUEUE_CONTINUATION_PROMPT.txt",
]

BLOCK_TEMPLATE = """<!-- QUEUE_DEPTH_BEGIN -->
**佇列深度檢查（數字來自research/queue_depth_config.py單一事實來源，
不要手動改這段文字裡的數字——2026-09-20總司令裁示【Q4前視與#23無法
重現】四：CLAUDE.md/dev_queue_runner.py/這份靜態prompt過去各自硬寫
過這兩個數字，2026-09-19門檻從5改12時只有部分位置同步更新，這份
文字停留在舊版本、連續5輪沒觸發才被發現。**改門檻請改
`queue_depth_config.py`後重跑`python research/sync_continuation_
prompts.py`，不要直接編輯這個區塊，否則下次同步會被覆蓋***）**：
**只算`- [ ]`（真正能馬上動手的），不含`- [!]`（已標記阻塞、目前做
不了的，阻塞項不會被消化，算進門檻會讓門檻失去意義——`- [!]`常態性
就有20項以上，若跟`- [ ]`合計，門檻永遠不會觸發，這正是舊版文字造成
連續5輪沒補件的根因）**。`- [ ]`項目數低於{min_depth}項時，
有責任自己補、一次補到{target_depth}項（來源優先序：
①`PENDING_QUEUE.md`「常備backlog」區塊 ②`research/REPORT.md`/
`LEADS.md`/`STRATEGY_GRAVEYARD.md`裡寫著「待辦」「下一步」「未解決」但
沒進佇列的項目 ③`HYPOTHESIS_QUEUE.md`排隊中的假設），補入時標
「[自走補入]」與來源出處，不需要事先請示。**這是每一輪開工前都要做的
檢查，不是只有「佇列已清空」才做**——即使佇列裡還有幾個`- [ ]`可以做，
只要總數低於{min_depth}項就要在做完手上這輪之後補件，不要等到
真的見底才動作。
<!-- QUEUE_DEPTH_END -->"""


def render_block() -> str:
    return BLOCK_TEMPLATE.format(min_depth=MIN_QUEUE_DEPTH, target_depth=TARGET_QUEUE_DEPTH)


def sync_file(path: Path, check_only: bool = False) -> bool:
    """回傳True代表這個檔案本來就同步（或已同步完成），False代表需要
    （或已經）更新。"""
    text = path.read_text(encoding="utf-8")
    if BEGIN_MARKER not in text or END_MARKER not in text:
        print(f"[警告] {path.name} 找不到QUEUE_DEPTH標記，跳過（可能需要手動補標記）")
        return False
    pattern = re.compile(re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER), re.S)
    new_block = render_block()
    already_synced = bool(pattern.search(text)) and pattern.search(text).group(0) == new_block
    if check_only:
        return already_synced
    if already_synced:
        print(f"{path.name}: 已同步，不需更新")
        return True
    new_text = pattern.sub(new_block, text)
    path.write_text(new_text, encoding="utf-8")
    print(f"{path.name}: 已更新為 門檻={MIN_QUEUE_DEPTH}／補到={TARGET_QUEUE_DEPTH}")
    return True


def main() -> int:
    check_only = "--check" in sys.argv
    all_ok = True
    for path in TARGET_FILES:
        ok = sync_file(path, check_only=check_only)
        all_ok = all_ok and ok
    if check_only:
        print("SYNCED" if all_ok else "OUT_OF_SYNC")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
