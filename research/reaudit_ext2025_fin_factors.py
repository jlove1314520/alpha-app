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
from pathlib import Path

from pit import _next_month_10th, _pivot_with_statutory_pit
from reaudit_ext2025_roe_factor import _raw

FIN_FACS = ["f_gross_profitability", "f_gross_margin_stability", "f_asset_growth", "f_accruals", "f_eps_growth", "f_eps_surprise",
            "f_revenue_surprise", "f_dividend_yield_ttm", "f_value_pe", "f_value_pb"]
# （DevQueue 20261107-230102）籌碼類：法人買賣超＋融資融券，日資料當日盤後公布、當日即 pit（同 factors.py 註解）。
CHIP_FACS = ["f_inst_flow", "f_foreign_streak", "f_inst_streak_days", "f_margin_utilization", "f_short_margin_ratio"]
FIN_FACS = FIN_FACS + CHIP_FACS

RAW = Path(__file__).resolve().parent / "data" / "raw"


def _month_rev_raw(sid):
    """（DevQueue 20261107-133102）月營收：本機所有 TaiwanStockMonthRevenue__{sid}__*.parquet 合併，
    舊檔（迄 2024-12-31）優先、新檔（2024-01-01__2026-07-01／2025-06-01__latest）只補新月份；
    pit_date 照 pit.month_revenue_pit：有 create_time 用它，否則次月 10 日。"""
    fs = sorted(RAW.glob(f"TaiwanStockMonthRevenue__{sid}__*.parquet"),
                key=lambda f: (0 if f.name.endswith("2024-12-31.parquet") else 1, f.name))
    parts = [pd.read_parquet(f) for f in fs]
    parts = [x for x in parts if not x.empty and "revenue_year" in x.columns]
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True).drop_duplicates(["revenue_year", "revenue_month"], keep="first")
    ct = x["create_time"].fillna("").astype(str)
    has_real = ct.str.len() > 0
    assumed = x.apply(lambda r: _next_month_10th(int(r["revenue_year"]), int(r["revenue_month"])), axis=1)
    x["pit_date"] = ct.where(has_real, assumed)
    return x


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
    if fac == "f_revenue_surprise":  # 照 factors._revenue_surprise_sue 逐字
        rev = _month_rev_raw(sid)
        if rev.empty:
            return empty
        rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
        prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
        prior["revenue_year"] += 1
        prior = prior.rename(columns={"revenue": "revenue_prior_year"})
        rev = rev.merge(prior, on=["revenue_year", "revenue_month"], how="left")
        rev["yoy"] = (rev["revenue"] - rev["revenue_prior_year"]) / rev["revenue_prior_year"].abs()
        W = F.REVENUE_SUE_TRAILING_MONTHS
        rev["yoy_std"] = rev["yoy"].rolling(W, min_periods=W).std()
        rev["v"] = rev["yoy"] / rev["yoy_std"]
        return rev[["pit_date", "v"]]
    if fac == "f_dividend_yield_ttm":  # （DevQueue 20261107-183102）分子照 factors._dividend_yield_ttm_cash_from_df
        fs = sorted(RAW.glob(f"TaiwanStockDividend__{sid}__*.parquet"))
        parts = [pd.read_parquet(f) for f in fs]
        parts = [x for x in parts if not x.empty]
        if not parts:
            return empty
        t = F._dividend_yield_ttm_cash_from_df(pd.concat(parts, ignore_index=True))
        return t.rename(columns={"ttm_cash_dividend": "v"})[["pit_date", "v"]]
    raise ValueError(fac)


def _per_daily(df, sid, fac):
    """（DevQueue 20261107-200102）f_value_pe／pb：照 factors.py (k)/(l) 逐字——TaiwanStockPER 逐日資料以 date 同日合併
    （不是 as-of），PBR／PER>0 才取負號、否則 NaN。本機快取全部檔案合併，同一天以起日最早的檔為準（舊檔優先，新檔只補 2025 起）。"""
    fs = sorted(RAW.glob(f"TaiwanStockPER__{sid}__*.parquet"))
    parts = [pd.read_parquet(f) for f in fs]
    parts = [x for x in parts if not x.empty and {"date", "PER", "PBR"} <= set(x.columns)]
    if not parts:
        return np.full(len(df), np.nan)
    per = pd.concat(parts, ignore_index=True)
    per["date"] = pd.to_datetime(per["date"])
    per = per.drop_duplicates("date", keep="first").set_index("date")
    col = "PBR" if fac == "f_value_pb" else "PER"
    x = pd.to_numeric(per[col], errors="coerce").reindex(pd.to_datetime(df["date"])).to_numpy(dtype=float)
    return np.where(x > 0, -x, np.nan)


def _chip_raw(ds, sid, key):
    """本機 {ds}__{sid}__*.parquet 全部合併；同一 key 以起日最早的檔為準（舊檔優先，2025-01-01 起新檔只補新日期）。"""
    fs = sorted(RAW.glob(f"{ds}__{sid}__*.parquet"), key=lambda f: (f.stem.split("__")[2:4], f.name))
    parts = [pd.read_parquet(f) for f in fs]
    parts = [x for x in parts if not x.empty and "date" in x.columns]
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    x["date"] = x["date"].astype(str).str[:10]
    return x.drop_duplicates(key, keep="first")


def _inst_wide(sid):
    """逐字照 factors._finmind_institutional_wide（FinMind 路徑；建 pkl 時主路徑是 T86 本機快取，
    所以 2024 底前由呼叫端沿用 pkl 原值，只取 2025 起）。"""
    cols = ["date", "foreign_net", "trust_net", "dealer_net", "total_net"]
    raw = _chip_raw("TaiwanStockInstitutionalInvestorsBuySell", sid, ["date", "name"])
    if raw.empty:
        return pd.DataFrame(columns=cols)
    raw = raw.copy()
    raw["net"] = raw["buy"] - raw["sell"]

    def _cat(name):
        if name == "Foreign_Investor":
            return "foreign_net"
        if name == "Investment_Trust":
            return "trust_net"
        if name in ("Dealer_self", "Dealer_Hedging"):
            return "dealer_net"
        return None

    raw["cat"] = raw["name"].map(_cat)
    raw = raw.dropna(subset=["cat"])
    if raw.empty:
        return pd.DataFrame(columns=cols)
    wide = raw.pivot_table(index="date", columns="cat", values="net", aggfunc="sum").reset_index()
    for c in ("foreign_net", "trust_net", "dealer_net"):
        if c not in wide.columns:
            wide[c] = 0.0
    wide["total_net"] = wide[["foreign_net", "trust_net", "dealer_net"]].sum(axis=1)
    return wide[cols]


def _chip_attach(df, sid, fac):
    if fac in ("f_inst_flow", "f_foreign_streak", "f_inst_streak_days"):  # 照 factors.prepare_factors 第 839～848 行
        d = pd.DataFrame({"date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d").to_numpy(),
                          "Trading_Volume": pd.to_numeric(df["Trading_Volume"], errors="coerce").to_numpy(),
                          "Trading_money": pd.to_numeric(df["Trading_money"], errors="coerce").to_numpy(),
                          "close": pd.to_numeric(df["close"], errors="coerce").to_numpy()})
        d = d.merge(_inst_wide(sid), on="date", how="left")
        for c in ("foreign_net", "trust_net", "dealer_net", "total_net"):
            d[c] = d[c].fillna(0.0)
        if fac == "f_foreign_streak":
            avg_vol20 = d["Trading_Volume"].rolling(F.FOREIGN_STREAK_VOL_WINDOW, min_periods=1).mean().to_numpy()
            return F._foreign_streak_strength(d["foreign_net"].to_numpy(), avg_vol20)
        if fac == "f_inst_streak_days":
            return F._consecutive_positive_streak_days(d["total_net"].to_numpy())
        W = F.INST_FLOW_WINDOW
        net_amount = d["total_net"] * d["close"]
        value20 = d["Trading_money"].rolling(W, min_periods=W).mean()
        return (net_amount.rolling(W, min_periods=W).sum() / (value20 * W)).to_numpy()
    # 融資使用率／券資比：照 factors._margin_utilization／_short_margin_ratio，當日即 pit，as-of 接
    raw = _chip_raw("TaiwanStockMarginPurchaseShortSale", sid, ["date"])
    if fac == "f_margin_utilization":
        num, den = "MarginPurchaseTodayBalance", "MarginPurchaseLimit"
    else:
        num, den = "ShortSaleTodayBalance", "MarginPurchaseTodayBalance"
    if raw.empty or not {num, den} <= set(raw.columns):
        return np.full(len(df), np.nan)
    m = raw[["date", num, den]].copy()
    m[num] = pd.to_numeric(m[num], errors="coerce")
    m[den] = pd.to_numeric(m[den], errors="coerce")
    m = m[m[den] > 0]
    if m.empty:
        return np.full(len(df), np.nan)
    p = pd.DataFrame({"_t": pd.to_datetime(m["date"]), "v": (m[num] / m[den]).to_numpy()}).dropna().sort_values("_t")
    left = pd.DataFrame({"_t": pd.to_datetime(df["date"]), "_i": np.arange(len(df))}).sort_values("_t")
    j = pd.merge_asof(left, p, on="_t", direction="backward")
    out = np.full(len(df), np.nan)
    out[j["_i"].to_numpy()] = j["v"].to_numpy()
    return out


_RAW_NAMES = None


def chip_coverage(sid):
    """2025 起新檔是否已在本機（法人、融資券各一）。raw 目錄檔案很多，只列一次目錄（每次 glob 太慢）。"""
    global _RAW_NAMES
    if _RAW_NAMES is None:
        import os
        _RAW_NAMES = set(os.listdir(RAW))
    out = {}
    for ds in ("TaiwanStockInstitutionalInvestorsBuySell", "TaiwanStockMarginPurchaseShortSale"):
        pre = f"{ds}__{sid}__"
        out[ds] = any(n.startswith(pre) and n.endswith(".parquet") and len(n[:-8].split("__")) == 4
                      and n[:-8].split("__")[2] <= "2025-01-01" and n[:-8].split("__")[3] >= "2026-09-24"
                      for n in _RAW_NAMES)
    return out


def attach(df, sid, fac):
    """照 factors._asof_join：先丟掉 NaN 季，每個交易日接 pit_date<=當日 的最新一季值。"""
    if fac in CHIP_FACS:
        return _chip_attach(df, sid, fac)
    if fac in ("f_value_pe", "f_value_pb"):
        return _per_daily(df, sid, fac)
    p = fin_pit(sid, fac).dropna()
    if p.empty:
        return np.full(len(df), np.nan)
    p = p.assign(_t=pd.to_datetime(p["pit_date"])).sort_values("_t")
    left = pd.DataFrame({"_t": pd.to_datetime(df["date"]), "_i": np.arange(len(df))}).sort_values("_t")
    j = pd.merge_asof(left, p[["_t", "v"]], on="_t", direction="backward")
    out = np.full(len(df), np.nan)
    out[j["_i"].to_numpy()] = j["v"].to_numpy()
    if fac == "f_dividend_yield_ttm":  # 分母＝當日原始收盤（2025 起列是 FinMind 原始 close；同 factors._raw_close_for_yield 原則）
        c = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
        out = np.where(c > 0, out / c, np.nan)
    return out
