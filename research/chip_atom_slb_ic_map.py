# -*- coding: utf-8 -*-
"""原子.六 出借總量(TWSE TWT72U)試驗——[自行裁量]獨立小腳本（原子.六腳本不易併入：其Tier/入口寫死89表達式assert）。
口徑同ATOM_CHIP_IC_MAP_SPEC.md第4~7節：lag1、snapshot不重疊、Spearman IC、TRAIN<=2020/VAL 2021-2024、
MIN_VALID=30、MIN_SNAP=8、危機窗沿用CRISIS_WINDOWS；不碰holdout；不發API（讀本機SLB快取）。
事前寫死的14個表達式（不得看IC後增減）：
  slb_bal: level, growth__{1,5,20,60}          (5)
  slb_chg(=borrow-return_): nf__{1,5,20,60} = ts_sum(chg,n)/ts_sum(v,n)   (4)
  slb_ratio=slb_bal/ts_mean(v,20): level, delta__{1,5,20,60}              (5)
x horizon{20,60} = 28測試；Bonferroni分母=178+28=206。"""
from __future__ import annotations
import glob, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mem_guard
mem_guard.install()
import chip_atom_library as cal
import ATOM_LIBRARY as al
from factor_ic import build_snapshots
from finmind_client import load_dev
from validation import holdout
from adjust import adjusted_price_series
from atom_ic_map import CRISIS_WINDOWS

HORIZONS = (20, 60); MIN_VALID = 30; MIN_SNAP = 8; SNAP_START = "2010-01-01"
W = (1, 5, 20, 60)

def load_slb() -> dict[str, pd.DataFrame]:
    fr = []
    for f in sorted(glob.glob(str(HERE / "data/raw_twse_slb/SLB_*.parquet"))):
        d = pd.read_parquet(f, columns=["date", "stock_id", "borrow", "return_", "bal"])
        fr.append(d)
    a = pd.concat(fr)
    a = a[a["stock_id"].str.fullmatch(r"\d{4}")]
    a["date"] = pd.to_datetime(a["date"])
    a["slb_bal"] = a["bal"].astype(float)
    a["slb_chg"] = a["borrow"].astype(float) - a["return_"].astype(float)
    a = a[a["date"] <= cal.VAL_END]
    return {k: g[["date", "slb_bal", "slb_chg"]].drop_duplicates("date") for k, g in a.groupby("stock_id")}

def exprs(d: pd.DataFrame) -> pd.DataFrame:
    o = {}
    o["level__slb_bal"] = d["slb_bal"]
    for n in W:
        o[f"growth__slb_bal__{n}"] = al.op_ratio(d["slb_bal"], al.op_delay(d["slb_bal"], n)) - 1.0
        o[f"nf__slb_chg__{n}"] = al.op_ratio(al.op_ts_sum(d["slb_chg"], n), al.op_ts_sum(d["v"], n))
    r = al.op_ratio(d["slb_bal"], al.op_ts_mean(d["v"], 20))
    o["level__slb_ratio"] = r
    for n in W:
        o[f"delta__slb_ratio__{n}"] = al.op_delta(r, n)
    return pd.DataFrame(o, index=d.index).astype(float)

def cross_ic(cross, ret):
    ic = cross.corrwith(ret, method="spearman")
    valid = cross.notna().mul(ret.notna(), axis=0).sum()
    return ic.where(valid >= MIN_VALID)

def main():
    assert not holdout.is_holdout_consumed()
    market = load_dev("TaiwanStockPrice", "TAIEX", SNAP_START)
    holdout.assert_no_holdout_leakage(market, context="TAIEX in chip_atom_slb_ic_map")
    calendar = sorted(pd.to_datetime(market["date"]).dt.strftime("%Y-%m-%d").unique())
    snaps = {h: build_snapshots(calendar, calendar[0], calendar[-1], horizon=h) for h in HORIZONS}
    need = sorted({pd.Timestamp(d) for h in HORIZONS for p in snaps[h] for d in p})
    slb = load_slb()
    ids = cal.universe_u()
    ids_l = [i for i in ids if i in slb]
    print(f"U={len(ids)} 有SLB(上市)={len(ids_l)}", flush=True)
    tab, pxt = {}, {}
    t0 = time.time()
    for i, sid in enumerate(ids_l, 1):
        try:
            p = adjusted_price_series(sid, SNAP_START)
            vcol = "volume" if "volume" in p.columns else "Trading_Volume"
            px = pd.DataFrame({"date": pd.to_datetime(p["date"]), "v": p[vcol].astype(float).values})
            ps = pd.Series(p["adj_close"].astype(float).values, index=pd.to_datetime(p["date"]))
            ps = ps[~ps.index.duplicated(keep="first")]
        except Exception as e:  # noqa: BLE001
            print(f"  [{sid}] 價格失敗 {str(e)[:80]}", flush=True); continue
        px = px[px["date"] <= cal.VAL_END].reset_index(drop=True)
        base = px.merge(slb[sid], on="date", how="left")
        lag = base[["v", "slb_bal", "slb_chg"]].shift(1)   # lag1（與chip_atom_library同口徑）
        out = exprs(lag); out.index = pd.DatetimeIndex(base["date"])
        out = out[~out.index.duplicated(keep="first")]
        tab[sid] = out.reindex(need); pxt[sid] = ps.reindex(need)
        if i % 50 == 0: print(f"  {i}/{len(ids_l)} {time.time()-t0:.0f}s", flush=True)
    names = list(next(iter(tab.values())).columns); assert len(names) == 14
    tr_end, va_end = pd.Timestamp(holdout.TRAIN_END), pd.Timestamp(holdout.VAL_END)
    res, allsnap = [], {}
    for h in HORIZONS:
        rows_ic = {}
        for as_of, fwd in snaps[h]:
            s0, s1 = pd.Timestamp(as_of), pd.Timestamp(fwd)
            rows, rets = {}, {}
            for sid, t in tab.items():
                p0, p1 = pxt[sid].get(s0, np.nan), pxt[sid].get(s1, np.nan)
                if pd.isna(p0) or pd.isna(p1) or p0 <= 0: continue
                rows[sid] = t.loc[s0]; rets[sid] = float(p1 / p0 - 1)
            if len(rows) < MIN_VALID: continue
            rows_ic[s0] = cross_ic(pd.DataFrame(rows).T.astype(float), pd.Series(rets))
        sd = pd.DataFrame(rows_ic).T.sort_index()
        sd.to_parquet(HERE / f"chip_atom_slb_ic_snapshots_h{h}.parquet"); allsnap[h] = sd
        for n in names:
            s = sd[n].dropna()
            tr, va = s[s.index <= tr_end], s[(s.index > tr_end) & (s.index <= va_end)]
            tm, vm = float(tr.mean()) if len(tr) else np.nan, float(va.mean()) if len(va) else np.nan
            ins = bool(len(tr) < MIN_SNAP or len(va) < MIN_SNAP)
            same = bool(not np.isnan(tm) and not np.isnan(vm) and tm != 0 and np.sign(tm) == np.sign(vm))
            # 逐年同號率（同號＝該年snapshot IC符號與TRAIN+VAL全期平均符號一致）
            allm = float(s.mean()); yr = s.groupby(s.index.year)
            ysame = float((np.sign(yr.mean()) == np.sign(allm)).mean()) if allm != 0 else np.nan
            # 危機窗：窗內至少1個有值snapshot才算K；全窗同號＝各窗平均IC符號皆等於全期符號
            wins = []
            for nm, a, b in CRISIS_WINDOWS:
                w = s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]
                if len(w): wins.append(float(w.mean()))
            K = len(wins)
            allwin = bool(K >= 3 and allm != 0 and all(np.sign(x) == np.sign(allm) for x in wins))
            res.append(dict(expression=n, horizon=h, train_mean_ic=tm, val_mean_ic=vm,
                            n_snap_train=len(tr), n_snap_val=len(va), insufficient=ins, same_sign=same,
                            year_same_rate=ysame, K=K, all_window_same_sign=allwin, val_abs_gt_002=bool(abs(vm) > 0.02) if not np.isnan(vm) else False,
                            high_screen=bool(same and allwin and ysame >= 0.7 and abs(vm) > 0.02 and not ins)))
    Path(HERE / "chip_atom_slb_ic_result.json").write_text(json.dumps(
        {"n_stocks_used": len(tab), "n_universe": len(ids), "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    df = pd.DataFrame(res)
    print(df.round(4).to_string(), flush=True)
    return 0
if __name__ == "__main__":
    sys.exit(main())
