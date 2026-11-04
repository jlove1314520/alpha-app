# -*- coding: utf-8 -*-
"""先.一三五-1kj 甲（收件匣 039 定案）自測：find_next() 找不到 `- [ ]` 時，把到期的標準時間閘 `- [!]` 轉回 `- [ ]`。
用合成片段，不碰真 PENDING_QUEUE（QUEUE 改指到暫存檔）。
1. 已過（含時間）→ 認；未到 → 不認；只有日期＝當天 00:00；時間後帶（說明）→ 認
2. 時間窗（09:05～13:20）、行中時間閘、事件條件、怪格式（月份 13）、``` 引文內 → 不認
3. find_next()：沒有 `- [ ]` 時轉回到期那行並取到它；未到期的保持 `- [!]`
4. 守門員自身失敗（讀檔例外）→ 回 0、不拋錯（十二節）
跑法：python scripts/selftest_dev_queue_time_gate.py
"""
import sys
import tempfile
from datetime import datetime
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


now = datetime(2026, 11, 4, 18, 30, tzinfo=D.TZ)
L = [
    "# 佇列",
    "- [!] 〔時間閘：2026-11-04（週三）09:00 後〕 **先.測-甲 已過** [維運]（DevQueue 可執行）",          # 1 認
    "- [!] 〔時間閘：2026-11-05（週四）09:00 後〕 **先.測-乙 未到** [維運]（DevQueue 可執行）",          # 2 不認
    "- [!] 〔時間閘：2026-11-04（週三）後〕 **先.測-丙 只有日期** [維運]（DevQueue 可執行）",            # 3 認
    "- [!] 〔時間閘：2026-11-04（週三）18:00 後（權證 17:30 班跑過）〕 **先.測-丁 帶說明** [維運]（DevQueue 可執行）",  # 4 認
    "- [!] 〔時間閘：2026-11-04（週三）09:05～13:20〕 **先.測-戊 時間窗** [維運]（DevQueue 可執行）",    # 5 不認
    "- [!] **先.測-己 〔時間閘：2026-11-01 起〕行中** [維運]（DevQueue 可執行）",                       # 6 不認
    "- [!] 〔時間閘：下一個告警日〕 **先.測-庚 事件條件** [維運]（DevQueue 可執行）",                   # 7 不認
    "- [!] 〔時間閘：2026-13-04（週三）09:00 後〕 **先.測-辛 怪格式** [維運]（DevQueue 可執行）",       # 8 不認
    "```",
    "- [!] 〔時間閘：2026-11-01（週日）09:00 後〕 **先.測-壬 引文內** [維運]（DevQueue 可執行）",       # 10 不認
    "```",
]
idx = D._expired_time_gate_indices(L, now)
check("1+2 只認到期的標準格式（含只有日期、帶說明）", idx == [1, 3, 4], str(idx))

with tempfile.TemporaryDirectory() as td:
    q = Path(td) / "pq.md"
    q.write_text("\n".join(L) + "\n", encoding="utf-8")
    D.QUEUE = q
    D._record_runner_write = lambda *a, **k: None
    D._explicit_order = lambda: []
    D._load_state = lambda: {}
    D._save_state = lambda st: None
    real = D._expired_time_gate_indices
    D._expired_time_gate_indices = lambda lines, n=None: real(lines, now)
    nxt = D.find_next()
    after = q.read_text(encoding="utf-8").splitlines()
    check("3a find_next 取到轉回的第一項", nxt is not None and "先.測-甲" in nxt[1], str(nxt and nxt[1][:40]))
    check("3b 到期三行改成 - [ ]、未到期／時間窗保持 - [!]",
          after[1].startswith("- [ ]") and after[3].startswith("- [ ]") and after[4].startswith("- [ ]")
          and after[2].startswith("- [!]") and after[5].startswith("- [!]") and after[10].startswith("- [!]"))
    D.QUEUE = Path(td) / "no_such_dir" / "pq.md"
    check("4 讀檔失敗 → 回 0 不拋錯", D._reopen_expired_time_gates(now) == 0)

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
