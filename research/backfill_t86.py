"""T86 (三大法人買賣超) historical date-cache backfill (2026-08-26).

Same "resumable, bounded batch, safe to call repeatedly" design as
backfill_universe.py, adapted to twse_t86_client.py's per-DATE caching unit
(one call = one trading date, ALL stocks at once -- see that module's
docstring for why this is structurally the opposite of the per-stock
FinMind/backfill_universe.py shape).

No separate state JSON is needed here: the cache itself (one parquet file
per calendar date under research/data/raw_twse_t86/) IS the completion
record -- a date is "done" iff `T86_{YYYYMMDD}.parquet` exists. This is
simpler than backfill_universe.py's state dict because there's no
per-stock success/skip distinction to track at this layer.

Only business days (Mon-Fri) are attempted; TW public holidays that happen
to fall on a weekday still cost one wasted-but-harmless call (TWSE returns
`stat != 'OK'`, which fetch_t86_day() caches as an empty frame so it's
never re-requested).
"""
from __future__ import annotations

import time

import pandas as pd

from twse_t86_client import DATA_DIR, TWSEBlockedError, fetch_t86_day

# 2026-08-27 從 2010-01-01 改成 2012-05-02：實測直接向 TWSE T86 端點查
# 2010-01-04 等更早日期，回傳的是明確的 `{"stat":"查詢日期小於101年05月02日，
# 請重新查詢!","total":0}`（不是反爬蟲封鎖、不是普通無交易日）——這是 TWSE 這個端點
# 本身資料起點的硬限制，不是本專案能繞過的。舊起點浪費了兩輪批次（共 186 天，全部
# 0 筆資料）在注定查不到資料的日期範圍，改對起點後往後的批次才會真的推進覆蓋率。
START_DATE = "2012-05-02"
MAX_CONSECUTIVE_ERRORS = 8  # network trouble, not TWSE's own "no trading today" response
# 2026-08-26 從 0.4 調高到 2.0：實測 0.4 秒間隔在約 30 次呼叫內就觸發 TWSE 這個 `rwd`
# 端點的反爬蟲封鎖（見 twse_t86_client.py 的 TWSEBlockedError 說明），封鎖後整個 IP
# 對這個端點會被擋到未知的冷卻時間過去，比等待更久的呼叫間隔代價高很多。這個值是
# 保守猜測，不是已驗證的安全上限——之後如果還是被封鎖，要再拉長，不要調回去。
SLEEP_BETWEEN_CALLS = 2.0


def run_batch(batch_size: int = 200, start_date: str = START_DATE, end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END

    effective_end = end_date or VAL_END
    all_dates = pd.bdate_range(start_date, effective_end).strftime("%Y%m%d").tolist()
    cached = {p.stem.replace("T86_", "") for p in DATA_DIR.glob("T86_*.parquet")}
    pending = [d for d in all_dates if d not in cached]

    print(f"T86 全範圍 {len(all_dates)} 個工作日（{start_date}~{effective_end}），"
          f"已快取 {len(cached)}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_empty = 0  # cached but stat != OK (holiday) -- still "done", just no data that day
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
            day_df = fetch_t86_day(date_str)
            newly_done += 1
            if day_df.empty:
                newly_empty += 1
            consecutive_errors = 0
        except TWSEBlockedError as e:
            print(f"  {date_str}：偵測到 TWSE 反爬蟲封鎖，立刻停止本批次（不要重試，重試只會延長封鎖）：{e}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {date_str} 失敗：{e}")
            consecutive_errors += 1
        time.sleep(SLEEP_BETWEEN_CALLS)

        if attempted % 50 == 0:
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}")

    total_cached = len(list(DATA_DIR.glob("T86_*.parquet")))
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
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--start-date", type=str, default=START_DATE)
    args = parser.parse_args()
    run_batch(batch_size=args.batch_size, start_date=args.start_date)
