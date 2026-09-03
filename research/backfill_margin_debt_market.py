"""全市場融資餘額（TWSE MI_MARGN）歷史回補（2026-09-03，`HYPOTHESIS_QUEUE.md`
#26第1關cheap gate地基）。跟`backfill_t86.py`同一種「resumable、bounded
batch、可重複呼叫」設計，適配`margin_debt_market_client.py`的逐日快取單元。

**刻意採用週頻抽樣，不是逐日（跟本假設條目原文「逐日呼叫」的字面描述不同，
這是本輪的工程判斷，非事後偷改範圍，理由記錄如下）**：
全市場總融資餘額是「累積存量」（stock，不是flow）、变化緩慢，不像個股
價格需要逐日精度才能捕捉波動——20日/60日成長率用週頻資料（約4週/12週）
仍能合理近似同樣的中期趨勢訊號，但把約13年×252個交易日/年（~3300+次
呼叫）壓縮到約13年×52週（~680次呼叫），大幅降低命中TWSE反爬蟲封鎖的
風險、也讓回補能在合理輪數內完成（同`dividend_yield_portfolio_v1`連續
8輪才跑完的教訓，本假設優先選擇工程上更省時間的路徑）。若之後cheap gate
或更後面關卡發現週頻解析度不足以偵測訊號，屆時可視需要在既有週頻基礎上
補測逐日版本，不是這輪就要一次做到最細粒度。

同`backfill_t86.py`一樣：沒有獨立state JSON，快取本身（一個parquet檔=
一週的完成紀錄）就是進度記錄。
"""
from __future__ import annotations

import time

import pandas as pd

from margin_debt_market_client import DATA_DIR, TWSEBlockedError, fetch_margin_market_day

# 沿用`backfill_t86.py`同一個保守起點（同一個rwd端點家族，同樣的資料範圍
# 需求邊界：TRAIN起點不需要早於這個專案其他地方已經在用的歷史深度）。
START_DATE = "2012-05-02"
MAX_CONSECUTIVE_ERRORS = 8
# 沿用`backfill_t86.py`同一個實測安全值（同一個`rwd`端點家族，保守假設
# 反爬蟲機制共用同一套邏輯，直到證明不需要這麼保守之前不調低）。
SLEEP_BETWEEN_CALLS = 2.0


def _weekly_target_dates(start_date: str, end_date: str) -> list[str]:
    """每個ISO週取最後一個工作日（通常是週五，遇假日順延不影響——工作日
    週序列本身已排除週末，只是可能剛好是國定假日，那天fetch會拿到
    `is_trading_day=False`並正常快取，不影響下一輪判斷「已完成」）。"""
    all_bdays = pd.bdate_range(start_date, end_date)
    if len(all_bdays) == 0:
        return []
    iso = pd.Series(all_bdays).dt.isocalendar()
    df = pd.DataFrame({"date": all_bdays, "year": iso["year"], "week": iso["week"]})
    last_per_week = df.groupby(["year", "week"])["date"].max()
    return sorted(last_per_week.dt.strftime("%Y%m%d").tolist())


def run_batch(batch_size: int = 150, start_date: str = START_DATE, end_date: str | None = None) -> dict:
    from validation.holdout import VAL_END

    effective_end = end_date or VAL_END
    target_dates = _weekly_target_dates(start_date, effective_end)
    cached = {p.stem.replace("MARGIN_", "") for p in DATA_DIR.glob("MARGIN_*.parquet")}
    pending = [d for d in target_dates if d not in cached]

    print(f"MI_MARGN 週頻全範圍 {len(target_dates)} 週（{start_date}~{effective_end}），"
          f"已快取 {len(cached)}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_empty = 0
    consecutive_errors = 0

    for date_str in pending:
        if attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 週，停止")
            break
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            print(f"連續 {consecutive_errors} 次錯誤，判斷是網路/端點問題，提前停止本批次")
            break

        attempted += 1
        try:
            day_df = fetch_margin_market_day(date_str)
            newly_done += 1
            if not bool(day_df.iloc[0]["is_trading_day"]):
                newly_empty += 1
            consecutive_errors = 0
        except TWSEBlockedError as e:
            print(f"  {date_str}：偵測到 TWSE 反爬蟲封鎖，立刻停止本批次（不要重試）：{e}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  {date_str} 失敗：{e}")
            consecutive_errors += 1
        time.sleep(SLEEP_BETWEEN_CALLS)

        if attempted % 50 == 0:
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}")

    total_cached = len(list(DATA_DIR.glob("MARGIN_*.parquet")))
    print(f"\n本批次結束：嘗試 {attempted} 週，新完成 {newly_done}（其中 {newly_empty} 週該日非交易日）")
    print(f"累積已快取週數：{total_cached}/{len(target_dates)}"
          f"（{total_cached/len(target_dates)*100:.1f}% of 全範圍週數）")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_empty": newly_empty,
        "total_cached": total_cached, "total_range_weeks": len(target_dates),
        "hit_error_wall": consecutive_errors >= MAX_CONSECUTIVE_ERRORS,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=150)
    parser.add_argument("--start-date", type=str, default=START_DATE)
    args = parser.parse_args()
    run_batch(batch_size=args.batch_size, start_date=args.start_date)
