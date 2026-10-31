# -*- coding: utf-8 -*-
"""先.一三五-1fa 自測：孤兒巡檢（orphan_process_scan.main）名單沒變但換日也要提交一次，同一天名單沒變不提交。

全部用假的：行程清單換空清單、輸出檔換暫存、_commit_push 換紀錄器；零外部請求、不碰真 repo、不推播。
用法：python scripts/selftest_orphan_scan_daily_commit.py
"""
import json
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.modules["mem_guard"] = types.SimpleNamespace(find_orphan_python_workers=lambda: [])
import orphan_process_scan as O  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


calls = []
O._commit_push = lambda msg: (calls.append(msg), "假提交")[1]
O.find_stuck_git = lambda now: []
O.find_orphan_shells = lambda now: []
with tempfile.TemporaryDirectory() as d:
    O.OUT = Path(d) / "orphan_scan.json"
    O.PUSH_STATE = Path(d) / "push.json"
    today = datetime.now(O.TZ)
    base = {"count": 0, "total_private_mb": 0, "orphans": [], "stuck_git": [], "orphan_shells": []}

    O.OUT.write_text(json.dumps({**base, "checked_at": today.isoformat(timespec="seconds")}), encoding="utf-8")
    calls.clear(); O.main(commit=True)
    check("同一天、名單沒變 → 不提交", not calls)

    O.OUT.write_text(json.dumps({**base, "checked_at": (today - timedelta(days=2)).isoformat(timespec="seconds")}), encoding="utf-8")
    calls.clear(); O.main(commit=True)
    check("名單沒變但上次檢查是前天 → 提交一次", len(calls) == 1)
    check("提交後檔案 checked_at 是今天", json.loads(O.OUT.read_text(encoding="utf-8"))["checked_at"][:10] == today.date().isoformat())

    O.OUT.write_text(json.dumps({**base, "checked_at": today.isoformat(timespec="seconds"),
                                 "orphans": [{"pid": 123}]}), encoding="utf-8")
    calls.clear(); O.main(commit=True)
    check("同一天但名單變了 → 提交（原行為不變）", len(calls) == 1)

    O.OUT.write_text("壞檔", encoding="utf-8")
    calls.clear(); O.main(commit=True)
    check("舊檔壞掉 → 提交（原行為不變）", len(calls) == 1)

    O.OUT.write_text(json.dumps({**base, "checked_at": (today - timedelta(days=1)).isoformat(timespec="seconds")}), encoding="utf-8")
    calls.clear(); O.main(commit=False)
    check("--no-commit → 不提交", not calls)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
