# -*- coding: utf-8 -*-
"""先.八十二-8（2026-10-13）：馬拉松／假設佇列「假設池空只記心跳」判定自測（用暫存狀態檔與暫存池檔，不碰真檔）。
① 尚無紀錄 → 照常跑  ② 上一輪有進度 → 照常跑  ③ 上一輪無進度且池未變 → 池空
④ 上一輪無進度但之後池檔變了 → 照常跑
用法：python scripts/selftest_pool_empty.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import quota_throttle as Q  # noqa: E402

tmp = Path(tempfile.mkdtemp())
Q.STATE_PATH = tmp / "state.json"
pool = tmp / "HYPOTHESIS_QUEUE.md"
pool.write_text("a", encoding="utf-8")
Q.POOL_SOURCES = [pool]
res = []
res.append(("①尚無紀錄→照常跑", Q.pool_empty("marathon") == 1))
Q._save_state({"marathon": {"last_run_pool_progress": True, "pool_hash_after_run": Q._pool_hash()}})
res.append(("②上一輪有進度→照常跑", Q.pool_empty("marathon") == 1))
Q._save_state({"marathon": {"last_run_pool_progress": False, "pool_hash_after_run": Q._pool_hash()}})
res.append(("③無進度且池未變→池空", Q.pool_empty("marathon") == 0))
pool.write_text("b", encoding="utf-8")
res.append(("④之後池檔變了→照常跑", Q.pool_empty("marathon") == 1))
res.append(("⑤另一軌不受影響", Q.pool_empty("hypothesis_queue") == 1))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
