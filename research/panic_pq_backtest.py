# -*- coding: utf-8 -*-
"""先.一五〇-2 第 2 步：恐慌求生日買進 PQ 成長股——格點回測＋對照組（描述性樣本內最優化，規格 research/PANIC_PQ_SPEC.md §3）。

零網路請求：只讀本機 FinMind 快取與 data/panic_pq/ 元件輸出，一律截到 2024-12-31（holdout 不碰）。
不寫 TRIALS_LEDGER（照 SPEC：同先.一五〇-1 描述性最優化，心跳寫 PROGRESS_HEARTBEAT.jsonl）。

〔自行裁量〕（SPEC 沒寫死、這裡選定並寫進輸出）：
 1. 共同期間 2007-05-15（PQ 名單第一個可得日）～2024-12-31；之前的恐慌事件沒有名單可買，不計。
 2. 報酬用 close/(close−spread)＝收盤÷官方參考價串接，除權息日不掉價（股利視同再投入）。
 3. 持有期 H 從觸發日起算：出場日＝觸發日後第 H 個交易日收盤；分批 k 日在前 k 個交易日開盤買。
 4. 停損／止盈用每日收盤判斷、當日收盤出場（比盤中觸價保守）。
 5. 一價到底（最高＝最低）且漲跌幅達限制＝鎖住，當天不能買賣，順延到下一個能交易的日子；無成交量同。
 6. 上一個事件還沒出場時，新的觸發日略過（資金只有一份，不加碼重疊）。
 7. 槓桿：每日 L×組合報酬 −（L−1）×6.5%/252×持股比例；現金不計利息。
 8. 循環股高峰濾網(b)：單季毛利率在自身近 20 季（含本季、至少 8 季）排名前 10%，且近四季 EPS÷觸發日收盤 >20%。
 9. 名單要求最新一季可得日在觸發日前 200 天內（過期名單不用）。
"""
from __future__ import annotations

import itertools
import json
import pickle
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from validation import holdout  # noqa: E402

RAW = HERE / "data" / "raw"
OUT = HERE / "data" / "panic_pq"
CACHE = OUT / "prices_wide.pkl"
START, END = "2007-05-15", "2024-12-31"
LOAD_START = "2007-01-01"
FIN = 0.065
FEE, TAX, SLIP = 0.001425, 0.003, 0.0005
TAX_ETF = 0.001

THETAS = [0.05, 0.10, 0.20, 0.30]
KS = [1, 5, 10]
NS = [5, 10, 20]
HS = [20, 60, 120]
LISTS = ["strict", "mid", "loose"]
FILTERS = ["none", "peak"]
TPS = [None, 0.30]
SLS = [None, -0.15]
LS = [1.0, 1.5, 2.0, 3.0]
MERGE_DAYS = 20

LIST_RULES = {
    "strict": dict(gm=2, om=2, rev=0.25, eps=0.30, ttm=10),
    "mid": dict(gm=1, om=1, rev=0.15, eps=0.20, ttm=5),
    "loose": dict(gm=1e-12, om=1e-12, rev=1e-12, eps=1e-12, ttm=1e-12),
}


# ---------------------------------------------------------------- 資料
def _files_by_id(dataset):
    out = defaultdict(list)
    for p in RAW.glob(f"{dataset}__*.parquet"):
        parts = p.name.split("__")
        if len(parts) >= 2:
            out[parts[1]].append(p)
    return out


def load_prices(ids):
    if CACHE.exists():
        obj = pickle.loads(CACHE.read_bytes())
        if set(ids) <= set(obj["ids"]):
            return obj
    files = _files_by_id("TaiwanStockPrice")
    cal = pd.read_csv(OUT / "panic_daily.csv", usecols=["date"])["date"]
    cal = cal[(cal >= LOAD_START) & (cal <= END)].tolist()
    pos = {d: i for i, d in enumerate(cal)}
    T, S = len(cal), len(ids)
    O = np.full((T, S), np.nan); C = np.full((T, S), np.nan)
    R = np.full((T, S), np.nan); LK = np.zeros((T, S), bool)
    cols = ["date", "open", "max", "min", "close", "spread", "Trading_Volume"]
    for j, sid in enumerate(ids):
        fr = []
        for p in files.get(sid, []):
            try:
                fr.append(pd.read_parquet(p, columns=cols))
            except Exception as e:
                print(f"[warn] {p.name}: {e}")
        if not fr:
            continue
        d = pd.concat(fr).drop_duplicates("date", keep="last")
        d = d[(d["date"] >= LOAD_START) & (d["date"] <= END) & (d["Trading_Volume"] > 0) & (d["close"] > 0)]
        d = d[d["date"].isin(pos)]
        idx = d["date"].map(pos).values
        ref = (d["close"] - d["spread"]).values
        r = np.where(ref > 0, d["close"].values / np.where(ref > 0, ref, 1), np.nan)
        lim = np.where(d["date"].values < "2015-06-01", 0.07, 0.10)
        locked = (d["max"].values == d["min"].values) & (np.abs(r - 1) >= lim - 0.006)
        O[idx, j] = d["open"].values; C[idx, j] = d["close"].values
        R[idx, j] = r; LK[idx, j] = locked
        if j % 300 == 0:
            print(f"價格 {j}/{S}", flush=True)
    obj = dict(ids=list(ids), cal=cal, O=O, C=C, R=R, LK=LK)
    CACHE.write_bytes(pickle.dumps(obj))
    return obj


def pq_table():
    p = pd.read_csv(OUT / "pq_snapshots.csv", dtype={"stock_id": str})
    p = p.sort_values(["stock_id", "quarter"])
    # 毛利率在自身近 20 季的百分位（含本季、至少 8 季），PIT：只用本季以前
    def _pct(s):
        return s.rolling(20, min_periods=8).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True)
    p["gm_pct20"] = p.groupby("stock_id")["gm"].transform(_pct)
    return p


def list_on(pq, date, rule, filt, close_row, sid_pos, n):
    a = pq[pq["avail"] <= date]
    a = a.groupby("stock_id").tail(1)
    a = a[pd.to_datetime(a["avail"]) >= pd.Timestamp(date) - pd.Timedelta(days=200)]
    r = LIST_RULES[rule]
    m = ((a["gm_yoy_pp"] >= r["gm"]) & (a["om_yoy_pp"] >= r["om"]) & (a["rev3m_yoy"] >= r["rev"])
         & (a["eps_yoy"] >= r["eps"]) & (a["eps_ttm"] >= r["ttm"]))
    a = a[m]
    a = a[a["stock_id"].isin(sid_pos)]
    if filt == "peak" and len(a):
        px = np.array([close_row[sid_pos[s]] for s in a["stock_id"]])
        ep = a["eps_ttm"].values / px
        peak = (a["gm_pct20"].values >= 0.9) & (ep > 0.20)
        a = a[~np.nan_to_num(peak, nan=0).astype(bool)]
    return a.sort_values("om_yoy_pp", ascending=False)["stock_id"].head(n).tolist()


# ---------------------------------------------------------------- 模擬
def stock_path(P, j, e, k, H, tp, sl, cm, etf=False):
    """回傳 (觸發日 e 起每日價值陣列〔投入 1 元〕, 出場日 index, 該筆淨報酬)。"""
    C, R, O, LK = P["C"], P["R"], P["O"], P["LK"]
    T = len(P["cal"])
    X = min(e + H, T - 1)
    buy_c = (FEE + SLIP) * cm
    sell_c = (FEE + (TAX_ETF if etf else TAX) + SLIP) * cm
    alive = np.where(~np.isnan(C[:, j]))[0]
    last_alive = alive[-1] if len(alive) else -1
    cash, sh, basis, pending = 1.0, 0.0, 0.0, k
    vals = [1.0]
    t = e
    for t in range(e + 1, T):
        has = not np.isnan(C[t, j])
        tradable = has and not LK[t, j] and O[t, j] > 0
        if sh > 0 and has and not np.isnan(R[t, j]):
            sh *= R[t, j]
        # 分批：第 i 批預定在 e+1+i 開盤，鎖住／停牌順延；超過出場日還沒買到就取消
        if pending > 0 and t <= X and t >= e + 1 + (k - pending) and tradable:
            amt = 1.0 / k
            cash -= amt; basis += amt
            sh += amt * (1 - buy_c) * C[t, j] / O[t, j]
            pending -= 1
        if t >= X:
            pending = 0
        hit = False
        if sh > 0 and pending == 0:
            ret = sh / basis - 1
            hit = (tp is not None and ret >= tp) or (sl is not None and ret <= sl)
        gone = t >= last_alive
        if sh > 0 and (((t >= X or hit) and tradable) or gone):
            cash += sh * (1 - sell_c); sh = 0.0
            vals.append(cash)
            break
        vals.append(cash + sh)
        if sh == 0 and pending == 0:
            break
    return np.array(vals), t, cash + sh - 1.0


def run_events(P, events, picks, k, H, tp, sl, cm, N, etf=False, cache=None):
    """events: 觸發日 index 清單；picks: 每個事件的股票 index 清單。回傳每日組合報酬（未槓桿）、持股比例、交易筆數。"""
    T = len(P["cal"])
    port_ret = np.zeros(T)
    inv = np.zeros(T)
    trades = []
    busy_until = -1
    used = 0
    for e, js in zip(events, picks):
        if e <= busy_until or not js:
            continue
        used += 1
        paths = []
        for j in js:
            key = (e, j, k, H, tp, sl, cm)
            if cache is not None and key in cache:
                v, x, r = cache[key]
            else:
                v, x, r = stock_path(P, j, e, k, H, tp, sl, cm, etf)
                if cache is not None:
                    cache[key] = (v, x, r)
            paths.append(v)
            trades.append(r)
        L = max(len(v) for v in paths)
        tot = np.full(L, 0.0)
        for v in paths:
            vv = np.concatenate([v, np.full(L - len(v), v[-1])])
            tot += vv / N
        tot += (N - len(js)) / N  # 名單不足 N：剩餘留現金
        r = tot[1:] / tot[:-1] - 1
        end = min(e + L, T)
        port_ret[e + 1:end] = r[: end - e - 1]
        inv[e + 1:end] = len(js) / N
        busy_until = e + L - 1
    return port_ret, inv, trades, used


def metrics(port_ret, inv, L, s0):
    r = L * port_ret - (L - 1) * FIN / 252 * inv
    r = r[s0:]
    eq = np.cumprod(1 + r)
    yrs = len(r) / 252
    cagr = eq[-1] ** (1 / yrs) - 1 if eq[-1] > 0 else -1.0
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    sd = r.std()
    sharpe = r.mean() / sd * np.sqrt(252) if sd > 0 else 0.0
    return cagr, mdd, sharpe, eq


def main():
    t0 = time.time()
    pan = pd.read_csv(OUT / "panic_daily.csv")
    pq = pq_table()
    loose = pq[(pq["gm_yoy_pp"] > 0) & (pq["om_yoy_pp"] > 0) & (pq["rev3m_yoy"] > 0) & (pq["eps_yoy"] > 0) & (pq["eps_ttm"] > 0)]
    ids = sorted(set(loose["stock_id"])) + ["0050"]
    P = load_prices(ids)
    print(f"價格載入 {len(P['ids'])} 檔（{time.time()-t0:.0f}s）", flush=True)
    cal = P["cal"]; pos = {d: i for i, d in enumerate(cal)}
    sid_pos = {s: i for i, s in enumerate(P["ids"])}
    s0 = pos[min(d for d in cal if d >= START)]
    holdout.assert_no_holdout_leakage(pd.DataFrame({"date": cal}), date_col="date", context="panic_pq backtest")

    # 事件（20 日合併）
    ev = {}
    pan = pan[(pan["date"] >= START) & (pan["date"] <= END)]
    for th in THETAS:
        days = [pos[d] for d in pan.loc[pan["frac_limit_down"] >= th, "date"] if d in pos]
        out, last = [], -10**9
        for d in days:
            if d - last > MERGE_DAYS:
                out.append(d)
            last = d if d - last > MERGE_DAYS else last
        ev[th] = out
    print({th: len(v) for th, v in ev.items()})

    all_ev = sorted(set(itertools.chain(*ev.values())))
    lists = {}
    for e in all_ev:
        for rule, filt in itertools.product(LISTS, FILTERS):
            lists[(e, rule, filt)] = [sid_pos[s] for s in list_on(pq, cal[e], rule, filt, P["C"][e], sid_pos, max(NS))]

    cache = {}
    rows = []
    for th, k, N, H, rule, filt, tp, sl in itertools.product(THETAS, KS, NS, HS, LISTS, FILTERS, TPS, SLS):
        picks = [lists[(e, rule, filt)][:N] for e in ev[th]]
        pr, inv, tr, used = run_events(P, ev[th], picks, k, H, tp, sl, 1.0, N, cache=cache)
        for L in LS:
            cagr, mdd, sh, _ = metrics(pr, inv, L, s0)
            rows.append(dict(theta=th, k=k, N=N, H=H, list=rule, filt=filt, tp=tp or 0, sl=sl or 0, L=L,
                             cagr=cagr, mdd=mdd, sharpe=sh, n_trades=len(tr), events_used=used,
                             win=float(np.mean([x > 0 for x in tr])) if tr else np.nan,
                             avg_trade=float(np.mean(tr)) if tr else np.nan))
        if len(rows) % 400 == 0:
            print(f"格 {len(rows)}（{time.time()-t0:.0f}s）", flush=True)
    df = pd.DataFrame(rows)
    df["calmar"] = df["cagr"] / df["mdd"].abs().replace(0, np.nan)
    df["violates_survival"] = df["mdd"] < -0.50
    df.to_csv(OUT / "grid_results.csv", index=False)

    # 最佳組 2× 成本敏感度
    ok = df[~df["violates_survival"] & (df["n_trades"] >= 10)]
    best = ok.sort_values("calmar", ascending=False).iloc[0].to_dict()
    picks = [lists[(e, best["list"], best["filt"])][: int(best["N"])] for e in ev[best["theta"]]]
    tpv = best["tp"] or None; slv = best["sl"] or None
    pr, inv, tr, _ = run_events(P, ev[best["theta"]], picks, int(best["k"]), int(best["H"]), tpv, slv, 2.0, int(best["N"]))
    c2 = metrics(pr, inv, best["L"], s0)
    pr1, inv1, tr1, _ = run_events(P, ev[best["theta"]], picks, int(best["k"]), int(best["H"]), tpv, slv, 1.0, int(best["N"]))
    best_eq = metrics(pr1, inv1, best["L"], s0)[3]
    best_trades = [dict(event=cal[e], picks=[P["ids"][j] for j in js]) for e, js in zip(ev[best["theta"]], picks)]

    # 對照 A：不分恐慌、每季可得日換 PQ 名單（同 N、名單、濾網）
    j50 = sid_pos["0050"]
    avails = sorted(d for d in pq["avail"].unique() if START <= d <= END)
    reb = sorted({pos[min(c for c in cal if c >= a)] for a in avails if any(c >= a for c in cal)})
    ctlA = []
    for N, rule, filt in itertools.product(NS, LISTS, FILTERS):
        T = len(cal); pr = np.zeros(T); inv = np.zeros(T); ntr = 0
        for i, e in enumerate(reb):
            nxt = reb[i + 1] if i + 1 < len(reb) else T - 1
            js = [sid_pos[s] for s in list_on(pq, cal[e], rule, filt, P["C"][e], sid_pos, N)]
            if not js:
                continue
            a, b, trd, _ = run_events(P, [e], [js], 1, nxt - e, None, None, 1.0, N)
            pr[e + 1: nxt + 1] = a[e + 1: nxt + 1]; inv[e + 1: nxt + 1] = b[e + 1: nxt + 1]; ntr += len(trd)
        for L in (1.0, 2.0):
            cagr, mdd, sh, _ = metrics(pr, inv, L, s0)
            ctlA.append(dict(N=N, list=rule, filt=filt, L=L, cagr=cagr, mdd=mdd, sharpe=sh, n_trades=ntr))
    # 對照 B：只看恐慌、觸發後買 0050（同 θ、k、H）
    ctlB = []
    for th, k, H in itertools.product(THETAS, KS, HS):
        pr, inv, tr, used = run_events(P, ev[th], [[j50]] * len(ev[th]), k, H, None, None, 1.0, 1, etf=True)
        for L in (1.0, 2.0):
            cagr, mdd, sh, _ = metrics(pr, inv, L, s0)
            ctlB.append(dict(theta=th, k=k, H=H, L=L, cagr=cagr, mdd=mdd, sharpe=sh, events_used=used))
    # 對照 C：0050 買進持有（總報酬）
    r50 = np.nan_to_num(P["R"][:, j50] - 1, nan=0.0)
    c_cagr, c_mdd, c_sh, c_eq = metrics(r50, np.ones(len(cal)), 1.0, s0)

    res = dict(generated=time.strftime("%Y-%m-%dT%H:%M:%S"), period=[START, END], network_requests=0,
               events={str(k): [cal[e] for e in v] for k, v in ev.items()},
               n_grid_engine=len(df) // len(LS), n_grid_total=len(df),
               best=best, best_cost2x=dict(cagr=c2[0], mdd=c2[1], sharpe=c2[2]), best_trades=best_trades,
               ctlA=ctlA, ctlB=ctlB, ctlC=dict(cagr=c_cagr, mdd=c_mdd, sharpe=c_sh),
               n_violates=int(df["violates_survival"].sum()), seconds=round(time.time() - t0))
    (OUT / "backtest_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    np.save(OUT / "best_equity.npy", best_eq)
    np.save(OUT / "c0050_equity.npy", c_eq)
    print(json.dumps({k: res[k] for k in ("best", "best_cost2x", "ctlC", "n_violates", "seconds")}, ensure_ascii=False, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
