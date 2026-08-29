"""Weinstein第二階段掃描v2（`research/HYPOTHESIS_QUEUE.md`#1，2026-08-29
新增，馬拉松自主循環第一條假設）。

**跟v1（`weinstein_stage2.py`，`TRIALS_LEDGER.md`#10/#11既有記錄）的
具體差異**：v1只有兩個gate（收盤價站上150日均線 + 均線本身上揚），
在通過的候選裡用「自身60日絕對報酬」排名；v2**新增第三個gate**——
`f_rel_strength`（`factors.py`既有因子，`ret60 - mkt_ret60`，個股60日
報酬減大盤60日報酬，就是「相對大盤強弱」的既有實作，不是重新發明一個
新因子），且**排名依據改用`f_rel_strength`本身**（不是v1的絕對動能）
——這代表v2篩出的股票池是v1的子集（v1通過的兩個gate，v2還要多過
`f_rel_strength>0`這一關），排序邏輯也不同（相對強度 vs 絕對動能，
兩者在多頭齊漲的環境下高度相關，但在大盤走弱時會分道揚鑣：絕對動能
可能仍為正但相對強度為負，v2會把這種股票排除，v1不會）。

**刻意不改v1檔案**：v1被`TRIALS_LEDGER.md`#10/#11引用，修改它會讓那些
既有記錄的可重現性出問題（違反`CLAUDE.md`「最高投資原則」的儀器穩定性
精神）——新版另立檔案，v1保持原狀可以隨時重新驗證舊結果。
"""
from __future__ import annotations

import pandas as pd

from strategies.weinstein_stage2 import prepare_price_data, prepare_market_data  # noqa: F401 -- re-exported


def stage2_signal_v2(price_data: dict[str, pd.DataFrame], as_of_date: str, market_df: pd.DataFrame) -> dict[str, float]:
    """signal_fn for backtest.engine.run_backtest()。假設`price_data`已經
    跑過`prepare_price_data()`（加ma150/ma150_prev欄位）且本身就含有
    `f_rel_strength`欄位（`factor_ic.py`的`load_sample_with_factors()`
    既有輸出，不需要另外算）。回傳{stock_id: f_rel_strength}，只包含
    三個gate同時成立的股票；大盤位階閘門同v1（TAIEX須站上200日均線）。
    """
    if as_of_date not in market_df["date"].values:
        return {}
    gate_row = market_df.loc[market_df["date"] == as_of_date].iloc[0]
    if not bool(gate_row["gate"]):
        return {}

    scores: dict[str, float] = {}
    for sid, df in price_data.items():
        matches = df.loc[df["date"] == as_of_date]
        if matches.empty:
            continue
        row = matches.iloc[0]
        ma, ma_prev, close = row.get("ma150"), row.get("ma150_prev"), row["adj_close"]
        rel_strength = row.get("f_rel_strength")
        if pd.isna(ma) or pd.isna(ma_prev) or pd.isna(rel_strength):
            continue
        if close <= ma:
            continue
        if ma <= ma_prev:
            continue
        if rel_strength <= 0:
            continue
        scores[sid] = float(rel_strength)
    return scores
