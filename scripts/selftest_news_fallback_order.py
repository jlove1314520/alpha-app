# -*- coding: utf-8 -*-
"""先.八十一-64（2026-10-13）：新聞本機補班步驟順序自測。
① 拆檔緊接在最後一個寫 events.json 的步驟之後  ② 拆檔之後的步驟原始碼都不寫 events.json
③ 步驟集合與 news_events.yml 相同（只換順序，不多不少）
用法：python scripts/selftest_news_fallback_order.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import news_local_fallback as N  # noqa: E402

names = [a[0] for a, _ in N.STEPS]
si = names.index("scripts/split_events_by_code.py")
last_w = max(i for i, n in enumerate(names) if n in N.EVENTS_WRITERS)
after = names[si + 1:]
writes_ev = [n for n in after if re.search(r'["\']events\.json["\'][^\n]*\)\.write_text|events\.json"\)\.write_text|\(DATA / "events\.json"\)\.write', (ROOT / n).read_text(encoding="utf-8"))]
wf = (ROOT / ".github" / "workflows" / "news_events.yml").read_text(encoding="utf-8")
wf_steps = set(re.findall(r"python3? ((?:\.github/scripts|scripts)/[\w_]+\.py)", wf)) - {"scripts/data_schema_guard.py"}
res = [("①拆檔緊接在 fetch_news_events 之後", si == last_w + 1),
       (f"②拆檔之後的步驟不寫 events.json（{after}）", not writes_ev),
       (f"③步驟集合與 workflow 相同（{sorted(wf_steps)}）", set(names) == wf_steps)]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
