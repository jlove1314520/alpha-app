"""先.一五二-1b ④ 恐慌 PQ（先.一五〇-2 最優格）套 drawdown_fix 同一套降回撤條件＋台指期避險。樣本內描述性，不是判定。

底層：`research/data/panic_pq/best_equity.npy`（PQ 最優格 1× 帳戶日權益，2007-05-15～2024-12-31，已含個股停損 −15%、閒置現金不計息）。
條件 A～D 與只調槓桿用 drawdown_fix.cond_series()／overlay()；台指期避險用 drawdown_fix_hedge 的 hedge_ratio()。
L' 由低往高掃到年化 ≥ 原版，比 MDD。零外部請求、holdout 未讀。非投資建議。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drawdown_fix as D  # noqa: E402
import drawdown_fix_hedge as H  # noqa: E402

PQ = HERE / "data" / "panic_pq"
OUT = D.OUT_DIR / "pq.json"


def main():
    eq = np.load(PQ / "best_equity.npy")
    cal = pd.read_csv(PQ / "panic_daily.csv", usecols=["date"])["date"]
    cal = cal[(cal >= "2007-05-15") & (cal <= D.END)].reset_index(drop=True)
    assert len(cal) == len(eq), (len(cal), len(eq))
    dates = pd.to_datetime(cal)
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    rf = np.zeros(len(r))  # 同原腳本：閒置現金不計息
    c0, _ = D.overlay(r, rf, np.ones(len(r)), None)
    cagr0, mdd0, sh0 = D.stats(c0, dates)
    print(f"PQ 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%}（PQ_OPTIMIZED +2.1%／-8.3%）", flush=True)
    c1x = np.cumprod(1 + r)
    tx = D.taiex()
    mkt = tx if tx.index.min() <= dates.iloc[0] else H.tx_series()
    proxy = "加權指數" if mkt is tx else "台指期連續合約（還原，加權指數快取起點晚於 2007-05）"
    res = {"orig": {"L": 1.0, "stop": None, "cagr": cagr0, "mdd": mdd0, "sharpe": sh0, "calmar": cagr0 / abs(mdd0)},
           "market_proxy": proxy, "invested_share": float((np.abs(r) > 1e-12).mean()),
           "episodes": [D.attribute(e, dates, c1x, mkt) for e in D.episodes(c0, dates)]}
    rows = []
    for kind, p in D.variants():
        f, info = D.cond_series(kind, p, dates, r, mkt)
        for stop in (None, 0.10):
            best = None
            for L in D.L_GRID:
                cv, _ = D.overlay(r, rf, L * f, stop)
                cg, md, sh = D.stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh}
                    break
            rows.append({"kind": kind, "desc": D.desc(kind, p), "stop": stop, "same_cagr": best})
    txs = H.tx_series()
    px = txs.reindex(pd.DatetimeIndex(dates)).ffill().to_numpy()
    rtx = np.zeros(len(px))
    rtx[1:] = np.where(np.isfinite(px[1:] / px[:-1]), px[1:] / px[:-1] - 1.0, 0.0)
    inv = (np.abs(r) > 1e-12).astype(float)  # 只在有持股的日子避險〔自行裁量〕
    for kind, p in H.hedge_variants():
        h = H.hedge_ratio(kind, p, px) * np.r_[0.0, inv[:-1]]
        reff = r - h * rtx - np.abs(np.diff(np.r_[0.0, h])) * H.TX.COST
        reff[0] = 0.0
        best = None
        for L in D.L_GRID:
            cv, _ = D.overlay(reff, rf, np.full(len(r), L), None)
            cg, md, sh = D.stats(cv, dates)
            if cg >= cagr0 - 1e-9:
                best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh}
                break
        rows.append({"kind": "hedge_" + kind, "desc": "避險：" + H.hdesc(kind, p), "stop": None, "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    bykind = {}
    for x in feas:
        if x["kind"] not in bykind or x["same_cagr"]["mdd"] > bykind[x["kind"]]["same_cagr"]["mdd"]:
            bykind[x["kind"]] = x
    res.update(n_variants=len(rows), n_feasible=len(feas), best_by_kind=bykind,
               best=max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None,
               _generated_at=datetime.now().isoformat(timespec="seconds"))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    b = res["best"]
    print("最好：", b["desc"] if b else None, b["stop"] if b else None, b["same_cagr"] if b else None)


if __name__ == "__main__":
    main()
