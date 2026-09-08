"""`HYPOTHESIS_QUEUE.md` #52 事件反應速度——資料回補（2026-09-08）。

跟`backfill_day_trading_ratio.py`同一種「可重複呼叫、有界批次、快取
檔案本身就是完成紀錄」設計，適用於`mops_material_news_client.py`
（`ajax_t05st01`全市場逐日窄查詢，一次一天，是本腳本的瓶頸——MOPS
非商用API需要呼叫間隔，見`SLEEP_BETWEEN_CALLS`）。

範圍：2015-01-01 ~ VAL_END（`validation/holdout.py`），跟本佇列多數
index-level timing gate同一個起點慣例。全範圍`pd.bdate_range`近似值
約2,500個工作日（含少數國定假日，會得到空結果並正常快取，backfill視
為「已完成」不重打，比照`backfill_day_trading_ratio.py`同一個慣例）。
預估2秒/次×2,500≈83分鐘，單輪session不硬等，建議用`run_detached.py
submit`投遞背景執行，多輪接續完成（比照`backfill_t86.py`/`backfill_
day_trading_ratio.py`既有的checkpoint可續跑設計）。

用法：`python backfill_material_news.py --batch-size 250`
"""
from __future__ import annotations

import argparse
import time

import pandas as pd

from mops_material_news_client import (
    DATA_DIR,
    MOPSMaterialNewsError,
    fetch_material_news_day,
    new_session,
)

START_DATE = "2015-01-01"
MAX_CONSECUTIVE_ERRORS = 8
SLEEP_BETWEEN_CALLS = 2.0  # 沿用mops_buyback_client.py同一個MOPS節流精神


def backfill(batch_size: int = 250, start_date: str = START_DATE, end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("MATNEWS_", "") for p in DATA_DIR.glob("MATNEWS_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"MOPS重大訊息全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}），"
          f"已快取 {len(cached)}，待處理 {len(pending)}")

    session = new_session()
    attempted = 0
    newly_done = 0
    newly_empty = 0
    consecutive_errors = 0

    for date_str in pending:
        if attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 天，停止")
            break
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            print(f"連續 {consecutive_errors} 次錯誤，判斷是網路/session/端點問題，提前停止本批次")
            break

        attempted += 1
        try:
            day_df = fetch_material_news_day(session, date_str)
            newly_done += 1
            if day_df.empty:
                newly_empty += 1
            consecutive_errors = 0
        except MOPSMaterialNewsError as e:
            print(f"  {date_str}：疑似session過期或非預期錯誤，重建session後繼續：{e}")
            consecutive_errors += 1
            session = new_session()
        except Exception as e:  # noqa: BLE001 -- 資料源禮儀：記錄失敗原因，不靜默吞錯
            print(f"  {date_str} 失敗：{e}")
            consecutive_errors += 1
        time.sleep(SLEEP_BETWEEN_CALLS)

        if attempted % 50 == 0:
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}")

    total_cached = len(list(DATA_DIR.glob("MATNEWS_*.parquet")))
    print(f"\n本批次結束：嘗試 {attempted} 天，新完成 {newly_done}（其中 {newly_empty} 天無公告/非交易日）")
    print(f"累積已快取交易日：{total_cached}/{len(all_dates)}"
          f"（{total_cached/len(all_dates)*100:.1f}% of 全範圍工作日）")
    return {
        "attempted": attempted,
        "newly_done": newly_done,
        "newly_empty": newly_empty,
        "total_cached": total_cached,
        "total_range": len(all_dates),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=None)
    args = parser.parse_args()
    backfill(batch_size=args.batch_size, start_date=args.start_date, end_date=args.end_date)
