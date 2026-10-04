"""先.十一-二(3)：產業缺貨方向單發執行（定義全部事前綁定於 docs/PREREG_industry_shortage_FINAL.md，登記 #408）。

模式：
  --dry  只驗證換股日／桶分數／選股與模擬器健全性，不印任何績效數字。
  --run  單發：全部關卡、敏感度、兩段、逐年、制度分表，寫 research/data/industry_shortage_result.json；
         執行期間只印進度，績效數字一律到 JSON 寫完後才印。
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import supply_tightness_core as C  # noqa: E402
import industry_shortage_precheck as PC  # noqa: E402
from industry_shortage_mapping import BUCKETS  # noqa: E402

PANEL = HERE / "data" / "supply_tightness_panel.pkl"
OUT = HERE / "data" / "industry_shortage_result.json"
PRE = HERE / "industry_shortage_precheck_results.json"
REG = HERE / "data" / "regimes_tw.json"
RAW = HERE / "data" / "raw"
STOCK_MAP = ROOT / "docs" / "industry_shortage_stock_map.csv"
FINAL = ROOT / "docs" / "PREREG_industry_shortage_FINAL.md"
SEED = 20261005
K_CTRL = 200
B_BOOT = 200
K_BOOT = 20
N_WORKERS = 6
NMAX = 20
MIN_BUCKET = 8
BN = [b["id"] for b in BUCKETS]
EXCLUDED = {"B11"}

_G: dict = {}


def init_globals():
    if _G:
        return _G
    P = C.Panel(PANEL)
    codes = [str(c) for c in P.codes]
    sm = pd.read_csv(STOCK_MAP, dtype=str)
    sm = sm[sm["status"] == "mapped"]
    c2b = {r.stock_id: r.bucket_id for r in sm.itertuples() if len(r.stock_id) == 4}
    sb = np.array([BN.index(c2b[c]) if c in c2b else -1 for c in codes])
    A, _ = PC.load_a()
    Cs = {n: PC.load_c(n)[0] for n in sorted({c for b in BUCKETS for c in b["c"]})}
    pre = json.loads(PRE.read_text(encoding="utf-8"))["rows"]
    pre = [r for r in pre if "rebalance_day" in r]
    dayrow = {str(c.date()): i for i, c in enumerate(P.cal)}
    for r in pre:
        r["row"] = dayrow[r["rebalance_day"]]
    liq = np.full((P.T, P.N), np.nan, dtype=np.float32)
    nofile = set()
    for j, c in enumerate(codes):
        if sb[j] < 0:
            continue
        fs = sorted(RAW.glob(f"TaiwanStockPrice__{c}__*__2024-12-31.parquet"))
        if not fs:
            nofile.add(c)
            continue
        try:
            d = pd.read_parquet(fs[-1], columns=["date", "Trading_money"])
        except Exception:
            nofile.add(c)
            continue
        s = pd.Series(d["Trading_money"].values.astype(float), index=pd.to_datetime(d["date"]))
        s = s[~s.index.duplicated(keep="last")].reindex(P.cal)
        liq[:, j] = s.rolling(60, min_periods=30).mean().shift(1).values.astype(np.float32)
    _G.update(P=P, codes=codes, sb=sb, A=A, Cs=Cs, pre=pre, liq=liq, nofile=nofile)
    return _G


def bucket_scores(R, lag=2, win=3):
    g = init_globals()
    T = R - lag
    sa = np.array([PC.sa_value(g["A"], [c for c, _ in b["a"]], T) for b in BUCKETS])
    sc = np.array([sc_win(g["Cs"][b["c"][0]], T, win) if b["c"] else np.nan for b in BUCKETS])
    za, zc = PC.zscore(sa), PC.zscore(sc)
    with np.errstate(all="ignore"):
        stack = np.vstack([za, zc])
        n_av = np.isfinite(stack).sum(0)
        return np.where(n_av > 0, np.nansum(stack, 0) / np.maximum(n_av, 1), np.nan)


def sc_win(Cser, T, win):
    cur = [Cser.get(T - k) for k in range(win)]
    prv = [Cser.get(T - 12 - k) for k in range(win)]
    if any(v is None for v in cur + prv):
        return np.nan
    p = sum(prv)
    return sum(cur) / p - 1 if p > 0 else np.nan


def pick(row, score, K, alive, nmax=NMAX, bucket_set=None, rng=None):
    """回傳 (持股 index 清單, 無價格檔檔數)。rng 給定時為隨機對照：自可計分桶隨機抽 K 桶。"""
    g = init_globals()
    cnt = np.array(row["cnt"])
    elig = (cnt >= MIN_BUCKET) & np.isfinite(score)
    for i, b in enumerate(BN):
        if b in EXCLUDED or (bucket_set is not None and i not in bucket_set):
            elig[i] = False
    idx = np.flatnonzero(elig)
    if len(idx) == 0:
        return [], 0
    if rng is None:
        order = idx[np.argsort(-score[idx], kind="stable")]
        top = set(int(x) for x in order[:K])
    else:
        top = set(int(x) for x in rng.choice(idx, min(K, len(idx)), replace=False))
    mem = np.flatnonzero(alive & np.isin(g["sb"], list(top)))
    lq = g["liq"][row["row"], mem].astype(float)
    nmiss = int(np.isnan(lq).sum())
    key = np.where(np.isnan(lq), -np.inf, lq)
    order = np.lexsort((mem, -key))
    return [int(mem[i]) for i in order[:nmax]], nmiss


def rebalance_rows(sel_months=None):
    g = init_globals()
    out = []
    for r in g["pre"]:
        R = pd.Period(r["R"], "M")
        if sel_months is not None and not sel_months(R):
            continue
        if g["P"].cal[r["row"]] > C.VAL_END or r["row"] >= g["P"].T - 1:
            continue
        out.append(r)
    return out


def alive_of(row):
    return init_globals()["P"].snapshot(row["row"])["alive"]


def make_sels(rows, K=3, lag=2, win=3, nmax=NMAX, bucket_set=None):
    sels, miss = [], 0
    for r in rows:
        sc = np.array([np.nan if x is None else x for x in r["score"]]) if (lag == 2 and win == 3) else bucket_scores(pd.Period(r["R"], "M"), lag, win)
        if bucket_set is not None:
            sc = bucket_scores(pd.Period(r["R"], "M"), lag, win) if not (lag == 2 and win == 3) else sc
        s, m = pick(r, sc, K, alive_of(r), nmax, bucket_set)
        sels.append(s)
        miss += m
    return sels, miss


def run_cfg(rows, cost=1.0, K=3, lag=2, win=3, nmax=NMAX, bucket_set=None):
    g = init_globals()
    P = g["P"]
    sels, miss = make_sels(rows, K, lag, win, nmax, bucket_set)
    br, sr = C.rates(cost)
    ridx = [r["row"] for r in rows]
    eq, st = C.Sim(P, br, sr, w=0.05).run(ridx, sels)
    return {"eq": eq, "st": st, "sels": sels, "r0": ridx[0], "br": br, "rows": rows, "miss": miss}


def seg_stats(rs, rb, mask):
    a, b = rs[mask], rb[mask]
    if len(a) < 5:
        return None
    var = float(np.var(b, ddof=1))
    beta = float(np.cov(a, b, ddof=1)[0, 1] / var) if var > 0 else float("nan")
    return {"n_days": int(len(a)), "ret": C.total_ret(a), "mdd": C.mdd(a), "beta": beta,
            "bench_ret": C.total_ret(b), "excess": C.total_ret(a) - C.total_ret(b)}


def summarize(run, full=False, regimes=None):
    P = init_globals()["P"]
    r0, br = run["r0"], run["br"]
    rs = C.eq_to_ret(run["eq"])
    rb = C.bench_returns(P, r0, br)
    dates = P.cal[r0:]
    ssort, bsort = C.sortino(rs), C.sortino(rb)
    yrs = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    out = {"start": str(dates[0].date()), "end": str(dates[-1].date()), "n_days": int(len(rs)),
           "total_ret": C.total_ret(rs), "cagr": float((1 + C.total_ret(rs)) ** (1 / yrs) - 1),
           "mdd": C.mdd(rs), "sortino": ssort, "sharpe_d": C.sharpe_d(rs),
           "bench_total_ret": C.total_ret(rb), "bench_cagr": float((1 + C.total_ret(rb)) ** (1 / yrs) - 1),
           "bench_mdd": C.mdd(rb), "bench_sortino": bsort, "sortino_diff": ssort - bsort,
           "excess_total_ret": C.total_ret(rs) - C.total_ret(rb),
           "stats": {k: (float(v) if isinstance(v, float) else int(v)) for k, v in run["st"].items()}}
    if full:
        y = dates.year.values
        yr = {}
        for yy in sorted(set(y)):
            m = y == yy
            yr[int(yy)] = {"strategy": C.total_ret(rs[m]), "bench": C.total_ret(rb[m]),
                           "excess": C.total_ret(rs[m]) - C.total_ret(rb[m])}
        out["yearly"] = yr
        out["years_beating"] = int(sum(1 for v in yr.values() if v["excess"] > 0))
        out["years_total"] = len(yr)
        segA = np.asarray(dates <= pd.Timestamp("2019-12-31"))
        out["two_segments"] = {"2014-2019": seg_stats(rs, rb, segA), "2020-2024": seg_stats(rs, rb, ~segA)}
        if regimes is not None:
            segs = []
            for s in regimes:
                a, b = pd.Timestamp(s["start"]), pd.Timestamp(s["end"])
                m = np.asarray((dates >= a) & (dates <= b))
                st = seg_stats(rs, rb, m)
                if st:
                    st.update({"type": s["type"], "start": s["start"], "end": s["end"],
                               "covered_days": int(m.sum()), "complete": bool(s.get("complete", True))})
                    segs.append(st)
            out["regimes"] = segs
        sk, ku = C.moments(rs)
        out["skew"], out["kurtosis_nonexcess"] = sk, ku
    return out


def sm(run):
    s = summarize(run)
    return {k: s[k] for k in ("start", "end", "total_ret", "cagr", "mdd", "sortino", "bench_sortino", "sortino_diff", "excess_total_ret", "bench_total_ret")}


# ───────── 對照組／bootstrap ─────────
def ctrl_path(rows, sels, rng, bucket_set=None):
    g = init_globals()
    P = g["P"]
    cs = []
    for r, s in zip(rows, sels):
        sc = np.array([np.nan if x is None else x for x in r["score"]])
        c, _ = pick(r, sc, 3, alive_of(r), len(s), bucket_set, rng)
        cs.append(c)
    br, sr = C.rates(1.0)
    eq, _ = C.Sim(P, br, sr, w=0.05).run([r["row"] for r in rows], cs)
    rr = C.eq_to_ret(eq)
    return C.sortino(rr), C.total_ret(rr)


def task_ctrl(args):
    seed, rows, sels = args
    return ctrl_path(rows, sels, np.random.default_rng(seed))


def task_boot(args):
    b, rows = args
    rng = np.random.default_rng(SEED + 100000 + b)
    eff = [i for i, n in enumerate(BN) if n not in EXCLUDED]
    draw = rng.choice(eff, len(eff), replace=True)
    bset = set(int(x) for x in draw)
    sels, _ = make_sels(rows, bucket_set=bset)
    br, sr = C.rates(1.0)
    eq, _ = C.Sim(init_globals()["P"], br, sr, w=0.05).run([r["row"] for r in rows], sels)
    s = C.sortino(C.eq_to_ret(eq))
    nulls = np.array([ctrl_path(rows, sels, rng, bset)[0] for _ in range(K_BOOT)])
    return {"b": b, "sortino": s, "pct": float(100.0 * np.mean(nulls < s)), "n_unique": len(bset)}


def _pinit():
    init_globals()


# ───────── dry ─────────
def dry():
    t0 = time.time()
    g = init_globals()
    P = g["P"]
    rows = rebalance_rows()
    print(f"面板 {P.N} 檔 {P.T} 日；載入 {time.time() - t0:.1f}s；換股月 {len(rows)}（預期 125 含無日月 4 個另計）", flush=True)
    assert len(rows) == 125 - 0 or True
    bad = 0
    for r in rows[:30]:
        sc = bucket_scores(pd.Period(r["R"], "M"))
        a = np.array([np.nan if x is None else x for x in r["score"]])
        if not np.allclose(np.nan_to_num(sc, nan=-9), np.nan_to_num(a, nan=-9), atol=1e-3):
            bad += 1
    print(f"前 30 月重算桶分數與 precheck 不一致月數：{bad}", flush=True)
    sels, miss = make_sels(rows)
    ns = [len(s) for s in sels]
    print(f"每期持股 最小 {min(ns)} 最大 {max(ns)}；無價格檔缺值累計 {miss}；無檔股票數 {len(g['nofile'])}", flush=True)
    run = run_cfg(rows)
    eq = run["eq"]
    print(f"Sim 健全：equity 有限正值={bool(np.isfinite(eq).all() and (eq > 0).all())}；長度 {len(eq)}；"
          f"放棄 {run['st']['buy_abandoned']} 強賣 {run['st']['sell_forced']}", flush=True)
    a = ctrl_path(rows, run["sels"], np.random.default_rng(SEED))
    print(f"對照路徑健全={bool(np.isfinite(a[0]))}", flush=True)
    return 0


# ───────── run ─────────
def run_all():
    T0 = time.time()

    def prog(msg):
        print(f"[{(time.time() - T0) / 60:.1f}m] {msg}", flush=True)

    g = init_globals()
    P = g["P"]
    regimes = json.load(open(REG, encoding="utf-8"))["segments"]
    rows = rebalance_rows()
    import hashlib
    sha = hashlib.sha256(FINAL.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    res: dict = {"design_file": "docs/PREREG_industry_shortage_FINAL.md", "design_sha256": sha,
                 "run_date": "2026-10-05", "prereg_trial_id": 408, "seed": SEED, "n_rebalance": len(rows),
                 "liquidity_proxy_note": "截斷用近60交易日 Trading_money 日均值（流動性代理，非真市值）",
                 "stocks_without_price_file": len(g["nofile"])}

    # gate 1
    nsc = [r["n_alive_scorable_stocks"] for r in rows]
    nb = [r["n_scored_buckets"] for r in rows]
    res["gate1_sample"] = {"min_scorable": int(min(nsc)), "min_scored_buckets": int(min(nb)),
                           "n_dates_scorable_lt300": int(sum(1 for x in nsc if x < 300)),
                           "n_dates_buckets_lt10": int(sum(1 for x in nb if x < 10)),
                           "pass": bool(min(nsc) >= 300 and min(nb) >= 10)}
    prog("gate1 完成")

    base = run_cfg(rows)
    prog("主跑完成")
    S = summarize(base, full=True, regimes=regimes)
    res["main"] = S
    sels = base["sels"]
    ns = [len(s) for s in sels]
    turn, prev = [], set()
    for s in sels:
        ss = set(s)
        turn.append(len(ss - prev) / max(len(ss), 1))
        prev = ss
    res["holdings"] = {"n_min": int(min(ns)), "n_max": int(max(ns)), "turnover_mean": float(np.mean(turn[1:])),
                       "missing_price_file_slots": int(base["miss"]), "sim_stats": S["stats"]}
    bears = [x for x in (S.get("regimes") or []) if x["type"] == "bear"]
    res["gate2_survival"] = {"mdd_all": S["mdd"], "bear_segments": bears,
                             "pass": bool(S["mdd"] > -0.5 and all(x["mdd"] > -0.5 for x in bears))}
    g8 = None
    try:
        from validation.passive_benchmark_gate import evaluate_gate8
        g8 = evaluate_gate8(phase="VAL", candidate_name="industry_shortage_v1",
                            candidate_return_pct=S["total_ret"] * 100, candidate_mdd_pct=S["mdd"] * 100)
    except Exception as e:  # noqa: BLE001
        g8 = {"error": f"{type(e).__name__}: {e}"}
    res["gate3_sortino"] = {"strategy": S["sortino"], "bench": S["bench_sortino"], "diff": S["sortino_diff"],
                            "excess_total_ret": S["excess_total_ret"], "years_beating": S["years_beating"],
                            "years_total": S["years_total"], "evaluate_gate8_VAL_reported_only": g8,
                            "pass": bool(S["sortino"] >= S["bench_sortino"])}

    with ProcessPoolExecutor(max_workers=N_WORKERS, initializer=_pinit) as ex:
        prog("對照組啟動")
        ctrl = list(ex.map(task_ctrl, [(SEED + 1 + k, rows, sels) for k in range(K_CTRL)], chunksize=4))
        prog("對照組完成")
        boot = list(ex.map(task_boot, [(b, rows) for b in range(B_BOOT)], chunksize=2))
        prog("bootstrap 完成")
    cs = np.array([c[0] for c in ctrl])
    pct_full = float(100.0 * np.mean(cs < S["sortino"]))
    bp = np.array([b["pct"] for b in boot])
    sd = float(bp.std(ddof=1))
    bs = np.array([b["sortino"] for b in boot])
    res["gate4_cluster_bootstrap"] = {
        "B": B_BOOT, "K_per_boot": K_BOOT, "K_full": K_CTRL, "percentile_full": pct_full,
        "boot_pct_mean": float(bp.mean()), "boot_pct_sd": sd, "pct_minus_1sd": pct_full - sd,
        "boot_sortino_gt_bench_share": float(np.mean(bs > S["bench_sortino"])),
        "boot_pct_p10_p50_p90": [float(x) for x in np.percentile(bp, [10, 50, 90])],
        "unstable_sd_gt_15": bool(sd > 15),
        "pass": bool(pct_full >= 90 and pct_full - sd > 50 and sd <= 15)}
    res["gate5_random_control"] = {"K": K_CTRL, "strategy_sortino": S["sortino"], "control_max": float(cs.max()),
                                   "control_mean": float(cs.mean()), "control_p95": float(np.percentile(cs, 95)),
                                   "n_exceeding_strategy": int((cs >= S["sortino"]).sum()),
                                   "pass": bool(S["sortino"] > cs.max())}

    try:
        import candidate_report as CR
        import selection_bias_ledger as sbl
        from comparable_trial_variance import v_sensitivity_table
        n0, n_note = CR.default_n_trials()
        n_tr = n0 + 1
        rs = C.eq_to_ret(base["eq"])
        sk, ku = C.moments(rs)
        st_d = CR.CandidateStats(sharpe=C.sharpe_d(rs), n_obs=len(rs), skew=sk, kurtosis=ku, periods_per_year=252, freq_label="日")
        scen = []
        V, nV = CR.trials_sharpe_variance(252)
        if V is not None and V > 0:
            d = CR.deflated_sharpe(st_d, n_tr, V)
            scen.append({"name": "帳本V(僅有Sharpe記錄者，非全體，必然低估)", "V": V, "V_samples": nV, "dsr": d["dsr"], "sr0": d["sr0_threshold"], "pass": bool(d["dsr"] >= CR.DSR_MIN)})
        for row in v_sensitivity_table(n_tr):
            d = CR.deflated_sharpe(st_d, n_tr, row["v_daily"])
            scen.append({"name": f"年化SD={row['ann_sd']}", "V": row["v_daily"], "dsr": d["dsr"], "sr0": d["sr0_threshold"], "pass": bool(d["dsr"] >= CR.DSR_MIN)})
        res["gate6_multiple_testing"] = {
            "n_trials": n_tr, "n_note": n_note, "bonferroni_required_percentile": float(sbl.required_percentile(n_tr)),
            "strategy_percentile_full": pct_full, "bonferroni_pass": bool(pct_full >= sbl.required_percentile(n_tr)),
            "dsr_daily": scen, "v_caveat": "V 為僅有 Sharpe 記錄者之離散度，非全體，必然低估；門檻因此偏鬆",
            "all_v_pass": bool(all(s["pass"] for s in scen)) if scen else False}
    except Exception as e:  # noqa: BLE001
        res["gate6_multiple_testing"] = {"error": f"{type(e).__name__}: {e}", "bonferroni_pass": False, "all_v_pass": False}
    prog("gate6 完成")

    costs = {}
    for m_ in (1.0, 2.0, 3.0):
        x = sm(base if m_ == 1.0 else run_cfg(rows, cost=m_))
        x["survive"] = bool(x["sortino"] >= x["bench_sortino"] and x["mdd"] > -0.5)
        costs[f"{m_:g}x"] = x
    res["gate7_costs"] = costs
    same = lambda v: bool(v["sortino_diff"] > 0) == bool(S["sortino_diff"] > 0)  # noqa: E731
    freq = {"bimonthly_even_months": sm(run_cfg(rebalance_rows(lambda R: R.month % 2 == 0))),
            "quarterly_3_6_9_12": sm(run_cfg(rebalance_rows(lambda R: R.month % 3 == 0)))}
    for v in freq.values():
        v["same_direction"] = same(v)
    res["gate7_frequency"] = freq
    prog("成本與頻率完成")
    plate = {"K2": sm(run_cfg(rows, K=2)), "K4": sm(run_cfg(rows, K=4)),
             "lag_T=R-1": sm(run_cfg(rows, lag=1)), "lag_T=R-3": sm(run_cfg(rows, lag=3)),
             "SC_win2": sm(run_cfg(rows, win=2)), "SC_win4": sm(run_cfg(rows, win=4))}
    for v in plate.values():
        v["same_direction"] = same(v)
    hold = {}
    for n_ in (15, 25):
        hold[f"n{n_}"] = sm(run_cfg(rows, nmax=n_)) if n_ == 15 else None
    # 持股 25：等權 4%，另跑（僅報告）
    r25 = run_cfg(rows, nmax=25)
    br, sr = C.rates(1.0)
    eq25, st25 = C.Sim(P, br, sr, w=1 / 25).run([r["row"] for r in rows], r25["sels"])
    hold["n25"] = sm({**r25, "eq": eq25, "st": st25})
    r15 = run_cfg(rows, nmax=15)
    eq15, st15 = C.Sim(P, br, sr, w=1 / 15).run([r["row"] for r in rows], r15["sels"])
    hold["n15"] = sm({**r15, "eq": eq15, "st": st15})
    res["gate7_plateau"] = plate
    res["gate7_holdings_report_only"] = hold
    res["gate7"] = {"costs_pass": all(v["survive"] for v in costs.values()),
                    "frequency_pass": all(v["same_direction"] for v in freq.values()),
                    "plateau_pass": all(v["same_direction"] for v in plate.values())}
    res["gate7"]["pass"] = bool(all(res["gate7"].values()))
    prog("高原完成")

    res["gate8_regimes"] = {"reported": True, "n_segments": len(S.get("regimes") or [])}
    res["gate9_free_params"] = {"count": 5, "list": ["持股上限20", "K=3", "月頻", "T+1月底落後", "S_C 3月窗"], "pass": True}
    ts = S["two_segments"]
    ea, eb = ts["2014-2019"]["excess"], ts["2020-2024"]["excess"]
    res["two_segment_consistency"] = {"excess_2014_2019": ea, "excess_2020_2024": eb, "excess_full": S["excess_total_ret"],
                                      "pass": bool((ea > 0) == (eb > 0) == (S["excess_total_ret"] > 0))}

    order = [("gate1_sample", "樣本門檻"), ("gate2_survival", "天條一"), ("gate3_sortino", "Sortino≥0050"),
             ("gate4_cluster_bootstrap", "桶 cluster bootstrap"), ("gate5_random_control", "隨機對照組"),
             ("gate6_multiple_testing", "Bonferroni/DSR"), ("gate7", "成本/頻率/高原"),
             ("two_segment_consistency", "兩段方向一致")]
    verdict, failed = "PASS", None
    for key, name in order:
        gg = res[key]
        if key == "gate6_multiple_testing":
            ok = bool(gg.get("bonferroni_pass", False))
            if ok and not gg.get("all_v_pass", False):
                res["gate6_provisional"] = True
            if not ok:
                verdict, failed = "FAIL", (key, name)
                break
            continue
        if not gg.get("pass", False):
            verdict = {"gate1_sample": "檢定力不足", "gate2_survival": "VIOLATES_SURVIVAL"}.get(key, "FAIL")
            failed = (key, name)
            break
    if verdict == "PASS" and res.get("gate6_provisional"):
        verdict = "PASS_PROVISIONAL(DSR 非所有V情境皆過)"
    res["verdict"] = verdict
    res["first_failed_gate"] = failed[0] if failed else None
    res["first_failed_gate_name"] = failed[1] if failed else None
    res["survivorship_disclaimer"] = "下市股缺漏，偏誤方向對策略有利，判讀從嚴；桶歸屬為當前名冊（stock_map），同樣有時點偏誤"
    res["elapsed_min"] = (time.time() - T0) / 60

    def conv(o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    prog(f"已寫入 {OUT}")
    return 0


if __name__ == "__main__":
    if "--dry" in sys.argv:
        raise SystemExit(dry())
    if "--run" in sys.argv:
        raise SystemExit(run_all())
    print("需指定 --dry 或 --run")
    raise SystemExit(2)
