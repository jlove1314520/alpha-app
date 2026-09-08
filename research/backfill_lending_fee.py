"""`HYPOTHESIS_QUEUE.md` #63 借券費率異常飆升——資料回補（2026-09-09）。

跟`backfill_block_trade.py`同一種「可重複呼叫、有界批次、快取檔案本身就是
完成紀錄」設計，但單位是**年**不是**日**（`twse_lending_fee_client.py`
docstring「歷史回溯」段落已實測單次查詢一整年無明顯筆數上限，逐年批次比
逐日省下365倍請求量）。因為總請求數只有個位數到十幾筆，一次呼叫通常就能
在單一馬拉松輪次內（<5分鐘）跑完全部範圍，不需要`run_detached.py`。

範圍：2012 ~ VAL_END（`validation/holdout.py`）所屬年度，2012起點沿用
`twse_lending_fee_client.py`docstring記錄的實測回溯下限（未查證更早年份
是否有資料，不假設）。

用法：`python backfill_lending_fee.py`——處理全部年度，可重複執行接續，
不會重打已快取的年度。
"""
from __future__ import annotations

import time

from twse_lending_fee_client import DATA_DIR, TWSEBlockedError, fetch_lending_fee_year

START_YEAR = 2012
SLEEP_BETWEEN_CALLS = 2.0  # 沿用backfill_block_trade.py同一個rwd網域實測安全值


def backfill_lending_fee(start_year: int = START_YEAR, end_year: int | None = None) -> dict:
    from validation.holdout import VAL_END
    effective_end_year = end_year or int(VAL_END[:4])
    all_years = list(range(start_year, effective_end_year + 1))
    cached = {int(p.stem.replace("LENDING_FEE_", "")) for p in DATA_DIR.glob("LENDING_FEE_*.parquet")}
    pending = [y for y in all_years if y not in cached]

    print(f"借券費率全範圍 {len(all_years)} 個年度（{start_year}~{effective_end_year}），"
          f"已快取 {len(cached)}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_empty = 0
    total_rows_new = 0

    for year in pending:
        attempted += 1
        try:
            df = fetch_lending_fee_year(year)
            newly_done += 1
            total_rows_new += len(df)
            if df.empty:
                newly_empty += 1
            print(f"  {year}：{len(df)} 筆")
        except TWSEBlockedError as e:
            print(f"  {year}：偵測到TWSE反爬蟲封鎖，立刻停止本批次：{e}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {year} 失敗：{e}")
            break
        if year != pending[-1]:
            time.sleep(SLEEP_BETWEEN_CALLS)

    total_cached = len(list(DATA_DIR.glob("LENDING_FEE_*.parquet")))
    print(f"\n本批次結束：嘗試 {attempted} 年，新完成 {newly_done}（其中 {newly_empty} 年無資料，"
          f"新增 {total_rows_new} 筆）")
    print(f"累積已快取年度：{total_cached}/{len(all_years)}"
          f"（{total_cached/len(all_years)*100:.1f}% of 全範圍年度）")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_empty": newly_empty,
        "total_rows_new": total_rows_new, "total_cached": total_cached,
        "total_range_years": len(all_years),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=None)
    args = parser.parse_args()
    backfill_lending_fee(start_year=args.start_year, end_year=args.end_year)
