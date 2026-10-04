# -*- coding: utf-8 -*-
"""先.十一-二(1)：產業缺貨桶分數 vs #406 組合分數／I5／SUE 的相關係數（不讀任何報酬、不登記試驗）。

逐換股日（沿用 industry_shortage_precheck_results.json 的 125 個換股日與桶分數），個股層級 Spearman：
桶分數（同桶個股同分，僅 status=mapped 且活躍者）對
  (a) #406 組合分數（supply_tightness_core.score_frame，產業內標準化 z 平均，與 #406 同口徑）
  (b) I5（月營收加速）
  (c) eps_sue（factors._eps_surprise_sue，pit_date < 換股日的最新值）
  (d) revenue_sue（factors._revenue_surprise_sue，同上；補充）
停止條件：任一指標的逐日 Spearman 平均值 |r| > 0.7 → 停下回報（另報逐日最大 |r| 與合併 pooled）。
輸出：research/industry_shortage_corr406_results.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
from industry_shortage_mapping import BUCKETS  # noqa: E402
import supply_tightness_core as core  # noqa: E402
import factors  # noqa: E402

PANEL = ROOT / "research" / "data" / "supply_tightness_panel.pkl"
PRE = ROOT / "research" / "industry_shortage_precheck_results.json"
STOCK_MAP = ROOT / "docs" / "industry_shortage_stock_map.csv"
OUT = ROOT / "research" / "industry_shortage_corr406_results.json"
THRESH = 0.7


def sue_series(codes, fn, col):
    out = {}
    for i, c in enumerate(codes):
        try:
            d = fn(c, "2010-01-01")
            d = d.dropna(subset=["pit_date", col]).copy()
            d["pit_date"] = pd.to_datetime(d["pit_date"])
            d = d.sort_values("pit_date")
            d = d[np.isfinite(d[col])]
            if len(d):
                out[c] = (d["pit_date"].values, d[col].values)
        except Exception:
            pass
        if i % 300 == 0:
            print("sue", col, i, len(codes), flush=True)
    return out


def asof(ser, codes, day):
    d64 = np.datetime64(day)
    v = np.full(len(codes), np.nan)
    for j, c in enumerate(codes):
        s = ser.get(c)
        if s is None:
            continue
        k = int(np.searchsorted(s[0], d64, side="left")) - 1
        if k >= 0 and s[0][k] >= d64 - np.timedelta64(400, "D"):
            v[j] = s[1][k]
    return v


def main():
    P = core.Panel(PANEL)
    codes = [str(c) for c in P.codes]
    pre = json.loads(PRE.read_text(encoding="utf-8"))
    rows = [r for r in pre["rows"] if "score" in r]
    bnames = [b["id"] for b in BUCKETS]
    sm = pd.read_csv(STOCK_MAP, dtype=str)
    sm = sm[sm["status"] == "mapped"]
    c2b = {r.stock_id: r.bucket_id for r in sm.itertuples() if len(r.stock_id) == 4}
    sb = np.array([bnames.index(c2b[c]) if c in c2b else -1 for c in codes])
    eps = sue_series(codes, factors._eps_surprise_sue, "eps_sue")
    rev = sue_series(codes, factors._revenue_surprise_sue, "revenue_sue")
    print("eps_sue stocks", len(eps), "revenue_sue stocks", len(rev), flush=True)
    dayrow = {str(c.date()): i for i, c in enumerate(P.cal)}
    res = {k: [] for k in ("score406", "I5", "eps_sue", "revenue_sue")}
    pooled = {k: ([], []) for k in res}
    for r in rows:
        i = dayrow.get(r["rebalance_day"])
        if i is None:
            continue
        d = P.cal[i]
        S = P.snapshot(i)
        sc = np.array([r["score"][b] if b >= 0 and r["score"][b] is not None else np.nan for b in sb], float)
        F = core.score_frame(P, S)
        s406 = np.full(len(codes), np.nan)
        if len(F["idx"]):
            s406[F["idx"]] = F["score"]
        feats = {"score406": s406, "I5": S["I5"], "eps_sue": asof(eps, codes, d), "revenue_sue": asof(rev, codes, d)}
        base = S["alive"] & np.isfinite(sc)
        for k, v in feats.items():
            m = base & np.isfinite(v)
            if m.sum() >= 100:
                a = pd.Series(sc[m]).rank(pct=True)
                b = pd.Series(v[m]).rank(pct=True)
                res[k].append(float(a.corr(b)))
                pooled[k][0].extend(a.tolist())
                pooled[k][1].extend(b.tolist())
    summ = {}
    for k, v in res.items():
        pa = pd.Series(pooled[k][0]).corr(pd.Series(pooled[k][1])) if pooled[k][0] else None
        summ[k] = {"n_dates": len(v), "mean": round(float(np.mean(v)), 3) if v else None,
                   "median": round(float(np.median(v)), 3) if v else None,
                   "min": round(float(np.min(v)), 3) if v else None, "max": round(float(np.max(v)), 3) if v else None,
                   "max_abs_daily": round(float(np.max(np.abs(v))), 3) if v else None,
                   "pooled_rank_corr": round(float(pa), 3) if pa is not None else None}
    stop = [k for k, s in summ.items() if s["mean"] is not None and abs(s["mean"]) > THRESH]
    stop_any = [k for k, s in summ.items() if s["max_abs_daily"] is not None and s["max_abs_daily"] > THRESH]
    out = {"threshold": THRESH, "summary": summ, "stop_by_mean_abs_gt_0.7": stop, "any_daily_abs_gt_0.7": stop_any,
           "note": "個股層級逐日 Spearman；桶分數為 mapped 活躍股的所屬桶分數；不含任何報酬。"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
