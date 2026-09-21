# -*- coding: utf-8 -*-
"""籌碼原子.補借券快取（2026-09-20，債務帽）：回補宇宙U的`TaiwanDailyShortSaleBalances`（借券賣出餘額）。

規格：`ATOM_CHIP_IC_MAP_SPEC.md`第9節。宇宙U＝`chip_atom_library.universe_u()`（392檔，本機僅2330已有快取）。
每檔1次請求，經`finmind_client.load_dev`（截在VAL_END、寫入與其他腳本一致的快取檔名）。
**額度紀律**：遇402（`finmind_client`已標`rate_limit_state.json`封鎖2小時）或連續失敗達上限即停，
不排隊、不重試、不換來源；已有快取者直接跳過，可跨cycle續跑。
FinMind免費層實測約300次請求/小時即402（2026-09-20 20:22），與`backfill_fin_atom_cache.py`共用同一額度，
所以本腳本預設批次只有100檔，兩者同一小時內合計請避免超過約250次。
用法：python research/backfill_sbl_cache.py --batch-size 100
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chip_atom_library as cal  # noqa: E402
import finmind_client  # noqa: E402

RAW = HERE / "data" / "raw"
LOG = HERE / "data" / "backfill_sbl_cache_status.json"
DS = "TaiwanDailyShortSaleBalances"
MAX_CONSECUTIVE_FAIL = 8


def has_cache(sid: str) -> bool:
    import pyarrow.parquet as pq
    for p in RAW.glob(f"{DS}__{sid}__*.parquet"):
        try:
            if pq.ParquetFile(p).metadata.num_rows > 0:
                return True
        except Exception:  # noqa: BLE001 讀不了就當沒有
            pass
    return False


def has_file(sid: str) -> bool:
    """已抓過（含空表）：空表＝該股沒有借券賣出餘額資料，不該每批重排進待補、佔用批次名額。"""
    return any(RAW.glob(f"{DS}__{sid}__*.parquet"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=100)
    a = ap.parse_args()
    U = cal.universe_u()
    pending = [s for s in U if not has_file(s)]
    todo = pending[: a.batch_size]
    print(f"宇宙U {len(U)}檔；已抓過 {len(U) - len(pending)}（其中非空 {sum(has_cache(s) for s in U)}）；待補 {len(pending)}；本批 {len(todo)}", flush=True)
    ok = fail = consec = 0
    stopped = ""
    for i, sid in enumerate(todo, 1):
        try:
            finmind_client.load_dev(DS, sid, "2010-01-01")
            ok += 1
            consec = 0
        except Exception as e:  # noqa: BLE001 402/封鎖/網路：計數並在連續失敗時停手
            fail += 1
            consec += 1
            print(f"  [{i}/{len(todo)}] {sid} 失敗：{str(e)[:120]}", flush=True)
            if "402" in str(e) or "blocked" in str(e).lower() or consec >= MAX_CONSECUTIVE_FAIL:
                stopped = f"停於第{i}次：{str(e)[:160]}"
                break
        if i % 20 == 0:
            print(f"  進度 {i}/{len(todo)}（成功{ok}/失敗{fail}）", flush=True)
    rem = len([s for s in U if not has_file(s)])
    cover = sum(has_cache(s) for s in U) / len(U)  # 覆蓋只算非空快取
    st = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
          "requested": len(todo), "ok": ok, "fail": fail, "stopped": stopped,
          "remaining_unfetched": rem, "coverage_of_U": round(cover, 4)}
    LOG.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
