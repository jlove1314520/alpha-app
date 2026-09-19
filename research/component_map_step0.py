"""零件.二 step 0：因子池覆蓋率／同家族相關／宇宙可得性／TRAIN IC權重（規格第1.1、2、6節）。
只看資料可得性與 TRAIN 期 IC 權重，不跑任何回測、不看績效。VAL 完全不碰。"""
from __future__ import annotations
import json, sys, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
from adjust import adjusted_price_series
from factor_ic import START_DATE, SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from factors import prepare_score_factors
from validation import holdout

OUT = Path(__file__).parent / "data"
POOL = ["eps_family", "revenue_surprise", "low_vol", "rev_accel", "quality_roe_stability", "rel_strength", "ma_breakout"]
COLS = {"revenue_surprise": "f_revenue_surprise", "low_vol": "f_low_vol", "rev_accel": "f_rev_accel",
        "quality_roe_stability": "f_quality_roe_stability", "rel_strength": "f_rel_strength", "ma_breakout": "f_ma_breakout"}
TRAIN_END = holdout.TRAIN_END

def comp_frame(d):
    out = pd.DataFrame({"date": d["date"]})
    e = d[["f_eps_growth", "f_eps_surprise"]].mean(axis=1, skipna=True)
    out["eps_family"] = e
    for k, c in COLS.items():
        out[k] = d[c] if c in d.columns else np.nan
    return out

def main():
    ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print("sample ids", len(ids))
    data, price = {}, {}
    for i, sid in enumerate(ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
            if px.empty or len(px) < 260: continue
            d = prepare_score_factors(sid, px, START_DATE)
        except Exception as e:  # noqa: BLE001
            print("drop", sid, str(e)[:60]); continue
        d = d[d["date"] <= TRAIN_END].reset_index(drop=True)
        holdout.assert_no_holdout_leakage(d, date_col="date", context="component_map_step0")
        data[sid] = d
    print("loaded", len(data))
    if data:
        print("cols", list(next(iter(data.values())).columns)[:60])
    # 快照：每 21 個交易日一次
    all_dates = sorted(set().union(*[set(d["date"]) for d in data.values()]))
    snaps = all_dates[::21]
    frames = {}
    for sid, d in data.items():
        f = comp_frame(d).set_index("date")
        frames[sid] = f
    # 橫斷面
    cs_by_snap = {}
    for s in snaps:
        rows = {sid: f.loc[s] for sid, f in frames.items() if s in f.index}
        if rows:
            cs_by_snap[s] = pd.DataFrame(rows).T.astype(float)
    # 1) 覆蓋率
    cov = {c: float(np.median([cs[c].notna().mean() for cs in cs_by_snap.values()])) for c in POOL}
    pool = [c for c in POOL if cov[c] >= 0.60]
    dropped_cov = [c for c in POOL if c not in pool]
    # 2) 同家族
    corr = {}
    for a, b in itertools.combinations(pool, 2):
        rs = []
        for cs in cs_by_snap.values():
            x = cs[[a, b]].dropna()
            if len(x) >= 20:
                rs.append(x[a].rank().corr(x[b].rank()))
        corr[f"{a}|{b}"] = float(np.nanmean(rs)) if rs else None
    dropped_fam = []
    for k, r in corr.items():
        a, b = k.split("|")
        if r is not None and abs(r) > 0.7 and a in pool and b in pool:
            keep = sorted([a, b], key=lambda c: (-cov[c], c))[0]
            drop = b if keep == a else a
            pool.remove(drop); dropped_fam.append({"drop": drop, "keep": keep, "r": r})
    # 3) 宇宙可得性
    n_ok = 0
    for sid, f in frames.items():
        sub = f[pool]
        nn = sub.notna().sum(axis=1)
        distinct_with_val = (sub.notna().sum(axis=0) > 0).sum()
        if distinct_with_val >= 3 and (nn >= 2).any():
            n_ok += 1
    universe_rule = "use_159" if n_ok >= 120 else "fallback_safe_pool"
    # 4) TRAIN IC 權重 (21日前瞻，不重疊快照，Spearman)
    close = {sid: d.set_index("date")["close"] if "close" in d.columns else None for sid, d in data.items()}
    ic = {c: [] for c in pool}
    sl = list(cs_by_snap.keys())
    for s0, s1 in zip(sl[:-1], sl[1:]):
        cs = cs_by_snap[s0]
        fwd = {}
        for sid in cs.index:
            cl = close.get(sid)
            if cl is not None and s0 in cl.index and s1 in cl.index and cl[s0] > 0:
                fwd[sid] = cl[s1] / cl[s0] - 1
        fw = pd.Series(fwd)
        for c in pool:
            x = pd.concat([cs[c], fw], axis=1).dropna()
            if len(x) >= 20:
                ic[c].append(x.iloc[:, 0].rank().corr(x.iloc[:, 1].rank()))
    w = {c: float(abs(np.nanmean(v))) if v else None for c, v in ic.items()}
    res = {"n_loaded": len(data), "n_snapshots": len(cs_by_snap), "coverage_median": cov,
           "dropped_coverage": dropped_cov, "rank_corr": corr, "dropped_family": dropped_fam,
           "pool_final": pool, "n_universe_ok_159": n_ok, "universe_rule": universe_rule,
           "ic_n_snapshots": {c: len(v) for c, v in ic.items()}, "ic_weights_train_abs": w}
    (OUT / "component_map_step0.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "component_map_ic_weights_train.json").write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
