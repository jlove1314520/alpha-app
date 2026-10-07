# -*- coding: utf-8 -*-
"""先.四十五-三：危機閘門 × 槓桿版 Bb-90 單發檢定（主線 A）。

定義全部事前綁定於 docs/PREREG_crisis_gate_leveraged_bb90.md（登記 #424，
SHA256=76c3eea0f3ccf504a21d3d4b2be9d47eb18938ea218105f96d89914bd0494222，commit 5cd891f41）。
**只跑一次；績效數字一律到 JSON 寫完後才印。** 不讀 2025-01-01 以後任何資料。

沿用 #421：合成 2 倍公式、成本、再平衡、期間（leveraged_bb90_backtest.py --formula 421 的 load_all／stats／dsr）。
本檔新增：月頻閘門訊號（S1 Faber 10 月均線、S2 Antonacci 12 月絕對動能、S3 BAA10Y > 12 月均值）、
時變目標權重的向量化模擬（執行前與 #421 逐日模擬比對一致才繼續）、隨機控制組、八市場複製。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.argv = [sys.argv[0], "--formula", "421"]          # 沿用 #421 公式（leveraged_bb90_backtest 於 import 時讀取）
import leveraged_bb90_backtest as LB  # noqa: E402
import core_allocation_backtest as CA  # noqa: E402
import trend_leverage_backtest as TL  # noqa: E402

PREREG = "docs/PREREG_crisis_gate_leveraged_bb90.md"
PREREG_SHA = "76c3eea0f3ccf504a21d3d4b2be9d47eb18938ea218105f96d89914bd0494222"
PREREG_TRIAL = 424
OUT = HERE / "data" / "crisis_gate_leveraged_bb90_result.json"
END = "2024-12-31"
SEED = 20261007
N_RAND = 1000
N_FAMILY = 42
MDD_LIMIT = -0.45
CAGR_MIN = 0.12
MARKETS = ["^GSPC", "^TWII", "^N225", "^FTSE", "^GDAXI", "^HSI", "^KS11", "^AXJO"]
CONFIGS = {"C5": LB.grid_target(0.65, 0.00, 0.35), "C6": LB.grid_target(0.50, 0.30, 0.20)}
SIGNALS = ("S1", "S2", "S3")
WARM = {"S1": 9, "S2": 12, "S3": 11}     # 第 k 個月底（0 起算）在 k < WARM 時歷史不足→開
KEYS = ["LTW", "LUS", "0050", "VTI", "IEF", "CASH"]
COL = {"0050": "r_0050", "VTI": "r_vti", "IEF": "r_ief", "CASH": "r_cash", "LTW": "r_ltw", "LUS": "r_lus"}
COST = np.array([[0.0, 1.0, 0.0, 1.0, 1.0, 0.0],                      # FX：LUS、VTI、IEF
                 [1.0, 0.0, 1.0, 0.0, 0.0, 0.0]])                     # 賣出稅：LTW、0050


def prog(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


# ───────── 向量化模擬（與 LB.simulate 同一算法，目標權重可逐段變動） ─────────
class Sim:
    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        self.R = np.column_stack([df[COL[k]].to_numpy(float) for k in KEYS])
        reb = (df["date"].dt.to_period("M") != df["date"].dt.to_period("M").shift(-1)).to_numpy()
        self.reb = reb
        self.me = np.flatnonzero(reb)                                   # 月底（再平衡日）索引
        seg = np.zeros(self.n, int)
        seg[1:] = np.cumsum(reb[:-1])                                   # 第 s 段＝第 s-1 個月底之後
        self.seg = seg
        self.nseg = int(seg[-1]) + 1
        G = np.empty_like(self.R)                                       # 段內累積成長（每段從 1 起算）
        start = np.r_[0, self.me[:-1] + 1] if self.me[-1] == self.n - 1 else np.r_[0, self.me + 1]
        for a, b in zip(start, list(start[1:]) + [self.n]):
            G[a:b] = np.cumprod(1.0 + self.R[a:b], axis=0)
        self.G = G
        self.Gprev = np.ones_like(G)
        for a, b in zip(start, list(start[1:]) + [self.n]):
            if b - a > 1:
                self.Gprev[a + 1:b] = G[a:b - 1]

    def run(self, T: np.ndarray) -> np.ndarray:
        """T：每段目標權重（nseg × 6）。回傳日報酬（含月底再平衡成本）。"""
        Td = T[self.seg]
        V = (Td * self.G).sum(1)
        Vp = (Td * self.Gprev).sum(1)
        out = V / Vp - 1.0
        for k, i in enumerate(self.me):                                 # 月底 i 的成本：舊段權重漂移後 → 下一段目標
            t_old = Td[i]
            w = t_old * self.G[i] / V[i]
            t_new = T[k + 1] if k + 1 < self.nseg else T[k]
            d = t_new - w
            out[i] -= float((np.abs(d) * COST[0]).sum() * CA.FX_COST + (np.abs(np.minimum(d, 0)) * COST[1]).sum() * CA.TW_SELL_TAX)
        return out


def tvec(t: dict) -> np.ndarray:
    return np.array([t.get(k, 0.0) for k in KEYS], float)


def gated_targets(base: dict, on_tw: np.ndarray, on_us: np.ndarray, nseg: int) -> np.ndarray:
    """第 0 段＝暖機（開）；第 s 段（s≥1）由第 s-1 個月底的訊號決定。關→該槓桿腿權重移到 CASH。"""
    b = tvec(base)
    T = np.tile(b, (nseg, 1))
    for s in range(1, nseg):
        k = s - 1
        if not on_tw[k]:
            T[s, KEYS.index("CASH")] += T[s, 0]
            T[s, 0] = 0.0
        if not on_us[k]:
            T[s, KEYS.index("CASH")] += T[s, 1]
            T[s, 1] = 0.0
    return T


# ───────── 訊號 ─────────
def sig_sma10(me_vals: np.ndarray) -> np.ndarray:
    on = np.ones(len(me_vals), bool)
    for k in range(WARM["S1"], len(me_vals)):
        on[k] = me_vals[k] >= me_vals[k - 9:k + 1].mean()
    return on


def sig_absmom(me_vals: np.ndarray, me_rf: np.ndarray) -> np.ndarray:
    on = np.ones(len(me_vals), bool)
    for k in range(WARM["S2"], len(me_vals)):
        on[k] = (me_vals[k] / me_vals[k - 12] - 1.0) > (me_rf[k] / me_rf[k - 12] - 1.0)
    return on


def sig_credit(me_spread: np.ndarray) -> np.ndarray:
    on = np.ones(len(me_spread), bool)
    for k in range(WARM["S3"], len(me_spread)):
        on[k] = not (me_spread[k] > me_spread[k - 11:k + 1].mean())
    return on


def load_baa(dates: pd.Series) -> np.ndarray:
    from fred_yield_curve_gate import fetch_fred_series
    b = fetch_fred_series("BAA10Y", "2001-01-01")
    b = b[b["date"] <= END]
    s = pd.Series(b["value"].astype(float).to_numpy(), index=pd.to_datetime(b["date"]).dt.normalize()).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(pd.to_datetime(dates))).ffill().reindex(pd.to_datetime(dates)).to_numpy(float)


def vti_usd_tr(dates: pd.Series) -> np.ndarray:
    d = pd.read_parquet(CA.CACHE / "VTI.parquet")
    d = d[d["date"] <= END].reset_index(drop=True)
    c, dv = d["close"].to_numpy(float), d["dividends"].to_numpy(float)
    r = np.zeros(len(c))
    r[1:] = (c[1:] + dv[1:] * (1.0 - CA.WHT)) / c[:-1] - 1.0
    tr = pd.Series(np.cumprod(1.0 + r), index=pd.to_datetime(d["date"]).dt.normalize())
    tr = tr[~tr.index.duplicated(keep="last")]
    return tr.reindex(tr.index.union(pd.to_datetime(dates))).ffill().reindex(pd.to_datetime(dates)).to_numpy(float)


def calmar(r: np.ndarray, dates: pd.Series) -> float:
    m = TL.mdd(r)
    return TL.cagr(r, dates) / abs(m) if m < 0 else float("inf")


# ───────── 八市場複製 ─────────
def replicate(market: str) -> dict:
    from yf_price_client import fetch_yf_index
    d = fetch_yf_index(market, "2001-01-01", END)
    d["date"] = pd.to_datetime(d["date"])
    d = d[(d["date"] >= CA.START) & (d["date"] <= END)].dropna(subset=["close"]).reset_index(drop=True)
    if len(d) < 300:
        return {"market": market, "error": "資料不足"}
    c = d["close"].to_numpy(float)
    r = np.zeros(len(c))
    r[1:] = c[1:] / c[:-1] - 1.0
    dates = d["date"]
    rf = LB.load_dtb3_annual(dates) / 252.0
    lev = 2.0 * r - rf - LB.FEE / 252.0
    lev[0] = 0.0
    reb = (dates.dt.to_period("M") != dates.dt.to_period("M").shift(-1)).to_numpy()
    me = np.flatnonzero(reb)
    seg = np.zeros(len(d), int)
    seg[1:] = np.cumsum(reb[:-1])
    me_px = c[me]
    me_rf = np.cumprod(1.0 + rf)[me]
    me_sp = load_baa(dates)[me]
    sigs = {"S1": sig_sma10(me_px), "S2": sig_absmom(me_px, me_rf), "S3": sig_credit(me_sp)}
    base_mdd, base_cal = TL.mdd(lev), calmar(lev, dates)
    out = {"market": market, "n_days": int(len(d)), "start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()),
           "ungated_2x": {"cagr": TL.cagr(lev, dates), "mdd": base_mdd, "calmar": base_cal}}
    for s, on in sigs.items():
        on_day = np.r_[True, on][seg]                                   # 第 s 段用第 s-1 個月底訊號；第 0 段開
        g = np.where(on_day, lev, rf)
        gm, gc = TL.mdd(g), calmar(g, dates)
        out[s] = {"cagr": TL.cagr(g, dates), "mdd": gm, "calmar": gc, "off_month_share": float(1 - on.mean()),
                  "holds": bool(gm > base_mdd and gc > base_cal)}
    return out


def conv(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def main() -> int:
    sha = hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()
    if sha != PREREG_SHA:
        print(f"事前登記檔 SHA256 不符（{sha}），拒絕執行")
        return 2
    prog("載入資料（#421 load_all，截至 2024-12-31）")
    df, _fx = LB.load_all()
    df = df[df["date"] <= END].reset_index(drop=True)
    dates = df["date"]
    sim = Sim(df)

    # 0) 實作一致性檢查：向量化模擬 vs #421 逐日模擬（Bb-90、C5、C6 不閘門），不一致就停
    chk = {}
    for name, t in (("Bb-90", LB.target_418("Bb-90")), ("C5", CONFIGS["C5"]), ("C6", CONFIGS["C6"])):
        a = LB.simulate(df, t)
        b = sim.run(np.tile(tvec(t), (sim.nseg, 1)))
        chk[name] = float(np.max(np.abs(a - b)))
    if max(chk.values()) > 1e-10:
        print(f"向量化模擬與 #421 不一致：{chk}，停止（未計算任何閘門結果）")
        return 3
    prog(f"一致性檢查通過（最大差 {max(chk.values()):.2e}）")

    # 1) 月底序列與訊號
    me = sim.me
    tw_tr = np.cumprod(1.0 + df["r_0050"].to_numpy(float))
    us_tr = vti_usd_tr(dates)
    tw_rf = np.cumprod(1.0 + LB.load_tw_rf_daily(dates))
    us_rf = np.cumprod(1.0 + LB.load_dtb3_annual(dates) / 252.0)
    spread = load_baa(dates)
    S = {
        "S1": (sig_sma10(tw_tr[me]), sig_sma10(us_tr[me])),
        "S2": (sig_absmom(tw_tr[me], tw_rf[me]), sig_absmom(us_tr[me], us_rf[me])),
    }
    c = sig_credit(spread[me])
    S["S3"] = (c, c)

    base = {"Bb-90": LB.simulate(df, LB.target_418("Bb-90"))}
    for cn, t in CONFIGS.items():
        base[cn] = LB.simulate(df, t)
    bb = LB.stats(base["Bb-90"], dates)

    rng = np.random.default_rng(SEED)
    res = {"prereg": PREREG, "prereg_sha256": sha, "prereg_trial": PREREG_TRIAL,
           "generated_at": datetime.now(timezone.utc).isoformat(), "period": [str(dates.iloc[0].date()), END],
           "impl_check_max_abs_diff": chk, "n_family": N_FAMILY, "bb90": bb,
           "ungated": {cn: LB.stats(base[cn], dates) for cn in CONFIGS}, "trials": {}}
    rets = {}
    for sname in SIGNALS:
        on_tw, on_us = S[sname]
        for cn, t in CONFIGS.items():
            key = f"{sname}-{cn}"
            prog(f"試驗 {key}")
            T = gated_targets(t, on_tw, on_us, sim.nseg)
            r = sim.run(T)
            rets[key] = r
            st = LB.stats(r, dates)
            cal = calmar(r, dates)
            # 隨機控制組：各腿在暖機後月份中隨機抽相同數量關閉月份（S3 兩腿共用同一遮罩）
            w0 = WARM[sname]
            nm = len(on_tw)
            idx = np.arange(w0, nm)
            off_tw, off_us = int((~on_tw[w0:]).sum()), int((~on_us[w0:]).sum())
            cals = np.empty(N_RAND)
            for b in range(N_RAND):
                rt = np.ones(nm, bool)
                rt[rng.choice(idx, off_tw, replace=False)] = False
                if sname == "S3":
                    ru = rt
                else:
                    ru = np.ones(nm, bool)
                    ru[rng.choice(idx, off_us, replace=False)] = False
                cals[b] = calmar(sim.run(gated_targets(t, rt, ru, sim.nseg)), dates)
            p95 = float(np.percentile(cals, 95))
            res["trials"][key] = {
                "signal": sname, "config": cn, "stats": st, "calmar": cal,
                "off_month_share_tw": float(1 - on_tw[w0:].mean()), "off_month_share_us": float(1 - on_us[w0:].mean()),
                "control": {"n": N_RAND, "seed": SEED, "p50": float(np.percentile(cals, 50)), "p95": p95,
                            "percentile_of_signal": float((cals < cal).mean() * 100), "pass": bool(cal > p95)},
                "stress": {k: LB.seg(r, dates, a, b2) for k, (a, b2) in LB.STRESS.items()},
                "cluster_bootstrap_vs_bb90": LB.cluster_boot(r, base["Bb-90"], dates),
            }

    # 2) 八市場複製
    rep = {}
    for m in MARKETS:
        prog(f"複製 {m}")
        try:
            rep[m] = replicate(m)
        except Exception as e:
            rep[m] = {"market": m, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    res["replication"] = rep
    repl = {}
    for sname in SIGNALS:
        ok = [m for m in MARKETS if isinstance(rep[m].get(sname), dict) and rep[m][sname].get("holds")]
        computable = [m for m in MARKETS if isinstance(rep[m].get(sname), dict)]
        repl[sname] = {"holds": len(ok), "computable": len(computable), "markets_holding": ok, "pass": len(ok) >= 6}
    res["replication_summary"] = repl

    # 3) DSR（V＝#418 24 組重算＋#421 6 組＋本次 6 組日 Sharpe；只報告）
    sh = []
    for eq in ("A", "B"):
        for sf in ("a", "b", "c"):
            for w in CA.EQUITY_W:
                k = f"{eq}{sf}-{int(w * 100)}"
                rr = LB.simulate(df, LB.target_418(k))
                sh.append(float(rr.mean() / rr.std(ddof=1)))
    for g in LB.GRID.values():
        rr = LB.simulate(df, LB.grid_target(*g))
        sh.append(float(rr.mean() / rr.std(ddof=1)))
    sh += [float(r.mean() / r.std(ddof=1)) for r in rets.values()]
    V = float(np.var(sh, ddof=1))
    res["dsr_V"] = {"value_daily": V, "n_sharpes": len(sh), "N_used": N_FAMILY,
                    "source": "#418 24 組重算＋#421 6 組網格＋本次 6 組，日頻 Sharpe 樣本變異數",
                    "bias_note": "V 為僅有 Sharpe 記錄者的離散度，非全體；同家族高度相關，V 偏小→DSR 偏寬鬆"}

    # 4) 判定
    for key, tr in res["trials"].items():
        st = tr["stats"]
        d = LB.dsr(rets[key], N_FAMILY, V)
        tr["dsr_report_only"] = d
        cond = {
            "mdd_full_gt_-45": st["mdd"] > MDD_LIMIT,
            "mdd_first_half_gt_-45": st["mdd_first_half"] > MDD_LIMIT,
            "mdd_second_half_gt_-45": st["mdd_second_half"] > MDD_LIMIT,
            "cagr_ge_12": st["cagr"] >= CAGR_MIN,
            "cagr_gt_bb90": st["cagr"] > bb["cagr"],
            "control_beats_p95": tr["control"]["pass"],
            "replication_ge_6_of_8": repl[tr["signal"]]["pass"],
        }
        tr["conditions"] = cond
        tr["verdict"] = "PASS" if all(cond.values()) else "FAIL"
    res["verdict"] = "PASS" if any(t["verdict"] == "PASS" for t in res["trials"].values()) else "FAIL"
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    prog(f"結果已寫入 {OUT.relative_to(ROOT)}")
    print(json.dumps({k: {"verdict": v["verdict"], "cagr": round(v["stats"]["cagr"] * 100, 2),
                          "mdd": round(v["stats"]["mdd"] * 100, 1), "conds": v["conditions"]}
                      for k, v in res["trials"].items()}, ensure_ascii=False, indent=1))
    print("replication", json.dumps(repl, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
