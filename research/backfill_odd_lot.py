"""`HYPOTHESIS_QUEUE.md` #67 盤中零股逐檔成交資訊——歷史回補
（2026-09-09 hypothesis_queue排程接續新增）。

跟`backfill_day_trading_detail.py`（#57）同一種「可重複呼叫、有界批次、
快取檔案本身就是完成紀錄」設計：每次呼叫處理至多`--batch-size`個交易日，
用`twse_odd_lot_client.py::fetch_odd_lot_day()`打TWTC7U端點，快取進
`data/raw_twse_odd_lot/`，下次呼叫自動跳過已快取的日期接續，直到全範圍
回補完成才適合進入#67第1關cheap gate（比照#37/#57先例）。

**範圍起點是`EARLIEST_AVAILABLE_DATE`（2020-10-26），不是本專案其他
假設慣用的2015-01-01**——官方文件明載零股盤中逐筆制度2020-10-26才上路，
更早的日期一律沒有資料，強行往前回補只會浪費API配額換來全部空值。

**TRAIN/VAL切分需重新評估（`HYPOTHESIS_QUEUE.md` #67「已知限制」第2點
本輪兌現）**：`validation/holdout.py`的標準邊界`TRAIN_END=2020-12-31`
若原封不動套用，TRAIN期只剩約2個月資料（2020-10-26~2020-12-31），
樣本量遠不足以支撐任何統計判準。**本假設專用切分（事前綁定，寫在這裡
供`odd_lot_gate67.py`引用，不事後更動）**：
    ODD_LOT_TRAIN_END = "2022-12-31"   # TRAIN = [2020-10-26, 2022-12-31]，約2.2年
    ODD_LOT_VAL_END   = "2024-12-31"   # VAL = (2022-12-31, 2024-12-31]，約2年
`ODD_LOT_VAL_END`刻意等於既有`validation.holdout.VAL_END`，**沒有更動
holdout物理邊界本身**——(VAL_END, 今天]依然是聖域，只是在「非holdout」
的可用區間裡，把TRAIN/VAL的內部分界點從2020-12-31往後移到2022-12-31，
理由是資料起點比其他假設晚了將近6年，原分界點對這個假設不適用，這是
資料可用性限制而非動了門柱的行為。

用法：`python backfill_odd_lot.py --batch-size 250`——每次處理至多250
個交易日，`SLEEP_BETWEEN_CALLS`沿用#37/#57/T86同一個實測安全值2.0秒/次
（同一個`rwd`網域，假設同一套封鎖規則）。
"""
from __future__ import annotations

import time

import pandas as pd

from twse_odd_lot_client import (
    DATA_DIR,
    EARLIEST_AVAILABLE_DATE,
    TWSEBlockedError,
    fetch_odd_lot_day,
)

# 本假設專用TRAIN/VAL切分（見本檔案docstring「TRAIN/VAL切分需重新評估」）。
ODD_LOT_TRAIN_END = "2022-12-31"
ODD_LOT_VAL_END = "2024-12-31"

MAX_CONSECUTIVE_ERRORS = 8
SLEEP_BETWEEN_CALLS = 2.0


def backfill_odd_lot(batch_size: int = 250, start_date: str = EARLIEST_AVAILABLE_DATE,
                      end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("TWTC7U_", "") for p in DATA_DIR.glob("TWTC7U_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"TWTC7U全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}，"
          f"早於{EARLIEST_AVAILABLE_DATE}的日期本就不存在故不在此範圍內），"
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
            day_df = fetch_odd_lot_day(date_str)
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

    total_cached = len(list(DATA_DIR.glob("TWTC7U_*.parquet")))
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
    parser.add_argument("--start-date", type=str, default=EARLIEST_AVAILABLE_DATE)
    args = parser.parse_args()
    backfill_odd_lot(batch_size=args.batch_size, start_date=args.start_date)
