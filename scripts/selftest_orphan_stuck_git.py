# -*- coding: utf-8 -*-
"""先.一〇三-15ah 自測：orphan_process_scan.classify_stuck_git()（假行程清單，不碰真行程、不結束任何程序）。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import orphan_process_scan as O  # noqa: E402

now = datetime(2026, 10, 16, 16, 0, tzinfo=O.TZ)
rows = [
    {"Name": "git.exe", "ProcessId": 1, "CommandLine": "git.exe push -q", "Start": "2026-10-15T09:57:23"},
    {"Name": "git-credential-manager.exe", "ProcessId": 2, "CommandLine": "git-credential-manager get", "Start": "2026-10-15T09:57:23"},
    {"Name": "python.exe", "ProcessId": 3, "CommandLine": "python.exe scripts/commit_local_heartbeats.py connectivity", "Start": "2026-10-15T09:57:17"},
    {"Name": "git.exe", "ProcessId": 4, "CommandLine": "git.exe status", "Start": "2026-10-16T15:30:00"},          # 30 分鐘，不算
    {"Name": "python.exe", "ProcessId": 5, "CommandLine": "python.exe research\alpha_live_server.py", "Start": "2026-10-10T00:00:00"},  # 常駐服務，不算
    {"Name": "git.exe", "ProcessId": 6, "CommandLine": "git.exe push", "Start": None},                            # 讀不到時間，略過
]
res = O.classify_stuck_git(rows, now)
ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)
check("超過 2 小時的 push／credential-manager／心跳 python 都列出", [r["pid"] for r in res] == [1, 2, 3])
check("種類判對", [r["kind"] for r in res] == ["push", "credential-manager", "heartbeat-python"])
check("不回命令列", all("CommandLine" not in r and "cmd" not in r for r in res))
check("已跑小時數", res[0]["age_hours"] == 30.0)
check("空清單／None 不出錯", O.classify_stuck_git(None, now) == [] and O.classify_stuck_git([], now) == [])
print(f"合計 {len(ok)} 項，失敗 {ok.count(False)}")
sys.exit(0 if all(ok) else 1)
