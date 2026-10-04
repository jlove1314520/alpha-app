"""先.十三-三：產業缺貨衛星策略——單發執行協調器（定義全部事前綁定於
docs/PREREG_industry_shortage_FINAL.md，TRIALS_REGISTRY #408）。

模式：
  --dry  只驗證資料與計分（換股日、可計分桶數、可計分股數對照 precheck）與模擬器健全性；
         不印任何績效數字。
  --run  單發執行：全部關卡、敏感度、兩段、逐年、制度分表，寫 research/data/industry_shortage_result.json。
         執行期間只印進度標記，績效數字一律到 JSON 寫完後才印。印出績效前崩潰可修後重跑並記錄；印出後不得重跑。
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
sys.path.insert(0, str(HERE))
import supply_tightness_core as C  # noqa: E402
import industry_shortage_core as IC  # noqa: E402

OUT = HERE / "data" / "industry_shortage_result.json"
PRE = HERE / "industry_shortage_precheck_results.json"
REG = HERE / "data" / "regimes_tw.json"
SEED = 20261005
K_CTRL = 200   # 隨機對照組（gate5）抽樣次數
B_BOOT = 200   # 桶 cluster bootstrap 次數（gate4）
K_BOOT = 40    # 每次 bootstrap 內的對照路徑數
N_WORKERS = 6
DESIGN_SHA256 = "7e73dd0b0600f9ccfc8f7caea96fffa3dcedfa010773c6a989644d47dee6241b"
PREREG_TRIAL_ID = 408

_P: C.Panel | None = None
_BD: IC.BucketData | None = None
_CACHE: list | None = None
_VALID_BUCKETS: np.ndarray | None = None


def _init_worker():
    global _P, _BD, _CACHE, _VALID_BUCKETS
    _P = C.Panel(IC.PANEL_PATH)
    _BD = IC.BucketData(_P)
    rows = IC.rebalance_rows(_P)
    _CACHE = IC.precompute_dates(_P, _BD, rows)
    _VALID_BUCKETS = valid_buckets(_CACHE)


def valid_buckets(cache) -> np.ndarray:
    """每個換股日都是 eligible 的桶（固定12個，B11全期不出分數因此排除）。"""
    elig_all = np.ones(len(cache[0]["elig"]), bool)
    for c in cache:
        elig_all &= c["elig"]
    return np.flatnonzero(elig_all)


# ───────────────────────── 指標（沿用 #406 的量尺） ─────────────────────────
def seg_stats(rs, rb, mask):
    a, b = rs[mask], rb[mask]
    if len(a) < 5:
        return None
    var = float(np.var(b, ddof=1))
    beta = float(np.cov(a, b, ddof=1)[0, 1] / var) if var > 0 else float("nan")
    return {"n_days": int(len(a)), "ret": C.total_ret(a), "mdd": C.mdd(a), "beta": beta,
            "bench_ret": C.total_ret(b), "excess": C.total_ret(a) - C.total_ret(b)}


def summarize(P, run, full=False, regimes=None):
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
        segA = dates <= pd.Timestamp("2019-12-31")
        out["two_segments"] = {"2014-2019": seg_stats(rs, rb, np.asarray(segA)),
                               "2020-2024": seg_stats(rs, rb, np.asarray(~segA))}
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


# ───────────────────────── 對照組／bootstrap 工作（ProcessPool） ─────────────────────────
def task_ctrl(seed):
    rng = np.random.default_rng(seed)
    run = IC.run_from_cache(_P, _BD, _CACHE, cost=1.0, random_rng=rng)
    rs = C.eq_to_ret(run["eq"])
    return float(C.sortino(rs)), float(C.total_ret(rs))


def task_boot(b):
    rng = np.random.default_rng(SEED + 100000 + b)
    draw = rng.choice(_VALID_BUCKETS, size=len(_VALID_BUCKETS), replace=True)
    inc = np.zeros(len(_CACHE[0]["elig"]), bool)
    inc[np.unique(draw)] = True
    run = IC.run_from_cache(_P, _BD, _CACHE, cost=1.0, bucket_inc=inc)
    s = float(C.sortino(C.eq_to_ret(run["eq"])))
    nulls = np.array([task_ctrl_inc(rng, inc)[0] for _ in range(K_BOOT)])
    return {"b": b, "sortino": s, "pct": float(100.0 * np.mean(nulls < s)), "null_mean": float(nulls.mean()),
            "n_unique_buckets": int(inc.sum())}


def task_ctrl_inc(rng, inc):
    run = IC.run_from_cache(_P, _BD, _CACHE, cost=1.0, bucket_inc=inc, random_rng=rng)
    rs = C.eq_to_ret(run["eq"])
    return float(C.sortino(rs)), float(C.total_ret(rs))


# ───────────────────────── dry ─────────────────────────
def dry():
    t0 = time.time()
    P = C.Panel(IC.PANEL_PATH)
    BD = IC.BucketData(P)
    print(f"面板+桶資料載入 {time.time() - t0:.1f}s；股票 {P.N}，交易日 {P.T}", flush=True)
    rows = IC.rebalance_rows(P)
    cache = IC.precompute_dates(P, BD, rows)
    pre = json.load(open(PRE, encoding="utf-8"))["rows"]
    ok_pre = [r for r in pre if "n_scored_buckets" in r]
    assert len(rows) == len(cache) == len(ok_pre) == 125, (len(rows), len(cache), len(ok_pre))
    de, dp = [], []
    for c, p in zip(cache, ok_pre):
        assert str(P.cal[c["r"]].date()) == p["rebalance_day"], (P.cal[c["r"]].date(), p["rebalance_day"])
        de.append(int(c["elig"].sum()) - p["n_scored_buckets"])
        dp.append(int(c["cnt"][c["elig"]].sum()) - p["n_alive_scorable_stocks"])
    print(f"125 個換股日日期與 precheck 完全一致；有訊號桶數差(本-precheck) 平均 {np.mean(de):+.2f} 範圍 [{min(de)},{max(de)}]；"
          f"可計分活躍股差 平均 {np.mean(dp):+.1f} 範圍 [{min(dp)},{max(dp)}]", flush=True)
    vb = valid_buckets(cache)
    print(f"固定有效桶(全期皆eligible) n={len(vb)}：{[BD.bnames[i] for i in vb]}", flush=True)
    t1 = time.time()
    run = IC.run_from_cache(P, BD, cache)
    eq = run["eq"]
    print(f"Sim 健全性：equity 全為有限正值={bool(np.isfinite(eq).all() and (eq > 0).all())}；長度={len(eq)}；"
          f"耗時 {time.time() - t1:.1f}s；買進放棄={run['st']['buy_abandoned']} 延後={run['st']['buy_deferred']} 強制賣出={run['st']['sell_forced']}", flush=True)
    npos = [len(s) for s in run["sels"]]
    print(f"每期持股數 最小 {min(npos)} 最大 {max(npos)}", flush=True)
    rs = C.eq_to_ret(eq)
    rb = C.bench_returns(P, run["r0"], run["br"])
    print(f"主跑健全性（不是正式判定，純粹確認不是NaN）：sortino 有限={np.isfinite(C.sortino(rs))}、bench sortino 有限={np.isfinite(C.sortino(rb))}；"
          f"mdd={C.mdd(rs):.4f}（僅確認可計算，正式判定見 --run 輸出）", flush=True)
    global _P, _BD, _CACHE, _VALID_BUCKETS
    _P, _BD, _CACHE, _VALID_BUCKETS = P, BD, cache, vb
    t2 = time.time()
    a = task_ctrl(SEED)
    print(f"對照路徑健全性：輸出有限={bool(np.isfinite(a[0]))}；耗時 {time.time() - t2:.1f}s", flush=True)
    t3 = time.time()
    x = task_boot(0)
    print(f"bootstrap 單次健全性：pct 在[0,100]={0 <= x['pct'] <= 100}；耗時 {time.time() - t3:.1f}s；唯一桶數={x['n_unique_buckets']}", flush=True)
    return 0


# ───────────────────────── run ─────────────────────────
def run_all():
    T0 = time.time()

    def prog(msg):
        print(f"[{(time.time() - T0) / 60:.1f}m] {msg}", flush=True)

    global _P, _BD, _CACHE, _VALID_BUCKETS
    P = C.Panel(IC.PANEL_PATH)
    BD = IC.BucketData(P)
    rows = IC.rebalance_rows(P)
    cache = IC.precompute_dates(P, BD, rows)
    _P, _BD, _CACHE, _VALID_BUCKETS = P, BD, cache, valid_buckets(cache)
    regimes = json.load(open(REG, encoding="utf-8"))["segments"]
    res: dict = {"design_file": "docs/PREREG_industry_shortage_FINAL.md", "design_sha256": DESIGN_SHA256,
                 "run_date": "2026-10-05", "prereg_trial_id": PREREG_TRIAL_ID, "n_rebalance": len(rows),
                 "operationalization": {
                     "rebalance": "每月26日起第一個交易日(2014-04~2024-12，4個月無此日延續持股)，開盤價進場，漲停鎖住順延最多10交易日",
                     "signal": "S_A=-(桶內A中分類YoY差均值)，S_C=近3月外銷訂單合計YoY，13桶1%/99%縮尾z分數簡單等權平均，T=R-2",
                     "selection": "前K=3有訊號(cnt>=8)桶，桶內alive mapped個股以近60日Trading_money均值(流動性代理)截斷至20檔等權各5%",
                     "cost": "BacktestConfig 買賣分腿費率(手續費+證交稅+滑價5bps)×cost_multiplier；0050僅期初買進成本",
                     "sortino": "engine同定義：日報酬均值/√(負報酬平方均值)×√252，MAR=0",
                     "gate4": "以桶為單位cluster bootstrap(B=200)：對12個固定有效桶有放回重抽12個(取unique為inclusion mask)，"
                              "限制當日候選桶=原eligible∩inclusion，重算前3桶選股；每次bootstrap另生成K_BOOT=40條同inclusion下的隨機3桶對照路徑，"
                              "百分位=bootstrap路徑Sortino在這40條對照中的位置；SD=200次百分位之標準差",
                     "gate5": "從可計分桶(原始eligible，無bootstrap遮罩)隨機抽3桶×200組，同持股上限、同換股日、同成本",
                 }}

    # ---- 1. 樣本門檻（前置）
    nsb = np.array([int(c["elig"].sum()) for c in cache])
    npool = np.array([int(c["cnt"][c["elig"]].sum()) if c["elig"].any() else 0 for c in cache])
    prog("gate1 計數完成")
    res["gate1_sample"] = {"min_scored_buckets": int(nsb.min()), "min_alive_scorable": int(npool.min()),
                           "per_date": [{"date": str(P.cal[c["r"]].date()), "n_scored_buckets": int(c["elig"].sum()),
                                        "n_alive_scorable": int(c["cnt"][c["elig"]].sum()) if c["elig"].any() else 0}
                                       for c in cache],
                           "pass": bool(nsb.min() >= IC.GATE_BUCKETS and npool.min() >= 300)}

    # ---- 2. 主跑
    base = IC.run_from_cache(P, BD, cache)
    prog("主跑完成")
    S = summarize(P, base, full=True, regimes=regimes)
    res["main"] = S
    sels = base["sels"]
    turn, held_delisted, cnt_sel = [], [], []
    prev = set()
    for s in sels:
        ss = set(int(x) for x in s)
        turn.append(len(ss - prev) / max(len(ss), 1))
        held_delisted.append(float(np.mean([P.later_delisted[i] for i in s])) if len(s) else float("nan"))
        cnt_sel.append(len(s))
        prev = ss
    res["holdings"] = {"n_min": int(min(cnt_sel)), "n_max": int(max(cnt_sel)),
                       "turnover_mean": float(np.nanmean(turn[1:])), "later_delisted_share_mean": float(np.nanmean(held_delisted)),
                       "later_delisted_share_universe": float(np.mean(P.later_delisted)), "sim_stats": S["stats"]}

    # ---- 3. 天條一
    bears = [g for g in (S.get("regimes") or []) if g["type"] == "bear"]
    res["gate2_survival"] = {"mdd_all": S["mdd"], "bear_segments": bears,
                             "pass": bool(S["mdd"] > -0.5 and all(g["mdd"] > -0.5 for g in bears))}
    # ---- 4. 天條二
    res["gate3_sortino"] = {"strategy": S["sortino"], "bench": S["bench_sortino"], "diff": S["sortino_diff"],
                            "excess_total_ret": S["excess_total_ret"], "years_beating": S["years_beating"],
                            "years_total": S["years_total"], "pass": bool(S["sortino"] >= S["bench_sortino"])}

    # ---- 5. 對照組（gate5）＋ bootstrap（gate4）
    with ProcessPoolExecutor(max_workers=N_WORKERS, initializer=_init_worker) as ex:
        prog("對照組啟動")
        ctrl = list(ex.map(task_ctrl, [SEED + 1 + k for k in range(K_CTRL)], chunksize=4))
        prog("對照組完成")
        boot = list(ex.map(task_boot, list(range(B_BOOT)), chunksize=2))
        prog("bootstrap 完成")
    cs = np.array([c[0] for c in ctrl])
    pct_full = float(100.0 * np.mean(cs < S["sortino"]))
    bp = np.array([b["pct"] for b in boot])
    sd = float(bp.std(ddof=1))
    res["gate4_resample"] = {"percentile_full": pct_full, "boot_pct_mean": float(bp.mean()), "boot_pct_sd": sd,
                             "boot_pct_p10_p50_p90": [float(x) for x in np.percentile(bp, [10, 50, 90])],
                             "B": B_BOOT, "K_per_boot": K_BOOT, "K_full": K_CTRL,
                             "pct_minus_1sd": pct_full - sd, "unstable_sd_gt_15": bool(sd > 15),
                             "pass": bool(pct_full >= 90 and pct_full - sd > 50 and sd <= 15)}
    res["gate5_random_control"] = {"K": K_CTRL, "strategy_sortino": S["sortino"], "control_max": float(cs.max()),
                                   "control_mean": float(cs.mean()), "control_p95": float(np.percentile(cs, 95)),
                                   "control_ret_mean": float(np.mean([c[1] for c in ctrl])),
                                   "n_exceeding_strategy": int((cs >= S["sortino"]).sum()),
                                   "pass": bool(S["sortino"] > cs.max())}

    # ---- 6. Bonferroni / DSR
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
        q = pd.Series(1 + rs, index=P.cal[base["r0"]:]).groupby(P.cal[base["r0"]:].to_period("Q")).prod().values - 1
        skq, kuq = C.moments(q)
        st_q = CR.CandidateStats(sharpe=float(q.mean() / q.std(ddof=1)), n_obs=len(q), skew=skq, kurtosis=kuq, periods_per_year=4, freq_label="季")
        scen_q = []
        for row in v_sensitivity_table(n_tr):
            vq = row["ann_sd"] ** 2 / 4
            d = CR.deflated_sharpe(st_q, n_tr, vq, var_periods_per_year=4)
            scen_q.append({"name": f"年化SD={row['ann_sd']}(季頻)", "V": vq, "dsr": d["dsr"], "pass": bool(d["dsr"] >= CR.DSR_MIN)})
        res["gate6_multiple_testing"] = {
            "n_trials": n_tr, "n_note": n_note, "bonferroni_required_percentile": float(sbl.required_percentile(n_tr)),
            "strategy_percentile_full": pct_full, "bonferroni_pass": bool(pct_full >= sbl.required_percentile(n_tr)),
            "dsr_daily": scen, "dsr_quarterly_reported_only": scen_q, "quarters": int(len(q)),
            "v_caveat": "V 為僅有 Sharpe 記錄者之離散度，非全體，必然低估；門檻因此偏鬆",
            "all_v_pass": bool(all(s["pass"] for s in scen)) if scen else False}
    except Exception as e:  # noqa: BLE001
        res["gate6_multiple_testing"] = {"error": f"{type(e).__name__}: {e}", "all_v_pass": False}
    prog("gate6 完成")

    # ---- 7. 成本、頻率、高原
    def sm(run):
        s = summarize(P, run)
        return {k: s[k] for k in ("start", "end", "total_ret", "cagr", "mdd", "sortino", "bench_sortino", "sortino_diff", "excess_total_ret", "bench_total_ret")}

    costs = {}
    for m_ in (1.0, 2.0, 3.0):
        rr = base if m_ == 1.0 else IC.run_from_cache(P, BD, cache, cost=m_)
        x = sm(rr)
        x["survive"] = bool(x["sortino"] >= x["bench_sortino"] and x["mdd"] > -0.5)
        costs[f"{m_:g}x"] = x
    res["gate7_costs"] = costs
    prog("成本完成")

    def bimonthly_rows():
        return [(r, R) for r, R in rows if R.month % 2 == 0]

    def quarterly_rows():
        return [(r, R) for i, (r, R) in enumerate(rows) if i % 3 == 0]

    freq = {}
    freq["bimonthly"] = sm(IC.run_cfg(P, BD, bimonthly_rows()))
    freq["quarterly"] = sm(IC.run_cfg(P, BD, quarterly_rows()))
    for v in freq.values():
        v["same_direction"] = bool(v["sortino_diff"] > 0) == bool(S["sortino_diff"] > 0)
    res["gate7_frequency"] = freq
    prog("頻率完成")

    plate = {"K2": sm(IC.run_from_cache(P, BD, cache, k=2)), "K4": sm(IC.run_from_cache(P, BD, cache, k=4)),
             "lag_Rm1": sm(IC.run_cfg(P, BD, rows, lag_months=1)), "lag_Rm3": sm(IC.run_cfg(P, BD, rows, lag_months=3)),
             "scwin2": sm(IC.run_cfg(P, BD, rows, sc_window=2)), "scwin4": sm(IC.run_cfg(P, BD, rows, sc_window=4))}
    for v in plate.values():
        v["same_direction"] = bool(v["sortino_diff"] > 0) == bool(S["sortino_diff"] > 0)
    hold = {"n15": sm(IC.run_from_cache(P, BD, cache, n_hold=15)), "n25": sm(IC.run_from_cache(P, BD, cache, n_hold=25))}
    res["gate7_plateau"] = plate
    res["gate7_holdings_report_only"] = hold
    res["gate7"] = {"costs_pass": all(v["survive"] for v in costs.values()),
                    "frequency_pass": all(v["same_direction"] for v in freq.values()),
                    "plateau_pass": all(v["same_direction"] for v in plate.values())}
    res["gate7"]["pass"] = bool(all(res["gate7"].values()))
    prog("高原完成")

    # ---- 8. 制度分表
    res["gate8_regimes"] = {"reported": True, "n_segments": len(S.get("regimes") or [])}
    res["gate9_free_params"] = {"count": 5, "list": ["持股上限20", "入選桶數K=3", "換股頻率(月頻)", "可得落後(T+1月底後)", "S_C近3月窗口"], "pass": True}

    # ---- 兩段方向一致
    ts = S["two_segments"]
    ea, eb = ts["2014-2019"]["excess"], ts["2020-2024"]["excess"]
    res["two_segment_consistency"] = {"excess_2014_2019": ea, "excess_2020_2024": eb, "excess_full": S["excess_total_ret"],
                                      "pass": bool((ea > 0) == (eb > 0) == (S["excess_total_ret"] > 0))}

    res["elapsed_min"] = (time.time() - T0) / 60

    # ---- 判定（依 §3 順序）
    order = [("gate1_sample", "樣本門檻"), ("gate2_survival", "天條一"), ("gate3_sortino", "Sortino≥0050"),
             ("gate4_resample", "池內重抽百分位"), ("gate5_random_control", "隨機對照組"),
             ("gate6_multiple_testing", "Bonferroni/DSR"), ("gate7", "成本/頻率/高原"),
             ("two_segment_consistency", "兩段方向一致")]
    verdict, failed = "PASS", None
    for key, name in order:
        g = res[key]
        if key == "gate6_multiple_testing":
            ok = bool(g.get("bonferroni_pass", False))
            if ok and not g.get("all_v_pass", False):
                res["gate6_provisional"] = True
            if not ok:
                verdict, failed = "FAIL", (key, name)
                break
            continue
        if not g.get("pass", False):
            if key == "gate1_sample":
                verdict = "檢定力不足"
            elif key == "gate2_survival":
                verdict = "VIOLATES_SURVIVAL"
            else:
                verdict = "FAIL"
            failed = (key, name)
            break
    if verdict == "PASS" and res.get("gate6_provisional"):
        verdict = "PASS_PROVISIONAL(DSR 非所有V情境皆過)"
    res["verdict"] = verdict
    res["first_failed_gate"] = failed[0] if failed else None
    res["first_failed_gate_name"] = failed[1] if failed else None
    res["survivorship_disclaimer"] = "面板母體非PIT、缺已下市股(沿用#406母體)，所有結果均帶偏誤，PASS亦不免除（FINAL §9）"

    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    prog(f"已寫入 {OUT}；verdict={verdict}")
    return 0


if __name__ == "__main__":
    if "--dry" in sys.argv:
        raise SystemExit(dry())
    if "--run" in sys.argv:
        raise SystemExit(run_all())
    print("需指定 --dry 或 --run")
    raise SystemExit(2)
