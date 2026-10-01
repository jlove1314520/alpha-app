"""先.四-二：供給緊縮衛星策略——計分／選股／模擬／績效指標（事前綁定定義，對應 docs/PREREG_supply_tightness_FINAL.md §4）。

不含任何可調參數的掃描；參數只以函式參數形式露出，供 §4(d).7 的參數高原與敏感度使用。
"""
from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pit import statutory_quarterly_pit_date  # noqa: E402

try:
    from scipy.stats import rankdata as _rankdata
except Exception:  # pragma: no cover
    _rankdata = None

COLS5 = ["I1", "I2", "I3", "I4", "I5"]
COLS_I1C = ["I1c", "I2", "I3", "I4", "I5"]
COLS_NO_I5 = ["I1", "I2", "I3", "I4"]
MIN_BUCKET = 8
VAL_END = pd.Timestamp("2024-12-31")


class Panel:
    def __init__(self, path: Path):
        with open(path, "rb") as f:
            d = pickle.load(f)
        self.__dict__.update(d)
        self.N = len(self.codes)
        self.T = len(self.cal)
        self.cal64 = self.cal.values
        self.pit = {p: statutory_quarterly_pit_date(p.end_time.normalize()) for p in self.qper}
        self._snap: dict = {}

    def latest_period(self, d: pd.Timestamp):
        best = None
        for p in self.qper:
            if pd.Timestamp(self.pit[p]) < d:
                best = p
        return best

    def snapshot(self, r: int) -> dict:
        if r in self._snap:
            return self._snap[r]
        d = self.cal[r]
        d64 = np.datetime64(d)
        lim64 = np.datetime64(d - pd.Timedelta(days=45))
        N = self.N
        alive = np.zeros(N, bool)
        p12 = np.full(N, np.nan)
        p60 = np.full(N, np.nan)
        for j in range(N):
            ods = self.own_dates[j]
            k = int(np.searchsorted(ods, d64, side="left"))
            if k == 0 or ods[k - 1] < lim64:
                continue
            alive[j] = True
            adj = self.own_adj[j]
            if k >= 130:
                last = pd.Timestamp(ods[k - 1])
                tgt = np.datetime64(last - pd.DateOffset(months=12))
                b = int(np.searchsorted(ods, tgt, side="right")) - 1
                if b >= 0:
                    p12[j] = adj[k - 1] / adj[b] - 1
            if k > 61:
                p60[j] = adj[k - 1] / adj[k - 61] - 1
        per = self.latest_period(d)
        qi = self.qper.get_loc(per)
        S = {"alive": alive, "p12": p12, "p60": p60, "period": per, "date": d, "row": r}
        for k in ("I1", "I1c", "I2", "I3", "I4"):
            S[k] = self.QM[k][qi]
        S["I5"] = self._i5(d)
        self._snap[r] = S
        return S

    def _i5(self, d: pd.Timestamp) -> np.ndarray:
        mp = pd.Period(d, "M") - (1 if d.day >= 10 else 2)

        def yoy3(p):
            a = self.mper.get_loc(p - 2)
            b = self.mper.get_loc(p)
            c = self.mper.get_loc(p - 14)
            e = self.mper.get_loc(p - 12)
            cur = self.MM[a:b + 1]
            prv = self.MM[c:e + 1]
            bad = np.isnan(cur).any(0) | np.isnan(prv).any(0)
            ps = prv.sum(0)
            with np.errstate(invalid="ignore", divide="ignore"):
                y = cur.sum(0) / ps - 1
            y[bad | (ps <= 0)] = np.nan
            return y

        return yoy3(mp) - yoy3(mp - 3)


def _rank_pct(v: np.ndarray) -> np.ndarray:
    out = np.full(len(v), np.nan)
    fin = np.isfinite(v)
    if fin.sum() == 0:
        return out
    if _rankdata is not None:
        out[fin] = _rankdata(v[fin], method="average") / fin.sum()
    else:
        out[fin] = pd.Series(v[fin]).rank(pct=True).values
    return out


def score_frame(P: Panel, S: dict, cols=COLS5, inc=None, min_ind=3) -> dict:
    ok = S["alive"].copy()
    if inc is not None:
        ok &= inc
    X = np.column_stack([S[c] for c in cols])
    nind = np.isfinite(X).sum(1)
    idx = np.flatnonzero(ok & (nind >= min_ind))
    if len(idx) == 0:
        return {"idx": idx, "score": np.array([]), "rk12": np.array([]), "rk60": np.array([]), "bucket": np.array([], int), "buckets": []}
    ind = P.industry[idx]
    u, cnt = np.unique(ind, return_counts=True)
    small = set(u[cnt < MIN_BUCKET])
    bucket = np.array(["其他" if (x in small or x == "其他") else x for x in ind])
    bcode, buniq = pd.factorize(bucket)
    Xs = X[idx]
    Z = np.full(Xs.shape, np.nan)
    rk12 = np.full(len(idx), np.nan)
    rk60 = np.full(len(idx), np.nan)
    p12, p60 = S["p12"][idx], S["p60"][idx]
    for b in range(len(buniq)):
        m = np.flatnonzero(bcode == b)
        rk12[m] = _rank_pct(p12[m])
        rk60[m] = _rank_pct(p60[m])
        for a in range(Xs.shape[1]):
            v = Xs[m, a]
            fin = v[np.isfinite(v)]
            if len(fin) < 2:
                continue
            lo, hi = np.quantile(fin, [0.01, 0.99])
            vc = np.clip(v, lo, hi)
            f2 = vc[np.isfinite(vc)]
            sd = f2.std(ddof=1)
            if sd > 0:
                Z[m, a] = (vc - f2.mean()) / sd
    with np.errstate(all="ignore"):
        cntz = np.isfinite(Z).sum(1)
        score = np.where(cntz > 0, np.nansum(Z, axis=1) / np.maximum(cntz, 1), np.nan)
    return {"idx": idx, "score": score, "rk12": rk12, "rk60": rk60, "bucket": bcode, "buckets": list(buniq)}


def lag_mask(F: dict, lag_key="p12", lag_thr=0.60) -> np.ndarray:
    rk = F["rk12"] if lag_key == "p12" else F["rk60"]
    with np.errstate(invalid="ignore"):
        return (rk <= lag_thr) & np.isfinite(F["score"])


def select(F: dict, prev, lag_key="p12", lag_thr=0.60, n=20, hyst=30) -> list:
    m = lag_mask(F, lag_key, lag_thr)
    pos = np.flatnonzero(m)
    if len(pos) == 0:
        return []
    order = pos[np.argsort(-F["score"][pos], kind="stable")]
    gidx = F["idx"][order]
    rank = {int(g): i + 1 for i, g in enumerate(gidx)}
    keep = [int(s) for s in prev if int(s) in rank and rank[int(s)] <= hyst]
    ks = set(keep)
    for g in gidx:
        if len(keep) >= n:
            break
        g = int(g)
        if g not in ks:
            keep.append(g)
            ks.add(g)
    return keep


def control_draw(F: dict, strat_sel, strat_prev, prev_ctrl, rng, lag_key="p12", lag_thr=0.60) -> list:
    m = lag_mask(F, lag_key, lag_thr)
    pool = F["idx"][m]
    pbuck = F["bucket"][m]
    pset = set(int(x) for x in pool)
    sprev = set(int(x) for x in strat_prev)
    n_keep = len([s for s in strat_sel if int(s) in sprev])
    keepable = [int(s) for s in prev_ctrl if int(s) in pset]
    if len(keepable) > n_keep:
        keepable = [int(x) for x in rng.choice(keepable, n_keep, replace=False)]
    chosen = list(keepable)
    cs = set(chosen)
    g2b = {int(g): int(b) for g, b in zip(pool, pbuck)}
    new_strat = [int(s) for s in strat_sel if int(s) not in sprev]
    need: dict[int, int] = {}
    for s in new_strat:
        b = g2b.get(s)
        need[b] = need.get(b, 0) + 1
    for b, c in need.items():
        cand = [int(g) for g, bb in zip(pool, pbuck) if int(bb) == b and int(g) not in cs] if b is not None else []
        take = min(c, len(cand))
        if take:
            pick = [int(x) for x in rng.choice(cand, take, replace=False)]
            chosen += pick
            cs.update(pick)
    target = len(strat_sel)
    if len(chosen) < target:
        rest = [int(g) for g in pool if int(g) not in cs]
        take = min(target - len(chosen), len(rest))
        if take:
            chosen += [int(x) for x in rng.choice(rest, take, replace=False)]
    return chosen


def rates(cost_mult: float, slippage_bps=5.0, instrument="normal"):
    from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate
    cfg = BacktestConfig(start_date="2014-01-01", end_date="2024-12-31", slippage_bps=slippage_bps,
                         cost_multiplier=cost_mult, instrument_type=instrument)
    return buy_leg_rate(cfg), sell_leg_rate(cfg)


class Sim:
    def __init__(self, P: Panel, buy_rate: float, sell_rate: float, w: float = 0.05, defer_max: int = 10):
        self.P, self.br, self.sr, self.w, self.dm = P, buy_rate, sell_rate, w, defer_max

    def run(self, rows, sels):
        P, N, T = self.P, self.P.N, self.P.T
        AO, ACFF, LU, LD = P.AO, P.ACFF, P.LU, P.LD
        sh = np.zeros(N)
        cash = 1.0
        eq = np.full(T, np.nan)
        sell_orders: dict[int, int] = {}
        buy_orders: dict[int, int] = {}
        stats = {"buy_deferred": 0, "buy_abandoned": 0, "sell_forced": 0, "traded_value": 0.0, "cost_paid": 0.0}
        nxt = 0
        r0 = rows[0]
        for t in range(r0, T):
            if nxt < len(rows) and rows[nxt] == t:
                tgt = [int(x) for x in sels[nxt]]
                ts = set(tgt)
                for i in np.flatnonzero(sh > 0):
                    if int(i) not in ts:
                        sell_orders[int(i)] = t + self.dm
                for i in list(sell_orders):
                    if i in ts:
                        del sell_orders[i]
                stats["buy_abandoned"] += len(buy_orders)
                buy_orders ={i: t + self.dm for i in tgt}
                nxt += 1
            ao = AO[t]
            prevc = ACFF[t - 1] if t > 0 else ACFF[t]
            pxo = np.where(np.isfinite(ao), ao, prevc)
            E = cash + float(np.nansum(sh * pxo))
            for i in list(sell_orders):
                if sh[i] <= 0:
                    del sell_orders[i]
                    continue
                if np.isfinite(ao[i]) and not LD[t, i]:
                    v = sh[i] * ao[i]
                    cash += v * (1 - self.sr)
                    stats["traded_value"] += v
                    stats["cost_paid"] += v * self.sr
                    sh[i] = 0.0
                    del sell_orders[i]
                elif t >= sell_orders[i]:
                    price = ACFF[t, i]
                    v = sh[i] * (price if np.isfinite(price) else 0.0)
                    cash += v * (1 - self.sr)
                    stats["traded_value"] += v
                    stats["cost_paid"] += v * self.sr
                    stats["sell_forced"] += 1
                    sh[i] = 0.0
                    del sell_orders[i]
            buys = []
            for i, exp in list(buy_orders.items()):
                if t > exp:
                    stats["buy_abandoned"] += 1
                    del buy_orders[i]
                    continue
                tradable = np.isfinite(ao[i])
                if not tradable:
                    continue
                held = sh[i] * ao[i]
                need = self.w * E - held
                if need < 0:
                    if not LD[t, i]:
                        v = -need
                        cash += v * (1 - self.sr)
                        sh[i] -= v / ao[i]
                        stats["traded_value"] += v
                        stats["cost_paid"] += v * self.sr
                        del buy_orders[i]
                    continue
                if LU[t, i]:
                    continue
                buys.append((i, need))
            if buys:
                tot = sum(v * (1 + self.br) for _, v in buys)
                f = min(1.0, cash / tot) if tot > 0 else 1.0
                for i, v in buys:
                    v = v * f
                    if v <= 0:
                        continue
                    sh[i] += v / ao[i]
                    cash -= v * (1 + self.br)
                    stats["traded_value"] += v
                    stats["cost_paid"] += v * self.br
                    del buy_orders[i]
            acf = ACFF[t]
            eq[t] = cash + float(np.sum(sh[sh > 0] * np.nan_to_num(acf[sh > 0])))
        stats["buy_abandoned"] += len(buy_orders)
        return eq[r0:], stats


def bench_returns(P: Panel, r0: int, buy_rate: float) -> np.ndarray:
    c = P.c50[r0 - 1:]
    r = c[1:] / c[:-1] - 1
    r = r.copy()
    r[0] = (1 + r[0]) * (1 - buy_rate) - 1
    return r


def eq_to_ret(eq: np.ndarray) -> np.ndarray:
    e = np.r_[1.0, eq]
    return e[1:] / e[:-1] - 1


def sortino(r: np.ndarray) -> float:
    r = np.asarray(r, float)
    dn = r[r < 0]
    dd = math.sqrt(float(np.mean(dn ** 2))) if len(dn) else 0.0
    return float(np.mean(r) / dd * math.sqrt(252)) if dd > 0 else float("nan")


def sharpe_d(r: np.ndarray) -> float:
    s = float(np.std(r, ddof=1))
    return float(np.mean(r) / s) if s > 0 else float("nan")


def mdd(r: np.ndarray) -> float:
    e = np.cumprod(1 + np.asarray(r, float))
    e = np.r_[1.0, e]
    return float((e / np.maximum.accumulate(e) - 1).min())


def total_ret(r: np.ndarray) -> float:
    return float(np.prod(1 + np.asarray(r, float)) - 1)


def moments(r: np.ndarray):
    r = np.asarray(r, float)
    m, s = r.mean(), r.std()
    z = (r - m) / s
    return float((z ** 3).mean()), float((z ** 4).mean())


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def psr_p(r: np.ndarray, sr0: float = 0.0) -> float:
    sr = sharpe_d(r)
    sk, ku = moments(r)
    den = 1 - sk * sr + (ku - 1) / 4 * sr * sr
    z = (sr - sr0) * math.sqrt(len(r) - 1) / math.sqrt(den)
    return 1 - norm_cdf(z)
