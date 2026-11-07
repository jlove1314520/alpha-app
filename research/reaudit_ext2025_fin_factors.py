# -*- coding: utf-8 -*-
"""先.一五五-3 第二批：財報類因子延長到 2025 起（零新外部請求；紙上優化軌描述性，非投資建議）。

做法同 F13 的 reaudit_ext2025_roe_factor.py：讀本機 FinMind 快取（2010～2024 舊檔為準＋2024/2025 起新檔只補新季），
PIT 日照 pit.py::_pivot_with_statutory_pit()（只呼叫、不改）；公式逐字照 factors.py：
- f_gross_profitability＝GrossProfit÷TotalAssets（_gross_profitability）
- f_gross_margin_stability＝−(GrossProfit÷Revenue) 近 8 季標準差（_gross_margin_stability）
- f_asset_growth＝−(TotalAssets÷4 季前 −1)（_asset_growth）
- f_accruals＝−Δ4季(非現金流動資產−營業流動負債)÷TotalAssets（_accruals）
- f_eps_growth＝(EPS−4季前)÷|4季前|（_eps_yoy_growth）；f_eps_surprise＝4季差÷近 8 季 4季差標準差（_eps_surprise_sue）
2024 底前的值由呼叫端跟 reaudit_ssu_loaded.pkl 原欄逐值核對，差 >1e-6 就停。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import factors as F
from pit import _pivot_with_statutory_pit
from reaudit_ext2025_roe_factor import _raw

FIN_FACS = ["f_gross_profitability", "f_gross_margin_stability", "f_asset_growth", "f_accruals", "f_eps_growth", "f_eps_surprise"]


def _inc(sid):
    return _pivot_with_statutory_pit(_raw("TaiwanStockFinancialStatements", sid))


def _bs(sid):
    return _pivot_with_statutory_pit(_raw("TaiwanStockBalanceSheet", sid))


def fin_pit(sid, fac):
    empty = pd.DataFrame(columns=["pit_date", "v"])
    if fac == "f_gross_profitability":
        inc, bs = _inc(sid), _bs(sid)
        if inc.empty or bs.empty or "GrossProfit" not in inc.columns or "TotalAssets" not in bs.columns:
            return empty
        m = inc[["fiscal_period_end", "pit_date", "GrossProfit"]].merge(
            bs[["fiscal_period_end", "TotalAssets"]], on="fiscal_period_end", how="inner"
        ).sort_values("fiscal_period_end").reset_index(drop=True)
        m["v"] = m["GrossProfit"] / m["TotalAssets"].replace(0, np.nan)
        return m[["pit_date", "v"]]
    if fac == "f_gross_margin_stability":
        inc = _inc(sid)
        if inc.empty or "Revenue" not in inc.columns or "GrossProfit" not in inc.columns:
            return empty
        inc = inc[["fiscal_period_end", "pit_date", "Revenue", "GrossProfit"]].sort_values("fiscal_period_end").reset_index(drop=True)
        gm = inc["GrossProfit"] / inc["Revenue"].replace(0, np.nan)
        W = F.ROE_STABILITY_TRAILING_QUARTERS
        inc["v"] = -gm.rolling(W, min_periods=W).std()
        return inc[["pit_date", "v"]]
    if fac == "f_asset_growth":
        bs = _bs(sid)
        if bs.empty or "TotalAssets" not in bs.columns:
            return empty
        bs = bs[["fiscal_period_end", "pit_date", "TotalAssets"]].sort_values("fiscal_period_end").reset_index(drop=True)
        bs["v"] = -(bs["TotalAssets"] / bs["TotalAssets"].shift(F.ASSET_GROWTH_LAG_QUARTERS) - 1)
        return bs[["pit_date", "v"]]
    if fac == "f_accruals":
        bs = _bs(sid)
        req = ["CurrentAssets", "CashAndCashEquivalents", "CurrentLiabilities", "ShorttermBorrowings", "TotalAssets"]
        if bs.empty or any(c not in bs.columns for c in req):
            return empty
        bs = bs[["fiscal_period_end", "pit_date"] + req].sort_values("fiscal_period_end").reset_index(drop=True)
        wc = (bs["CurrentAssets"] - bs["CashAndCashEquivalents"]) - (bs["CurrentLiabilities"] - bs["ShorttermBorrowings"])
        bs["v"] = -((wc - wc.shift(F.ACCRUALS_LAG_QUARTERS)) / bs["TotalAssets"])
        return bs[["pit_date", "v"]]
    if fac in ("f_eps_growth", "f_eps_surprise"):
        q = _inc(sid)
        if q.empty or "EPS" not in q.columns:
            return empty
        q = q.sort_values("fiscal_period_end").reset_index(drop=True)[["pit_date", "fiscal_period_end", "EPS"]]
        if fac == "f_eps_growth":
            q["v"] = (q["EPS"] - q["EPS"].shift(4)) / q["EPS"].shift(4).abs()
        else:
            dd = q["EPS"] - q["EPS"].shift(4)
            W = F.SUE_TRAILING_QUARTERS
            q["v"] = dd / dd.rolling(W, min_periods=W).std()
        return q[["pit_date", "v"]]
    raise ValueError(fac)


def attach(df, sid, fac):
    """照 factors._asof_join：先丟掉 NaN 季，每個交易日接 pit_date<=當日 的最新一季值。"""
    p = fin_pit(sid, fac).dropna()
    if p.empty:
        return np.full(len(df), np.nan)
    p = p.assign(_t=pd.to_datetime(p["pit_date"])).sort_values("_t")
    left = pd.DataFrame({"_t": pd.to_datetime(df["date"]), "_i": np.arange(len(df))}).sort_values("_t")
    j = pd.merge_asof(left, p[["_t", "v"]], on="_t", direction="backward")
    out = np.full(len(df), np.nan)
    out[j["_i"].to_numpy()] = j["v"].to_numpy()
    return out
