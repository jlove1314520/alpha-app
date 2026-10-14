# -*- coding: utf-8 -*-
"""先.九十七-2：core_tilt v2 第 1 階段——同一把量尺下，±2pp A_4pass 傾斜臂 vs 不傾斜臂（單發）。

定義全部事前綁定於 docs/PREREG_core_tilt_v2_stage1_FINAL.md（本程式啟動時核對該檔 SHA256，
與登記時寫進帳本的值不同就拒跑）。兩種模式：
  --coverage  登記前的資料覆蓋檢查（不是試驗、不計 N）：判定期每個再平衡日「有分數的成分」權重覆蓋率，
              任一 <80% → 印 STOP，不得登記。
  --run       單發執行（只跑一次）：結果檔 research/data/core_tilt_v2_stage1_result.json 已存在就拒跑。
只讀本機快取、0 次網路請求、不讀 holdout（2025-01-01 起；VAL_END 截止）。非投資建議。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import mem_guard  # noqa: E402,F401  多檔×全歷史常駐記憶體的安全閥（同 core_tilt_backtest.py）
import pit_mktcap_rank as pmr  # noqa: E402
import portfolio_backtest_v2 as pb2  # noqa: E402
from adjust import adjusted_price_series  # noqa: E402
from factor_ic import START_DATE  # noqa: E402
from factors import prepare_factors  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from score import load_industry_map  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation.costs import round_trip_cost_pct  # noqa: E402
from validation.holdout import TRAIN_END, VAL_END  # noqa: E402
from verify_taiwan50_rules import START, build_portfolio  # noqa: E402
from verify_taiwan50_rules_nav import nav_total_return  # noqa: E402

PREREG = ROOT / "docs" / "PREREG_core_tilt_v2_stage1_FINAL.md"
OUT = HERE / "data" / "core_tilt_v2_stage1_result.json"
COV_OUT = HERE / "data" / "core_tilt_v2_stage1_coverage.json"
TILT_PP = 0.02
INDUSTRY_BAND_PP = 0.03
REBAL_EVERY = 21
N_RANDOM = 1000
SEED = 20261014
COVERAGE_STOP = 0.80
TE_CAP = 0.03
MDD_CAP = 0.50
BEAR_WINDOWS = [("2015-04-01", "2016-01-31"), ("2018-01-01", "2018-12-31"),
                ("2020-01-01", "2020-03-31"), ("2022-01-01", "2022-10-31")]


def prereg_sha() -> str:
    return hashlib.sha256(PREREG.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ---------------------------------------------------------------- 資料
def load_inputs():
    etf = pmr.total_return_index("0050")
    days = [d for d in etf.index if START <= d <= VAL_END]
    port, sched, _tsmc, no_px = build_portfolio(days)          # 不傾斜臂＝第 0 階段量尺本身
    members = sorted({m for s in sched for m in s["members"]})
    market_df = prepare_market_data(load_dev("TaiwanStockPrice", "TAIEX", START_DATE))
    data, dropped = {}, []
    for sid in members:
        try:
            px = adjusted_price_series(sid, START_DATE)
            if px.empty or len(px) < 260:
                dropped.append((sid, "價格不足 260 日"))
                continue
            data[sid] = prepare_factors(sid, px, market_df, START_DATE)
        except Exception as e:  # noqa: BLE001  單檔失敗只讓該檔沒分數（Δw=0），不中斷
            dropped.append((sid, f"{type(e).__name__}: {str(e)[:80]}"))
    tri = {m: pmr.total_return_index_patched(m) for m in members}
    return dict(days=days, port=port, sched=sched, no_px=no_px, members=members, data=data,
                dropped=dropped, tri=tri, industry=load_industry_map(), market_df=market_df)


def scores_at(as_of: str, members: list[str], inp) -> pd.Series:
    """成分內 A_4pass equal 綜合分數（沿用 core_tilt_backtest.build_target_weights 的
    compute_composite_at_date＋_eligible；data 限縮成當期成分）。回傳 {sid: composite}，沒分數的不在內。"""
    sub = {m: inp["data"][m] for m in members if m in inp["data"]}
    if not sub:
        return pd.Series(dtype=float)
    liq = {m: pb2._liquidity_proxy_series(d) for m, d in sub.items()}
    cs = pb2._eligible(pb2.compute_composite_at_date(
        as_of, sub, inp["industry"], pb2.FACTOR_VERSIONS["A_4pass"], "equal", pd.Series(dtype=object), liq))
    cs = cs[cs["composite"].notna()]
    return cs.set_index("stock_id")["composite"].astype(float)


def tilt(w: pd.Series, comp: pd.Series, industry: dict) -> pd.Series:
    """build_target_weights 的映射：min-max→[-1,1]×2pp，截 ±2pp，w+Δw<0 截 0 再正規化；產業偏離 >±3pp 依原程式縮放。
    基準（產業代理）＝不傾斜臂當天權重 w。沒分數的成分 Δw=0。"""
    dev = pd.Series(0.0, index=w.index)
    c = comp.reindex(w.index).dropna()
    if len(c) >= 2 and c.max() > c.min():
        z = 2 * (c - c.min()) / (c.max() - c.min()) - 1
        dev.loc[c.index] = (z * TILT_PP).clip(-TILT_PP, TILT_PP)
    wt = (w + dev).clip(lower=0.0)
    wt = wt / wt.sum()
    ind = pd.Series({m: industry.get(m, "UNKNOWN") for m in w.index})
    act, prox = wt.groupby(ind).sum(), w.groupby(ind).sum()
    for g in act.index:
        d = act[g] - prox.get(g, 0.0)
        if abs(d) > INDUSTRY_BAND_PP:
            mem = ind[ind == g].index
            target = prox.get(g, 0.0) + np.sign(d) * INDUSTRY_BAND_PP
            scale = target / act[g] if act[g] > 0 else 1.0
            excess = (wt.loc[mem] * (1 - scale)).sum()
            wt.loc[mem] = wt.loc[mem] * scale
            oth = wt.index.difference(mem)
            if len(oth) and wt.loc[oth].sum() > 0:
                wt.loc[oth] = wt.loc[oth] + excess * (wt.loc[oth] / wt.loc[oth].sum())
    return wt / wt.sum()


# ---------------------------------------------------------------- 引擎
def segments(inp):
    """把期間切成「權重重設點」：成分異動（weight_day 收盤定權、effective 起生效）＋每 21 個交易日的傾斜再平衡
    （第 d 天收盤定權、隔天起生效）。回傳 [(base_day, seg_days, members, kind, cap_weights|None)]。"""
    days, sched = inp["days"], inp["sched"]
    cap = pmr.mktcap_panel(sorted({s["weight_day"] for s in sched})).set_index(["date", "stock_id"])["mktcap"]
    starts = {}
    for k, s in enumerate(sched):
        w = {m: float(cap.get((s["weight_day"], m), np.nan)) for m in s["members"]}
        w = {m: v for m, v in w.items() if v == v and v > 0}
        tot = sum(w.values())
        starts[s["effective"]] = ("change", s["weight_day"], pd.Series({m: v / tot for m, v in w.items()}))
    pos = {d: i for i, d in enumerate(days)}
    for i in range(0, len(days), REBAL_EVERY):
        if i + 1 < len(days) and days[i + 1] not in starts:
            starts[days[i + 1]] = ("tilt", days[i], None)
    eff = sorted(d for d in starts if d >= sched[0]["effective"])
    out = []
    for j, e in enumerate(eff):
        end = eff[j + 1] if j + 1 < len(eff) else None
        seg = [d for d in days[pos[e]:] if end is None or d < end]
        kind, base, w = starts[e]
        k = max(i for i, s in enumerate(sched) if s["effective"] <= e)
        k_end = sched[k + 1]["effective"] if k + 1 < len(sched) else None
        anchor = (sched[k]["weight_day"], tuple(d for d in days if d >= sched[k]["effective"] and (k_end is None or d < k_end)))
        out.append((base, seg, kind, w, anchor))
    return out


_PCACHE: dict = {}


def price_ratio(inp, base: str, seg: list[str], members, anchor) -> pd.DataFrame:
    """取價與 build_portfolio 完全同一套：以所屬成分異動的 weight_day 起整段 reindex→ffill(limit=5)→
    weight_day 沒價者剔除→再 ffill()。傾斜再平衡段從這份整段價格切出 [base]+seg 再除以 base 價，
    中途停牌的成分沿用舊價（不因再平衡日剛好沒價而被剔除）。"""
    wd, rng = anchor
    cols = {}
    for m in members:
        key = (m, wd, rng[0] if rng else None)
        if key not in _PCACHE:
            p = inp["tri"][m].reindex(list(dict.fromkeys([wd] + list(rng)))).ffill(limit=5)
            _PCACHE[key] = None if pd.isna(p.iloc[0]) else p.ffill()
        p = _PCACHE[key]
        if p is None:
            continue
        q = p.reindex([base] + seg)
        cols[m] = q / q.iloc[0]
    return pd.DataFrame(cols)


def simulate(inp, segs, score_fn, cost_rt: float):
    """回傳 (untilted_gross, untilted_net, tilted_gross, tilted_net, rebalance_log)，皆為 days 上的日報酬。
    score_fn(base_day, members) → 分數 Series；None 代表不傾斜臂。"""
    idx = pd.Index(inp["days"])
    ug, tg = pd.Series(np.nan, index=idx), pd.Series(np.nan, index=idx)
    ucost, tcost = pd.Series(0.0, index=idx), pd.Series(0.0, index=idx)
    w_u = w_t = None            # 上一段結束時漂移後的權重
    log = []
    for base, seg, kind, capw, anchor in segs:
        if kind == "change":
            new_u = capw
        else:
            new_u = w_u
        pr = price_ratio(inp, base, seg, new_u.index, anchor)
        new_u = new_u.reindex(pr.columns).fillna(0.0)
        comp = score_fn(base, list(new_u.index)) if score_fn else pd.Series(dtype=float)
        new_t = tilt(new_u / new_u.sum(), comp, inp["industry"]) if score_fn else new_u / new_u.sum()
        # 成本：單邊換手 × 來回成本（加在本段第一天）
        if w_u is not None:
            tu = 0.5 * (new_u / new_u.sum()).sub(w_u, fill_value=0.0).abs().sum()
            tt = 0.5 * new_t.sub(w_t, fill_value=0.0).abs().sum()
        else:
            tu = tt = 0.0
        ucost.loc[seg[0]] += tu * cost_rt
        tcost.loc[seg[0]] += tt * cost_rt
        vu = (pr * new_u).sum(axis=1)                       # 不傾斜：權重和可 <1（同量尺：base 沒價者剔除不補）
        vt = (pr * new_t.reindex(pr.columns).fillna(0.0)).sum(axis=1)
        ug.loc[seg] = (vu / vu.shift(1)).iloc[1:].to_numpy() - 1
        tg.loc[seg] = (vt / vt.shift(1)).iloc[1:].to_numpy() - 1
        last = pr.iloc[-1]
        w_u = (new_u * last) / (new_u * last).sum()
        w_t = (new_t.reindex(pr.columns).fillna(0.0) * last) / (new_t.reindex(pr.columns).fillna(0.0) * last).sum()
        n_sc = len(comp)
        cov = float((new_u / new_u.sum()).reindex(comp.index).fillna(0).sum()) if score_fn else None
        log.append({"base": base, "kind": kind, "n_members": int(len(new_u)), "n_scored": n_sc,
                    "coverage_w": round(cov, 4) if cov is not None else None,
                    "turnover_untilted": round(float(tu), 4), "turnover_tilted": round(float(tt), 4)})
    return ug, ug - ucost, tg, tg - tcost, log


# ---------------------------------------------------------------- 統計
def cagr(r: pd.Series) -> float:
    r = r.dropna()
    return float((1 + r).prod() ** (252 / len(r)) - 1) if len(r) else float("nan")


def mdd(r: pd.Series) -> float:
    eq = (1 + r.dropna()).cumprod()
    return float((eq / eq.cummax() - 1).min())


def te(a: pd.Series, b: pd.Series) -> float:
    d = (a - b).dropna()
    return float(d.std() * np.sqrt(252))


def val(r: pd.Series) -> pd.Series:
    return r[(r.index > TRAIN_END) & (r.index <= VAL_END)]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--coverage", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--registered-id", type=int)
    a = ap.parse_args()
    if a.run:
        if OUT.exists():
            raise SystemExit(f"{OUT.name} 已存在：本試驗只准跑一次，拒跑")
        if not a.registered_id:
            raise SystemExit("--run 需要 --registered-id（先登記才准執行）")
    inp = load_inputs()
    print(f"成分聯集 {len(inp['members'])} 檔；有因子資料 {len(inp['data'])} 檔；剔除 {len(inp['dropped'])}", flush=True)
    segs = segments(inp)
    cost_rt = round_trip_cost_pct()

    if a.coverage:
        # 只需各再平衡日的權重與分數，不計報酬
        _, _, _, _, log = simulate(inp, segs, lambda b, m: scores_at(b, m, inp), cost_rt)
        vlog = [r for r in log if TRAIN_END < r["base"] <= VAL_END]
        low = [r for r in vlog if r["coverage_w"] < COVERAGE_STOP]
        res = {"generated_at": datetime.now().isoformat(timespec="seconds"), "task": "先.九十七-2 登記前覆蓋檢查（不計 N）",
               "n_rebalances_val": len(vlog), "min_coverage_val": min(r["coverage_w"] for r in vlog),
               "median_coverage_val": float(np.median([r["coverage_w"] for r in vlog])),
               "min_coverage_all": min(r["coverage_w"] for r in log),
               "n_below_80_val": len(low), "below_80_val": low,
               "verdict": "STOP_不登記" if low else "GO_可登記",
               "dropped_members": inp["dropped"], "rebalance_log": log}
        COV_OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items() if k not in ("rebalance_log", "below_80_val")}, ensure_ascii=False, indent=1))
        # 引擎確認：不傾斜臂重算要等於量尺
        ug, _, tg, _, _ = simulate(inp, segs, None, cost_rt)
        diff = (ug - inp["port"]).abs().max()
        print(f"引擎核對：重算不傾斜臂 vs build_portfolio 最大日報酬差 {diff:.2e}")
        return 0

    sha = prereg_sha()
    print(f"PREREG SHA256={sha}")
    rng = np.random.default_rng(SEED)
    real_fn = lambda b, m: scores_at(b, m, inp)  # noqa: E731
    cache = {}

    def cached(b, m):
        k = (b, tuple(m))
        if k not in cache:
            cache[k] = real_fn(b, m)
        return cache[k]

    ug, un, tg, tn, log = simulate(inp, segs, cached, cost_rt)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "task": "先.九十七-2 core_tilt v2 第 1 階段單發",
           "trial_id": a.registered_id, "prereg": str(PREREG.relative_to(ROOT)).replace("\\", "/"), "prereg_sha256": sha,
           "cost_round_trip": cost_rt, "period_all": [inp["days"][0], inp["days"][-1]], "judgment": [TRAIN_END, VAL_END]}
    eng = float((ug - inp["port"]).abs().max())
    out["engine_check_max_abs_diff_vs_build_portfolio"] = eng
    if not eng < 1e-9:
        raise SystemExit(f"引擎核對失敗：重算不傾斜臂與 build_portfolio 最大差 {eng:.2e} ≥ 1e-9，不跑（PREREG 第 1 節）")
    out["engine_check_std"] = {"untilted": float(val(ug).std()), "tilted": float(val(tg).std()),
                               "min_members": min(r["n_members"] for r in log)}

    def excess(mult: float):
        u = ug - (ug - un) * mult
        t = tg - (tg - tn) * mult
        return cagr(val(t)) - cagr(val(u)), u, t

    ex = {}
    for m in (1, 2, 3):
        e, u, t = excess(m)
        ex[f"{m}x"] = {"excess_cagr": e, "tilted_cagr": cagr(val(t)), "untilted_cagr": cagr(val(u))}
    _, u1, t1 = excess(1)

    # 天條一
    surv = {"mdd_all": mdd(t1), "mdd_val": mdd(val(t1)), "bear": []}
    tx = inp["market_df"].set_index("date")["close"] if "close" in inp["market_df"] else None
    for s, e in BEAR_WINDOWS:
        rec = {"window": [s, e]}
        if tx is not None:
            w = tx[(tx.index >= s) & (tx.index <= e)]
            pk = w.idxmax()
            tr = w[w.index >= pk].idxmin()
            rec.update(taiex_peak=pk, taiex_trough=tr)
            seg = t1[(t1.index > pk) & (t1.index <= tr)]
            rec["tilted_drawdown_peak_to_trough"] = float((1 + seg).prod() - 1) if len(seg) else None
        rec["tilted_mdd_in_window"] = mdd(t1[(t1.index >= s) & (t1.index <= e)])
        surv["bear"].append(rec)
    survival_ok = all(x > -MDD_CAP for x in [surv["mdd_all"], surv["mdd_val"]] + [b["tilted_mdd_in_window"] for b in surv["bear"]])

    te_tu = te(val(t1), val(u1))
    # 隨機對照：每個再平衡日把成分內分數隨機重排
    rand = []
    for i in range(N_RANDOM):
        def perm(b, m):
            c = cached(b, m)
            return pd.Series(rng.permutation(c.to_numpy()), index=c.index)
        rug, run_, rtg, rtn, _ = simulate(inp, segs, perm, cost_rt)
        rand.append(cagr(val(rtn)) - cagr(val(run_)))
        if (i + 1) % 100 == 0:
            print(f"  隨機對照 {i + 1}/{N_RANDOM}", flush=True)
    p95 = float(np.percentile(rand, 95))
    gates = {"1_excess_gt0_1x": ex["1x"]["excess_cagr"] > 0,
             "2_excess_gt0_2x_3x": ex["2x"]["excess_cagr"] > 0 and ex["3x"]["excess_cagr"] > 0,
             "3_beats_random_p95": ex["1x"]["excess_cagr"] > p95,
             "4_survival_mdd_le_50": survival_ok,
             "5_te_tilted_vs_untilted_le_3pct": te_tu <= TE_CAP}
    verdict = "VIOLATES_SURVIVAL" if not survival_ok else ("PASS" if all(gates.values()) else "FAIL")
    # 只報告：對 0050 官方 NAV 含息
    nav_r, _ = nav_total_return(inp["days"])
    mkt = pmr.total_return_index("0050").reindex(inp["days"]).pct_change()
    rep = {}
    for nm, r in (("tilted", t1), ("untilted", u1)):
        rr = {"vs_nav_excess_cagr": cagr(val(r)) - cagr(val(nav_r)), "te_vs_nav": te(val(r), val(nav_r)),
              "vs_market_excess_cagr": cagr(val(r)) - cagr(val(mkt))}
        yrs = {}
        for y, gr in val(pd.DataFrame({"a": r, "n": nav_r})).groupby(pd.to_datetime(val(r).index).year):
            yrs[int(y)] = round(float((1 + gr["a"]).prod() - (1 + gr["n"]).prod()), 4)
        rr["by_year_vs_nav"] = yrs
        rr["years_beating_nav"] = f"{sum(v > 0 for v in yrs.values())}/{len(yrs)}"
        rep[nm] = rr
    rep["nav_cagr_val"], rep["market_0050_cagr_val"] = cagr(val(nav_r)), cagr(val(mkt))
    vlog = [r for r in log if TRAIN_END < r["base"] <= VAL_END]
    out.update({
        "primary": {"excess_by_cost": ex, "random_control": {"n": N_RANDOM, "seed": SEED, "p95": p95,
                    "mean": float(np.mean(rand)), "rank_pct": float((np.array(rand) < ex["1x"]["excess_cagr"]).mean())},
                    "te_tilted_vs_untilted_val": te_tu, "survival": surv, "gates": gates, "verdict": verdict},
        "train_report_only": {"excess_cagr_1x": cagr(t1[t1.index <= TRAIN_END]) - cagr(u1[u1.index <= TRAIN_END])},
        "report_only_vs_0050_nav": rep,
        "other": {"coverage_val_min": min(r["coverage_w"] for r in vlog),
                  "mean_turnover_tilted": float(np.mean([r["turnover_tilted"] for r in log])),
                  "mean_turnover_untilted": float(np.mean([r["turnover_untilted"] for r in log])),
                  "n_rebalances": len(log), "dropped_members": inp["dropped"]},
        "daily_val_sharpe_tilted_minus_untilted": float(val(t1 - u1).mean() / val(t1 - u1).std() * np.sqrt(252)),
        "n_obs_val": int(val(t1).notna().sum()), "requests_made": 0,
    })
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out["primary"], ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
