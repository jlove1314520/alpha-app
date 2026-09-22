"""S&P500 Total Return 序列建構（`CONCENTRATED_SPEC.md`第3節缺口，
2026-09-23馬拉松軌·研究帽，US軌工作單位）。

背景：`spillover_overnight_gate.py::_daily_returns("^GSPC")`用的`^GSPC`
是S&P500價格報酬指數（不含股利再投資），`CONCENTRATED_SPEC.md`已明文
指出用它當美股集中版天條二基準會系統性高估策略贏面（基準漏了股利）。
本檔解決第3節列的候選來源#1：Yahoo Finance `^SP500TR`（官方S&P500
Total Return指數ticker），沿用既有`yf_price_client.py::fetch_yf_index()`
基礎設施，不需要新的抓取邏輯。

**查證結果（本輪實測，供CONCENTRATED_SPEC.md後續引用）**：
- `^SP500TR`資料涵蓋 1990-01-02 起（holdout裁切到VAL_END=2024-12-31後
  共8816列），零缺值（`close`欄位無NaN）。
- 2003-06-30~2024-12-31同一段期間，TR年化報酬10.87% vs 價格報酬指數
  （`^GSPC`同期）8.74%，缺口約2.1個百分點/年，與S&P500歷史平均股利
  殖利率量級（約1.8~2.2%/年）吻合——確認`^SP500TR`確實是計入股利再
  投資的total return序列，不是價格指數的誤標。
- 涵蓋範圍早於`CONCENTRATED_SPEC.md`0050基準序列起點（2003-06-30），
  不構成瓶頸。

**本檔只解決資料缺口本身**，不代表`concentrated_backtest.py`可以動筆
——第4節參數掃描方式仍待總司令裁示（`AWAITING_REVIEW.md`），本檔案
只是把候選來源#1的查證做完並提供可重用函式，供裁示核准後直接import。
"""
from __future__ import annotations

import pandas as pd

from yf_price_client import fetch_yf_index
from validation import holdout

TICKER = "^SP500TR"


def load_sp500tr_full_history() -> pd.DataFrame:
    """回傳S&P500 Total Return完整歷史，欄位跟`survival_constraint_
    allocation_test.py::load_0050_full_history()`相容：date/adj_close
    （這裡的`close`本身已經是total return，不需要額外還原股利，直接
    改名成`adj_close`供下游共用同一套回測程式碼）。"""
    raw = fetch_yf_index(ticker=TICKER, start_date="1990-01-01")
    if raw.empty:
        raise RuntimeError(f"{TICKER} yfinance回傳為空，無法建立S&P500 TR序列")
    out = raw.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["adj_close"] = out["close"].astype(float)
    out = out.sort_values("date").reset_index(drop=True)
    out = out[out["date"] <= pd.Timestamp(holdout.VAL_END)].reset_index(drop=True)
    holdout.assert_no_holdout_leakage(out, context="sp500_tr_series full history")
    return out[["date", "adj_close"]]


if __name__ == "__main__":
    df = load_sp500tr_full_history()
    print(f"rows={len(df)} range={df['date'].min().date()}~{df['date'].max().date()} "
          f"nulls={df['adj_close'].isna().sum()}")
