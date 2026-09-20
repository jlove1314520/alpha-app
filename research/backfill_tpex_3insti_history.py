# -*- coding: utf-8 -*-
"""籌碼原子.補上櫃三大法人歷史（2026-09-20，債務帽）：逐交易日回補TPEx
`dailyTrade`三大法人買賣超，範圍涵蓋train/val（不是既有
`backfill_tpex_3insti.py`那支只抓近250天給`data/sector_flow.json`
產品面板用的版本）。

**為什麼需要這支（2026-09-20總司令裁示【depth-1閘門設計缺陷要修；
p=0.053作廢要正式處理】三）**：`ATOM_CHIP_IC_MAP_SPEC.md`已記錄T86
（三大法人）只有上市股，上櫃股缺席，籌碼原子的三大法人族因此只反映
上市股、不代表全市場，尤其上櫃正是小型股集中的地方。既有的FinMind
`TPEX3INSTI`資料集只從2025-08起有資料、落在VAL_END之後不得使用；
但`tpex_3insti_client.py`（金流一.2，2026-09-10）本身是直接打TPEx
官方`dailyTrade`端點、**支援任意歷史日期查詢**，只是既有的
`backfill_tpex_3insti.py`只拿它做「近250天」的產品面板回補，從未
做過涵蓋train/val範圍的歷史回補——**同樣的力氣、同一個已驗證可用
的官方端點，花在正確的日期範圍上就能補上這個覆蓋缺口**。

沿用`backfill_twse_slb.py`／`backfill_t86.py`同一套「日期快取檔存在
＝完成，可跨cycle續跑」設計，重用既有`tpex_3insti_client.py`（不修改
該檔案本身，只是用不同的呼叫範圍）。**節流沿用該檔案既有的既定速率
（總司令原話：間隔≥2秒/次、每日上限300次請求、失敗退避60秒）**，
不因為這次是歷史回補就放寬。

**Holdout邊界（沿用`tpex_3insti_client.py`檔頭同一條紀律）**：範圍
2010-01-04~VAL_END，不碰holdout；本回補的快取跟既有`backfill_
tpex_3insti.py`寫進同一個`DATA_DIR`（`data/raw_tpex_3insti/`，同一種
檔名格式`TPEX3INSTI_<date>.parquet`），日期快取本身沒有區分「為了
產品面板抓的」還是「為了研究回測抓的」——**這是刻意的**：同一個交易日
的三大法人數字只有一份事實，不需要為了兩種用途各存一份重複資料，
差別只在於「回補的日期範圍」，不在於資料內容本身。

用法：
    python research/backfill_tpex_3insti_history.py --batch-size 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

try:  # Windows cp950主控台印不出特殊符號時降級，不崩潰（見CLAUDE.md第十二節）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tpex_3insti_client import DATA_DIR, TPExBlockedError, fetch_tpex_3insti_day  # noqa: E402

START = "2018-06-01"  # **2026-09-20實測發現，不是跟T86對齊的原始猜測**：
    # 逐點探測`fetch_tpex_3insti_day()`發現2018-07-01之前（含2010-01-04/
    # 2012-05-02/2015-01-05/2018-01-02/2018-07-01）全部回空表，2018-08-01
    # 起有真實資料（483列）；2018-07-01~2018-08-01之間確切轉折點未進一步
    # 逐日narrow down（機率成本考量），START留一個月緩衝取2018-06-01，
    # 由回補結果自然揭露空表比例。**這代表TPEx這個端點的上櫃三大法人
    # 歷史深度只到約2018年中，不像T86回溯到2012年**——覆蓋範圍本來就
    # 比上市股窄，回補完成後的覆蓋率報告需要誠實反映這個結構性落差，
    # 不能假裝跟T86同樣深度。
SLEEP = 2.0  # 沿用tpex_3insti_client.py檔頭與backfill_tpex_3insti.py既定節流
MAX_CONSECUTIVE_ERRORS = 5
STATUS = HERE / "data" / "backfill_tpex_3insti_history_status.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=200)
    a = ap.parse_args()
    from validation.holdout import VAL_END
    all_dates = pd.bdate_range(START, VAL_END).strftime("%Y%m%d").tolist()
    have = {p.stem.replace("TPEX3INSTI_", "") for p in DATA_DIR.glob("TPEX3INSTI_*.parquet")}
    pending = [d for d in all_dates if d not in have]
    print(f"範圍{START}~{VAL_END}工作日{len(all_dates)}，已快取{len(have)}，"
          f"待處理{len(pending)}，本批≤{a.batch_size}", flush=True)

    done = empty = err_streak = 0
    stopped = ""
    for d in pending[: a.batch_size]:
        try:
            df = fetch_tpex_3insti_day(d)
            done += 1
            empty += int(df.empty)
            err_streak = 0
        except TPExBlockedError as e:
            err_streak += 1
            print(f"  {d} 疑似封鎖/非JSON（連續{err_streak}）：{str(e)[:100]}", flush=True)
            if err_streak >= MAX_CONSECUTIVE_ERRORS:
                stopped = f"連續{err_streak}次封鎖/非JSON，停於{d}"
                break
        except Exception as e:  # noqa: BLE001 -- 網路等：計數，連續失敗同樣停手
            err_streak += 1
            print(f"  {d} 失敗：{str(e)[:100]}", flush=True)
            if err_streak >= MAX_CONSECUTIVE_ERRORS:
                stopped = f"連續失敗{err_streak}次，停於{d}：{str(e)[:100]}"
                break
        if done % 50 == 0 and done:
            print(f"  進度 完成{done}（空表{empty}）", flush=True)
        time.sleep(SLEEP)

    have2 = len(list(DATA_DIR.glob("TPEX3INSTI_*.parquet")))
    st = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
          "new_done": done, "new_empty": empty, "stopped": stopped,
          "cached_total": have2, "range_workdays": len(all_dates),
          "remaining": len(all_dates) - have2}
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
