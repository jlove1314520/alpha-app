"""先.四-二：供給緊縮衛星策略——單發執行協調器（定義全部事前綁定於 docs/PREREG_supply_tightness_FINAL.md）。

模式：
  --dry  只驗證資料與計分（換股日、可計分檔數、落後池檔數對照 precheck 的 per_date）與模擬器健全性；
         不印任何績效數字。
  --run  單發執行：全部關卡、敏感度、兩段、逐年、制度分表，寫 research/data/supply_tightness_result.json。
         執行期間只印進度標記，績效數字一律到 JSON 寫完後才印。
"""
from __future__ import annotations

import json
import math
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

PANEL = HERE / "data" / "supply_tightness_panel.pkl"
OUT = HERE / "data" / "supply_tightness_result.json"
PRE = HERE / "precheck_supply_tightness_results.json"
REG = HERE / "data" / "regimes_tw.json"
SEED = 20260930
K_CTRL = 200       # 隨機對照組（gate 5）抽樣次數
B_BOOT = 200       # 池內重抽 bootstrap 次數（gate 4）
K_BOOT = 40        # 每次 bootstrap 內的對照路徑數
N_WORKERS = 6
DEADLINES = ((3, 31), (5, 15), (8, 14), (11, 14))
CONS = "建材營造"

_P: C.Panel | None = None
_FC: dict = {}


# ───────────────────────── 基礎 ─────────────────────────
def _init_worker():
    global _P
    _P = C.Panel(PANEL)


def get_panel() -> C.Panel:
    global _P
    if _P is None:
        _P = C.Panel(PANEL)
    return _P


def stat_dates(P, years=range(2014, 2025), which=(0, 1, 2, 3)):
    out = []
    for y in years:
        for k in which:
            m, d = DEADLINES[k]
            dl = pd.Timestamp(y, m, d)
            r = int(P.cal.searchsorted(dl, side="right"))
            if r < P.T and P.cal[r] <= C.VAL_END:
                out.append(r)
    return out


def shifted(P, rows, delta_days):
    out = []
    for r in rows:
        t = P.cal[r] + pd.Timedelta(days=delta_days)
        rr = int(P.cal.searchsorted(t, side="left"))
        if rr < P.T - 1 and P.cal[rr] <= C.VAL_END and (not out or rr > out[-1]):
            out.append(rr)
    return out


def bimonthly(P):
    out = []
    for y in range(2014, 2025):
        for m in (1, 3, 5, 7, 9, 11):
            dl = pd.Timestamp(y, m, 15)
            r = int(P.cal.searchsorted(dl, side="right"))
            if r < P.T and pd.Timestamp(2014, 4, 1) <= P.cal[r] <= pd.Timestamp(2024, 11, 30):
                out.append(r)
    return out


VARIANT_COLS = {"base": C.COLS5, "I1c": C.COLS_I1C, "noI5": C.COLS_NO_I5, "no2018": C.COLS5, "nocons": C.COLS5}


def getF(P, r, variant="base", inc=None, use_cache=True):
    key = (r, variant)
    if inc is None and use_cache and key in _FC:
        return _FC[key]
    S = P.snapshot(r)
    if variant == "no2018" and S["period"].year == 2018:
        S = dict(S)
        S["I1"] = np.full_like(S["I1"], np.nan)
    incm = inc
    if variant == "nocons":
        incm = (P.industry != CONS) if inc is None else (inc & (P.industry != CONS))
    F = C.score_frame(P, S, VARIANT_COLS[variant], incm, 3)
    if inc is None and use_cache:
        _FC[key] = F
    return F


def make_sels(P, rows, variant="base", lag_key="p12", lag_thr=0.60, n=20, hyst=30, inc=None):
    sels, Fl, prev = [], [], []
    for r in rows:
        F = getF(P, r, variant, inc)
        sel = C.select(F, prev, lag_key, lag_thr, n, hyst)
        sels.append(sel)
        Fl.append(F)
        prev = sel
    return sels, Fl


def run_cfg(P, rows, cost=1.0, variant="base", lag_key="p12", lag_thr=0.60, n=20, hyst=30):
    sels, Fl = make_sels(P, rows, variant, lag_key, lag_thr, n, hyst)
    br, sr = C.rates(cost)
    eq, st = C.Sim(P, br, sr, w=1.0 / n).run(rows, sels)
    return {"eq": eq, "st": st, "sels": sels, "Fl": Fl, "r0": rows[0], "br": br, "rows": rows}


# ───────────────────────── 指標 ─────────────────────────
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


# ───────────────────────── 對照組／bootstrap 工作 ─────────────────────────
def _ctrl_path(P, rows, sels, Fl, rng, br, sr):
    prev_ctrl, cs = [], []
    for i in range(len(rows)):
        sprev = sels[i - 1] if i > 0 else []
        c = C.control_draw(Fl[i], sels[i], sprev, prev_ctrl, rng)
        cs.append(c)
        prev_ctrl = c
    eq, _ = C.Sim(P, br, sr, w=0.05).run(rows, cs)
    return C.sortino(C.eq_to_ret(eq)), C.total_ret(C.eq_to_ret(eq))


def task_ctrl(args):
    seed, rows, sels = args
    P = get_panel()
    Fl = [getF(P, r) for r in rows]
    br, sr = C.rates(1.0)
    rng = np.random.default_rng(seed)
    return _ctrl_path(P, rows, sels, Fl, rng, br, sr)


def task_boot(args):
    b, rows = args
    P = get_panel()
    rng = np.random.default_rng(SEED + 100000 + b)
    draw = rng.integers(0, P.N, P.N)
    inc = np.zeros(P.N, bool)
    inc[draw] = True
    sels, Fl = make_sels(P, rows, inc=inc)
    br, sr = C.rates(1.0)
    eq, _ = C.Sim(P, br, sr, w=0.05).run(rows, sels)
    s = C.sortino(C.eq_to_ret(eq))
    nulls = np.array([_ctrl_path(P, rows, sels, Fl, rng, br, sr)[0] for _ in range(K_BOOT)])
    return {"b": b, "sortino": s, "pct": float(100.0 * np.mean(nulls < s)), "null_mean": float(nulls.mean()),
            "n_unique": int(inc.sum())}


# ───────────────────────── dry ─────────────────────────
def dry():
    t0 = time.time()
    P = get_panel()
    print(f"面板載入 {time.time() - t0:.1f}s；股票 {P.N}，交易日 {P.T}", flush=True)
    rows = stat_dates(P)
    pre = json.load(open(PRE, encoding="utf-8"))["per_date"]
    assert len(rows) == len(pre) == 44, (len(rows), len(pre))
    dn, dp, dtop = [], [], []
    for r, p in zip(rows, pre):
        assert str(P.cal[r].date()) == p["date"], (P.cal[r].date(), p["date"])
        F = getF(P, r)
        m = C.lag_mask(F)
        dn.append(len(F["idx"]) - p["n_scorable"])
        dp.append(int(m.sum()) - p["lagpool_r12_adj"])
    print(f"44 個換股日日期與 precheck 完全一致；可計分檔數差(本-precheck) 平均 {np.mean(dn):+.1f} 範圍 [{min(dn)},{max(dn)}]；"
          f"落後池檔數差 平均 {np.mean(dp):+.1f} 範圍 [{min(dp)},{max(dp)}]", flush=True)
    sc = [len(getF(P, r)["idx"]) for r in rows]
    pl = [int(C.lag_mask(getF(P, r)).sum()) for r in rows]
    print(f"可計分檔數 最小 {min(sc)}；落後池 最小 {min(pl)}", flush=True)
    t1 = time.time()
    run = run_cfg(P, rows)
    eq = run["eq"]
    print(f"Sim 健全性：equity 全為有限正值={bool(np.isfinite(eq).all() and (eq > 0).all())}；長度={len(eq)}；"
          f"耗時 {time.time() - t1:.1f}s；買進放棄={run['st']['buy_abandoned']} 延後={run['st']['buy_deferred']} 強制賣出={run['st']['sell_forced']}", flush=True)
    npos = [len(s) for s in run["sels"]]
    print(f"每期持股數 最小 {min(npos)} 最大 {max(npos)}", flush=True)
    t2 = time.time()
    a = task_ctrl((SEED, rows, run["sels"]))
    print(f"對照路徑健全性：輸出有限={bool(np.isfinite(a[0]))}；耗時 {time.time() - t2:.1f}s", flush=True)
    t3 = time.time()
    x = task_boot((0, rows))
    print(f"bootstrap 單次健全性：pct 在[0,100]={0 <= x['pct'] <= 100}；耗時 {time.time() - t3:.1f}s；唯一股票數={x['n_unique']}", flush=True)
    return 0


# ───────────────────────── run ─────────────────────────
def run_all():
    T0 = time.time()

    def prog(msg):
        print(f"[{(time.time() - T0) / 60:.1f}m] {msg}", flush=True)

    P = get_panel()
    regimes = json.load(open(REG, encoding="utf-8"))["segments"]
    rows = stat_dates(P)
    res: dict = {"design_file": "docs/PREREG_supply_tightness_FINAL.md",
                 "design_sha256": "cad8741362daa350d501bf15f2c9bb313132d4be5d3aec52f368681def8f2740",
                 "run_date": "2026-09-30", "prereg_trial_id": 405, "n_rebalance": len(rows),
                 "operationalization": {
                     "rebalance": "各法定期限日(3/31,5/15,8/14,11/14)後第一個交易日，2014-04-01~2024-11-15，開盤價進場，漲停鎖住順延至多10個交易日",
                     "cost": "BacktestConfig 買賣分腿費率(手續費+證交稅+滑價5bps)×cost_multiplier；0050 僅期初買進成本",
                     "delisted_handling": "下市／停牌無開盤價者，賣單等待最多10個交易日，逾期以最後有效價強制賣出並計數",
                     "sortino": "engine 同定義：日報酬均值/√(負報酬平方均值)×√252，MAR=0",
                     "bench": "0050 總報酬(還原)，與策略同起點；期初扣同倍數買進成本",
                     "gate4": "以股票為單位 bootstrap(有放回抽宇宙，B=200)，每次重算計分/選股，對照組為同桶同落後濾網同換手之隨機路徑(每次40條)；百分位=策略 Sortino 在對照路徑中的位置；SD=200 次百分位之標準差；全樣本百分位取 gate5 之 200 條對照",
                     "gate7_survive": "各成本倍數下 Sortino≥同倍數成本之0050 Sortino 且 MDD>-50%；相鄰頻率／參數高原以 Sortino 差正負號與基準版一致為準",
                     "plateau": "遲滯 21/39；落後百分位 0.42/0.78(±30%相對)；持股數 15/25(等權1/n，僅報告)",
                     "semiannual": "兩相位：(3/31,8/14)與(5/15,11/14)；雙月頻：1,3,5,7,9,11 月 15 日後第一個交易日",
                     "phase_shift": "+30 日曆日、-14 日曆日後第一個交易日",
                     "two_segment": "2014-04~2019-12 與 2020-01~2024-12，相對 0050 超額報酬正負號",
                 }}

    # ---- 1. 樣本門檻（前置）
    Fs = [getF(P, r) for r in rows]
    nsc = [len(F["idx"]) for F in Fs]
    npool = [int(C.lag_mask(F).sum()) for F in Fs]
    prog("gate1 計數完成")
    res["gate1_sample"] = {"min_scorable": int(min(nsc)), "min_pool": int(min(npool)),
                           "per_date": [{"date": str(P.cal[r].date()), "n_scorable": a, "n_pool": b} for r, a, b in zip(rows, nsc, npool)],
                           "pass": bool(min(nsc) >= 300 and min(npool) >= 20)}

    # ---- 2. 主跑
    base = run_cfg(P, rows)
    prog("主跑完成")
    S = summarize(P, base, full=True, regimes=regimes)
    res["main"] = S
    sels = base["sels"]
    turn, held_delisted, cnt_sel = [], [], []
    prev = set()
    for s in sels:
        ss = set(s)
        turn.append(len(ss - prev) / max(len(ss), 1))
        held_delisted.append(float(np.mean([P.later_delisted[i] for i in s])) if s else float("nan"))
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

    # ---- 5. 對照組（gate 5）＋ bootstrap（gate 4）
    with ProcessPoolExecutor(max_workers=N_WORKERS, initializer=_init_worker) as ex:
        prog("對照組啟動")
        ctrl = list(ex.map(task_ctrl, [(SEED + 1 + k, rows, sels) for k in range(K_CTRL)], chunksize=4))
        prog("對照組完成")
        boot = list(ex.map(task_boot, [(b, rows) for b in range(B_BOOT)], chunksize=2))
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
        rr = base if m_ == 1.0 else run_cfg(P, rows, cost=m_)
        x = sm(rr)
        x["survive"] = bool(x["sortino"] >= x["bench_sortino"] and x["mdd"] > -0.5)
        costs[f"{m_:g}x"] = x
    res["gate7_costs"] = costs
    freq = {}
    freq["semi_A_3/31+8/14"] = sm(run_cfg(P, stat_dates(P, which=(0, 2))))
    freq["semi_B_5/15+11/14"] = sm(run_cfg(P, stat_dates(P, which=(1, 3))))
    freq["bimonthly"] = sm(run_cfg(P, bimonthly(P)))
    for v in freq.values():
        v["same_direction"] = bool(v["sortino_diff"] > 0) == bool(S["sortino_diff"] > 0)
    res["gate7_frequency"] = freq
    prog("成本與頻率完成")
    plate = {"hyst_21": sm(run_cfg(P, rows, hyst=21)), "hyst_39": sm(run_cfg(P, rows, hyst=39)),
             "lag_0.42": sm(run_cfg(P, rows, lag_thr=0.42)), "lag_0.78": sm(run_cfg(P, rows, lag_thr=0.78))}
    for v in plate.values():
        v["same_direction"] = bool(v["sortino_diff"] > 0) == bool(S["sortino_diff"] > 0)
    hold = {"n15": sm(run_cfg(P, rows, n=15)), "n25": sm(run_cfg(P, rows, n=25))}
    res["gate7_plateau"] = plate
    res["gate7_holdings_report_only"] = hold
    res["gate7"] = {"costs_pass": all(v["survive"] for v in costs.values()),
                    "frequency_pass": all(v["same_direction"] for v in freq.values()),
                    "plateau_pass": all(v["same_direction"] for v in plate.values())}
    res["gate7"]["pass"] = bool(all(res["gate7"].values()))
    prog("高原完成")

    # ---- 8. 制度分表：main.regimes 已含
    res["gate8_regimes"] = {"reported": True, "n_segments": len(S.get("regimes") or [])}
    res["gate9_free_params"] = {"count": 5, "list": ["持股數20", "價格落後百分位60%", "12個月回看窗", "遲滯帶30名", "最少可得指標數3"], "pass": True}

    # ---- 兩段方向一致
    ts = S["two_segments"]
    ea, eb = ts["2014-2019"]["excess"], ts["2020-2024"]["excess"]
    res["two_segment_consistency"] = {"excess_2014_2019": ea, "excess_2020_2024": eb, "excess_full": S["excess_total_ret"],
                                      "pass": bool((ea > 0) == (eb > 0) == (S["excess_total_ret"] > 0))}

    # ---- 敏感度（不影響判定）
    sens = {}
    sens["lag60d"] = sm(run_cfg(P, rows, lag_key="p60"))
    r_c = [r for r in rows if P.cal[r] >= pd.Timestamp("2019-05-01")]
    sens["pure_contract_I1c_2019on"] = sm(run_cfg(P, r_c, variant="I1c"))
    sens["baseline_same_window_2019on"] = sm(run_cfg(P, r_c))
    sens["ablation_noI5_I1toI4"] = sm(run_cfg(P, rows, variant="noI5"))
    sens["exclude_2018_I1"] = sm(run_cfg(P, rows, variant="no2018"))
    sens["exclude_construction"] = sm(run_cfg(P, rows, variant="nocons"))
    sens["phase_+30d"] = sm(run_cfg(P, shifted(P, rows, 30)))
    sens["phase_-14d"] = sm(run_cfg(P, shifted(P, rows, -14)))
    res["sensitivities"] = sens
    prog("敏感度完成")

    # ---- 判定（依 §4(d) 順序）
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
    res["survivorship_disclaimer"] = "下市股缺 39/92（42.4%），偏誤方向對策略有利，判讀從嚴"
    res["elapsed_min"] = (time.time() - T0) / 60

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
    prog(f"已寫入 {OUT}")
    return 0


if __name__ == "__main__":
    if "--dry" in sys.argv:
        raise SystemExit(dry())
    if "--run" in sys.argv:
        raise SystemExit(run_all())
    print("需指定 --dry 或 --run")
    raise SystemExit(2)
