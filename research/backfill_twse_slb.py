# -*- coding: utf-8 -*-
"""籌碼原子.補出借總量快取（2026-09-20，債務帽）：逐交易日回補TWSE TWT72U借券餘額。

沿用 `backfill_t86.py` 樣式：以日期快取檔存在＝完成，可跨cycle續跑、≤batch-size請求/次。
**節流**：固定3秒間隔（同族T86端點0.4秒即被封，2秒是保守值，這裡再放寬）；`TWSEBlockedError`
（封鎖頁／非JSON）連續3次即停，不重試。範圍2010-01-04～VAL_END（不碰holdout）。
用法：python research/backfill_twse_slb.py --batch-size 800
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from twse_slb_client import DATA_DIR, TWSEBlockedError, fetch_slb_day  # noqa: E402

START = "2010-01-04"
SLEEP = 3.0
MAX_BLOCKED = 3
STATUS = HERE / "data" / "backfill_twse_slb_status.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=800)
    a = ap.parse_args()
    from validation.holdout import VAL_END
    all_dates = pd.bdate_range(START, VAL_END).strftime("%Y%m%d").tolist()
    have = {p.stem.replace("SLB_", "") for p in DATA_DIR.glob("SLB_*.parquet")}
    pending = [d for d in all_dates if d not in have]
    print(f"範圍{START}~{VAL_END}工作日{len(all_dates)}，已快取{len(have)}，待處理{len(pending)}，本批≤{a.batch_size}", flush=True)
    done = empty = blocked = err = 0
    stopped = ""
    for d in pending[: a.batch_size]:
        try:
            df = fetch_slb_day(d)
            done += 1
            empty += int(df.empty)
            blocked = 0
        except TWSEBlockedError as e:
            blocked += 1
            print(f"  {d} 疑似封鎖/非JSON（連續{blocked}）：{str(e)[:100]}", flush=True)
            if blocked >= MAX_BLOCKED:
                stopped = f"連續{blocked}次封鎖/非JSON，停於{d}"
                break
        except Exception as e:  # noqa: BLE001 網路等：計數，連續失敗同樣停手
            err += 1
            blocked += 1
            print(f"  {d} 失敗：{str(e)[:100]}", flush=True)
            if blocked >= MAX_BLOCKED:
                stopped = f"連續失敗{blocked}次，停於{d}：{str(e)[:100]}"
                break
        if (done + err) % 50 == 0:
            print(f"  進度 完成{done}（空表{empty}）/失敗{err}", flush=True)
        time.sleep(SLEEP)
    have2 = len(list(DATA_DIR.glob("SLB_*.parquet")))
    st = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
          "new_done": done, "new_empty": empty, "errors": err, "stopped": stopped,
          "cached_total": have2, "range_workdays": len(all_dates), "remaining": len(all_dates) - have2}
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
