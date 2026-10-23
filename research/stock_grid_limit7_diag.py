# -*- coding: utf-8 -*-
"""先.一三三-2c 揭露用診斷（不改判定、不重跑單發）：stock_grid_oneshot 用的 costs.limit_status() 寫死 ±10%，
但台股 2015-06-01 前漲跌幅是 ±7%。重建同一份資料、重播中性 1× 模擬（決定性，結果與結果檔相同），
數有幾筆成交落在「±7% 一字鎖死」日。輸出印在主控台，數字抄進 research/data/stock_grid_oneshot_limit7_diag.json。"""
import sys, json; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, stock_grid_oneshot as G
M = G.build_real()
sim = G.simulate(M, "neutral", G.cost_legs(1))
O,H,L,C = M["O"],M["H"],M["L"],M["C"]
j_of = {c:j for j,c in enumerate(M["codes"])}
def prevc(j,d):
    v = np.where(~np.isnan(C[:d,j]))[0]; return C[v[-1],j] if len(v) else np.nan
def locked(j,d,up):
    pc = prevc(j,d); lim = pc*(1.07 if up else 0.93); tol=0.0015
    if up: return O[d,j]>=lim*(1-tol) and L[d,j]>=lim*(1-tol)
    return O[d,j]<=lim*(1+tol) and H[d,j]<=lim*(1+tol)
nb=ns=0; pnl_ns=0.0
for t in sim["trades"]:
    j=j_of[t["stock_id"]]
    if t["entry_i"]>=0 and locked(j,t["entry_i"],True): nb+=1
    if t["exit_how"]=="open" and locked(j,t["exit_i"],False): ns+=1
print(json.dumps({"final_equity":sim["final_equity"],"n_trades":len(sim["trades"]),"buys_on_7pct_limitup_lock":nb,"sells_on_7pct_limitdown_lock":ns}, ensure_ascii=False))
