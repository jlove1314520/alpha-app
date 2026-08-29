"""Weinstein第二階段掃描v2（`research/HYPOTHESIS_QUEUE.md`#1，2026-08-29
新增，馬拉松自主循環第一條假設）。

**跟v1（`weinstein_stage2.py`，`TRIALS_LEDGER.md`#10/#11既有記錄）的
具體差異**：v1只有兩個gate（收盤價站上150日均線 + 均線本身上揚），
在通過的候選裡用「自身60日絕對報酬」排名；v2**新增第三個gate**——
相對大盤強弱（60日個股報酬 − 60日大盤報酬，跟`factors.py::f_rel_
strength`同一個既有定義，不是重新發明一個新因子），且**排名依據改用
相對強度本身**（不是v1的絕對動能）——這代表v2篩出的股票池是v1的子集
（v1通過的兩個gate，v2還要多過「相對強度>0」這一關），排序邏輯也不同
（相對強度 vs 絕對動能，兩者在多頭齊漲的環境下高度相關，但在大盤走弱
時會分道揚鑣：絕對動能可能仍為正但相對強度為負，v2會把這種股票排除，
v1不會）。

**刻意不改v1檔案**：v1被`TRIALS_LEDGER.md`#10/#11引用，修改它會讓那些
既有記錄的可重現性出問題（違反`CLAUDE.md`「最高投資原則」的儀器穩定性
精神）——新版另立檔案，v1保持原狀可以隨時重新驗證舊結果。

**2026-08-29馬拉松自主循環真bug修正（誠實記錄）**：第一版`stage2_signal_v2()`
假設呼叫端傳入的`price_data`已經含有`f_rel_strength`欄位（沿用
`factor_ic.py::load_sample_with_factors()`的既有輸出），但
`run_weinstein_unbiased_v2.py`走的是另一條資料路徑（`adjusted_price_
series()`+這個模組自己的`prepare_price_data()`），根本沒有算過這個
欄位——`row.get("f_rel_strength")`永遠拿到`None`，`pd.isna(None)`永遠
是`True`，導致**每一檔股票在每一天都被跳過，整個回測期間0筆交易**。
GATE_SEQUENCE第1關sanity檢查用的是`factor_ic.py`的快取資料（那份剛好
有這個欄位），沒測到這個真實會被使用的資料路徑，這是sanity檢查涵蓋率
不足的教訓：**之後sanity階段要用「跟後續關卡完全同一條資料載入路徑」
測試，不能圖方便借用別的pipeline的現成資料**。修法：新增
`_add_rel_strength()`，在這個模組自己的`prepare_price_data_v2()`裡
獨立算相對強度，不依賴外部欄位是否存在。
"""
from __future__ import annotations

import pandas as pd

from strategies.weinstein_stage2 import prepare_price_data as _prepare_price_data_base
from strategies.weinstein_stage2 import prepare_market_data  # noqa: F401 -- re-exported

REL_STRENGTH_WINDOW = 60  # 跟factors.py::REL_STRENGTH_WINDOW同一個定義


def prepare_price_data_v2(price_data: dict[str, pd.DataFrame], market_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """v1的`prepare_price_data()`（加ma150/ma150_prev/momentum）之外，
    再獨立算一份相對強度（60日個股報酬 − 60日大盤報酬），不依賴呼叫端
    是否已經算過這個欄位——這是修掉「假設外部欄位存在」那個真bug的核心。
    """
    out = _prepare_price_data_base(price_data)
    mkt_close = market_df.set_index("date")["close"]
    for sid, df in out.items():
        df["mkt_close"] = df["date"].map(mkt_close)
        ret = df["adj_close"] / df["adj_close"].shift(REL_STRENGTH_WINDOW) - 1
        mkt_ret = df["mkt_close"] / df["mkt_close"].shift(REL_STRENGTH_WINDOW) - 1
        df["rel_strength_v2"] = ret - mkt_ret
    return out


def stage2_signal_v2(price_data: dict[str, pd.DataFrame], as_of_date: str, market_df: pd.DataFrame) -> dict[str, float]:
    """signal_fn for backtest.engine.run_backtest()。假設`price_data`已經
    跑過這個模組的`prepare_price_data_v2()`（加ma150/ma150_prev/
    rel_strength_v2欄位）。回傳{stock_id: rel_strength_v2}，只包含三個
    gate同時成立的股票；大盤位階閘門同v1（TAIEX須站上200日均線）。
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
        rel_strength = row.get("rel_strength_v2")
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
