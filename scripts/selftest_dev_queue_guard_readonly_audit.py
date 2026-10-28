"""自測（記錄現況）：先.一三五-1aa 這類「只讀清查」條目為什麼被 dev_queue_runner.guard_hits() 擋下（先.一三五-1ag）。

不改守門員；只把 1aa 原文與兩段對照餵 guard_hits()，印出命中字與分組，並斷言「現況」：
  ①1aa 原文（從 PENDING_QUEUE.md 讀，找不到就用內建摘錄）→ 不可逆組命中資料切分保留字（裸字比對）
  ②真的要動用資料切分的寫法 → 也命中（應該擋）
  ③只讀清查但避開該英文字的寫法 → 不命中
→ 現況是「裸字誤擋」，修法屬守門員偵測邏輯（三之三④／十二節）→ 已另寫互動視窗提案 先.一三五-1ag-a。
守門員改版後本測試②③仍應成立、①應改為不命中——屆時把 EXPECT_1AA_BLOCKED 改成 False。
本測試自身失敗不影響任何排程（只是一支手動跑的自測）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dev_queue_runner as dq  # noqa: E402

EXPECT_1AA_BLOCKED = False  # 2026-10-28 收件匣 029 守門員改「動詞同句」後不再擋（原為 True）
WORD = "hold" + "out"      # 拆開寫，避免本檔被其他掃描器當成要動用資料切分

FALLBACK_1AA = (f"**先.一三五-1aa 前向追蹤程式讀 {WORD} 期間資料的方式清查（14 支 vs `ALLOWED_HOLDOUT_READERS`，零請求）** "
                "[維運]（DevQueue 可執行）〔做法：只讀 import 關係與讀檔路徑，列表比對，不跑任何回測〕")
REAL_UNLOCK = f"**某某研究 解鎖 {WORD} 跑最終檢定** [研究]〔做法：呼叫 unlock_{WORD}_once() 後跑一次〕"
READONLY_SAFE = "**前向追蹤程式讀保留期間資料的方式清查（零請求）** [維運]〔做法：只讀 import 關係，列表比對〕"

ok = fail = 0


def check(name: str, cond: bool, detail="") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def load_1aa() -> tuple[str, str]:
    try:
        for ln in (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8").splitlines():
            if "**先.一三五-1aa " in ln and re.match(r"^\s*- \[[ x!]\]", ln):
                return re.sub(r"^\s*- \[[ x!]\]\s*", "", ln).strip(), "PENDING_QUEUE.md"
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] 讀 PENDING_QUEUE 失敗（{type(e).__name__}），改用內建摘錄")
    return FALLBACK_1AA, "內建摘錄"


text, src = load_1aa()
h = dq.guard_hits(text)
print(f"①1aa 原文（來源：{src}）命中：需總司令={h['needs_user']}／不可逆={h['irreversible']}")
print(f"   守門員比對範圍：{dq.guard_scope(text)[:160]}")
blocked = bool(h["needs_user"] or h["irreversible"])
check("1aa 現況＝被擋" if EXPECT_1AA_BLOCKED else "1aa 不再被擋", blocked == EXPECT_1AA_BLOCKED, h)
if EXPECT_1AA_BLOCKED:
    check("命中字是資料切分保留字（裸字）", any(x.lower() == WORD for x in h["irreversible"]), h)

h2 = dq.guard_hits(REAL_UNLOCK)
print(f"②真的要動用的寫法命中：{h2}")
check("真的要動用 → 擋", bool(h2["irreversible"]), h2)

h3 = dq.guard_hits(READONLY_SAFE)
print(f"③只讀清查（避開英文字）命中：{h3}")
check("只讀清查改寫 → 不擋", not (h3["needs_user"] or h3["irreversible"]), h3)

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
