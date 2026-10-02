"""先.十-五：產業缺貨方向 §5 執行前偽影檢查（登記前；不讀報酬、不計算任何績效）。

只用：MOEA A（製造業存貨率）／C（外銷訂單貨品別）快照 CSV、docs/industry_shortage_stock_map.csv、
supply_tightness_panel.pkl 的「是否存活」與季報／月營收欄位（僅供與 #406 欄位的相關係數；價格只用來判斷存活，不輸出）。
輸出：research/industry_shortage_precheck_results.json（統計）；docs/industry_shortage_precheck.md 由後續人工彙整引用。
訊號定義與草案一致：S_A=-(桶內A碼均值 YoY 差)；S_C=近3月合計 YoY 成長率；T+1月底後可用 → 換股月 R 可用資料月 T=R-2。
"""
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
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

PIT = ROOT / "data" / "moea_pit"
OUT = ROOT / "research" / "industry_shortage_precheck_results.json"
PANEL = ROOT / "research" / "data" / "supply_tightness_panel.pkl"
STOCK_MAP = ROOT / "docs" / "industry_shortage_stock_map.csv"
MIN_BUCKET = 8
GATE_BUCKETS = 10
FIRST, LAST = pd.Period("2014-04", "M"), pd.Period("2024-12", "M")


def roc_to_period(s):
    s = str(s).strip()
    return pd.Period(f"{int(s[:-2]) + 1911}-{s[-2:]}", "M")


def load_a():
    f = sorted(glob.glob(str(PIT / "A" / "製造業存貨率" / "*.csv")))[-1]
    d = defaultdict(dict)
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        try:
            d[r["行業代碼"]][roc_to_period(r["資料期(民國年)"])] = float(r["統計值(比率)"])
        except ValueError:
            pass
    return d, Path(f).name


def load_c(name):
    f = sorted(glob.glob(str(PIT / "C" / f"外銷訂單_{name}" / "*.csv")))[-1]
    d = {}
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        if r["統計項目"] != "外銷訂單金額_美元":
            continue
        try:
            d[roc_to_period(r["資料期(民國年)"])] = float(r["統計值(金額)"])
        except ValueError:
            pass
    return d, Path(f).name


def sa_value(A, codes, T):
    xs0, xs1 = [], []
    for c in codes:
        s = A.get(c, {})
        if T not in s or (T - 12) not in s:
            return np.nan
        xs0.append(s[T])
        xs1.append(s[T - 12])
    return -(np.mean(xs0) - np.mean(xs1))


def sc_value(C, T):
    cur = [C.get(T - k) for k in range(3)]
    prv = [C.get(T - 12 - k) for k in range(3)]
    if any(v is None for v in cur + prv):
        return np.nan
    p = sum(prv)
    return sum(cur) / p - 1 if p > 0 else np.nan


def zscore(v):
    v = np.asarray(v, float)
    fin = np.isfinite(v)
    out = np.full(len(v), np.nan)
    if fin.sum() < 2:
        return out
    lo, hi = np.quantile(v[fin], [0.01, 0.99])
    w = np.clip(v, lo, hi)
    sd = np.nanstd(w[fin], ddof=1)
    if sd > 0:
        out[fin] = (w[fin] - np.nanmean(w[fin])) / sd
    return out


def series_diagnostics(A, Cs):
    res = {"A": {}, "C": {}}
    rng = pd.period_range("2012-01", "2024-12", freq="M")
    for code, s in sorted(A.items()):
        miss = [str(p) for p in rng if p not in s]
        res["A"][code] = {"first": str(min(s)), "last": str(max(s)), "missing_2012_2024": miss[:12], "n_missing": len(miss),
                          "nonpositive": int(sum(v <= 0 for v in s.values()))}
    for name, s in Cs.items():
        miss = [str(p) for p in rng if p not in s]
        res["C"][name] = {"first": str(min(s)), "last": str(max(s)), "missing_2012_2024": miss[:12], "n_missing": len(miss),
                          "nonpositive": int(sum(v <= 0 for v in s.values()))}
    return res


def jump_check(A, Cs):
    """行業標準分類修訂（第10次 2016-01、第11次 2021-01）與 2023-03 附近的單月變動，相對該序列自身單月變動的標準差倍數。"""
    out = {}
    for tag, month in (("rev10_2016-01", "2016-01"), ("rev11_2021-01", "2021-01"), ("2023-03", "2023-03")):
        p = pd.Period(month, "M")
        zs = []
        for code, s in A.items():
            if code in ("C", "I1", "I2", "I3", "I4"):
                continue
            ps = sorted(s)
            d = np.array([s[q] - s[q - 1] for q in ps if (q - 1) in s and pd.Period("2012-01", "M") <= q <= pd.Period("2024-12", "M")])
            if p in s and (p - 1) in s and len(d) > 20 and d.std() > 0:
                zs.append(abs((s[p] - s[p - 1]) - d.mean()) / d.std())
        out[tag] = {"A_n": len(zs), "A_mean_abs_z": round(float(np.mean(zs)), 2) if zs else None,
                    "A_max_abs_z": round(float(np.max(zs)), 2) if zs else None}
    return out


def main():
    A, a_file = load_a()
    c_names = sorted({c for b in BUCKETS for c in b["c"]})
    Cs, c_files = {}, {}
    for n in c_names:
        Cs[n], c_files[n] = load_c(n)

    sm = pd.read_csv(STOCK_MAP, dtype=str)
    sm = sm[sm["status"] == "mapped"]
    code2bucket = {r.stock_id: r.bucket_id for r in sm.itertuples() if len(r.stock_id) == 4}
    n_total_current = Counter(code2bucket.values())

    import pickle
    sys.path.insert(0, str(ROOT / "research"))
    with open(PANEL, "rb") as f:
        P = pickle.load(f)
    codes = list(P["codes"])
    own_dates = P["own_dates"]
    cal = P["cal"]
    bnames = [b["id"] for b in BUCKETS]
    bpos = {b: i for i, b in enumerate(bnames)}
    sb = np.array([bpos.get(code2bucket.get(c), -1) for c in codes])
    print("panel codes", len(codes), "mapped-to-bucket", int((sb >= 0).sum()), flush=True)

    rows = []
    months = pd.period_range(FIRST, LAST, freq="M")
    for R in months:
        ds = cal[(cal.year == R.year) & (cal.month == R.month) & (cal.day >= 26)]
        if len(ds) == 0:
            rows.append({"R": str(R), "no_rebalance_day": True})
            continue
        d = ds[0]
        d64 = np.datetime64(d)
        lim = np.datetime64(d - pd.Timedelta(days=45))
        alive = np.zeros(len(codes), bool)
        for j in range(len(codes)):
            od = own_dates[j]
            k = int(np.searchsorted(od, d64, side="left"))
            if k and od[k - 1] >= lim:
                alive[j] = True
        cnt = np.array([int(((sb == i) & alive).sum()) for i in range(len(bnames))])
        T = R - 2
        sa = np.array([sa_value(A, [c for c, _ in b["a"]], T) for b in BUCKETS])
        sc = np.array([sc_value(Cs[b["c"][0]], T) if b["c"] else np.nan for b in BUCKETS])
        za, zc = zscore(sa), zscore(sc)
        with np.errstate(all="ignore"):
            stack = np.vstack([za, zc])
            n_av = np.isfinite(stack).sum(0)
            score = np.where(n_av > 0, np.nansum(stack, 0) / np.maximum(n_av, 1), np.nan)
        elig = (cnt >= MIN_BUCKET) & np.isfinite(score)
        sc_elig = np.where(elig, score, np.nan)
        order = [i for i in np.argsort(-np.nan_to_num(sc_elig, nan=-1e9)) if elig[i]][:3]
        rows.append({"R": str(R), "rebalance_day": str(d.date()), "T": str(T), "n_sa": int(np.isfinite(sa).sum()),
                     "n_sc": int(np.isfinite(sc).sum()), "n_scored_buckets": int(elig.sum()),
                     "buckets_below_min_stocks": [bnames[i] for i in range(len(bnames)) if cnt[i] < MIN_BUCKET],
                     "n_alive_scorable_stocks": int(cnt[elig].sum()), "top3": [bnames[i] for i in order],
                     "top3_stocks": int(sum(cnt[i] for i in order)), "cnt": cnt.tolist(),
                     "score": [None if not np.isfinite(x) else round(float(x), 3) for x in score]})

    ok = [r for r in rows if "n_scored_buckets" in r]
    nsb = np.array([r["n_scored_buckets"] for r in ok])
    summary = {
        "n_rebalance_dates": len(ok), "no_rebalance_day": sum(1 for r in rows if r.get("no_rebalance_day")),
        "gate_buckets_ge10": GATE_BUCKETS,
        "dates_failing_gate": [r["R"] for r in ok if r["n_scored_buckets"] < GATE_BUCKETS],
        "n_dates_failing_gate": int((nsb < GATE_BUCKETS).sum()),
        "scored_buckets_min_med_max": [int(nsb.min()), float(np.median(nsb)), int(nsb.max())],
        "dates_top3_stocks_lt20": [r["R"] for r in ok if r["top3_stocks"] < 20],
        "alive_scorable_stocks_min_med_max": [min(r["n_alive_scorable_stocks"] for r in ok),
                                              float(np.median([r["n_alive_scorable_stocks"] for r in ok])),
                                              max(r["n_alive_scorable_stocks"] for r in ok)],
        "dates_alive_scorable_lt300": [r["R"] for r in ok if r["n_alive_scorable_stocks"] < 300],
        "top3_selection_freq": Counter(b for r in ok for b in r["top3"]),
        "top3_stocks_min_med_max": [min(r["top3_stocks"] for r in ok), float(np.median([r["top3_stocks"] for r in ok])),
                                    max(r["top3_stocks"] for r in ok)],
        "bucket_below_min_dates": {b: sum(1 for r in ok if b in r["buckets_below_min_stocks"]) for b in bnames},
        "mean_alive_stocks_per_bucket": {b: round(float(np.mean([r["cnt"][i] for r in ok])), 1) for i, b in enumerate(bnames)},
        "current_mapped_4digit_per_bucket": dict(sorted(n_total_current.items())),
    }

    # 與 #406 欄位的相關（不含報酬）：逐換股日，個股層級 Spearman（桶分數 vs I5／I2 原始值）
    corr = {"I5": [], "I2": [], "I4": []}
    try:
        sys.path.insert(0, str(ROOT / "research"))
        import supply_tightness_core as core
        PP = core.Panel(PANEL)
        dayrow = {str(c.date()): i for i, c in enumerate(PP.cal)}
        for r in ok:
            i = dayrow.get(r["rebalance_day"])
            if i is None:
                continue
            S = PP.snapshot(i)
            sc_bucket = np.array([r["score"][b] if b >= 0 and r["score"][b] is not None else np.nan for b in sb])
            alive_m = S["alive"] & np.isfinite(sc_bucket)
            for k in corr:
                v = S[k]
                m = alive_m & np.isfinite(v)
                if m.sum() >= 100:
                    corr[k].append(float(pd.Series(sc_bucket[m]).corr(pd.Series(v[m]), method="spearman")))
        summary["corr_with_406_cols_stock_level_spearman"] = {
            k: {"n_dates": len(v), "mean": round(float(np.mean(v)), 3) if v else None,
                "median": round(float(np.median(v)), 3) if v else None,
                "min": round(float(np.min(v)), 3) if v else None, "max": round(float(np.max(v)), 3) if v else None}
            for k, v in corr.items()}
    except Exception as e:
        summary["corr_with_406_cols_stock_level_spearman"] = f"未能計算：{type(e).__name__}: {e}"
    summary["corr_note"] = ("個股層級：桶分數（同桶個股同分）對 #406 的 I5（月營收加速）、I2（存貨周轉）、I4（資本支出）原始值的逐日 Spearman。"
                           "#406 組合分數與 SUE 因其為產業內標準化／未在面板內，另待財報預熱完成後補做（見草案 §5）。")

    diag = series_diagnostics(A, Cs)
    summary["series_diag_A_n_with_missing"] = sum(1 for v in diag["A"].values() if v["n_missing"])
    summary["series_diag_C_n_with_missing"] = sum(1 for v in diag["C"].values() if v["n_missing"])
    summary["jump_check"] = jump_check(A, Cs)
    summary["files"] = {"A": a_file, "C": c_files}

    OUT.write_text(json.dumps({"summary": summary, "diag": diag, "rows": rows}, ensure_ascii=False, indent=1, default=int),
                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=int))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
