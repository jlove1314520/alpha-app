# -*- coding: utf-8 -*-
"""證.一（2026-09-26總司令裁示【緊急：H.一立即暫停重跑，修正兩個bug後先做
乾跑檢查】）：只印資料診斷，不得產生任何策略結果數字。

驗證Cowork讀碼推論①：`factors.py::_dividend_yield_ttm_cash()`用
`load_dev()`抓`TaiwanStockDividend`，會截在`VAL_END`(2024-12-31)；
`holdout_2025_dividend_account_test.py`的載入迴圈呼叫`prepare_factors()`
時，從未把這個內部的`load_dev()`呼叫換成uncapped版本（跟同一支腳本裡
`uncapped_adjusted_price_series()`特地為股價做的處理不同）——所以H.一的
訊號計算裡，2025年以後真實發生的除息事件對因子完全不可見。

**只用已快取的parquet，零額外FinMind呼叫**：`load_dev()`與
`load_full_history()`最終都呼叫`_fetch(dataset, data_id, start_date,
end_date=None)`，快取鍵完全相同（`TaiwanStockDividend__{id}__2024-01-01__
latest.parquet`）——只要檔案已經在`research/data/raw/`，兩種呼叫方式都
是cache hit，不會真的發送請求。這裡選的5檔全部來自已快取檔案（見選取
腳本），不會觸發任何網路呼叫，符合停.一「立即停止一切自動重跑」的精神
（這支診斷腳本本身不是「H.一的正式回測段落」，只是讀已有的快取資料做
比對）。

跑法：python research/audit_h1_dividend_pit_lag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import pandas as pd

from factors import _dividend_yield_ttm_cash
from finmind_client import load_full_history

LOOKBACK_START = "2024-01-01"  # 與 holdout_2025_dividend_account_test.py 的 LOOKBACK_START 一致

# 從已快取的 TaiwanStockDividend parquet 檔案中，挑出 5 檔在 2025-01-01~
# 2026-09-26 之間有實際發生（非未來公告）除息事件、且日期最新的普通股。
SAMPLE_STOCK_IDS = ["3260", "5906", "6584", "7738", "2464"]


def _uncapped_latest_ex_date(stock_id: str) -> str | None:
    """不截斷的 TaiwanStockDividend：直接讀已快取的uncapped原始資料，
    找出最新的 CashExDividendTradingDate（僅取 <= 今天的，過濾掉board已
    公告但尚未發生的未來除息日，避免跟「已發生的PIT事件」混為一談）。
    """
    div = load_full_history("TaiwanStockDividend", stock_id, LOOKBACK_START, allow_holdout=True)
    if div.empty or "CashExDividendTradingDate" not in div.columns:
        return None
    dates = div["CashExDividendTradingDate"].astype(str)
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    valid = dates[(dates >= "2025-01-01") & (dates <= today)]
    return valid.max() if len(valid) else None


def _capped_factor_last_pit_date(stock_id: str) -> str | None:
    """factors.py::_dividend_yield_ttm_cash() 目前實際使用的路徑——
    load_dev()，會被裁在VAL_END。"""
    div_pit = _dividend_yield_ttm_cash(stock_id, LOOKBACK_START)
    if div_pit.empty:
        return None
    return str(pd.to_datetime(div_pit["pit_date"]).max().date())


def main() -> None:
    print("=" * 78)
    print("證.一：H.一股利因子PIT延遲診斷（只印資料診斷，不含任何策略結果數字）")
    print("=" * 78)
    rows = []
    for sid in SAMPLE_STOCK_IDS:
        capped_pit = _capped_factor_last_pit_date(sid)
        uncapped_ex = _uncapped_latest_ex_date(sid)
        mismatch = (capped_pit != uncapped_ex)
        rows.append({"stock_id": sid, "capped_factor_last_pit_date": capped_pit,
                      "uncapped_latest_ex_date_2025plus": uncapped_ex, "mismatch": mismatch})
        print(f"\n{sid}:")
        print(f"  因子資料(load_dev()截VAL_END)最後一筆pit_date：{capped_pit}")
        print(f"  不截斷TaiwanStockDividend最新2025+除息日：{uncapped_ex}")
        print(f"  {'不一致（證實①：2025年股利事件對因子不可見）' if mismatch else '一致'}")

    n_mismatch = sum(r["mismatch"] for r in rows)
    print("\n" + "=" * 78)
    print(f"總結：{n_mismatch}/{len(rows)} 檔不一致。")
    if n_mismatch:
        print("結論：證實Cowork推論①——factors.py::_dividend_yield_ttm_cash()"
              "用load_dev()導致2025年以後的股利事件不會進入H.一的訊號計算，"
              "需依修.五修正。")
    print("=" * 78)

    out = {"generated_at": pd.Timestamp.now().isoformat(), "rows": rows,
           "n_mismatch": int(n_mismatch), "n_total": len(rows)}
    out_path = Path(__file__).parent / "data" / "h1_dividend_pit_lag_evidence.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {out_path}")


if __name__ == "__main__":
    main()
