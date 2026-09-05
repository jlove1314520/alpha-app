"""假設#40（庫藏股買回公告效應）——MOPS t35sc09歷史回補，逐半年窗口
（2015-01-01 ~ `validation/holdout.py` VAL_END，絕不越界抓holdout）。

跟`backfill_day_trading_ratio.py`同一種「可重複呼叫、有界批次、快取檔案
本身就是完成紀錄」設計：已存在的窗口直接跳過，中斷後重跑會自動接續。

用法：`python backfill_buyback_announcement.py`——一次把全部窗口跑完
（約20個半年窗口 x 2市場=40次請求，`SLEEP_BETWEEN_CALLS=2.0`秒/次，
預估總時間約3~4分鐘，比T86/當沖比重輕量很多，不需要`--batch-size`
分批）。
"""
from __future__ import annotations

import pandas as pd

from mops_buyback_client import fetch_window, DATA_DIR
from validation.holdout import VAL_END

START_YEAR_ROC = 2015 - 1911  # 民國104年


def _roc_windows(end_date_str: str = VAL_END) -> list[tuple[str, str]]:
    end_year_ad = int(end_date_str[:4])
    end_year_roc = end_year_ad - 1911
    windows = []
    for roc_year in range(START_YEAR_ROC, end_year_roc + 1):
        windows.append((f"{roc_year}0101", f"{roc_year}0630"))
        windows.append((f"{roc_year}0701", f"{roc_year}1231"))
    return windows


def main() -> None:
    windows = _roc_windows()
    cached_before = len(list(DATA_DIR.glob("BUYBACK_*.parquet")))
    print(f"共{len(windows)}個半年窗口 x 2市場={len(windows) * 2}次請求，"
          f"回補範圍2015-01-01~{VAL_END}，開始前已快取{cached_before}個檔案")

    total_rows = 0
    for market in ("sii", "otc"):
        for d1, d2 in windows:
            df = fetch_window(market, d1, d2)
            total_rows += len(df)
            print(f"  {market} {d1}~{d2}: {len(df)}列（累計{total_rows}）")

    cached_after = len(list(DATA_DIR.glob("BUYBACK_*.parquet")))
    print(f"回補完成：{cached_after}個快取檔案（本輪新增{cached_after - cached_before}個），"
          f"累計原始列數（未去重）約{total_rows}")


if __name__ == "__main__":
    main()
