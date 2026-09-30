"""先.三-一：探測 FinMind 能否補到缺損益表快取的下市股（存活者偏誤，草案 §5.6／§6.8）。

只看「能否取得資料」與取得的資料期間，不計算任何報酬、不登記試驗。
名單取自 precheck_supply_tightness_results.json 的 roster.delisted_missing_from_fs_cache（依代碼排序）；
經 finmind_client.load_dev 抓取（內建節流；遇 402 即停，不重試）。
用法：python research/probe_delisted_fs.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finmind_client  # noqa: E402

DS = "TaiwanStockFinancialStatements"
OUT = HERE / "data" / "probe_delisted_fs_status.json"
MAX_CONSECUTIVE_FAIL = 5


def main() -> int:
    res = json.loads((HERE / "precheck_supply_tightness_results.json").read_text(encoding="utf-8"))
    codes = sorted(res["roster"]["delisted_missing_from_fs_cache"])
    print(f"探測 {len(codes)} 檔下市股損益表", flush=True)
    got: dict[str, dict] = {}
    empty: list[str] = []
    failed: list[dict] = []
    consec = 0
    stopped = ""
    for i, c in enumerate(codes, 1):
        try:
            df = finmind_client.load_dev(DS, c, "2010-01-01")
            consec = 0
            if df.empty:
                empty.append(c)
            else:
                got[c] = {"rows": int(len(df)), "first": str(df["date"].min()), "last": str(df["date"].max())}
        except Exception as e:
            consec += 1
            failed.append({"code": c, "err": str(e)[:120]})
            print(f"  [{i}/{len(codes)}] {c} 失敗：{str(e)[:120]}", flush=True)
            if "402" in str(e) or "blocked" in str(e).lower() or consec >= MAX_CONSECUTIVE_FAIL:
                stopped = f"停於第{i}次：{str(e)[:160]}"
                break
        if i % 10 == 0:
            print(f"  進度 {i}/{len(codes)}（有資料{len(got)}／空表{len(empty)}／失敗{len(failed)}）", flush=True)
    status = {
        "ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "targets": len(codes), "recovered": got, "empty_response": empty, "failed": failed,
        "stopped": stopped, "not_attempted": [c for c in codes if c not in got and c not in empty
                                               and c not in {f["code"] for f in failed}],
    }
    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in status.items()}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
