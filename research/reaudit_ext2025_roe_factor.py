# -*- coding: utf-8 -*-
"""先.一五五-2 F13 用：把 f_quality_roe_stability 延長到 2025 起（零新外部請求）。

公式完全照 factors.py::_roe_stability()（季淨利歸屬母公司÷期末母公司權益，取最近 8 季標準差的負值），
PIT 日照 pit.py::_pivot_with_statutory_pit()（只呼叫、不改；Q4＝次年 3/31、Q1～Q3＝法定 45 日）。
原版經 finmind_client.load_dev() 讀、截在 2024-12-31；這裡改直接讀本機 FinMind 快取：
`{資料集}__{代號}__2010-01-01__2024-12-31.parquet` ＋ `__2024-01-01__latest` ＋ `__2025-01-01__latest`（同 date+type 以舊檔為準，讓 2024 底以前與原版一致；新檔只補 2025 起新季），
再用 merge_asof（pit_date<=當日）接到價格上。核對：2024 底以前的值要與 reaudit_ssu_loaded.pkl 原欄一致。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pit import _pivot_with_statutory_pit

RAW = Path(__file__).resolve().parent / "data" / "raw"
TQ = 8


def _raw(ds, sid):
    fs = [RAW / f"{ds}__{sid}__2010-01-01__2024-12-31.parquet",
          RAW / f"{ds}__{sid}__2024-01-01__latest.parquet",
          RAW / f"{ds}__{sid}__2025-01-01__latest.parquet"]
    parts = []
    for i, f in enumerate(fs):
        if f.exists():
            x = pd.read_parquet(f)
            if not x.empty and "date" in x.columns:
                x = x.assign(_pri=i)
                parts.append(x)
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    x["date"] = x["date"].astype(str).str[:10]
    x = x[x["date"] >= "2010-01-01"]
    return x.sort_values("_pri").drop_duplicates(["date", "type"], keep="first").drop(columns="_pri")


def roe_stability_pit(sid):
    inc = _pivot_with_statutory_pit(_raw("TaiwanStockFinancialStatements", sid))
    bs = _pivot_with_statutory_pit(_raw("TaiwanStockBalanceSheet", sid))
    col = "EquityAttributableToOwnersOfParent"
    if inc.empty or bs.empty or col not in inc.columns or col not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "roe_stability"])
    inc = inc[["fiscal_period_end", "pit_date", col]].rename(columns={col: "net_income"})
    bs = bs[["fiscal_period_end", col]].rename(columns={col: "equity"})
    m = inc.merge(bs, on="fiscal_period_end", how="inner").sort_values("fiscal_period_end").reset_index(drop=True)
    m["roe"] = m["net_income"] / m["equity"]
    m["roe_stability"] = -m["roe"].rolling(TQ, min_periods=TQ).std()
    return m[["pit_date", "roe_stability"]]


def attach(df, sid):
    """df 的 date 是字串；回傳同列序的 f_quality_roe_stability 值（numpy）。"""
    p = roe_stability_pit(sid).dropna()
    if p.empty:
        return np.full(len(df), np.nan)
    p = p.assign(_t=pd.to_datetime(p["pit_date"])).sort_values("_t")
    left = pd.DataFrame({"_t": pd.to_datetime(df["date"]), "_i": np.arange(len(df))}).sort_values("_t")
    j = pd.merge_asof(left, p[["_t", "roe_stability"]], on="_t", direction="backward")
    out = np.full(len(df), np.nan)
    out[j["_i"].to_numpy()] = j["roe_stability"].to_numpy()
    return out
