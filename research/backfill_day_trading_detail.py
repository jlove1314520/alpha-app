"""`HYPOTHESIS_QUEUE.md` #57 全市場當沖比重截面離散度——逐檔資料回補
（2026-09-08）。

跟`backfill_day_trading_ratio.py`（#37，只存「合計」單列）同一種
「可重複呼叫、有界批次、快取檔案本身就是完成紀錄」設計，差別只在
呼叫`twse_day_trading_client.py::fetch_day_trading_detail_day()`（逐檔
版本，存進獨立目錄`data/raw_twse_day_trading_detail/`），**無法沿用
#37已快取的彙總parquet**——原始逐檔JSON從未落地，這裡是重新打一次
TWTASU端點，不是重工，是查證後發現的必要成本（見
`twse_day_trading_client.py`該函式上方的說明段落）。

範圍：2015-01-01 ~ VAL_END（`validation/holdout.py`），跟#37同一個
起點慣例，因為兩者本來就是同一個經濟現象（現股當沖）的不同統計量。

用法：`python backfill_day_trading_detail.py --batch-size 250`——每次
呼叫處理至多250個交易日（約8~9分鐘，`SLEEP_BETWEEN_CALLS`沿用#37/T86
同一個實測安全值2.0秒/次，同一個`rwd`網域、假設同一套封鎖規則）。
"""
from __future__ import annotations

import time

import pandas as pd

from twse_day_trading_client import (
    DETAIL_DATA_DIR,
    TWSEBlockedError,
    fetch_day_trading_detail_day,
)

START_DATE = "2015-01-01"
MAX_CONSECUTIVE_ERRORS = 8
SLEEP_BETWEEN_CALLS = 2.0  # 沿用backfill_day_trading_ratio.py/twse_t86_client.py同一個實測安全值


def backfill_day_trading_detail(batch_size: int = 250, start_date: str = START_DATE,
                                 end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("TWTASU_detail_", "") for p in DETAIL_DATA_DIR.glob("TWTASU_detail_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"TWTASU逐檔全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}），"
          f"已快取 {len(cached)}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_empty = 0
    consecutive_errors = 0

    for date_str in pending:
        if attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 天，停止")
            break
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            print(f"連續 {consecutive_errors} 次錯誤，判斷是網路/端點問題，提前停止本批次")
            break

        attempted += 1
        try:
            day_df = fetch_day_trading_detail_day(date_str)
            newly_done += 1
            if day_df.empty:
                newly_empty += 1
            consecutive_errors = 0
        except TWSEBlockedError as e:
            print(f"  {date_str}：偵測到TWSE反爬蟲封鎖，立刻停止本批次：{e}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {date_str} 失敗：{e}")
            consecutive_errors += 1
        time.sleep(SLEEP_BETWEEN_CALLS)

        if attempted % 50 == 0:
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}")

    total_cached = len(list(DETAIL_DATA_DIR.glob("TWTASU_detail_*.parquet")))
    print(f"\n本批次結束：嘗試 {attempted} 天，新完成 {newly_done}（其中 {newly_empty} 天無交易/無資料）")
    print(f"累積已快取交易日：{total_cached}/{len(all_dates)}"
          f"（{total_cached/len(all_dates)*100:.1f}% of 全範圍工作日）")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_empty": newly_empty,
        "total_cached": total_cached, "total_range_bdays": len(all_dates),
        "hit_error_wall": consecutive_errors >= MAX_CONSECUTIVE_ERRORS,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--start-date", type=str, default=START_DATE)
    args = parser.parse_args()
    backfill_day_trading_detail(batch_size=args.batch_size, start_date=args.start_date)
