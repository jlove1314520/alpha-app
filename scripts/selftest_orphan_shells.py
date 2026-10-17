# -*- coding: utf-8 -*-
"""先.一〇九-11 自測：orphan_process_scan.classify_orphan_shells()（假行程清單，不碰真行程、不結束任何程序）。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import orphan_process_scan as O  # noqa: E402

now = datetime(2026, 10, 17, 11, 0, tzinfo=O.TZ)
rows = [
    {"Name": "bash.exe", "ProcessId": 73864, "ParentProcessId": 69432, "Start": "2026-10-16T12:01:55"},   # 父已不在、23 小時 → 列
    {"Name": "python.exe", "ProcessId": 74400, "ParentProcessId": 73864, "Start": "2026-10-16T12:01:55"},  # 它的 http.server 子行程
    {"Name": "bash.exe", "ProcessId": 76044, "ParentProcessId": 80560, "Start": "2026-10-16T16:02:33"},   # 父已不在 → 列
    {"Name": "bash.exe", "ProcessId": 100, "ParentProcessId": 200, "Start": "2026-10-16T08:00:00"},       # 父還在 → 不列
    {"Name": "claude.exe", "ProcessId": 200, "ParentProcessId": 1, "Start": "2026-10-16T08:00:00"},
    {"Name": "bash.exe", "ProcessId": 300, "ParentProcessId": 999, "Start": "2026-10-17T10:30:00"},       # 父不在但只 30 分鐘 → 不列
    {"Name": "bash.exe", "ProcessId": 400, "ParentProcessId": 998, "Start": None},                        # 讀不到時間 → 略過
    {"Name": "python.exe", "ProcessId": 500, "ParentProcessId": 997, "Start": "2026-10-10T00:00:00"},     # 不是 bash → 不歸這裡管
]
res = O.classify_orphan_shells(rows, now)
ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)
check("父行程不在且超過 2 小時的 bash 都列出、其他不列", [r["pid"] for r in res] == [73864, 76044])
check("子行程數", [r["children"] for r in res] == [1, 0])
check("已跑小時數", res[0]["age_hours"] == 23.0)
check("不回命令列", all("CommandLine" not in r and "cmd" not in r for r in res))
check("空清單／None 不出錯", O.classify_orphan_shells(None, now) == [] and O.classify_orphan_shells([], now) == [])
print(f"合計 {len(ok)} 項，失敗 {ok.count(False)}")
sys.exit(0 if all(ok) else 1)
