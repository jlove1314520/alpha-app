# -*- coding: utf-8 -*-
"""先.四十五-三 主線 A 的時序敏感度（只報告、不改判定）。

單發結果（#424 登記、crisis_gate_leveraged_bb90.py）在月底收盤當下就依訊號切換權重；但 S3 用的 BAA10Y、
美股腿用的 VTI 月底值，要等美國收盤（台北時間隔日清晨）才知道——比台股月底收盤晚。本檔把「閘門狀態變更」
延後一個交易日執行（月底照常再平衡回『舊狀態』目標，隔一個交易日收盤才切到新狀態），其餘參數完全相同。
**不是重跑、不改任何事前參數、不改判定**；結果另寫 research/data/crisis_gate_timing_sensitivity.json。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import crisis_gate_leveraged_bb90 as M  # noqa: E402

OUT = HERE / "data" / "crisis_gate_timing_sensitivity.json"


def run_lagged(sim: "M.Sim", base: dict, on_tw: np.ndarray, on_us: np.ndarray) -> np.ndarray:
    T = M.gated_targets(base, on_tw, on_us, sim.nseg)          # 第 s 段（第 s-1 個月底之後）應有的狀態
    R = sim.R
    me_set = {int(i): k for k, i in enumerate(sim.me)}
    switch_day = {int(i) + 1: k for k, i in enumerate(sim.me) if int(i) + 1 < sim.n}
    cur = T[0].copy()                                            # 目前生效的目標
    w = cur.copy()
    out = np.zeros(sim.n)

    def cost(d):
        return float((np.abs(d) * M.COST[0]).sum() * M.CA.FX_COST + (np.abs(np.minimum(d, 0)) * M.COST[1]).sum() * M.CA.TW_SELL_TAX)

    for i in range(sim.n):
        w = w * (1.0 + R[i])
        tot = w.sum()
        out[i] = tot - 1.0
        w = w / tot
        if i in switch_day:                                      # 月底後第 1 個交易日收盤：切到新狀態
            new = T[switch_day[i] + 1] if switch_day[i] + 1 < sim.nseg else T[switch_day[i]]
            if not np.allclose(new, cur):
                out[i] -= cost(new - w)
                w = new.copy()
                cur = new.copy()
        if i in me_set:                                          # 月底：照常再平衡回目前狀態的目標
            out[i] -= cost(cur - w)
            w = cur.copy()
    return out


def main() -> int:
    df, _ = M.LB.load_all()
    df = df[df["date"] <= M.END].reset_index(drop=True)
    dates = df["date"]
    sim = M.Sim(df)
    me = sim.me
    tw_tr = np.cumprod(1.0 + df["r_0050"].to_numpy(float))
    us_tr = M.vti_usd_tr(dates)
    tw_rf = np.cumprod(1.0 + M.LB.load_tw_rf_daily(dates))
    us_rf = np.cumprod(1.0 + M.LB.load_dtb3_annual(dates) / 252.0)
    c = M.sig_credit(M.load_baa(dates)[me])
    S = {"S1": (M.sig_sma10(tw_tr[me]), M.sig_sma10(us_tr[me])),
         "S2": (M.sig_absmom(tw_tr[me], tw_rf[me]), M.sig_absmom(us_tr[me], us_rf[me])),
         "S3": (c, c)}
    bb = M.LB.stats(M.LB.simulate(df, M.LB.target_418("Bb-90")), dates)
    res = {"note": "只報告的時序敏感度：閘門狀態變更延後一個交易日執行；不改事前參數、不改 #424 單發判定",
           "bb90_cagr": bb["cagr"], "trials": {}}
    for sname, (a, b) in S.items():
        for cn, t in M.CONFIGS.items():
            r = run_lagged(sim, t, a, b)
            st = M.LB.stats(r, dates)
            res["trials"][f"{sname}-{cn}"] = {
                "cagr": st["cagr"], "mdd": st["mdd"], "mdd_first_half": st["mdd_first_half"],
                "mdd_second_half": st["mdd_second_half"], "worst_12m": st["worst_12m"],
                "calmar": M.calmar(r, dates),
                "would_meet_mdd_and_cagr": bool(min(st["mdd"], st["mdd_first_half"], st["mdd_second_half"]) > M.MDD_LIMIT
                                                and st["cagr"] >= M.CAGR_MIN and st["cagr"] > bb["cagr"])}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=M.conv), encoding="utf-8")
    for k, v in res["trials"].items():
        print(k, f"CAGR {v['cagr']*100:.2f}%  MDD {v['mdd']*100:.1f}%  calmar {v['calmar']:.3f}  達報酬回撤門檻 {v['would_meet_mdd_and_cagr']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
