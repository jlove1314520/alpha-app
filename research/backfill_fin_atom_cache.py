"""財報原子.補快取（2026-09-20，債務帽）：補抓「有income快取、缺資產負債表/現金流量表快取」的股票。

背景：`FIN_ATOM_COVERAGE.md`——total_assets/equity/inventory/receivable/ocf 全體覆蓋僅20~31%，
肇因是本機缺檔（有快取者覆蓋75~85%），補抓後才能重評原子.五的「覆蓋不足」標記。

做法：掃`data/raw/`找「有TaiwanStockFinancialStatements__{code}__2010-01-01__2024-12-31.parquet、
缺BalanceSheet或CashFlowsStatement同名快取」的代碼，一次處理≤`--batch-size`檔（預設200），
經`finmind_client.load_dev`（holdout封頂VAL_END，寫入跟其他腳本一致的快取檔名）補抓。
**額度紀律**：遇402（`finmind_client`已標`rate_limit_state.json`封鎖2小時）或連續失敗達上限即停，
不排隊、不重試、不換來源；已抓過的組合下次直接命中快取。可跨cycle續跑。
用法：python backfill_fin_atom_cache.py --batch-size 200
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finmind_client  # noqa: E402

RAW = HERE / "data" / "raw"
LOG = HERE / "data" / "backfill_fin_atom_cache_status.json"
SUFFIX = "__2010-01-01__2024-12-31.parquet"
DATASETS = ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement")
MAX_CONSECUTIVE_FAIL = 8


def missing_pairs() -> list[tuple[str, str]]:
    have = {p.name for p in RAW.glob("*" + SUFFIX)}
    codes = sorted(n.split("__")[1] for n in have if n.startswith("TaiwanStockFinancialStatements__"))
    return [(c, ds) for c in codes for ds in DATASETS if f"{ds}__{c}{SUFFIX}" not in have]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=200)
    a = ap.parse_args()
    pairs = missing_pairs()
    codes = list(dict.fromkeys(c for c, _ in pairs))[: a.batch_size]
    todo = [(c, ds) for c, ds in pairs if c in set(codes)]
    print(f"缺快取(code,dataset)組合 {len(pairs)}（涉及 {len(set(c for c, _ in pairs))} 檔）；本批 {len(codes)} 檔/{len(todo)} 次請求", flush=True)
    ok = fail = consec = 0
    stopped = ""
    for i, (c, ds) in enumerate(todo, 1):
        try:
            df = finmind_client.load_dev(ds, c, "2010-01-01")
            ok += 1
            consec = 0
        except Exception as e:  # 402/封鎖/網路：計數並在連續失敗時停手，原因寫進status
            fail += 1
            consec += 1
            print(f"  [{i}/{len(todo)}] {ds} {c} 失敗：{str(e)[:120]}", flush=True)
            if "402" in str(e) or "blocked" in str(e).lower() or consec >= MAX_CONSECUTIVE_FAIL:
                stopped = f"停於第{i}次：{str(e)[:160]}"
                break
        if i % 20 == 0:
            print(f"  進度 {i}/{len(todo)}（成功{ok}/失敗{fail}）", flush=True)
    rem = len(missing_pairs())
    status = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
              "requested": len(todo), "ok": ok, "fail": fail, "stopped": stopped, "remaining_pairs": rem}
    LOG.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
