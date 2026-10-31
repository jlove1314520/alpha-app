# -*- coding: utf-8 -*-
"""先.一三五-1fe 自測：本機管線清點表（pipeline_inventory.main）。

evaluate／load_registry 換假的；零外部請求、不讀真登錄檔。
用法：python scripts/selftest_pipeline_inventory.py
"""
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pipeline_inventory as P  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def run(rows, stalled, reg, argv):
    P.evaluate = lambda now: ([dict(r) for r in rows], list(stalled))
    P.load_registry = lambda: reg
    sys.argv = ["pipeline_inventory.py"] + argv
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = P.main()
    except Exception as e:  # noqa: BLE001
        return f"例外 {e!r}", buf.getvalue()
    return rc, buf.getvalue()


ROWS = [
    {"task": "AlphaX", "artifact": "data/a.json", "status": "ok", "expected_interval_min": 30, "age_min": 12},
    {"task": "AlphaX", "artifact": "data/b.json", "status": "stalled", "expected_interval_min": 1440,
     "age_min": 9000, "source": "JSON 欄位 updated_at"},
    {"task": "AlphaY", "artifact": "data/c.json", "status": "missing", "expected_interval_min": 20160,
     "reason": "檔案不存在"},
]
REG = {"stall_factor": 3, "pipelines": [
    {"task": "AlphaX", "artifact": "data/a.json", "fault_history": {}},
    {"task": "AlphaX", "artifact": "data/b.json",
     "fault_history": {"count": 2, "fault_types": {"stale": 2}, "last_fault_at": "2026-10-30T10:00"}},
]}

rc, out = run(ROWS, ["AlphaX::data/b.json"], REG, ["--json"])
doc = json.loads(out) if not str(rc).startswith("例外") else {}
check("--json 有停擺 → exit 1", rc == 1)
check("--json 輸出合法 JSON 且三列都在", len(doc.get("pipelines", [])) == 3)
fh = {f'{r["task"]}::{r["artifact"]}': r["fault_history"] for r in doc.get("pipelines", [])}
check("同 task 不同 artifact 的故障帳分開對", fh.get("AlphaX::data/b.json", {}).get("count") == 2
      and fh.get("AlphaX::data/a.json") == {})
check("登錄檔沒有的節點 fault_history＝{}、不拋例外", fh.get("AlphaY::data/c.json") == {})

rc, out = run(ROWS, ["AlphaX::data/b.json"], REG, [])
check("文字表有停擺 → exit 1、印停擺清單與累積故障", rc == 1 and "1 條停擺" in out and "累積故障 2 次" in out)
check("沒有 age_min 的列印 reason、不拋例外", "檔案不存在" in out)
check("預期間隔換算（30 分／1 天／2 週）", "每 30 分" in out and "每 1 天" in out and "每 2 週" in out)

rc, out = run(ROWS[:1], [], {"pipelines": []}, [])
check("全部正常 → exit 0", rc == 0 and "全部在預期新鮮度內" in out)
rc, out = run(ROWS[:1], [], {}, ["--json"])
check("登錄檔沒有 pipelines 鍵 → 不拋例外、exit 0", rc == 0)

print(f"\n{sum(results)}/{len(results)} PASS")
sys.exit(0 if all(results) else 1)
