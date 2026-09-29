"""驗.九二：有節流的 FinMind 快取補抓（只補缺的、可續跑、撞牆即停不吞錯）。

不 import factor_ic（不需要重計算、不裝 mem_guard；只做請求+寫 parquet）。
免費層無 token 上限 300 次/小時：每次真實請求之間至少 SPACING 秒（預設14秒≈257次/小時），
任何 RuntimeError（402/冷卻/封鎖）→ 立刻停手並回報，絕不重試。
用法：python audit_v9_fetch_missing.py [--phase nowcast|crosscheck|all] [--max N]
"""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from finmind_client import _cache_path, load_dev
from universe import listing_date_lookup, universe

import os
SPACING = float(os.environ.get("V9_SPACING", "14"))
END = "2024-12-31"  # holdout.VAL_END（此處硬寫以避免 import 驗證模組鏈）
OUT = Path(__file__).parent / "data" / "diag_v9_fetch_missing.json"
NOWCAST = [("TaiwanStockFinancialStatements", "2010-01-01"), ("TaiwanStockMonthRevenue", "2010-01-01"),
           ("TaiwanStockBalanceSheet", "2010-01-01")]
CROSS = [("TaiwanStockPrice", "2010-01-01"), ("TaiwanStockDividend", "2010-01-01"),
         ("TaiwanStockSplitPrice", "2010-01-01"), ("TaiwanStockCapitalReductionReferencePrice", "2010-01-01")]


def main() -> int:
    phase = sys.argv[sys.argv.index("--phase") + 1] if "--phase" in sys.argv else "all"
    cap = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10**9
    ids = random.Random(20260822).sample(list(universe()["stock_id"]), 300)  # 同 factor_ic.sample_universe_ids(300, SAMPLE_SEED)
    lst = listing_date_lookup()
    ids_c = [s for s in ids if s in lst] + [s for s in ids if s not in lst]
    todo = []
    if phase in ("nowcast", "all"):
        todo += [(ds, s, st, "nowcast") for s in ids for ds, st in NOWCAST]
    if phase in ("crosscheck", "all"):
        todo += [("TaiwanStockParValueChange", "", "2010-01-01", "crosscheck")]
        todo += [(ds, s, st, "crosscheck") for s in ids_c for ds, st in CROSS]
    missing = [t for t in todo if not _cache_path(t[0], t[1], t[2], END).exists()]
    print(f"[{datetime.now():%H:%M:%S}] phase={phase} 待補 {len(missing)} / {len(todo)}", flush=True)
    used, stopped, per_phase = 0, None, {}
    for ds, sid, st, ph in missing:
        if used >= cap:
            stopped = "max_reached"
            break
        t0 = time.time()
        try:
            load_dev(ds, sid, st)
        except RuntimeError as e:
            stopped = f"RuntimeError: {str(e)[:200]}"
            print(f"[{datetime.now():%H:%M:%S}] 停手：{stopped}", flush=True)
            break
        used += 1
        per_phase[ph] = per_phase.get(ph, 0) + 1
        if used % 20 == 0:
            print(f"[{datetime.now():%H:%M:%S}] 已補 {used}/{len(missing)}", flush=True)
        time.sleep(max(0.0, SPACING - (time.time() - t0)))
    remaining = [t for t in missing if not _cache_path(t[0], t[1], t[2], END).exists()]
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "phase": phase, "requests_used": used,
           "remaining": len(remaining), "stopped": stopped, "per_phase": per_phase}
    if cap > 0:
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0 if not remaining else (3 if stopped else 0)


if __name__ == "__main__":
    sys.exit(main())
