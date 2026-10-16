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

# ④～⑥ 先.一〇三-14x：提交前同班檢查（臨時目錄、刻意製造不同班；不碰 repo 檔）
import json as _json  # noqa: E402
import tempfile  # noqa: E402


def _fake_root(ev, others):
    d = Path(tempfile.mkdtemp(prefix="nlf_same_"))
    (d / "data" / "events_by_code").mkdir(parents=True)
    w = lambda p, o: (d / p).write_text(_json.dumps(o), encoding="utf-8")  # noqa: E731
    w("data/events.json", {"fetched_at": ev})
    w("data/events_search.json", {"top": {"fetched_at": others}})
    w("data/events_by_code/_index.json", {"fetched_at": others})
    w("data/ir_events.json", {"fetched_at": others})
    return d


class _R:
    returncode = 0


_orig_root = N.ROOT
try:
    N.ROOT = _fake_root("T1", "T0")

    def _fix():
        for p in ("data/events_by_code/_index.json", "data/ir_events.json"):
            (N.ROOT / p).write_text(_json.dumps({"fetched_at": "T1"}), encoding="utf-8")
        (N.ROOT / "data/events_search.json").write_text(_json.dumps({"top": {"fetched_at": "T1"}}), encoding="utf-8")
        return _R()
    m4 = N.ensure_split_same_batch({}, run=_fix)
    res.append((f"④不同班→重跑拆檔後同班（{m4[-12:]}）", "已同班" in m4 and N._split_fetched_at()["index"] == "T1"))
    m5 = N.ensure_split_same_batch({}, run=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    res.append(("⑤已同班→不重跑、回空字串", m5 == ""))
    N.ROOT = _fake_root("T1", "T0")
    m6 = N.ensure_split_same_batch({}, run=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    res.append((f"⑥重跑本身拋例外→只回警告不拋（十二節）（{m6[:30]}）", m6.startswith("[warn]")))
finally:
    N.ROOT = _orig_root

for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
