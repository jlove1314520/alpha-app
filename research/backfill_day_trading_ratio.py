"""`HYPOTHESIS_QUEUE.md` #37 全市場現股當沖比重——資料回補（2026-09-05）。

跟`backfill_t86.py`同一種「可重複呼叫、有界批次、快取檔案本身就是完成
紀錄」設計，適用於`twse_day_trading_client.py`（TWTASU，一次一天，是本
腳本的瓶頸——TWSE反爬蟲封鎖需要呼叫間隔，見`SLEEP_BETWEEN_CALLS`）+
`twse_market_volume_client.py`（FMTQIK，一次一整月，便宜，直接一次跑完
不分批）。

範圍：2015-01-01 ~ VAL_END（`validation/holdout.py`），跟本佇列多數
index-level timing gate（`option_pcr_gate.py`等）同一個起點慣例。

用法：`python backfill_day_trading_ratio.py --batch-size 250`——每次呼叫
處理至多250個交易日的TWTASU（約8~9分鐘，SLEEP_BETWEEN_CALLS=2.0秒/次，
跟T86同一個實測安全值，同一個`rwd`網域、假設同一套封鎖規則），FMTQIK
月檔案數量少（120個月）直接一次全部跑完不受batch-size限制。
"""
from __future__ import annotations

import time

import pandas as pd

from twse_day_trading_client import DATA_DIR as DT_DIR, TWSEBlockedError, fetch_day_trading_ratio_day
from twse_market_volume_client import fetch_market_volume_month

START_DATE = "2015-01-01"
MAX_CONSECUTIVE_ERRORS = 8
SLEEP_BETWEEN_CALLS = 2.0  # 沿用twse_t86_client.py實測安全值，同一個rwd網域


def backfill_market_volume(start_date: str = START_DATE, end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    months = pd.period_range(start_date, effective_end, freq="M")
    done = 0
    for p in months:
        fetch_market_volume_month(p.year, p.month)
        done += 1
        time.sleep(0.3)  # FMTQIK量小很多，用比TWTASU寬鬆的間隔即可
    print(f"FMTQIK全市場成交量：{done}個月已確認快取（{start_date}~{effective_end}）")
    return {"months_done": done}


def backfill_day_trading(batch_size: int = 250, start_date: str = START_DATE,
                          end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("TWTASU_", "") for p in DT_DIR.glob("TWTASU_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"TWTASU全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}），"
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
            day_df = fetch_day_trading_ratio_day(date_str)
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

    total_cached = len(list(DT_DIR.glob("TWTASU_*.parquet")))
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
    parser.add_argument("--skip-market-volume", action="store_true")
    args = parser.parse_args()
    if not args.skip_market_volume:
        backfill_market_volume(start_date=args.start_date)
    backfill_day_trading(batch_size=args.batch_size, start_date=args.start_date)
