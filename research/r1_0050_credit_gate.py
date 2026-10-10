# -*- coding: utf-8 -*-
"""先.五十八-B：R1 — 0050 核心＋信用利差閘門槓桿 單發檢定。

定義全部事前綁定於 docs/PREREG_R1_0050_credit_gate.md（登記 #429，
SHA256=7654ec952962c3c4440e493ce7cdcf3889433d1a25db9f5635c5f8ecdfe7609b，commit 536a7505a）。
**只跑一次；績效數字一律到 JSON 寫完後才印。** 不讀 2025-01-01 以後任何資料。

沿用：#421 合成 2 倍公式與 #418 成本（leveraged_bb90_backtest.py --formula 421 的 load_all／stats／seg／dsr），
#424 的 S3 閘門（crisis_gate_leveraged_bb90.sig_credit／load_baa），
延後一日執行沿用 crisis_gate_timing_sensitivity.run_lagged 的規則（月底照舊狀態再平衡，隔一個交易日收盤才切換）。
本檔新增：3 資產（0050、台股 2 倍、現金）的延後一日向量化模擬（執行前與逐日迴圈版、LB.simulate 比對一致才繼續）。
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
import crisis_gate_leveraged_bb90 as M  # noqa: E402  （import 時已把 LB 設成 --formula 421）

LB, CA, TL = M.LB, M.CA, M.TL
assert LB.F421, "必須使用 #421 公式"

PREREG = "docs/PREREG_R1_0050_credit_gate.md"
PREREG_SHA = "7654ec952962c3c4440e493ce7cdcf3889433d1a25db9f5635c5f8ecdfe7609b"
PREREG_TRIAL = 429
OUT = HERE / "data" / "r1_0050_credit_gate_result.json"
END = "2024-12-31"
SEED = 20261010
N_RAND = 1000
N_FAMILY = 46
MDD_LIMIT = -0.45
SURVIVAL = -0.50
WARM = 11
MARKETS = ["^GSPC", "^TWII", "^N225", "^FTSE", "^GDAXI", "^HSI", "^KS11", "^AXJO"]
# 資產順序：[1 倍腿, 2 倍腿, 現金]
GROUPS = {
    "R1-A": {"open": (0.70, 0.30, 0.00), "closed": (0.70, 0.00, 0.30)},
    "R1-B": {"open": (0.70, 0.30, 0.00), "closed": (1.00, 0.00, 0.00)},
    "R1-C": {"open": (0.50, 0.50, 0.00), "closed": (0.50, 0.00, 0.50)},
    "R1-D": {"open": (0.50, 0.50, 0.00), "closed": (1.00, 0.00, 0.00)},
}
SELL_TAX_TW = np.array([1.0, 1.0, 0.0]) * CA.TW_SELL_TAX        # 台股：0050、台股 2 倍腿減碼計賣出稅


def prog(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def month_ends(dates: pd.Series) -> np.ndarray:
    return np.flatnonzero((dates.dt.to_period("M") != dates.dt.to_period("M").shift(-1)).to_numpy())


def events(n: int, me: np.ndarray, on: np.ndarray, w_open, w_closed) -> list[tuple[int, np.ndarray]]:
    """延後一日規則的再平衡事件（收盤時點, 新目標）。第 0 段（第一個月底之前）＝開。"""
    wo, wc = np.array(w_open, float), np.array(w_closed, float)
    cur_on = True
    ev = []
    for k, i in enumerate(me):
        ev.append((int(i), wo if cur_on else wc))                  # 月底：照目前狀態再平衡
        if int(i) + 1 < n and bool(on[k]) != cur_on:               # 隔一個交易日收盤：切到新狀態
            cur_on = bool(on[k])
            ev.append((int(i) + 1, wo if cur_on else wc))
    return ev


def run_fast(R: np.ndarray, C: np.ndarray, ev, w0, sell_tax: np.ndarray) -> np.ndarray:
    """C＝vstack(1, cumprod(1+R))。各持有期內權重漂移，事件日收盤再平衡並扣成本。"""
    n = R.shape[0]
    out = np.empty(n)
    w = np.array(w0, float)
    a = 0
    for b, new in list(ev) + [(n - 1, None)]:
        if b < a:
            continue
        g = C[a + 1:b + 2] / C[a]                                   # 第 a..b 天收盤相對 a 開始前的成長
        V = g @ w
        out[a] = V[0] - 1.0
        if b > a:
            out[a + 1:b + 1] = V[1:] / V[:-1] - 1.0
        if new is not None:
            wd = w * g[-1] / V[-1]
            d = new - wd
            out[b] -= float((np.abs(np.minimum(d, 0.0)) * sell_tax).sum())
            w = new.copy()
            a = b + 1
        else:
            a = n
    return out


def run_loop(R: np.ndarray, ev, w0, sell_tax: np.ndarray) -> np.ndarray:
    """逐日參考實作（只用於一致性檢查）。"""
    evd = {}
    for b, new in ev:
        evd.setdefault(b, []).append(new)
    w = np.array(w0, float)
    out = np.zeros(R.shape[0])
    for i in range(R.shape[0]):
        w = w * (1.0 + R[i])
        tot = w.sum()
        out[i] = tot - 1.0
        w = w / tot
        for new in evd.get(i, []):
            d = new - w
            out[i] -= float((np.abs(np.minimum(d, 0.0)) * sell_tax).sum())
            w = new.copy()
    return out


def calmar(r: np.ndarray, dates: pd.Series) -> float:
    m = TL.mdd(r)
    return TL.cagr(r, dates) / abs(m) if m < 0 else float("inf")


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
    R = np.column_stack([r, lev, rf])
    Cm = np.vstack([np.ones((1, 3)), np.cumprod(1.0 + R, axis=0)])
    me = month_ends(dates)
    on = M.sig_credit(M.load_baa(dates)[me])
    bh_c, bh_m = TL.cagr(r, dates), TL.mdd(r)
    out = {"market": market, "n_days": int(len(d)), "start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()),
           "buy_hold": {"cagr": bh_c, "mdd": bh_m}, "off_month_share": float(1 - on[WARM:].mean())}
    zero = np.zeros(3)
    for g, spec in GROUPS.items():
        x = run_fast(R, Cm, events(len(r), me, on, spec["open"], spec["closed"]), spec["open"], zero)
        gc, gm = TL.cagr(x, dates), TL.mdd(x)
        out[g] = {"cagr": gc, "mdd": gm, "holds": bool(gc > bh_c and gm >= bh_m)}
    return out


def main() -> int:
    sha = hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()
    if sha != PREREG_SHA:
        print(f"事前登記檔 SHA256 不符（{sha}），拒絕執行")
        return 2
    prog("載入資料（#421 load_all，截至 2024-12-31）")
    df, _fx = LB.load_all()
    df = df[df["date"] <= END].reset_index(drop=True)
    dates = df["date"]
    n = len(df)
    R = np.column_stack([df["r_0050"].to_numpy(float), df["r_ltw"].to_numpy(float), df["r_cash"].to_numpy(float)])
    C = np.vstack([np.ones((1, 3)), np.cumprod(1.0 + R, axis=0)])
    me = month_ends(dates)
    on = M.sig_credit(M.load_baa(dates)[me])
    r0050 = df["r_0050"].to_numpy(float)

    # 0) 實作一致性檢查：①全開（無閘門）＝ LB.simulate ②延後一日：向量化 vs 逐日迴圈。不一致就停
    chk = {}
    for g, spec in GROUPS.items():
        o, _c, _ = spec["open"]
        t = {"0050": o, "LTW": spec["open"][1]}
        allon = np.ones(len(me), bool)
        a = run_fast(R, C, events(n, me, allon, spec["open"], spec["closed"]), spec["open"], SELL_TAX_TW)
        chk[f"{g}_ungated_vs_LB.simulate"] = float(np.max(np.abs(a - LB.simulate(df, t))))
        ev = events(n, me, on, spec["open"], spec["closed"])
        chk[f"{g}_lagged_fast_vs_loop"] = float(np.max(np.abs(run_fast(R, C, ev, spec["open"], SELL_TAX_TW)
                                                              - run_loop(R, ev, spec["open"], SELL_TAX_TW))))
    if max(chk.values()) > 1e-10:
        print(f"實作不一致：{chk}，停止（未判定）")
        return 3
    prog(f"一致性檢查通過（最大差 {max(chk.values()):.2e}）")

    b0050 = LB.stats(r0050, dates)
    b0050["calmar"] = calmar(r0050, dates)
    res = {"prereg": PREREG, "prereg_sha256": sha, "prereg_trial": PREREG_TRIAL,
           "generated_at": datetime.now(timezone.utc).isoformat(), "period": [str(dates.iloc[0].date()), END],
           "n_days": n, "impl_check_max_abs_diff": chk, "n_family": N_FAMILY,
           "gate": {"n_month_ends": int(len(me)), "warm": WARM, "off_months": int((~on[WARM:]).sum()),
                    "off_month_share": float(1 - on[WARM:].mean()), "execution": "延後一個交易日"},
           "benchmark_0050_buy_hold": b0050,
           "benchmark_0050_stress": {k: LB.seg(r0050, dates, a, b) for k, (a, b) in LB.STRESS.items()},
           "trials": {}}
    rets = {}
    rng = np.random.default_rng(SEED)
    nm = len(me)
    idx = np.arange(WARM, nm)
    n_off = int((~on[WARM:]).sum())
    for g, spec in GROUPS.items():
        prog(f"試驗 {g}")
        r = run_fast(R, C, events(n, me, on, spec["open"], spec["closed"]), spec["open"], SELL_TAX_TW)
        rets[g] = r
        st = LB.stats(r, dates)
        cal = calmar(r, dates)
        cals = np.empty(N_RAND)
        cagrs = np.empty(N_RAND)
        for b in range(N_RAND):
            m = np.ones(nm, bool)
            m[rng.choice(idx, n_off, replace=False)] = False
            x = run_fast(R, C, events(n, me, m, spec["open"], spec["closed"]), spec["open"], SELL_TAX_TW)
            cals[b] = calmar(x, dates)
            cagrs[b] = TL.cagr(x, dates)
        p95 = float(np.percentile(cals, 95))
        res["trials"][g] = {
            "weights_open": spec["open"], "weights_closed": spec["closed"], "stats": st, "calmar": cal,
            "control": {"n": N_RAND, "seed": SEED, "statistic": "Calmar", "p50": float(np.percentile(cals, 50)),
                        "p95": p95, "percentile_of_signal": float((cals < cal).mean() * 100), "pass": bool(cal > p95),
                        "cagr_percentile_of_signal_report_only": float((cagrs < st["cagr"]).mean() * 100)},
            "stress": {k: LB.seg(r, dates, a, b2) for k, (a, b2) in LB.STRESS.items()},
            "cluster_bootstrap_vs_0050": LB.cluster_boot(r, r0050, dates),
        }

    # 2) 8 市場複製
    rep = {}
    for mk in MARKETS:
        prog(f"複製 {mk}")
        try:
            rep[mk] = replicate(mk)
        except Exception as e:  # noqa: BLE001
            rep[mk] = {"market": mk, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    res["replication"] = rep
    repl = {}
    for g in GROUPS:
        ok = [mk for mk in MARKETS if isinstance(rep[mk].get(g), dict) and rep[mk][g].get("holds")]
        comp = [mk for mk in MARKETS if isinstance(rep[mk].get(g), dict)]
        repl[g] = {"holds": len(ok), "computable": len(comp), "markets_holding": ok, "pass": len(ok) >= 6}
    res["replication_summary"] = repl

    # 3) DSR（只報告）：V＝#418 24 組重算＋#421 6 組網格＋#424 6 組重算＋本次 4 組，日頻 Sharpe 樣本變異數
    prog("DSR 的 V（重算家族 Sharpe）")
    sh = []
    for eq in ("A", "B"):
        for sf in ("a", "b", "c"):
            for w in CA.EQUITY_W:
                rr = LB.simulate(df, LB.target_418(f"{eq}{sf}-{int(w * 100)}"))
                sh.append(float(rr.mean() / rr.std(ddof=1)))
    for gg in LB.GRID.values():
        rr = LB.simulate(df, LB.grid_target(*gg))
        sh.append(float(rr.mean() / rr.std(ddof=1)))
    sim = M.Sim(df)
    mi = sim.me
    tw_tr = np.cumprod(1.0 + df["r_0050"].to_numpy(float))
    us_tr = M.vti_usd_tr(dates)
    tw_rf = np.cumprod(1.0 + LB.load_tw_rf_daily(dates))
    us_rf = np.cumprod(1.0 + LB.load_dtb3_annual(dates) / 252.0)
    S424 = {"S1": (M.sig_sma10(tw_tr[mi]), M.sig_sma10(us_tr[mi])),
            "S2": (M.sig_absmom(tw_tr[mi], tw_rf[mi]), M.sig_absmom(us_tr[mi], us_rf[mi])),
            "S3": (on, on)}
    for sname, (a, b) in S424.items():
        for t in M.CONFIGS.values():
            rr = sim.run(M.gated_targets(t, a, b, sim.nseg))
            sh.append(float(rr.mean() / rr.std(ddof=1)))
    sh += [float(r.mean() / r.std(ddof=1)) for r in rets.values()]
    V = float(np.var(sh, ddof=1))
    n_total = sum(1 for ln in (HERE / "TRIALS_REGISTRY.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip())
    res["dsr_V"] = {"value_daily": V, "n_sharpes": len(sh), "N_family": N_FAMILY, "N_total_registry_rows": n_total,
                    "source": "#418 24 組重算＋#421 6 組網格＋#424 6 組（以 #424 程式重算）＋本次 4 組，日頻 Sharpe 樣本變異數",
                    "bias_note": "V 為僅有 Sharpe 記錄者的離散度，非全體；同家族高度相關，V 偏小→DSR 偏寬鬆"}

    # 4) 判定
    for g, tr in res["trials"].items():
        st = tr["stats"]
        tr["dsr_report_only"] = {"N_family": LB.dsr(rets[g], N_FAMILY, V), "N_total": LB.dsr(rets[g], n_total, V)}
        worst = min(st["mdd"], st["mdd_first_half"], st["mdd_second_half"])
        cond = {
            "mdd_full_gt_-45": st["mdd"] > MDD_LIMIT,
            "mdd_first_half_gt_-45": st["mdd_first_half"] > MDD_LIMIT,
            "mdd_second_half_gt_-45": st["mdd_second_half"] > MDD_LIMIT,
            "cagr_gt_0050": st["cagr"] > b0050["cagr"],
            "mdd_not_worse_than_0050": st["mdd"] >= b0050["mdd"],
            "control_beats_p95": tr["control"]["pass"],
            "replication_ge_6_of_8": repl[g]["pass"],
        }
        tr["conditions"] = cond
        tr["verdict"] = "VIOLATES_SURVIVAL" if worst <= SURVIVAL else ("PASS" if all(cond.values()) else "FAIL")
    res["verdict"] = "PASS" if any(t["verdict"] == "PASS" for t in res["trials"].values()) else "FAIL"
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=M.conv), encoding="utf-8")
    prog(f"結果已寫入 {OUT.relative_to(ROOT)}")
    print("0050", json.dumps({k: round(b0050[k] * 100, 2) for k in ("cagr", "mdd")}, ensure_ascii=False))
    print(json.dumps({k: {"verdict": v["verdict"], "cagr": round(v["stats"]["cagr"] * 100, 2),
                          "mdd": round(v["stats"]["mdd"] * 100, 1), "conds": v["conditions"]}
                      for k, v in res["trials"].items()}, ensure_ascii=False, indent=1))
    print("replication", json.dumps(repl, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
