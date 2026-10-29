"""自測：前向名單計數一致性（先.一三五-1bb，DevQueue 2026-10-29 空轉補件）。

核對三份東西說的是同一份名單：
1. `research/FORWARD_CANDIDATES.md` 標題「進行中：X／上限」的 X ＝ 進行中表格列數；
2. 表格「程式代號」欄每個 paper_N 都有 `research/paper_N_*_tracker.py`；
3. 表格的 paper_N 集合 ＝ `research/forward_sim_watch.py` 的 PAPER_IDS。
零外部請求、不讀帳本數值、不改名單（名單屬 Cowork；不一致只照實印出）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "research" / "FORWARD_CANDIDATES.md"
sys.path.insert(0, str(ROOT / "research"))

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def parse(text: str) -> tuple[int | None, int | None, list[int]]:
    """回傳（標題 X、標題上限、進行中表格的 paper 編號清單）。表格＝「## 進行中」段落裡第一個 | 模擬 | 開頭的表。"""
    m = re.search(r"^## 進行中：(\d+)／(\d+)", text, re.M)
    x, cap = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    sec = text[m.end():] if m else ""
    sec = sec.split("\n## ", 1)[0]
    ids, in_table = [], False
    for line in sec.splitlines():
        if line.startswith("| 模擬 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) > 1 and (pm := re.fullmatch(r"paper_(\d+)", cells[1])):
                ids.append(int(pm.group(1)))
    return x, cap, ids


print("合成：解析器自測")
x, cap, ids = parse("## 進行中：2／14（滿）\n\n| 模擬 | 程式代號 | 內容 |\n|---|---|---|\n| F | paper_5 | a |\n| G | paper_7 | b |\n\n## 候選\n| 模擬 | paper_99 |\n")
check("標題 X＝2、上限 14", (x, cap) == (2, 14), (x, cap))
check("只讀進行中表、不讀候選段", ids == [5, 7], ids)
check("沒有標題 → None", parse("無")[0] is None)

print("實檔：research/FORWARD_CANDIDATES.md")
x, cap, ids = parse(DOC.read_text(encoding="utf-8"))
print(f"  標題 {x}／{cap}、表格 {len(ids)} 列：{ids}")
check("標題 X ＝ 表格列數", x == len(ids), (x, len(ids)))
check("沒有重複代號", len(ids) == len(set(ids)), ids)
missing = [i for i in ids if not list((ROOT / "research").glob(f"paper_{i}_*tracker.py"))]
check("每支都有追蹤程式檔", not missing, missing)
try:
    import forward_sim_watch as W
    pid = set(W.PAPER_IDS)
    check("集合 ＝ forward_sim_watch.PAPER_IDS", set(ids) == pid,
          f"表格多 {sorted(set(ids) - pid)}／看守員多 {sorted(pid - set(ids))}")
except Exception as e:  # noqa: BLE001
    check("讀得到 forward_sim_watch.PAPER_IDS", False, f"{type(e).__name__}: {e}")
check("X 不超過上限", x is not None and cap is not None and x <= cap, (x, cap))

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
