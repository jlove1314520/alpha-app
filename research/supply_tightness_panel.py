"""先.四-二：供給緊縮衛星策略單發執行——面板建置（離線，只讀 research/data/raw 快取）。

只做資料整理（價格矩陣、季報指標矩陣、月營收矩陣、0050），不計算任何績效數字。
重用 precheck_supply_tightness 的指標定義（同一份程式，未改動），並把讀檔截斷在 VAL_END=2024-12-31
（precheck 的 _read 會讀進 *__latest 檔，此處在載入層截斷並去重，holdout 2025+ 不進入面板）。
輸出：research/data/supply_tightness_panel.pkl
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import precheck_supply_tightness as pt  # noqa: E402

VAL_END = "2024-12-31"
OUT = HERE / "data" / "supply_tightness_panel.pkl"
TRUNC_DS = ("TaiwanStockPrice", "TaiwanStockFinancialStatements", "TaiwanStockBalanceSheet",
            "TaiwanStockCashFlowsStatement", "TaiwanStockMonthRevenue")
_orig_read = pt._read


def _read_trunc(ds, code, suf=pt.FIN_SUF):
    df = _orig_read(ds, code, suf)
    if df is None or ds not in TRUNC_DS or "date" not in df.columns:
        return df
    df = df[df["date"].astype(str) <= VAL_END]
    if ds == "TaiwanStockPrice":
        df = df.sort_values("date", kind="stable").drop_duplicates("date", keep="last")
    return df if len(df) else None


pt._read = _read_trunc


def _quarter_table_fs_tolerant(code: str):
    """與 precheck_supply_tightness.quarter_table 同定義；差別只在：截斷到 VAL_END 後資產負債表整檔為空時，
    仍以損益表／現金流量表計算 I3、I4（I1、I2 為 NaN），與 precheck 的可計分口徑一致（2026-09-30 dry 對照修正）。"""
    fs = pt._read("TaiwanStockFinancialStatements", code)
    if fs is None or "type" not in fs.columns:
        return None
    bs = _orig_read("TaiwanStockBalanceSheet", code)
    if bs is None or "type" not in bs.columns:
        return None
    bs = bs[bs["date"].astype(str) <= VAL_END]
    f = pt._grid(pt._wide(fs, ["Revenue", "GrossProfit", "CostOfGoodsSold"]))
    if f.empty:
        return None
    bcols = ["TotalAssets", "OtherCurrentLiabilities", "CurrentContractLiabilities", "Inventories"]
    b = pt._grid(pt._wide(bs, bcols)) if len(bs) else pd.DataFrame(columns=bcols)
    idx = f.index.union(b.index)
    f, b = f.reindex(idx), b.reindex(idx)
    if b.empty or not all(c in b.columns for c in bcols):
        b = pd.DataFrame(np.nan, index=idx, columns=bcols)
    q = pd.DataFrame(index=idx)
    ta, ocl, ccl = b["TotalAssets"], b["OtherCurrentLiabilities"], b["CurrentContractLiabilities"]
    prox = (ocl.fillna(0) + ccl.fillna(0)).where(ocl.notna() | ccl.notna())
    q["i1_lvl"] = prox / ta
    q["i1c_lvl"] = ccl / ta
    ttm = lambda s: s.rolling(4, min_periods=4).sum()  # noqa: E731
    cogs, rev, gp = ttm(f["CostOfGoodsSold"]), ttm(f["Revenue"]), ttm(f["GrossProfit"])
    avg_inv = b["Inventories"].rolling(5, min_periods=5).mean()
    q["i2_lvl"] = cogs / avg_inv
    q["i3_lvl"] = gp / rev
    cf = pt._read("TaiwanStockCashFlowsStatement", code)
    capex_ttm = pd.Series(np.nan, index=idx)
    if cf is not None and "type" in cf.columns:
        c = pt._grid(pt._wide(cf, ["PropertyAndPlantAndEquipment"])).reindex(idx)["PropertyAndPlantAndEquipment"]
        qn = pd.Series(idx.quarter, index=idx)
        single = c.where(qn == 1, c - c.shift(1))
        capex_ttm = ttm(-single)
    q["i4_lvl"] = capex_ttm / rev.where(rev > 0)
    for k in ("i1", "i1c", "i2", "i3", "i4"):
        q[k.upper() if k != "i1c" else "I1c"] = q[f"{k}_lvl"] - q[f"{k}_lvl"].shift(4)
    q["fs_rev_q"] = f["Revenue"]
    return q


pt.quarter_table = _quarter_table_fs_tolerant


def main() -> int:
    RAW = pt.RAW
    info = pd.read_parquet(RAW / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet").drop_duplicates("stock_id").set_index("stock_id")
    pvp = sorted(RAW.glob("TaiwanStockParValueChange__ALL__2003-01-01__2024-12-31.parquet")) or sorted(RAW.glob("TaiwanStockParValueChange__ALL__*2024-12-31.parquet"))
    pt.PV = pd.read_parquet(pvp[0]) if pvp else None

    universe = []
    for c in sorted(pt._codes("TaiwanStockFinancialStatements")):
        if pt._read("TaiwanStockFinancialStatements", c) is None or c not in info.index:
            continue
        typ, ind = info.at[c, "type"], str(info.at[c, "industry_category"])
        if typ == "emerging" or ind in pt.FINANCIAL or pt.NON_STOCK.search(ind):
            continue
        universe.append(c)
    print(f"宇宙 {len(universe)} 檔", flush=True)

    qt, mt, px = {}, {}, {}
    for i, c in enumerate(universe):
        t = pt.quarter_table(c)
        if t is not None:
            qt[c] = t
        m = pt.month_table(c)
        if m is not None:
            mt[c] = m
        pm = pt._read("TaiwanStockPrice", c)
        if pm is not None and "close" in pm.columns:
            pm = pm[pm["close"].astype(float) > 0].sort_values("date")
            a = pt.adjusted_close(c, pm) if len(pm) else None
            if a is not None:
                px[c] = (pm, a)
        if (i + 1) % 300 == 0:
            print(f"  載入 {i + 1}/{len(universe)}", flush=True)

    codes = [c for c in universe if c in px]
    N = len(codes)
    cal = pd.DatetimeIndex(sorted({d for c in codes for d in px[c][1].index if d >= pd.Timestamp("2012-06-01")}))
    T = len(cal)
    print(f"有價格 {N} 檔；日曆 {T} 日 {cal[0].date()}~{cal[-1].date()}", flush=True)
    AO = np.full((T, N), np.nan)
    ACF = np.full((T, N), np.nan)
    RC = np.full((T, N), np.nan)
    LU = np.zeros((T, N), bool)
    LD = np.zeros((T, N), bool)
    own_dates, own_adj = [], []
    for j, c in enumerate(codes):
        pm, a = px[c]
        dts = pd.DatetimeIndex(pd.to_datetime(pm["date"].values))
        adj = a.reindex(dts).values.astype(float)
        rawc = pm["close"].astype(float).values
        op = pm["open"].astype(float).values
        op = np.where(op > 0, op, np.nan)
        hi = pm["max"].astype(float).values if "max" in pm.columns else pm["high"].astype(float).values
        lo = pm["min"].astype(float).values if "min" in pm.columns else pm["low"].astype(float).values
        fac = adj / rawc
        prev = np.r_[np.nan, rawc[:-1]]
        flat = (op == hi) & (hi == lo) & (op > 0)
        lu = flat & (op >= prev * 1.095)
        ld = flat & (op <= prev * 0.905)
        own_dates.append(dts.values)
        own_adj.append(adj)
        pos = cal.get_indexer(dts)
        ok = pos >= 0
        AO[pos[ok], j] = (op * fac)[ok]
        ACF[pos[ok], j] = adj[ok]
        RC[pos[ok], j] = rawc[ok]
        LU[pos[ok], j] = lu[ok]
        LD[pos[ok], j] = ld[ok]
    ACFF = pd.DataFrame(ACF).ffill().values

    qper = pd.period_range("2010Q1", "2024Q4", freq="Q")
    QM = {k: np.full((len(qper), N), np.nan) for k in ("I1", "I1c", "I2", "I3", "I4")}
    for j, c in enumerate(codes):
        t = qt.get(c)
        if t is None:
            continue
        t = t[~t.index.duplicated(keep="last")]
        ix = qper.get_indexer(t.index)
        ok = ix >= 0
        for k in QM:
            QM[k][ix[ok], j] = t[k].values[ok]
    mper = pd.period_range("2009-01", "2024-12", freq="M")
    MM = np.full((len(mper), N), np.nan)
    for j, c in enumerate(codes):
        s = mt.get(c)
        if s is None:
            continue
        ix = mper.get_indexer(s.index)
        ok = ix >= 0
        MM[ix[ok], j] = s.values[ok]

    delist = pd.read_parquet(RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    delist_set = set(delist[delist["stock_id"].astype(str).str.fullmatch(r"\d{4}")]["stock_id"].astype(str))
    last_px = {c: str(px[c][0]["date"].max()) for c in codes}
    later_delisted = np.array([(c in delist_set) or last_px[c] < "2024-11-30" for c in codes])
    industry = np.array([str(info.at[c, "industry_category"]) for c in codes])

    from portfolio_backtest_v2 import _load_0050_total_return_series
    s50 = _load_0050_total_return_series()
    s50.index = pd.to_datetime(s50.index)
    s50 = s50[s50.index <= pd.Timestamp(VAL_END)]
    c50 = s50.reindex(cal).ffill().values
    print(f"0050 期間 {s50.index.min().date()}~{s50.index.max().date()}，日曆內 NaN={int(np.isnan(c50).sum())}", flush=True)

    panel = dict(codes=codes, industry=industry, cal=cal, AO=AO, ACF=ACF, ACFF=ACFF, RC=RC, LU=LU, LD=LD,
                 own_dates=own_dates, own_adj=own_adj, qper=qper, QM=QM, mper=mper, MM=MM,
                 later_delisted=later_delisted, c50=c50, s50=s50)
    with open(OUT, "wb") as f:
        pickle.dump(panel, f, protocol=4)
    print(f"已寫入 {OUT}（{OUT.stat().st_size / 1e6:.1f} MB）", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
