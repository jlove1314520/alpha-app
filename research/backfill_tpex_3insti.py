"""上櫃三大法人歷史回補（金流一.2，2026-09-10）。

沿用 `backfill_t86.py` 同一套「可中斷續跑、快取檔本身就是完成紀錄」設計，
呼叫 `tpex_3insti_client.py`。跟 T86 版最大的不同：**這裡回補的是「近 250
個交易日」（截至執行當天），不是固定歷史起點往前推**——見
`tpex_3insti_client.py` 檔頭的 holdout 邊界說明，這份資料只餵
`data/sector_flow.json`，不得被接進任何回測 loader。

速率限制照總司令原話（PENDING_QUEUE.md「金流一」條目）：間隔 ≥2 秒／次、
每日上限 300 次請求、失敗退避 60 秒。
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd

from tpex_3insti_client import DATA_DIR, TPExBlockedError, fetch_tpex_3insti_day

TARGET_TRADING_DAYS = 250
# 250 個交易日 ≈ 350 個日曆天（5/7），再加台灣國定假日緩衝，抓 400 天確保
# 扣掉假日後仍 ≥250 個實際交易日（見開發時的試算：400 天回推有 287 個平日，
# 扣除約 15~20 個國定假日後仍有 260+ 個交易日）。
LOOKBACK_CALENDAR_DAYS = 400
DAILY_REQUEST_CAP = 300  # 總司令原話「每日上限 300 次請求」
SLEEP_BETWEEN_CALLS = 2.0  # 總司令原話「間隔 ≥2 秒／次」
FAILURE_BACKOFF_SECONDS = 60  # 總司令原話「失敗退避 60 秒」
MAX_CONSECUTIVE_ERRORS = 5  # 超過視為網路/端點問題，不是單日偶發，提前停止本批次


def run_batch(batch_size: int = DAILY_REQUEST_CAP, end_date: str | None = None) -> dict:
    effective_end = end_date or date.today().isoformat()
    end_dt = date.fromisoformat(effective_end)
    start_dt = end_dt - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    all_dates = pd.bdate_range(start_dt.isoformat(), effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("TPEX3INSTI_", "") for p in DATA_DIR.glob("TPEX3INSTI_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"TPEx 三大法人回補：近 {LOOKBACK_CALENDAR_DAYS} 個日曆天共 {len(all_dates)} 個平日"
          f"（{start_dt.isoformat()}~{effective_end}），已快取 {len(cached)}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_empty = 0  # 快取成功但當天無交易（週末夾在平日算法裡的殘留／國定假日）
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
            day_df = fetch_tpex_3insti_day(date_str)
            newly_done += 1
            if day_df.empty:
                newly_empty += 1
            consecutive_errors = 0
        except TPExBlockedError as e:
            print(f"  {date_str}：偵測到 TPEx 疑似封鎖/格式異常，立刻停止本批次（不重試）：{e}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {date_str} 失敗，退避 {FAILURE_BACKOFF_SECONDS} 秒：{e}")
            consecutive_errors += 1
            time.sleep(FAILURE_BACKOFF_SECONDS)
            continue
        time.sleep(SLEEP_BETWEEN_CALLS)

        if attempted % 50 == 0:
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}")

    total_cached = len(list(DATA_DIR.glob("TPEX3INSTI_*.parquet")))
    trading_days_with_data = sum(
        1 for p in DATA_DIR.glob("TPEX3INSTI_*.parquet")
        if p.stat().st_size > 0 and not pd.read_parquet(p).empty
    )
    print(f"\n本批次結束：嘗試 {attempted} 天，新完成 {newly_done}（其中 {newly_empty} 天無交易/無資料）")
    print(f"累積已快取天數：{total_cached}/{len(all_dates)}"
          f"（其中有實際資料的交易日：{trading_days_with_data}，目標 {TARGET_TRADING_DAYS}）")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_empty": newly_empty,
        "total_cached": total_cached, "total_range_bdays": len(all_dates),
        "trading_days_with_data": trading_days_with_data,
        "hit_error_wall": consecutive_errors >= MAX_CONSECUTIVE_ERRORS,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DAILY_REQUEST_CAP)
    parser.add_argument("--end-date", type=str, default=None)
    args = parser.parse_args()
    run_batch(batch_size=args.batch_size, end_date=args.end_date)
