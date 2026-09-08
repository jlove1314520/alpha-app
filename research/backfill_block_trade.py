"""`HYPOTHESIS_QUEUE.md` #62 鉅額逐筆交易——資料回補（2026-09-09）。

跟`backfill_day_trading_ratio.py`/`backfill_t86.py`同一種「可重複呼叫、
有界批次、快取檔案本身就是完成紀錄」設計。BFIAUU一次一天，是本腳本的
瓶頸（TWSE反爬蟲封鎖需要呼叫間隔，見`SLEEP_BETWEEN_CALLS`，沿用
`backfill_day_trading_ratio.py`實測安全值，同一個`rwd`網域、假設同一套
封鎖規則）。

範圍：2015-01-01 ~ VAL_END（`validation/holdout.py`），跟本佇列多數
timing/事件研究gate同一個起點慣例。

用法：`python backfill_block_trade.py --batch-size 250`——每次呼叫處理至多
250個交易日（約8~9分鐘），可重複執行接續，不會重打已快取的日期。
"""
from __future__ import annotations

import time

import pandas as pd

from twse_block_trade_client import DATA_DIR, TWSEBlockedError, fetch_block_trade_day

START_DATE = "2015-01-01"
MAX_CONSECUTIVE_ERRORS = 8
SLEEP_BETWEEN_CALLS = 2.0  # 沿用backfill_day_trading_ratio.py實測安全值，同一個rwd網域


def backfill_block_trade(batch_size: int = 250, start_date: str = START_DATE,
                          end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("BFIAUU_", "") for p in DATA_DIR.glob("BFIAUU_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"BFIAUU全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}），"
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
            day_df = fetch_block_trade_day(date_str)
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

    total_cached = len(list(DATA_DIR.glob("BFIAUU_*.parquet")))
    print(f"\n本批次結束：嘗試 {attempted} 天，新完成 {newly_done}（其中 {newly_empty} 天無資料）")
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
    backfill_block_trade(batch_size=args.batch_size, start_date=args.start_date)
