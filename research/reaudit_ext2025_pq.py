# -*- coding: utf-8 -*-
"""先.一五五-2 PQ：先.一五〇-2 恐慌求生日買 PQ 成長股，延長到 2025 起（紙上優化軌，描述性，不寫 TRIALS_LEDGER）。

零新外部請求：本行程封死 socket；只讀本機 data/raw 快取。
做法：執行期把 `panic_pq_components`／`panic_pq_backtest` 的 END 改成 EXT_END、輸出目錄改成 data/panic_pq_ext2025/
（**不改原始碼、不覆蓋原 data/panic_pq/ 結果**），照原程式重建恐慌日表＋PQ 名單，再：
 ① 原最優組（θ=20%、k=1、N=20、H=120、strict、peak、無止盈、止損 −15%、1×）參數不動，延長到 EXT_END，另列 2025 起段；
 ② 用全期（2007-05～EXT_END）重跑原格點（2,592 引擎格×槓桿 4）重新挑最優（同原規則：MDD≤50%、≥10 筆、Calmar 最高）。
EXT_END＝2026-10-02（本機 2025 起個股價格快取多數最後一日，同 reaudit_ext2025_coretilt.py）。
已知缺口（照實）：上櫃指數 2025 起本機無快取 → tpex_ret 2025 起空白（觸發只用跌停家數比例，不影響）；
2025 起價格快取只有 1,931 檔（2025 前下市的本來就不需要；2025 起才下市的若沒快取，跌停家數少算）。
用法：python research/reaudit_ext2025_pq.py [--skip-build] [--skip-grid]
"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _no_net(*a, **k):
    raise RuntimeError("reaudit_ext2025_pq：本行程禁止網路請求（只讀本機快取）")


socket.socket.connect = _no_net  # type: ignore[assignment]
socket.create_connection = _no_net  # type: ignore[assignment]

import panic_pq_components as PC  # noqa: E402
import panic_pq_backtest as PB  # noqa: E402

EXT_END = "2026-10-02"
EXT = HERE / "data" / "panic_pq_ext2025"
EXT.mkdir(parents=True, exist_ok=True)
PC.END, PC.OUT = EXT_END, EXT
PB.END, PB.OUT, PB.CACHE = EXT_END, EXT, EXT / "prices_wide.pkl"
ORIG = dict(theta=0.20, k=1, N=20, H=120, list="strict", filt="peak", tp=None, sl=-0.15, L=1.0)


def seg_stats(eq: np.ndarray, cal: list[str], s0: int, a: str | None = None):
    """eq 對應 cal[s0:]；a＝區段起點（含前一日當基準）。"""
    d = cal[s0:]
    i0 = 0 if a is None else max(0, next(i for i, x in enumerate(d) if x >= a) - 1)
    e = eq[i0:] / eq[i0]
    r = e[1:] / e[:-1] - 1
    yrs = len(r) / 252
    cagr = e[-1] ** (1 / yrs) - 1 if e[-1] > 0 else -1.0
    mdd = float((e / np.maximum.accumulate(e) - 1).min())
    sh = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0
    return {"start": d[i0], "end": d[-1], "cagr": float(cagr), "mdd": mdd, "sharpe": sh}


def fixed_config(cfg: dict) -> dict:
    """照 PB.main 的事件合併與名單邏輯跑單一組，回傳全期與 2025 起段。"""
    pan = pd.read_csv(EXT / "panic_daily.csv")
    pq = PB.pq_table()
    loose = pq[(pq["gm_yoy_pp"] > 0) & (pq["om_yoy_pp"] > 0) & (pq["rev3m_yoy"] > 0) & (pq["eps_yoy"] > 0) & (pq["eps_ttm"] > 0)]
    P = PB.load_prices(sorted(set(loose["stock_id"])) + ["0050"])
    cal = P["cal"]; pos = {d: i for i, d in enumerate(cal)}
    sid_pos = {s: i for i, s in enumerate(P["ids"])}
    s0 = pos[min(d for d in cal if d >= PB.START)]
    pan = pan[(pan["date"] >= PB.START) & (pan["date"] <= EXT_END)]
    days = [pos[d] for d in pan.loc[pan["frac_limit_down"] >= cfg["theta"], "date"] if d in pos]
    ev, last = [], -10**9
    for d in days:
        if d - last > PB.MERGE_DAYS:
            ev.append(d)
        last = d if d - last > PB.MERGE_DAYS else last
    picks = [[sid_pos[s] for s in PB.list_on(pq, cal[e], cfg["list"], cfg["filt"], P["C"][e], sid_pos, cfg["N"])] for e in ev]
    pr, inv, tr, used = PB.run_events(P, ev, picks, cfg["k"], cfg["H"], cfg["tp"], cfg["sl"], 1.0, cfg["N"])
    eq = PB.metrics(pr, inv, cfg["L"], s0)[3]
    j50 = sid_pos["0050"]
    r50 = np.nan_to_num(P["R"][:, j50] - 1, nan=0.0)
    eq50 = PB.metrics(r50, np.ones(len(cal)), 1.0, s0)[3]
    eq = np.concatenate([[1.0], eq]); eq50 = np.concatenate([[1.0], eq50])
    cal_s = [cal[s0 - 1] if s0 > 0 else cal[0]] + list(cal[s0:])
    events = [dict(event=cal[e], picks=[P["ids"][j] for j in js][: cfg["N"]]) for e, js in zip(ev, picks)]
    out = {"cfg": cfg, "n_trades": len(tr), "events_used": used,
           "events_2025": [x for x in events if x["event"] >= "2025-01-01"],
           "full": seg_stats(eq, cal_s, 0), "pre2025": None, "post2025": seg_stats(eq, cal_s, 0, "2025-01-01"),
           "c0050_full": seg_stats(eq50, cal_s, 0), "c0050_post2025": seg_stats(eq50, cal_s, 0, "2025-01-01")}
    cut = next(i for i, x in enumerate(cal_s) if x > "2024-12-31")
    out["pre2025"] = seg_stats(eq[:cut], cal_s[:cut], 0)
    out["_eq"] = (cal_s, eq, eq50)
    return out


def main() -> int:
    t0 = time.time()
    if "--skip-build" not in sys.argv:
        pan, m1 = PC.build_panic(); pan.to_csv(EXT / "panic_daily.csv", index=False)
        pq, m2 = PC.build_pq(); pq.to_csv(EXT / "pq_snapshots.csv", index=False)
        (EXT / "build_meta.json").write_text(json.dumps({"end": EXT_END, **m1, **m2, "network_requests": 0}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
        print(f"元件重建 {time.time()-t0:.0f}s：恐慌日 {pan['date'].min()}～{pan['date'].max()}，PQ 名單最後可得日 {pq['avail'].max()}", flush=True)
    fx = fixed_config(ORIG)
    cal_s, eq, eq50 = fx.pop("_eq")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(pd.to_datetime(cal_s), eq, label="orig best (theta20%,N20,H120,strict+peak,SL15%,1x)", color="#2a6fdb")
    ax.plot(pd.to_datetime(cal_s), eq50, label="0050 buy&hold (total return)", color="#999999")
    ax.axvline(pd.Timestamp("2025-01-01"), color="#c33", ls="--", lw=1)
    ax.set_yscale("log"); ax.legend(); ax.set_title("Panic PQ extended to 2026-10 (params fixed from 2007-2024)")
    fig.tight_layout(); fig.savefig(HERE / "data" / "reaudit_curves" / "ext2025_PQ.png", dpi=110)
    res = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "ext_end": EXT_END, "network_requests": 0, "orig_fixed": fx}
    if "--skip-grid" not in sys.argv:
        PB.main()
        g = json.loads((EXT / "backtest_result.json").read_text(encoding="utf-8"))
        b = g["best"]
        cfg = dict(theta=float(b["theta"]), k=int(b["k"]), N=int(b["N"]), H=int(b["H"]), list=b["list"], filt=b["filt"],
                   tp=(b["tp"] or None), sl=(b["sl"] or None), L=float(b["L"]))
        rb = fixed_config(cfg); rb.pop("_eq")
        res["reopt_full"] = rb
        res["reopt_ctlC"] = g["ctlC"]
        res["n_grid_total"] = g["n_grid_total"]; res["n_violates"] = g["n_violates"]
    (HERE / "data" / "reaudit_ext2025_pq.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float)[:5000])
    print(f"總耗時 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
