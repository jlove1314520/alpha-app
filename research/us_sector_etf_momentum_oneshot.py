#!/usr/bin/env python3
"""美股產業 ETF 相對強度（產業輪動）跨市場單發（補.研究-產業ETF相對強度）。

規則全部照 docs/PREREG_US_SECTOR_ETF_MOMENTUM_FINAL.md（commit 後凍結），本程式不得加任何 PREREG 沒寫的選項。

用法：
  python research/us_sector_etf_momentum_oneshot.py selftest   合成價格自測（零網路、不讀真實資料）
  python research/us_sector_etf_momentum_oneshot.py probe      下載＋快取，只印各檔第一個／最後一個日期（第 10 關起點探測，不算任何報酬）
  python research/us_sector_etf_momentum_oneshot.py run        單發（驗證帽輪次跑；結果檔已存在就拒絕重跑）＋register_trial()

不讀 holdout：下載 end 設 2025-01-01（yfinance end 不含當天），讀進來立刻 holdout.assert_no_holdout_leakage()。
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RESEARCH = Path(__file__).resolve().parent
sys.path.insert(0, str(RESEARCH))
from validation import holdout  # noqa: E402
from validation import us_costs  # noqa: E402

SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
BENCH = "SPY"
DL_START, DL_END_EXCL = "1998-12-01", "2025-01-01"
FIRST_SIGNAL_MIN = pd.Timestamp("2000-03-31")
MAIN = {"lookback": 12, "skip": 1, "top": 3, "freq": 1}
GRID_LOOKBACK, GRID_TOP = (9, 12, 15), (2, 3, 4)
NOTIONAL = 100_000.0
N_RANDOM, SEED = 1000, 20261022
DRAWDOWN_WINDOWS = [("2000-03-01", "2002-10-31"), ("2007-10-01", "2009-03-31"),
                    ("2020-02-01", "2020-04-30"), ("2022-01-01", "2022-10-31")]
OUT_DIR = RESEARCH / "data" / "us_sector_etf"
CACHE = OUT_DIR / "prices.parquet"
RESULT = OUT_DIR / "result.json"
PREREG = "docs/PREREG_US_SECTOR_ETF_MOMENTUM_FINAL.md"


# ---------- 資料 ----------
def download() -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(SECTORS + [BENCH], start=DL_START, end=DL_END_EXCL, auto_adjust=True,
                      progress=False, threads=False)
    close = raw["Close"][SECTORS + [BENCH]].dropna(how="all")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    close.to_parquet(CACHE)
    return close


def load_prices(allow_download: bool) -> pd.DataFrame:
    close = pd.read_parquet(CACHE) if CACHE.exists() else (download() if allow_download else None)
    if close is None:
        raise RuntimeError(f"沒有快取 {CACHE}，先跑 probe")
    holdout.assert_no_holdout_leakage(close.reset_index().rename(columns={close.index.name or "index": "date"}),
                                      context="us_sector_etf_momentum_oneshot")
    return close


# ---------- 引擎 ----------
def per_side_rate(price: float, mult: float) -> float:
    shares = (NOTIONAL / 3) / price
    return us_costs.round_trip_cost_pct(price, shares) / 2 * mult


def schedule(close: pd.DataFrame, freq: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """(訊號日＝月底最後交易日, 執行日＝下一交易日)；訊號月份 % freq == 0、≥FIRST_SIGNAL_MIN、執行日在資料內。"""
    idx = close.index
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max().tolist()
    out = []
    for d in month_ends:
        if d < FIRST_SIGNAL_MIN or d.month % freq:
            continue
        pos = idx.get_loc(d)
        if pos + 1 < len(idx):
            out.append((d, idx[pos + 1]))
    return out


def momentum_rank(close: pd.DataFrame, signal_day: pd.Timestamp, lookback: int, skip: int) -> list[str]:
    idx = close.index
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max()
    me = month_ends[month_ends <= signal_day].tolist()
    if len(me) < lookback + 1:
        raise ValueError(f"{signal_day.date()} 月底價格不足 {lookback + 1} 個")
    t_end, t_start = me[-1 - skip], me[-1 - lookback]
    r = close.loc[t_end, SECTORS] / close.loc[t_start, SECTORS] - 1
    if r.isna().any():
        raise ValueError(f"{signal_day.date()} 動能有缺值 {list(r[r.isna()].index)}")
    return list(r.sort_values(ascending=False, kind="mergesort").index)


def simulate(close: pd.DataFrame, sched, picks_by_exec: dict, cost_mult: float) -> dict:
    """picks_by_exec：執行日 → 目標持有清單（等權）。回傳日淨值、每期報酬、交易筆數。"""
    px = close[SECTORS]
    execs = [e for _, e in sched]
    start, end = execs[0], px.index[-1]
    days = px.loc[start:end].index
    nav = pd.Series(index=days, dtype=float)
    value, hold_w, base_px = 1.0, {}, None
    trades, period_ret, cur_held = 0, [], set()
    exec_set = {e: i for i, e in enumerate(execs)}
    last_val = 1.0
    for d in days:
        if base_px is not None:
            value_now = sum(w * px.at[d, s] / base_px[s] for s, w in hold_w.items()) * value
        else:
            value_now = value
        if d in exec_set:
            target = picks_by_exec[d]
            tw = {s: 1 / len(target) for s in target}
            cur_w = {}
            if base_px is not None:
                tot = sum(w * px.at[d, s] / base_px[s] for s, w in hold_w.items())
                cur_w = {s: w * px.at[d, s] / base_px[s] / tot for s, w in hold_w.items()}
            cost = sum(abs(tw.get(s, 0) - cur_w.get(s, 0)) * per_side_rate(px.at[d, s], cost_mult)
                       for s in set(tw) | set(cur_w))
            trades += len(set(target) - cur_held) + len(cur_held - set(target))
            cur_held = set(target)
            if exec_set[d] > 0:
                period_ret.append(value_now / last_val - 1)
            value = value_now * (1 - cost)
            last_val = value
            hold_w, base_px = tw, {s: px.at[d, s] for s in tw}
            value_now = value
        nav[d] = value_now
    period_ret.append(nav.iloc[-1] / last_val - 1)
    return {"nav": nav, "period_ret": period_ret, "trades": trades}


def stats(nav: pd.Series) -> dict:
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    dd = nav / nav.cummax() - 1
    dr = nav.pct_change().dropna()
    down = dr[dr < 0]
    return {"final": float(nav.iloc[-1] / nav.iloc[0]), "cagr": float(cagr), "mdd": float(dd.min()),
            "sharpe_ann": float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else None,
            "sortino_ann": float(dr.mean() / down.std() * np.sqrt(252)) if len(down) > 1 else None,
            "calmar": float(cagr / -dd.min()) if dd.min() < 0 else None}


def window_dd(nav: pd.Series, a: str, b: str) -> float | None:
    s = nav.loc[a:b]
    return float((s / s.cummax() - 1).min()) if len(s) > 1 else None


def strat_picks(close, sched, lookback, skip, top):
    return {e: momentum_rank(close, s, lookback, skip)[:top] for s, e in sched}


def ew_picks(sched):
    return {e: list(SECTORS) for _, e in sched}


def run_cell(close, lookback, top, freq, cost_mult=1.0):
    sc = schedule(close, freq)
    st = simulate(close, sc, strat_picks(close, sc, lookback, MAIN["skip"], top), cost_mult)
    ew = simulate(close, sc, ew_picks(sc), 1.0)
    s1, s2 = stats(st["nav"]), stats(ew["nav"])
    return {"lookback": lookback, "top": top, "freq": freq, "cost_mult": cost_mult,
            "strategy": s1, "ew": s2, "excess_cagr_vs_ew": s1["cagr"] - s2["cagr"],
            "trades": st["trades"], "_sim": st, "_ew": ew, "_sched": sc}


def random_control(close, sched, top, n=N_RANDOM, seed=SEED):
    rng = random.Random(seed)
    finals = []
    for _ in range(n):
        picks = {e: rng.sample(SECTORS, top) for _, e in sched}
        finals.append(float(simulate(close, sched, picks, 1.0)["nav"].iloc[-1]))
    return finals


def moments(x):
    a = np.asarray(x, float)
    m, sd = a.mean(), a.std(ddof=1)
    z = (a - m) / a.std(ddof=0)
    return float(m / sd), int(len(a)), float((z ** 3).mean()), float((z ** 4).mean())


# ---------- 判定（照 PREREG 第 4 節，依序判） ----------
def judge(close) -> dict:
    main = run_cell(close, MAIN["lookback"], MAIN["top"], 1)
    nav = main["_sim"]["nav"]
    sc = main["_sched"]
    spy = close[BENCH].loc[nav.index[0]:]
    spy_s = stats(spy)
    res = {"main": {k: v for k, v in main.items() if not k.startswith("_")}, "spy": spy_s,
           "first_exec": str(nav.index[0].date()), "last_day": str(nav.index[-1].date()),
           "n_periods": len(main["_sim"]["period_ret"]),
           "drawdown_windows": {f"{a}~{b}": window_dd(nav, a, b) for a, b in DRAWDOWN_WINDOWS},
           "gates": {}}
    g = res["gates"]
    s = main["strategy"]
    g["survival"] = s["mdd"] >= -0.50
    g["gate1_net_positive"] = s["final"] > 1.0
    g["gate8_vs_ew_and_spy"] = s["cagr"] > main["ew"]["cagr"] and s["cagr"] > spy_s["cagr"]
    cm = {m: run_cell(close, MAIN["lookback"], MAIN["top"], 1, m) for m in (2.0, 3.0)}
    res["cost_sens"] = {f"{m}x": {"cagr": c["strategy"]["cagr"], "excess_vs_ew": c["excess_cagr_vs_ew"]}
                        for m, c in cm.items()}
    g["gate4_cost_2x3x"] = all(c["excess_cagr_vs_ew"] > 0 for c in cm.values())
    finals = random_control(close, sc, MAIN["top"])
    p95 = float(np.percentile(finals, 95))
    pct = float((np.asarray(finals) < s["final"]).mean() * 100)
    try:
        import trial_registry
        n_all = len(trial_registry.trial_rows()) + 1
    except Exception as e:  # 只報不否決，讀不到就照實記
        print(f"警告：讀不到全體 N（{e}），Bonferroni 只報不否決", file=sys.stderr)
        n_all = None
    bonf = 100 * (1 - 0.05 / n_all) if n_all else None
    res["random_control"] = {"n": N_RANDOM, "seed": SEED, "p95_final": p95, "strategy_percentile": pct,
                             "n_all": n_all, "bonferroni_pct": bonf,
                             "passes_bonferroni": (pct > bonf) if bonf else None}
    g["gate5_random_p95"] = s["final"] > p95
    g["gate6_trades_ge_100"] = main["trades"] >= 100
    grid = [run_cell(close, lb, tp, 1) for lb in GRID_LOOKBACK for tp in GRID_TOP]
    ex = [c["excess_cagr_vs_ew"] for c in grid]
    res["grid"] = [{"lookback": c["lookback"], "top": c["top"], "excess_vs_ew": c["excess_cagr_vs_ew"]} for c in grid]
    g["gate3_plateau"] = sum(e > 0 for e in ex) >= 7 and float(np.median(ex)) > 0
    fr = {f: run_cell(close, MAIN["lookback"], MAIN["top"], f) for f in (2, 3)}
    res["freq"] = {f"every_{f}m": c["excess_cagr_vs_ew"] for f, c in fr.items()}
    sign = np.sign(main["excess_cagr_vs_ew"])
    g["gate7_adjacent_freq"] = all(np.sign(c["excess_cagr_vs_ew"]) == sign for c in fr.values())
    yearly = {}
    ewn = main["_ew"]["nav"]
    for y in sorted(set(nav.index.year)):
        a, b = nav[nav.index.year == y], ewn[ewn.index.year == y]
        yearly[y] = float((a.iloc[-1] / a.iloc[0]) - (b.iloc[-1] / b.iloc[0]))
    res["yearly_excess_vs_ew"] = yearly
    res["years_beating_ew"] = f"{sum(v > 0 for v in yearly.values())}/{len(yearly)}"
    res["dsr_inputs_monthly"] = dict(zip(("sharpe", "n_obs", "skew", "kurtosis"), moments(main["_sim"]["period_ret"])))
    order = [("survival", None), ("gate1_net_positive", "gate1"), ("gate8_vs_ew_and_spy", "gate2"),
             ("gate4_cost_2x3x", "gate4"), ("gate5_random_p95", "gate5"), ("gate6_trades_ge_100", "gate6"),
             ("gate3_plateau", "gate3"), ("gate7_adjacent_freq", "gate3")]
    verdict, failed = "PASS", []
    for key, vocab in order:
        if not g[key]:
            verdict = "VIOLATES_SURVIVAL" if key == "survival" else "FAIL"
            failed = [] if vocab is None else [vocab]
            res["stopped_at"] = key
            break
    res["verdict"], res["failed_gates"] = verdict, failed
    return res


def cmd_run() -> int:
    if RESULT.exists():
        print(f"拒絕：{RESULT} 已存在＝已經單發過，PREREG 只准跑一次")
        return 2
    close = load_prices(allow_download=True)
    res = judge(close)
    res["generated_at"] = datetime.now().isoformat(timespec="seconds")
    RESULT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("yearly_excess_vs_ew",)},
                     ensure_ascii=False, indent=2, default=str))
    import trial_registry
    m, s, d = res["main"], res["main"]["strategy"], res["dsr_inputs_monthly"]
    rc = res["random_control"]
    tid, row = trial_registry.register_trial(
        track="US", name="美股產業ETF 12-1動能前3名月頻（補.研究-產業ETF相對強度）",
        design=f"{PREREG} 事前定死：9檔原始SPDR產業ETF、12-1月動能、前3名等權、月頻、下一交易日收盤執行、us_costs 1x；"
               f"檢定 {res['first_exec']}~{res['last_day']}（yfinance非官方），不碰holdout",
        result=(f"CAGR {s['cagr']:.2%}／MDD {s['mdd']:.2%}／被動等權 CAGR {m['ew']['cagr']:.2%}／SPY CAGR {res['spy']['cagr']:.2%}；"
                f"隨機挑產業 n={rc['n']} 百分位 {rc['strategy_percentile']:.1f}（p95 門檻）；交易 {m['trades']} 筆；"
                f"高原 {sum(c['excess_vs_ew'] > 0 for c in res['grid'])}/9 格超額為正；贏等權年數 {res['years_beating_ew']}"),
        verdict=res["verdict"],
        notes=(f"停在 {res.get('stopped_at', '全過')}；Bonferroni 百分位 {rc['bonferroni_pct']}（只報）；"
               "主格登記 1 筆，另跑高原 8 格＋相鄰頻率 2 格不選點（PREREG 第 5 節 [自行裁量]）；"
               "美股存活者偏誤但書：已下市股約 97%（抽樣 55／57）無價格來源（本檢定只用未下市 ETF）"),
        round_note="DevQueue 驗證帽單發（補.研究-產業ETF相對強度）",
        sharpe=d["sharpe"], n_obs=d["n_obs"], skew=d["skew"], kurtosis=d["kurtosis"], periods_per_year=12,
        failed_gates=res["failed_gates"] if res["verdict"] == "FAIL" else None,
        code_paths=["research/us_sector_etf_momentum_oneshot.py"],
    )
    print(f"已登記 #{tid}")
    return 0


def cmd_probe() -> int:
    close = download() if not CACHE.exists() else pd.read_parquet(CACHE)
    for c in close.columns:
        s = close[c].dropna()
        print(f"{c}: {s.index[0].date()} ～ {s.index[-1].date()}（{len(s)} 列）")
    if close.index.max() > pd.Timestamp(holdout.VAL_END):
        print("錯誤：資料超過 VAL_END")
        return 1
    return 0


def cmd_selftest() -> int:
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("1998-12-22", "2003-12-31")
    cols = SECTORS + [BENCH]
    rets = rng.normal(0.0003, 0.01, size=(len(idx), len(cols)))
    rets[:, SECTORS.index("XLK")] += 0.002  # 一檔持續強勢：應該幾乎每期都被選中
    close = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx, columns=cols)
    ok = True
    sc = schedule(close, 1)
    first = sc[0]
    ok &= first[0] >= FIRST_SIGNAL_MIN and first[1] > first[0]
    print(f"[{'OK' if ok else 'NG'}] 第一個訊號 {first[0].date()} 執行 {first[1].date()}")
    picks = strat_picks(close, sc, 12, 1, 3)
    frac = np.mean(["XLK" in p for p in picks.values()])
    t1 = frac > 0.9
    print(f"[{'OK' if t1 else 'NG'}] 強勢檔被選中比例 {frac:.2f}")
    # 零成本等權：跟手算一致
    ew = simulate(close, sc, ew_picks(sc), 0.0)
    manual, last = 1.0, None
    execs = [e for _, e in sc] + [close.index[-1]]
    for a, b in zip(execs[:-1], execs[1:]):
        manual *= float((close.loc[b, SECTORS] / close.loc[a, SECTORS]).mean())
    t2 = abs(ew["nav"].iloc[-1] - manual) < 1e-9
    print(f"[{'OK' if t2 else 'NG'}] 零成本等權淨值 {ew['nav'].iloc[-1]:.6f} vs 手算 {manual:.6f}")
    # 有成本一定比零成本低；交易筆數＞0
    st0 = simulate(close, sc, picks, 0.0)
    st1 = simulate(close, sc, picks, 1.0)
    t3 = st1["nav"].iloc[-1] < st0["nav"].iloc[-1] and st1["trades"] > 0
    print(f"[{'OK' if t3 else 'NG'}] 成本 1x {st1['nav'].iloc[-1]:.4f} < 0x {st0['nav'].iloc[-1]:.4f}，交易 {st1['trades']}")
    # 同一 seed 隨機控制組可重現
    r1, r2 = random_control(close, sc, 3, n=5), random_control(close, sc, 3, n=5)
    t4 = r1 == r2
    print(f"[{'OK' if t4 else 'NG'}] 隨機控制組同 seed 可重現")
    # 前視檢查：訊號只用 ≤ 訊號日、而且跳過最近 1 個月
    future = close.copy()
    future.loc[future.index > sc[5][0], SECTORS] *= rng.uniform(0.5, 2, size=len(SECTORS))
    t5 = momentum_rank(close, sc[5][0], 12, 1) == momentum_rank(future, sc[5][0], 12, 1)
    print(f"[{'OK' if t5 else 'NG'}] 改動訊號日之後的價格不影響排名")
    allok = ok and t1 and t2 and t3 and t4 and t5
    print("selftest", "全過" if allok else "有失敗")
    return 0 if allok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"selftest": cmd_selftest, "probe": cmd_probe, "run": cmd_run}.get(cmd, lambda: (print(__doc__), 2)[1])())
