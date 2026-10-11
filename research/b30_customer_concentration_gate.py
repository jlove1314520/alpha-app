"""B30 客戶集中度（美股，SEC Notes Data Sets）：GATE_SEQUENCE 逐關判定。

規格（事前登記，執行前已 commit cf1ede586）：research/B30_CUSTOMER_CONCENTRATION_SPEC.md。
本檔只實作規格，不在這裡重新決定任何參數；改參數＝新試驗。

輸入：research/data/b30_concentration/*.csv（b30_sec_concentration_extract.py 產出）
      research/data/dera_insider/prices/px_*.csv（既有 yfinance 快取，零新增價格請求）
輸出：research/b30_customer_concentration_gate_result.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import sec_edgar_client as sec  # noqa: E402
from control_group_standard import evaluate_vs_control  # noqa: E402
from validation import holdout  # noqa: E402
from validation.us_costs import round_trip_cost_pct  # noqa: E402
from yf_price_client import fetch_yf_index  # noqa: E402

CONC_DIR = HERE / "data" / "b30_concentration"
PRICE_DIR = HERE / "data" / "dera_insider" / "prices"
PRICE_STATUS = HERE / "insider_dera_price_fetch_status.json"
OUT = HERE / "b30_customer_concentration_gate_result.json"

H = 60
H_GRID = [40, 50, 60, 75, 90]
TOP_PCTL = 67
N_DRAWS = 200
SEEDS = {"same_year": 20261011_301, "same_year_sic2": 20261011_302}
POSITION_USD = 10_000.0
ALLOWED_KEYS = {"ConcentrationRiskByBenchmark", "ConcentrationRiskByType", "MajorCustomers"}
GROUP_RE = re.compile(r"customers|top|next|total|aggregate|combined|other", re.I)


def qualifies(r: dict) -> float | None:
    """規格第 2 節 1～6 條；符合回傳占比，不符合回傳 None。"""
    if r["tag"] not in ("ConcentrationRiskPercentage1", "ConcentrationRiskPercentage"):
        return None
    if r["form"] != "10-K" or r["qtrs"] != "4" or r["ddate"] != r["period"]:
        return None
    kv = dict(x.split("=", 1) for x in r["segments"].split(";") if "=" in x)
    if not set(kv) <= ALLOWED_KEYS or "MajorCustomers" not in kv or "ConcentrationRiskByBenchmark" not in kv:
        return None
    if kv.get("ConcentrationRiskByType", "CustomerConcentrationRisk") != "CustomerConcentrationRisk":
        return None
    b = kv["ConcentrationRiskByBenchmark"]
    if not (b.startswith("Sales") or b.startswith("Revenue")) or re.search(r"Receivable|Purchase|Cost", b):
        return None
    if GROUP_RE.search(kv["MajorCustomers"]):
        return None
    try:
        v = float(r["value"])
    except ValueError:
        return None
    return v if 0 < v <= 1 else None


def load_filings() -> list[dict]:
    best: dict[str, dict] = {}
    for p in sorted(CONC_DIR.glob("*.csv")):
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                v = qualifies(r)
                if v is None:
                    continue
                cur = best.get(r["adsh"])
                if cur is None or v > cur["s"]:
                    best[r["adsh"]] = {"adsh": r["adsh"], "cik": int(r["cik"]), "name": r["name"],
                                       "sic2": (r["sic"] or "")[:2], "filed": r["filed"], "s": v}
    return list(best.values())


def load_px(ticker: str) -> pd.DataFrame | None:
    p = PRICE_DIR / f"px_{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p).rename(columns={"Date": "date"})
    d["date"] = d["date"].astype(str).str[:10]
    d = d[d["date"] <= holdout.VAL_END].dropna(subset=["adj_close"])
    d = d[d["adj_close"] > 0].reset_index(drop=True)
    return d if len(d) >= 60 else None


def main() -> int:
    filings = load_filings()
    print(f"符合規格第 2 節的 10-K：{len(filings)} 份，{len({f['cik'] for f in filings})} 家")
    st = json.loads(PRICE_STATUS.read_text(encoding="utf-8"))["tickers"]
    ok = {t for t, v in st.items() if v.get("status") == "ok"}
    cik2t: dict[int, str] = {}
    for t, c in sorted(sec.get_cik_map().items()):
        if t in ok and c not in cik2t:
            cik2t[c] = t
    spy = fetch_yf_index("SPY", start_date="2005-01-01")
    spy_close = dict(zip(spy["date"], spy["close"].astype(float)))
    hmax = max(H_GRID)

    px_cache: dict[str, tuple] = {}
    events = []
    skips = defaultdict(int)
    by_cik = defaultdict(list)
    for f in filings:
        by_cik[f["cik"]].append(f)
    for cik, fs in by_cik.items():
        t = cik2t.get(cik)
        if t is None:
            skips["no_ticker"] += len(fs)
            continue
        px = load_px(t)
        if px is None:
            skips["no_price"] += len(fs)
            continue
        cal = px["date"].tolist()
        closes = px["adj_close"].to_numpy(float)
        spy_al = np.array([spy_close.get(d, np.nan) for d in cal])
        px_cache[t] = (closes, spy_al)
        last = -10**9
        for f in sorted(fs, key=lambda x: x["filed"]):
            fd = f"{f['filed'][:4]}-{f['filed'][4:6]}-{f['filed'][6:8]}"
            i = int(np.searchsorted(np.array(cal), fd, side="right"))  # 申報日之後第一個交易日
            if i <= 0 or i >= len(cal) or i + hmax >= len(cal):
                skips["oob"] += 1
                continue
            if i - last <= H:
                skips["dup_in_window"] += 1
                continue
            if np.isnan(spy_al[i]) or np.isnan(spy_al[i + hmax]):
                skips["spy_missing"] += 1
                continue
            last = i
            row = {**f, "ticker": t, "date": cal[i], "idx": i, "year": cal[i][:4], "price": float(closes[i])}
            for h in H_GRID:
                row[f"x{h}"] = (closes[i + h] / closes[i] - 1.0) - (spy_al[i + h] / spy_al[i] - 1.0)
            events.append(row)
    holdout.assert_no_holdout_leakage(pd.DataFrame(events), date_col="date", context="b30_customer_concentration_gate")
    print(f"可用事件 {len(events)}；略過 {dict(skips)}")

    # 前一年第 67 百分位切點（PIT）
    by_year = defaultdict(list)
    for e in events:
        by_year[e["year"]].append(e)
    years = sorted(by_year)
    cut = {y: float(np.percentile([e["s"] for e in by_year[str(int(y) - 1)]], TOP_PCTL))
           for y in years if str(int(y) - 1) in by_year}
    for e in events:
        e["period"] = "TRAIN" if e["date"] <= holdout.TRAIN_END else "VAL"
        e["top"] = e["year"] in cut and e["s"] >= cut[e["year"]]
        e["in_test"] = e["year"] in cut
    pool = [e for e in events if e["in_test"]]
    top = {p: [e for e in pool if e["top"] and e["period"] == p] for p in ("TRAIN", "VAL")}
    allp = {p: [e for e in pool if e["period"] == p] for p in ("TRAIN", "VAL")}
    print({p: (len(top[p]), len(allp[p])) for p in top}, "暖身年（不進檢定）：", [y for y in years if y not in cut])

    def draws(sig_evs, all_evs, h, variant, seed):
        rng = np.random.default_rng(seed)
        y_idx = defaultdict(list)
        ys_idx = defaultdict(list)
        for e in all_evs:
            y_idx[e["year"]].append(e[f"x{h}"])
            ys_idx[(e["year"], e["sic2"])].append(e[f"x{h}"])
        out = []
        for _ in range(N_DRAWS):
            vals = []
            for e in sig_evs:
                cell = ys_idx[(e["year"], e["sic2"])] if variant == "same_year_sic2" else []
                src = cell if len(cell) >= 5 else y_idx[e["year"]]
                vals.append(src[rng.integers(len(src))])
            out.append(float(np.mean(vals)))
        return out

    def gate(p, h, label):
        sig = float(np.mean([e[f"x{h}"] for e in top[p]]))
        d = {k: draws(top[p], allp[p], h, k, s) for k, s in SEEDS.items()}
        flat = [x for v in d.values() for x in v]
        v = evaluate_vs_control(signal_stat=sig, control_draws=d, selection_spec=(
            f"事前綁定 B30_CUSTOMER_CONCENTRATION_SPEC.md（commit cf1ede586）：10-K 單一客戶營收占比最大值 "
            f">= 前一年第{TOP_PCTL}百分位，申報日次一交易日收盤進場持有 {h} 日相對 SPY 超額平均，{label}；"
            "控制組＝同年度／同年度同SIC兩碼揭露者隨機抽"))
        return sig, v, float(np.percentile(flat, 95))

    res = {"spec": "research/B30_CUSTOMER_CONCENTRATION_SPEC.md", "spec_commit": "cf1ede586",
           "n_filings_qualified": len(filings), "n_events": len(events), "skips": dict(skips),
           "cutoffs_by_year": cut, "n_top": {p: len(v) for p, v in top.items()},
           "n_pool": {p: len(v) for p, v in allp.items()}, "gates": {}}
    G = res["gates"]
    nan_n = sum(1 for p in top for e in top[p] if not np.isfinite(e[f"x{H}"]))
    G["1_sanity"] = {"pass": len(top["TRAIN"]) >= 100 and len(top["VAL"]) >= 100 and nan_n == 0,
                     "n_top_train": len(top["TRAIN"]), "n_top_val": len(top["VAL"]), "nan": nan_n,
                     "blowups_gt300pct": [(e["ticker"], e["date"], round(e[f"x{H}"], 3))
                                          for p in top for e in top[p] if abs(e[f"x{H}"]) > 3]}
    order = ["1_sanity", "2_random_control_TRAIN", "3_plateau_TRAIN", "4_cost",
             "5_leave_one_out", "6_yearly_consistency", "7_oos_VAL"]
    if len(top["TRAIN"]) >= 2 and len(top["VAL"]) >= 2:
        s_tr, v_tr, p95_tr = gate("TRAIN", H, "TRAIN")
        G["2_random_control_TRAIN"] = {"pass": bool(v_tr.passed), "signal_mean_excess": s_tr,
                                       "pool_mean_excess": float(np.mean([e[f"x{H}"] for e in allp["TRAIN"]])),
                                       "control_max": v_tr.control_max, "control_mean": v_tr.control_mean,
                                       "percentile": v_tr.control_percentile, "reason": v_tr.reason}
        plateau = {}
        for h in H_GRID:
            s, _, p95 = gate("TRAIN", h, "TRAIN 高原")
            plateau[h] = {"signal": s, "control_p95": p95, "ok": s > p95}
        G["3_plateau_TRAIN"] = {"pass": all(x["ok"] for x in plateau.values()), "grid": plateau}
        costs = {}
        for kx in (1, 2, 3):
            costs[f"{kx}x"] = {p: float(np.mean([e[f"x{H}"] - kx * round_trip_cost_pct(
                e["price"], shares=max(1.0, round(POSITION_USD / e["price"]))) for e in top[p]])) for p in top}
        G["4_cost"] = {"pass": all(r["TRAIN"] > 0 and r["VAL"] > 0 for r in costs.values()), "net_mean": costs}
        tr = pd.DataFrame(top["TRAIN"])
        yr = tr.groupby("year")[f"x{H}"].agg(["mean", "sum", "count"])
        drop = yr["sum"].idxmax()
        loo = float(tr[tr["year"] != drop][f"x{H}"].mean())
        G["5_leave_one_out"] = {"pass": loo > 0 and loo > p95_tr, "dropped_year": drop,
                                "mean_after_drop": loo, "train_control_p95": p95_tr}
        G["6_yearly_consistency"] = {"pass": float((yr["mean"] > 0).mean()) >= 5 / 6,
                                     "positive_year_ratio": float((yr["mean"] > 0).mean()),
                                     "by_year": {y: {"mean": float(r["mean"]), "n": int(r["count"])}
                                                 for y, r in yr.iterrows()}}
        s_va, v_va, _ = gate("VAL", H, "VAL")
        G["7_oos_VAL"] = {"pass": bool(v_va.passed), "signal_mean_excess": s_va,
                          "pool_mean_excess": float(np.mean([e[f"x{H}"] for e in allp["VAL"]])),
                          "control_max": v_va.control_max, "control_mean": v_va.control_mean,
                          "percentile": v_va.control_percentile, "reason": v_va.reason}
    first_fail = next((g for g in order if g not in G or not G[g]["pass"]), None)
    res["first_failed_gate"] = first_fail
    res["verdict"] = "FAIL" if first_fail else "PASS_GATES_1_7（天條一/前向待做，部署前停下提案）"
    res["note"] = ("依 GATE_SEQUENCE 第一個 FAIL 的關卡即為判定；其後各關數字僅供診斷。"
                   "存活者偏誤未完全修正：已下市股 7.1%（775／10,863 檔）無價格來源；"
                   "本試驗價格宇宙另偏向存活者（yfinance 現存代號＋DERA 內部人買入發行人快取）。")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for g in order:
        print(g, "—" if g not in G else ("PASS" if G[g]["pass"] else "FAIL"))
    print("判定：", res["verdict"], "首個 FAIL：", first_fail)
    print(json.dumps({k: {kk: vv for kk, vv in G[k].items() if kk not in ("by_year", "blowups_gt300pct", "grid")}
                      for k in order if k in G}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
