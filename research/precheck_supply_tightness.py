"""先.二-三 不看報酬前置檢查（供應緊縮草案 §7）。

只數檔數、看相關、看覆蓋率；不計算任何策略報酬、不呼叫 register_trial()、不構成試驗。
唯一用到價格的地方是「價格落後百分位」——它只用來決定池子有幾檔（分類），
不輸出任何持有期報酬或績效數字。

離線：只讀 research/data/raw 的 parquet 快取，不打 FinMind。
PIT：季報用 pit.statutory_quarterly_pit_date（法定期限），月營收用次月10日。
輸出：research/precheck_supply_tightness_results.json ＋ 終端機摘要。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adjust  # noqa: E402
from pit import statutory_quarterly_pit_date  # noqa: E402

RAW = HERE / "data" / "raw"
OUT = HERE / "precheck_supply_tightness_results.json"
FIN_SUF = "__2010-01-01__2024-12-31.parquet"
FINANCIAL = ("金融保險", "金融保險業", "金融業")
NON_STOCK = re.compile(r"ETF|ETN|Index|大盤|受益|存託")
IND = ["I1", "I2", "I3", "I4", "I5"]
MIN_BUCKET = 8
MIN_IND = 3
TOP_FRAC = 0.20
LAG_PCT = 0.60


_IDX: dict[str, dict[str, list[Path]]] = {}


def _index(ds: str) -> dict[str, list[Path]]:
    """快取檔名的起迄日不一（2006/2010/2012/2024起；迄 2024-12-31／latest／2026-xx），一律全部讀入合併。"""
    if ds not in _IDX:
        d: dict[str, list[Path]] = {}
        for p in RAW.glob(f"{ds}__*.parquet"):
            parts = p.name[:-8].split("__")
            if len(parts) == 4 and parts[0] == ds:
                d.setdefault(parts[1], []).append(p)
        _IDX[ds] = d
    return _IDX[ds]


def _read(ds: str, code: str, suf: str = FIN_SUF):
    files = _index(ds).get(code)
    if not files:
        return None
    dfs = []
    for p in sorted(files):
        df = pd.read_parquet(p)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return None
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    return df.drop_duplicates() if len(dfs) > 1 else df


def _codes(ds: str) -> set[str]:
    return {c for c in _index(ds) if re.fullmatch(r"\d{4}", c)}


def _wide(df: pd.DataFrame, types: list[str]) -> pd.DataFrame:
    df = df[df["type"].isin(types)].copy()
    if df.empty:
        return pd.DataFrame(columns=types)
    w = df.pivot_table(index="date", columns="type", values="value", aggfunc="first")
    w.index = pd.PeriodIndex(pd.to_datetime(w.index), freq="Q")
    w = w[~w.index.duplicated(keep="last")].sort_index()
    return w.reindex(columns=types)


def _grid(w: pd.DataFrame) -> pd.DataFrame:
    if w.empty:
        return w
    return w.reindex(pd.period_range(w.index.min(), w.index.max(), freq="Q"))


def quarter_table(code: str) -> pd.DataFrame | None:
    fs = _read("TaiwanStockFinancialStatements", code)
    bs = _read("TaiwanStockBalanceSheet", code)
    if fs is None or bs is None or "type" not in fs.columns or "type" not in bs.columns:
        return None
    f = _grid(_wide(fs, ["Revenue", "GrossProfit", "CostOfGoodsSold"]))
    b = _grid(_wide(bs, ["TotalAssets", "OtherCurrentLiabilities", "CurrentContractLiabilities", "Inventories"]))
    if f.empty or b.empty:
        return None
    idx = f.index.union(b.index)
    f, b = f.reindex(idx), b.reindex(idx)
    q = pd.DataFrame(index=idx)
    ta = b["TotalAssets"]
    ocl = b["OtherCurrentLiabilities"]
    ccl = b["CurrentContractLiabilities"]
    prox = (ocl.fillna(0) + ccl.fillna(0)).where(ocl.notna() | ccl.notna())
    q["i1_lvl"] = prox / ta
    q["i1c_lvl"] = ccl / ta
    ttm = lambda s: s.rolling(4, min_periods=4).sum()  # noqa: E731
    cogs, rev, gp = ttm(f["CostOfGoodsSold"]), ttm(f["Revenue"]), ttm(f["GrossProfit"])
    avg_inv = b["Inventories"].rolling(5, min_periods=5).mean()
    q["i2_lvl"] = cogs / avg_inv
    q["i3_lvl"] = gp / rev
    cf = _read("TaiwanStockCashFlowsStatement", code)
    capex_ttm = pd.Series(np.nan, index=idx)
    if cf is not None and "type" in cf.columns:
        c = _grid(_wide(cf, ["PropertyAndPlantAndEquipment"])).reindex(idx)["PropertyAndPlantAndEquipment"]
        single = c.copy()
        qn = pd.Series(idx.quarter, index=idx)
        prev = c.shift(1)
        single = c.where(qn == 1, c - prev)
        capex_ttm = ttm(-single)
    q["i4_lvl"] = capex_ttm / rev.where(rev > 0)
    for k in ("i1", "i1c", "i2", "i3", "i4"):
        q[k.upper() if k != "i1c" else "I1c"] = q[f"{k}_lvl"] - q[f"{k}_lvl"].shift(4)
    q["fs_rev_q"] = f["Revenue"]
    q["cf_ppe_cum"] = (_wide(cf, ["PropertyAndPlantAndEquipment"]).reindex(idx)["PropertyAndPlantAndEquipment"]
                       if cf is not None and "type" in cf.columns else np.nan)
    return q


def month_table(code: str) -> pd.Series | None:
    m = _read("TaiwanStockMonthRevenue", code)
    if m is None or "revenue" not in m.columns:
        return None
    s = m.dropna(subset=["revenue_year", "revenue_month"]).copy()
    s["p"] = pd.PeriodIndex.from_fields(year=s["revenue_year"].astype(int), month=s["revenue_month"].astype(int), freq="M")
    s = s.drop_duplicates("p", keep="last").set_index("p")["revenue"].sort_index()
    return s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))


def i5_at(rev: pd.Series, d: pd.Timestamp) -> float:
    mp = pd.Period(d, "M") - (1 if d.day >= 10 else 2)  # 次月10日才可用
    def yoy3(p):
        cur = rev.reindex(pd.period_range(p - 2, p, freq="M"))
        prv = rev.reindex(pd.period_range(p - 14, p - 12, freq="M"))
        if cur.isna().any() or prv.isna().any() or prv.sum() <= 0:
            return np.nan
        return cur.sum() / prv.sum() - 1
    a, b = yoy3(mp), yoy3(mp - 3)
    return a - b if not (np.isnan(a) or np.isnan(b)) else np.nan


def adjusted_close(code: str, pm: pd.DataFrame) -> pd.Series | None:
    """FinMind 原始價 × 已驗證事件因子（離線重建；與 adjust._finmind_adjusted_frame 同邏輯，僅改讀快取）。"""
    raw = pm.sort_values("date")
    close = dict(zip(raw["date"], raw["close"]))
    dates = raw["date"].tolist()
    S = FIN_SUF
    div = _read("TaiwanStockDividend", code, S)
    spl = _read("TaiwanStockSplitPrice", code, S)
    cr = _read("TaiwanStockCapitalReductionReferencePrice", code, S)
    div = div if div is not None else pd.DataFrame()
    spl = spl if spl is not None else pd.DataFrame()
    cr = cr if cr is not None else pd.DataFrame()
    pv = PV[PV["stock_id"] == code] if PV is not None else pd.DataFrame()
    try:
        ev = adjust._combine_adjustment_events(div, spl, cr, pv, close, dates) if not (div.empty and spl.empty and cr.empty and pv.empty) else pd.DataFrame()
    except Exception:
        return None
    fac = pd.Series(1.0, index=raw["date"].values)
    if len(ev):
        d_arr = np.array(dates)
        for _, e in ev.sort_values("ex_date", ascending=False).iterrows():
            fac[d_arr < e["ex_date"]] = fac[d_arr < e["ex_date"]] * e["factor"]
    return pd.Series(raw["close"].astype(float).values * fac.values, index=pd.to_datetime(raw["date"].values))


PV = None


def main() -> int:
    global PV
    info = pd.read_parquet(RAW / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet").drop_duplicates("stock_id").set_index("stock_id")
    pvp = sorted(RAW.glob("TaiwanStockParValueChange__ALL__2003-01-01__2024-12-31.parquet")) or sorted(RAW.glob("TaiwanStockParValueChange__ALL__*2024-12-31.parquet"))
    PV = pd.read_parquet(pvp[0]) if pvp else None

    fs_codes = _codes("TaiwanStockFinancialStatements")
    universe = []
    not_in_info = []
    for c in sorted(fs_codes):
        if _read("TaiwanStockFinancialStatements", c) is None:
            continue
        if c not in info.index:
            not_in_info.append(c)
            continue
        typ, ind = info.at[c, "type"], str(info.at[c, "industry_category"])
        if typ == "emerging" or ind in FINANCIAL or NON_STOCK.search(ind):
            continue
        universe.append(c)
    print(f"宇宙（有損益表快取、非金融、非興櫃、非ETF）{len(universe)} 檔", flush=True)

    qt, mt, px = {}, {}, {}
    last_px = {}
    for i, c in enumerate(universe):
        t = quarter_table(c)
        if t is not None:
            qt[c] = t
        m = month_table(c)
        if m is not None:
            mt[c] = m
        pm = _read("TaiwanStockPrice", c)
        if pm is not None and "close" in pm.columns:
            pm = pm[pm["close"].astype(float) > 0]
            a = adjusted_close(c, pm) if len(pm) else None
            if a is not None:
                px[c] = (a, pd.Series(pm.sort_values("date")["close"].astype(float).values, index=pd.to_datetime(pm.sort_values("date")["date"].values)))
                last_px[c] = str(pm["date"].max())
        if (i + 1) % 300 == 0:
            print(f"  載入 {i + 1}/{len(universe)}", flush=True)

    # 是否單季（FS）／累計（CF）
    ratio = {"fs_q2_q1": [], "fs_q4_q13": [], "cf_q2_q1": [], "cf_q4_q3": []}
    ppe_sign = []
    for c, t in qt.items():
        for y in range(2016, 2024):
            try:
                rr = np.array([t.at[pd.Period(f"{y}Q{k}"), "fs_rev_q"] for k in (1, 2, 3, 4)], dtype=float)
                pp = np.array([t.at[pd.Period(f"{y}Q{k}"), "cf_ppe_cum"] for k in (1, 2, 3, 4)], dtype=float)
            except KeyError:
                continue
            if np.isfinite(rr).all() and (rr > 0).all():
                ratio["fs_q2_q1"].append(rr[1] / rr[0])
                ratio["fs_q4_q13"].append(rr[3] / rr[:3].mean())
            if np.isfinite(pp).all() and (np.abs(pp) > 0).all():
                ratio["cf_q2_q1"].append(pp[1] / pp[0])
                ratio["cf_q4_q3"].append(pp[3] / pp[2])
        v = t["cf_ppe_cum"].dropna()
        if len(v):
            ppe_sign.append(float((v < 0).mean()))
    unit = {k: (round(float(np.median(v)), 3) if v else None) for k, v in ratio.items()}
    unit["n_stock_years"] = len(ratio["fs_q2_q1"])
    unit["ppe_negative_share"] = round(float(np.mean(ppe_sign)), 3) if ppe_sign else None
    print("單季/累計檢查", unit, flush=True)

    # 換股日
    cal = pd.DatetimeIndex(sorted({d for a, _ in px.values() for d in a.index if d.year >= 2014}))
    rebals = []
    for y in range(2014, 2025):
        for qy, qn, dl in ((y - 1, 4, pd.Timestamp(y, 3, 31)), (y, 1, pd.Timestamp(y, 5, 15)),
                           (y, 2, pd.Timestamp(y, 8, 14)), (y, 3, pd.Timestamp(y, 11, 14))):
            nxt = cal[cal > dl]
            if len(nxt) and nxt[0] <= pd.Timestamp(2024, 12, 31):
                assert statutory_quarterly_pit_date(pd.Period(f"{qy}Q{qn}", "Q").end_time.normalize()) == dl, (qy, qn)
                rebals.append((nxt[0], pd.Period(f"{qy}Q{qn}")))
    print(f"換股日 {len(rebals)} 個：{rebals[0][0].date()} ～ {rebals[-1][0].date()}", flush=True)

    delist = pd.read_parquet(RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    delist = delist[delist["stock_id"].astype(str).str.fullmatch(r"\d{4}")]
    delist_set = set(delist["stock_id"].astype(str))
    delist_date = dict(zip(delist["stock_id"].astype(str), delist["date"].astype(str)))

    rows = []
    poolrows = []
    corr_sp = []
    corr_z = []
    for d, per in rebals:
        recs = []
        n_alive_no_qt = 0
        for c in universe:
            t = qt.get(c)
            a = px.get(c)
            alive = a is not None and len(a[0].loc[d - pd.Timedelta(days=45):d - pd.Timedelta(days=1)]) > 0
            if not alive:
                continue
            if t is not None and per in t.index:
                r = t.loc[per]
                rec = {"code": c, "I1": r["I1"], "I1c": r["I1c"], "I2": r["I2"], "I3": r["I3"], "I4": r["I4"]}
            else:
                n_alive_no_qt += 1
                rec = {"code": c, "I1": np.nan, "I1c": np.nan, "I2": np.nan, "I3": np.nan, "I4": np.nan}
            m = mt.get(c)
            rec["I5"] = i5_at(m, d) if m is not None else np.nan
            adj, rawc = a
            for tag, ser in (("adj", adj), ("raw", rawc)):
                s = ser.loc[:d - pd.Timedelta(days=1)]
                if len(s) < 130:
                    rec[f"r12_{tag}"] = rec[f"r60_{tag}"] = np.nan
                    continue
                last = s.index[-1]
                base = s.loc[:last - pd.DateOffset(months=12)]
                rec[f"r12_{tag}"] = s.iloc[-1] / base.iloc[-1] - 1 if len(base) else np.nan
                rec[f"r60_{tag}"] = s.iloc[-1] / s.iloc[-61] - 1 if len(s) > 61 else np.nan
            rec["ind"] = str(info.at[c, "industry_category"])
            rec["delisted"] = c in delist_set or last_px.get(c, "9999") < "2024-11-30"
            recs.append(rec)
        df = pd.DataFrame(recs)
        n_alive = len(df)
        df["n_ind"] = df[IND].notna().sum(axis=1)
        sc = df[df["n_ind"] >= MIN_IND].copy()
        cnt = sc["ind"].value_counts()
        small = set(cnt[cnt < MIN_BUCKET].index)
        sc["bucket"] = np.where(sc["ind"].isin(small) | (sc["ind"] == "其他"), "其他", sc["ind"])
        # 桶內 winsorize 1/99 → z
        zc = []
        for k in IND:
            def z(g, k=k):
                v = g[k]
                lo, hi = v.quantile(0.01), v.quantile(0.99)
                v = v.clip(lo, hi)
                sd = v.std()
                return (v - v.mean()) / sd if sd and sd > 0 else v * np.nan
            sc[f"z_{k}"] = sc.groupby("bucket", group_keys=False).apply(z)
            zc.append(f"z_{k}")
        sc["score"] = sc[zc].mean(axis=1)
        sc["score_pct"] = sc.groupby("bucket")["score"].rank(pct=True)
        for tag in ("adj", "raw"):
            for w in ("r12", "r60"):
                sc[f"lag_{w}_{tag}"] = sc.groupby("bucket")[f"{w}_{tag}"].rank(pct=True) <= LAG_PCT
        top = sc["score_pct"] > (1 - TOP_FRAC)
        row = {"date": str(d.date()), "period": str(per), "n_alive_nonfin": n_alive, "n_alive_no_quarter_table": n_alive_no_qt,
               "n_scorable": len(sc), "n_bucket": int(sc["bucket"].nunique()),
               "n_other_bucket": int((sc["bucket"] == "其他").sum()),
               "other_share": round(float((sc["bucket"] == "其他").mean()), 4),
               "n_top20": int(top.sum())}
        for k in IND + ["I1c"]:
            row[f"cov_{k}"] = int(df[k].notna().sum())
        for tag in ("adj", "raw"):
            for w in ("r12", "r60"):
                row[f"pool_{w}_{tag}"] = int((top & sc[f"lag_{w}_{tag}"]).sum())
        row["n_delisted_later_scorable"] = int(sc["delisted"].sum())
        bsz = sc.groupby("bucket").size().sort_values(ascending=False)
        row["bucket_sizes"] = {k: int(v) for k, v in bsz.items()}
        rows.append(row)
        # 相關（每日橫斷面）
        corr_sp.append(sc[IND].corr(method="spearman"))
        corr_z.append(sc[[f"z_{k}" for k in IND]].corr(method="spearman"))
        poolrows.append(None)

    res = pd.DataFrame(rows)
    def _avg(lst):
        arr = np.stack([m.values for m in lst])
        return pd.DataFrame(np.nanmean(arr, axis=0), index=lst[0].index, columns=lst[0].columns)
    avg_sp, avg_z = _avg(corr_sp), _avg(corr_z)
    flags = []
    for i, a in enumerate(IND):
        for b in IND[i + 1:]:
            for nm, m in (("raw_spearman", avg_sp), ("bucket_z_spearman", avg_z.rename(index=lambda x: x[2:], columns=lambda x: x[2:]))):
                v = float(m.loc[a, b])
                if abs(v) > 0.7:
                    flags.append({"pair": f"{a}-{b}", "kind": nm, "r": round(v, 3)})

    def feas(col):
        s = res[col]
        return {"median": float(s.median()), "min": int(s.min()), "max": int(s.max()),
                "p10": float(s.quantile(0.1)), "p90": float(s.quantile(0.9)),
                "dates_lt10": int((s < 10).sum()), "share_lt10": round(float((s < 10).mean()), 3),
                "feasible": bool(s.median() >= 20 and (s < 10).mean() <= 0.30)}
    pool_summary = {c: feas(c) for c in res.columns if c.startswith("pool_")}

    # 覆蓋率（依年）
    res["year"] = res["date"].str[:4]
    cov_year = res.groupby("year").apply(lambda g: {
        "n_alive": int(g["n_alive_nonfin"].mean()), "n_scorable": int(g["n_scorable"].mean()),
        **{k: round(float(g[f"cov_{k}"].sum() / g["n_alive_nonfin"].sum()), 3) for k in IND + ["I1c"]}}).to_dict()

    # 下市股核對
    fs_univ_delisted = [c for c in universe if c in delist_set or last_px.get(c, "9999") < "2024-11-30"]
    delist_in_range = {c for c, dd in delist_date.items() if "2013-01-01" <= dd <= "2024-12-31"}
    delist_ind_ok = {c for c in delist_in_range if c in info.index and str(info.at[c, "industry_category"]) not in FINANCIAL
                     and not NON_STOCK.search(str(info.at[c, "industry_category"])) and info.at[c, "type"] != "emerging"}
    delist_with_fs = delist_ind_ok & set(universe)
    delist_with_score = {c for c in delist_ind_ok if c in qt}
    no_bs = sorted(set(universe) - set(qt))
    no_px = sorted(set(universe) - set(px))
    roster = {
        "fs_cache_not_in_taiwanstockinfo": not_in_info,
        "universe_without_quarter_table": len(no_bs), "universe_without_price": len(no_px),
        "no_quarter_table_codes_head": no_bs[:60], "no_price_codes_head": no_px[:60],
        "fs_cache_universe": len(universe),
        "fs_cache_delisted_or_stopped": len(fs_univ_delisted),
        "fs_cache_delisted_share": round(len(fs_univ_delisted) / len(universe), 4),
        "delisting_file_stocks_2013_2024_nonfin_nonemerging": len(delist_ind_ok),
        "of_which_in_fs_cache": len(delist_with_fs),
        "delisted_missing_from_fs_cache": sorted(delist_ind_ok - set(universe))[:80],
        "delisted_missing_count": len(delist_ind_ok - set(universe)),
        "delisted_missing_dataset_availability": {
            ds: sum(1 for c in (delist_ind_ok - set(universe)) if _read(ds, c) is not None)
            for ds in ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement", "TaiwanStockMonthRevenue", "TaiwanStockPrice")},
        "delisted_in_universe_dataset_availability": {
            ds: sum(1 for c in delist_with_fs if _read(ds, c) is not None)
            for ds in ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement", "TaiwanStockMonthRevenue", "TaiwanStockPrice")},
        "no_quarter_table_reason": {
            "bs_empty_or_absent": sum(1 for c in no_bs if _read("TaiwanStockBalanceSheet", c) is None),
            "bs_present_but_fs_lacks_needed_types": sum(1 for c in no_bs if _read("TaiwanStockBalanceSheet", c) is not None)},
        "scorable_delisted_later_share_by_date": {r["date"]: round(r["n_delisted_later_scorable"] / max(r["n_scorable"], 1), 3) for _, r in res.iterrows()},
        "listed_universe_json_note": "data/listed_universe.json 只有 active 2142 檔、inactive 為空、last_seen 皆為近期，無法當時點名冊；改以 TaiwanStockInfo（含已下市）＋TaiwanStockDelisting＋價格快取末日交叉核對",
    }
    out = {
        "n_universe": len(universe), "n_quarter_tables": len(qt), "n_month_tables": len(mt), "n_price": len(px),
        "unit_check": unit, "n_rebalance_dates": len(res),
        "scorable": {"median": float(res["n_scorable"].median()), "min": int(res["n_scorable"].min()),
                     "dates_lt300": res.loc[res["n_scorable"] < 300, "date"].tolist()},
        "corr_raw_spearman_mean": avg_sp.round(3).to_dict(), "corr_bucket_z_spearman_mean": avg_z.round(3).to_dict(),
        "corr_flags_abs_gt_0.7": flags, "pool_summary": pool_summary, "coverage_by_year": cov_year,
        "bucket": {"n_bucket_median": float(res["n_bucket"].median()), "other_share_median": float(res["other_share"].median()),
                   "other_share_max": float(res["other_share"].max()),
                   "last_date_bucket_sizes": rows[-1]["bucket_sizes"], "first_date_bucket_sizes": rows[0]["bucket_sizes"]},
        "roster": roster,
        "per_date": res.drop(columns=["year", "bucket_sizes"]).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("per_date", "coverage_by_year", "roster")}, ensure_ascii=False, indent=1, default=float)[:6000])
    print("coverage_by_year", json.dumps(cov_year, ensure_ascii=False))
    print("roster", json.dumps({k: v for k, v in roster.items() if k != "scorable_delisted_later_share_by_date"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
