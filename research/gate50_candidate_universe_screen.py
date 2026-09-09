"""#50（容量受限小型股）逐筆tick取樣候選清單 -- 地基準備工作，非統計判定。

背景：`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md` 指出目前
`shioaji_quotes.py` 動態訂閱清單（支援App報價畫面用）跟 #50 要求的
「日均成交值500萬~5,000萬新台幣」區間完全不重疊，需要另外篩一批候選代號。
該提案第2步明確寫「這一步不需要新增外部API呼叫」——本腳本就是做這一步：
用本機已快取的 FinMind `TaiwanStockPrice`/`TaiwanStockInfo`（零新增API呼叫，
純讀 `data/raw/*.parquet`）篩出候選代號，供提案核准後直接使用，不用等到
核准當下才臨時篩選。

**本腳本本身不執行訂閱變更、不改 `shioaji_quotes.py`、不改
`.live_watchlist.json`——只產生候選清單檔案，執行仍要等提案核准。**

已知限制（如實揭露，不隱藏）：
1. 成交值資料是本機快取，最新到 `VAL_END`（見 `validation/holdout.py`），
   不是即時成交值——提案本文第4點已指出成交值會隨時間漂移，真正要訂閱前
   應該用當下最新資料重新確認一次，這份清單只是「起點候選」不是「最終名單」。
2. 排除ETF（`00`開頭代號、`industry_category`含「ETF」字樣）與權證（沿用
   `universe.py::active_stock_ids()` 既有的6碼數字權證過濾邏輯），因為#50
   的經濟機制是「個股容量受限」，ETF/權證不適用。
3. 只保留「近60個交易日全數有成交量資料」的代號（排除長期停牌/新掛牌不足
   60日的股票），避免候選清單本身就充滿資料不全的雷。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from universe import active_stock_ids

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_PATH = DATA_DIR / "gate50_candidate_universe.json"

TARGET_MIN_NTD = 5_000_000
TARGET_MAX_NTD = 50_000_000
LOOKBACK_DAYS = 60
PRICE_CACHE_SUFFIX = "__2010-01-01__2024-12-31.parquet"


def _is_etf_or_warrant(row: pd.Series) -> bool:
    sid = str(row["stock_id"])
    if sid.startswith("00"):
        return True
    industry = str(row.get("industry_category") or "")
    if "ETF" in industry.upper():
        return True
    return False


def screen() -> dict:
    active = active_stock_ids()
    active = active[~active.apply(_is_etf_or_warrant, axis=1)].reset_index(drop=True)

    rows = []
    missing_cache = 0
    insufficient_history = 0
    for _, r in active.iterrows():
        sid = str(r["stock_id"])
        cache_path = RAW_DIR / f"TaiwanStockPrice__{sid}__2010-01-01__2024-12-31.parquet"
        if not cache_path.exists():
            missing_cache += 1
            continue
        try:
            df = pd.read_parquet(cache_path, columns=["date", "Trading_money"])
        except Exception:
            missing_cache += 1
            continue
        if df.empty or len(df) < LOOKBACK_DAYS:
            insufficient_history += 1
            continue
        df = df.sort_values("date").tail(LOOKBACK_DAYS)
        if (df["Trading_money"].fillna(0) <= 0).any():
            insufficient_history += 1
            continue
        avg_turnover = float(df["Trading_money"].mean())
        if TARGET_MIN_NTD <= avg_turnover <= TARGET_MAX_NTD:
            rows.append(
                {
                    "stock_id": sid,
                    "stock_name": str(r["stock_name"]),
                    "industry_category": str(r.get("industry_category") or ""),
                    "avg_daily_turnover_ntd": round(avg_turnover, 0),
                    "as_of_last_date": str(df["date"].max()),
                }
            )

    rows.sort(key=lambda x: x["avg_daily_turnover_ntd"])
    result = {
        "generated_by": "gate50_candidate_universe_screen.py",
        "purpose": "PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md 第2步的候選清單準備，"
        "尚未執行訂閱變更，等提案核准",
        "target_range_ntd": [TARGET_MIN_NTD, TARGET_MAX_NTD],
        "lookback_trading_days": LOOKBACK_DAYS,
        "data_as_of_note": "本機快取上限 VAL_END（validation/holdout.py），非即時成交值，"
        "訂閱前需用當下最新資料重新確認",
        "active_universe_count_ex_etf_warrant": int(len(active)),
        "missing_price_cache_count": missing_cache,
        "insufficient_history_count": insufficient_history,
        "candidate_count": len(rows),
        "candidates": rows,
    }
    return result


if __name__ == "__main__":
    result = screen()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"候選數: {result['candidate_count']}")
    print(f"母體(排除ETF/權證): {result['active_universe_count_ex_etf_warrant']}")
    print(f"無快取: {result['missing_price_cache_count']}  歷史不足/停牌: {result['insufficient_history_count']}")
    print(f"輸出: {OUT_PATH}")
    for c in result["candidates"][:10]:
        print(c)
