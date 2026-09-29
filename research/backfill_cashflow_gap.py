"""先.二-三(5)：補抓現金流量表缺口（供應緊縮草案 I4 資本支出用）。

範圍（與報酬無關，只看「有損益表快取、非金融、非興櫃、缺現金流量表快取」）：
按代碼排序逐檔經 finmind_client.load_dev 抓取（內建節流：600/hr→6秒一次；遇402即停，不重試）。
抓回空表者記為「補不到」，原因只可能是資料源無此檔，與報酬無關。
用法：python backfill_cashflow_gap.py [資料集名，預設現金流量表；亦可給 TaiwanStockBalanceSheet 補資產負債表缺口]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finmind_client  # noqa: E402
import pandas as pd  # noqa: E402

RAW = HERE / "data" / "raw"
OUT = HERE / "data" / ("backfill_cashflow_gap_status.json" if len(sys.argv) < 2 else f"backfill_gap_status_{sys.argv[1]}.json")
DS = sys.argv[1] if len(sys.argv) > 1 else "TaiwanStockCashFlowsStatement"
MAX_CONSECUTIVE_FAIL = 8


def _codes(ds: str) -> dict[str, list[Path]]:
    """任一起迄日命名的快取都算（實測有 2006／2010／2012／2024 起、迄 2024-12-31／latest／2026-xx 多種）。"""
    d = {}
    for p in RAW.glob(f"{ds}__*.parquet"):
        parts = p.name[:-8].split("__")
        if len(parts) == 4 and re.fullmatch(r"\d{4}", parts[1]):
            d.setdefault(parts[1], []).append(p)
    return d


def _nonempty(ps: list[Path]) -> bool:
    for p in ps:
        df = pd.read_parquet(p)
        if (not df.empty) and "type" in df.columns:
            return True
    return False


def target_codes() -> list[str]:
    info = pd.read_parquet(RAW / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet").drop_duplicates("stock_id")
    typ = info.set_index("stock_id")["type"].to_dict()
    ind = info.set_index("stock_id")["industry_category"].to_dict()
    fs, cf = _codes("TaiwanStockFinancialStatements"), _codes(DS)
    out = []
    for c, p in sorted(fs.items()):
        if not _nonempty(p) or typ.get(c) == "emerging" or ind.get(c) in ("金融保險", "金融業"):
            continue
        if c in cf:
            continue
        out.append(c)
    return out


def main() -> int:
    todo = target_codes()
    print(f"待補現金流量表 {len(todo)} 檔", flush=True)
    ok = 0
    empty: list[str] = []
    failed: list[dict] = []
    consec = 0
    stopped = ""
    for i, c in enumerate(todo, 1):
        try:
            df = finmind_client.load_dev(DS, c, "2010-01-01")
            ok += 1
            consec = 0
            if df.empty:
                empty.append(c)
        except Exception as e:  # 402/封鎖/網路：連續失敗即停，原因寫進status
            consec += 1
            failed.append({"code": c, "err": str(e)[:120]})
            print(f"  [{i}/{len(todo)}] {c} 失敗：{str(e)[:120]}", flush=True)
            if "402" in str(e) or "blocked" in str(e).lower() or consec >= MAX_CONSECUTIVE_FAIL:
                stopped = f"停於第{i}次：{str(e)[:160]}"
                break
        if i % 25 == 0:
            print(f"  進度 {i}/{len(todo)}（成功{ok}／空表{len(empty)}／失敗{len(failed)}）", flush=True)
    status = {
        "ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "targets": len(todo), "ok": ok, "empty_response": empty, "failed": failed,
        "stopped": stopped, "remaining_targets": len(target_codes()),
    }
    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in status.items()}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
