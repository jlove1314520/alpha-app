# -*- coding: utf-8 -*-
"""收件匣 028 自測：守門員認得「已經裁示過」的語境，不再把已核准條目當成要總司令操作。

不改任何檔案、不呼叫 claude。檢查：
①3 個應放行：「總司令裁示已核准（收件匣 027）」「核准後實作」「照裁示：甲」
②3 個應擋（另加 2 個邊界）：「請總司令核准」「需總司令輸入密碼後登入」「待總司令裁示」；「本人登入」「登入已過期」
③現行 PENDING_QUEUE 全部 - [ ] 跑一次 guard_hits，列修前（GUARD_APPROVED_ON=False）／修後被擋清單的差異；
  另拿 HEAD 版（Cowork 改措辭前）的 PENDING_QUEUE 再比一次，先.一三八-1～6 修前被擋、修後放行
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

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"｜{detail}" if detail and not ok else ""))


def needs(text):
    return D.guard_hits(text)["needs_user"]


PASS_CASES = [
    "**先.X 停資停券預告表掛 market.yml 17:13 班** [維運]（DevQueue 可執行；總司令裁示已核准，Cowork 收件匣 027）",
    "**先.X 上櫃次日漲跌停價另存檔（核准後實作）** [維運]（DevQueue 可執行）",
    "**先.X 照裁示：甲方案改 fetch_market_us.py** [維運]（DevQueue 可執行）",
]
BLOCK_CASES = [
    "**先.X 新排程請總司令核准** [維運]",
    "**先.X 需總司令輸入密碼後登入 Shioaji** [維運]",
    "**先.X 甲乙兩案待總司令裁示** [維運]",
    "**先.X 本人登入 IBKR Gateway 後重跑** [維運]",
    "**先.X Gateway 登入已過期，重新登入** [維運]",
]
for t in PASS_CASES:
    check("① 放行：" + t[6:30], not needs(t), str(needs(t)))
for t in BLOCK_CASES:
    check("② 照擋：" + t[6:30], bool(needs(t)), str(needs(t)))


def blocked_titles(pq_text):
    out = set()
    for ln in pq_text.splitlines():
        if ln.lstrip().startswith("- [ ]"):
            clean = re.sub(r"^\s*- \[ \]\s*", "", ln).strip()
            h = D.guard_hits(clean)
            if h["needs_user"] or h["irreversible"]:
                out.add(clean[:50])
    return out


def diff(label, pq_text):
    D.GUARD_APPROVED_ON = False
    before = blocked_titles(pq_text)
    D.GUARD_APPROVED_ON = True
    after = blocked_titles(pq_text)
    print(f"\n[{label}] 修前被擋 {len(before)} 條、修後 {len(after)} 條")
    for t in sorted(before - after):
        print("  修後放行：" + t)
    for t in sorted(after - before):
        print("  修後新擋：" + t)
    return before, after


cur = (ROOT / "PENDING_QUEUE.md").read_text(encoding="utf-8", errors="replace")
b, a = diff("現行 PENDING_QUEUE", cur)
check("③a 現行佇列：修後被擋 ⊆ 修前被擋（新增的需總司令字樣除外不新擋）", a <= b or all("總司令" in t or "本人登入" in t for t in a - b), str(a - b))
try:
    head = subprocess.run(["git", "-C", str(ROOT), "show", "3db43d5fce:PENDING_QUEUE.md"], capture_output=True, check=True).stdout.decode("utf-8", "replace")
    b, a = diff("收件匣 027 原措辭（3db43d5fce）", head)
    hit = {t for t in b - a if "先.一三八-" in t}
    check("③b 原措辭的先.一三八-1～6：修前被擋、修後放行", len(hit) == 5, str(sorted(hit)))
except subprocess.CalledProcessError as e:
    check("③b 讀 3db43d5fce 版 PENDING_QUEUE", False, str(e))

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} PASS")
sys.exit(1 if bad else 0)
