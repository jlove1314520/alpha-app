# -*- coding: utf-8 -*-
"""驗.六 第一部分：資料路徑普查（診斷，不改任何判定）。

背景：#398/#399/#7/#8/#9 皆用 `single_shot_2007_2014_test.
load_common_stock_data_2007_2014()` 的 2007-2014 樣本宇宙（300檔抽樣中的
普通股）。`adjust.py::adjusted_price_series()` 會優先用 yfinance，只有
yfinance 查無資料時才落回 FinMind 手動還原路徑（回傳的 DataFrame 有
`source` 欄位標示 'yfinance' 或 'finmind'）。本腳本統計這個宇宙裡
股票數/股票×日數的 yfinance vs FinMind 路徑佔比，並列出 FinMind 路徑
中有碰到股票股利（修.七）或現金增資（查.三）還原事件的股票數——這兩類
事件正是本輪四項資料修正的其中兩項，只有走 FinMind 路徑的股票才會受到
影響（yfinance 路徑用的是 yfinance 自己的 auto_adjust，不經過
`adjust.py` 的股利/分割/減資公式）。

**只做診斷，零新增 API 呼叫**：`adjusted_price_series()` 讀本機快取
（yfinance parquet + FinMind 手動還原兩條路徑皆為本機快取），不觸發
任何新請求。#398/#399/#400 判定全部鎖定不動，本腳本不產生任何判定
結果。

輸出：research/data/v6_data_path_audit.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from pathlib import Path

import pandas as pd

from adjust import adjusted_price_series
from single_shot_2007_2014_test import (
    EXTENDED_START,
    SAMPLE_SEED,
    SAMPLE_SIZE,
    _info_lookup,
    sample_universe_ids,
)
from universe import classify_security

OUT = Path(__file__).parent / "data" / "v6_data_path_audit.json"


def _load_dividend_cache() -> pd.DataFrame | None:
    """讀本機快取的 TaiwanStockDividend（若不存在則回傳 None，不新增請求）。"""
    for cand in (
        Path(__file__).parent / "data" / "cache" / "TaiwanStockDividend.parquet",
        Path(__file__).parent.parent / "alpha-data" / "cache" / "TaiwanStockDividend.parquet",
    ):
        if cand.exists():
            try:
                return pd.read_parquet(cand)
            except Exception:  # noqa: BLE001
                continue
    return None


def main() -> None:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    info_lookup = _info_lookup()
    common_ids = [
        sid
        for sid in sample_ids
        if classify_security(
            sid,
            (info_lookup.get(sid) or {}).get("stock_name"),
            (info_lookup.get(sid) or {}).get("industry_category"),
        )
        == "普通股"
    ]
    print(f"2007-2014樣本宇宙普通股共{len(common_ids)}檔", flush=True)

    div_cache = _load_dividend_cache()
    if div_cache is not None:
        div_cache["stock_id"] = div_cache["stock_id"].astype(str)

    per_stock = {}
    n_yfinance_stocks = 0
    n_finmind_stocks = 0
    n_load_fail = 0
    total_rows_yfinance = 0
    total_rows_finmind = 0
    finmind_stocks_with_stock_dividend = []
    finmind_stocks_with_cash_increase = []

    for sid in common_ids:
        try:
            px = adjusted_price_series(sid, EXTENDED_START)
        except Exception as e:  # noqa: BLE001
            n_load_fail += 1
            per_stock[sid] = {"status": "load_fail", "error": str(e)[:200]}
            continue
        if px is None or px.empty or "source" not in px.columns:
            n_load_fail += 1
            per_stock[sid] = {"status": "empty_or_no_source_column"}
            continue

        counts = px["source"].value_counts(dropna=False).to_dict()
        n_yf = int(counts.get("yfinance", 0))
        n_fm = int(counts.get("finmind", 0))
        total_rows_yfinance += n_yf
        total_rows_finmind += n_fm

        dominant = "yfinance" if n_yf >= n_fm else "finmind"
        if dominant == "yfinance":
            n_yfinance_stocks += 1
        else:
            n_finmind_stocks += 1

        has_stock_dividend = False
        has_cash_increase = False
        if dominant == "finmind" and div_cache is not None:
            sub = div_cache[div_cache["stock_id"] == sid]
            if not sub.empty:
                if "StockEarningsDistribution" in sub.columns:
                    has_stock_dividend = bool((sub["StockEarningsDistribution"].fillna(0) != 0).any())
                if "CashIncreaseSubscriptionRate" in sub.columns:
                    has_cash_increase = bool((sub["CashIncreaseSubscriptionRate"].fillna(0) != 0).any())
            if has_stock_dividend:
                finmind_stocks_with_stock_dividend.append(sid)
            if has_cash_increase:
                finmind_stocks_with_cash_increase.append(sid)

        per_stock[sid] = {
            "rows_yfinance": n_yf,
            "rows_finmind": n_fm,
            "dominant_path": dominant,
            "has_stock_dividend_event": has_stock_dividend,
            "has_cash_increase_event": has_cash_increase,
        }

    total_rows = total_rows_yfinance + total_rows_finmind
    result = {
        "scope": "2007-2014樣本宇宙（#7/#8/#9因子層級與#398/#399候選層級共用同一份宇宙）",
        "universe_stock_count": len(common_ids),
        "load_fail_count": n_load_fail,
        "dominant_path_stock_counts": {
            "yfinance": n_yfinance_stocks,
            "finmind": n_finmind_stocks,
        },
        "row_level_counts": {
            "yfinance": total_rows_yfinance,
            "finmind": total_rows_finmind,
            "finmind_pct_of_total_rows": round(100 * total_rows_finmind / total_rows, 3) if total_rows else None,
        },
        "finmind_dominant_stocks_with_stock_dividend_event": {
            "count": len(finmind_stocks_with_stock_dividend),
            "stock_ids": finmind_stocks_with_stock_dividend,
        },
        "finmind_dominant_stocks_with_cash_increase_event": {
            "count": len(finmind_stocks_with_cash_increase),
            "stock_ids": finmind_stocks_with_cash_increase,
        },
        "dividend_cache_available": div_cache is not None,
        "note": "只涵蓋2007-2014樣本宇宙，未涵蓋holdout宇宙（214檔）——budget範圍限制，"
                "如實記錄未完成部分，留待下一輪繼續，不假裝已涵蓋。",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
