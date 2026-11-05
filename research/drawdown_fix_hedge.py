"""先.一五二-1b ③ 台指期空單避險（帳戶層，樣本內描述性最優化，不是判定）。

做法：台股個股家族（F12／F14／F17／F18）的 1× 底層日報酬 r，疊一條台指期（TX 連續合約、還原）空單：
    r_eff[t] = r[t] − h[t]·r_tx[t] − |h[t] − h[t−1]|·TX.COST
h＝避險比例（每 1 元多頭配多少元期貨空單名目），只用前一日以前的資訊決定。
帳戶再用 drawdown_fix.overlay() 照原版 L／帳戶停損模擬（避險名目隨 L 放大），L' 由低往高掃到年化 ≥ 原版，比 MDD。
期貨保證金假設由帳戶現金支應、現金照領 rf（overlay 已處理 1−e 的部分），不另計保證金機會成本〔自行裁量〕。
期貨空單沒有借券問題；但這仍是含空單腿的數字，附資料缺陷但書（轉倉價差用還原序列近似、未計逐筆滑價）。
零外部請求；資料只到 2024-12-31，holdout 未讀。非投資建議。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ARGV = sys.argv[1:]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drawdown_fix as D  # noqa: E402  （會改寫 sys.argv，先存起來）
import reaudit_optimized_batch2_tx as TX  # noqa: E402

OUT = D.OUT_DIR / "hedge.json"


def tx_series():
    s, _ = TX.build_continuous_series(contract="TX", session="position")
    s = s.copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[s["date"] <= D.END].sort_values("date")
    return pd.Series(s["adj_close"].to_numpy(float), index=pd.DatetimeIndex(s["date"]))


def hedge_variants():
    for h in (0.25, 0.5, 0.75):
        yield "static", {"h": h}
    for n in (60, 120, 200):
        for h in (0.5, 1.0):
            yield "ma", {"n": n, "h": h}
    for n in (120, 200):
        for x in (0.10, 0.15, 0.20):
            for h in (0.5, 1.0):
                yield "crash", {"n": n, "x": x, "h": h}


def hdesc(kind, p):
    if kind == "static":
        return f"固定空 {p['h']:.2f} 倍台指期"
    if kind == "ma":
        return f"台指期<{p['n']}日均線→空 {p['h']:.2f} 倍"
    return f"台指期<{p['n']}日均線且距252日高點跌>{p['x']:.0%}→空 {p['h']:.2f} 倍"


def hedge_ratio(kind, p, px):
    n = len(px)
    if kind == "static":
        h = np.full(n, p["h"])
    else:
        s = pd.Series(px)
        ma = s.rolling(p["n"], min_periods=p["n"]).mean().to_numpy()
        on = px < ma
        if kind == "crash":
            hi = s.rolling(252, min_periods=60).max().to_numpy()
            on = on & (px / hi - 1 < -p["x"])
        h = np.where(on, p["h"], 0.0)
    h = np.concatenate([[0.0], h[:-1]])  # 前一日資訊
    return np.where(np.isfinite(h), h, 0.0)


def run(fid, txs):
    F = D.load_family(fid)
    dates, r = F["dates"], F["r"]
    rf = D.LB.load_tw_rf_daily(dates)
    stop0 = None if F["stop"] is None or F["stop"] != F["stop"] else float(F["stop"])
    c0, _ = D.overlay(r, rf, np.full(len(r), F["L"]), stop0)
    cagr0, mdd0, sh0 = D.stats(c0, dates)
    ok = abs(cagr0 - F["cagr0"]) < 0.002 and abs(mdd0 - F["mdd0"]) < 0.002
    print(f"{fid} 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%} → {'對上' if ok else '對不上'}", flush=True)
    res = {"fid": fid, "title": F["title"], "orig": {"L": F["L"], "stop": stop0, "cagr": cagr0, "mdd": mdd0,
                                                     "sharpe": sh0, "calmar": cagr0 / abs(mdd0)}, "reproduced": ok}
    if not ok:
        res["error"] = "重建對不上"
        return res
    idx = pd.DatetimeIndex(dates)
    px = txs.reindex(idx).ffill().to_numpy()
    rtx = np.zeros(len(px))
    rtx[1:] = np.where(np.isfinite(px[1:] / px[:-1]), px[1:] / px[:-1] - 1.0, 0.0)
    res["corr_r_tx"] = float(np.corrcoef(r[1:], rtx[1:])[0, 1])
    rows = []
    for kind, p in hedge_variants():
        h = hedge_ratio(kind, p, px)
        cost = np.abs(np.diff(np.r_[0.0, h])) * TX.COST
        reff = r - h * rtx - cost
        reff[0] = 0.0
        for stop in ({None, stop0}):
            best = None
            for L in D.L_GRID:
                cv, ns = D.overlay(reff, rf, np.full(len(r), L), stop)
                cg, md, sh = D.stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None}
                    break
            cv1, _ = D.overlay(reff, rf, np.full(len(r), F["L"]), stop)
            cg1, md1, sh1 = D.stats(cv1, dates)
            rows.append({"kind": kind, "params": p, "desc": hdesc(kind, p), "stop": stop,
                         "avg_hedge": float(h.mean()), "hedge_on_share": float((h > 0).mean()),
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1}, "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    res["n_variants"], res["n_feasible"] = len(rows), len(feas)
    bykind = {}
    for x in feas:
        if x["kind"] not in bykind or x["same_cagr"]["mdd"] > bykind[x["kind"]]["same_cagr"]["mdd"]:
            bykind[x["kind"]] = x
    res["best_by_kind"] = bykind
    res["best"] = max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None
    # 原槓桿下 MDD 最淺（不要求同年化）的版本，看「避險能把回撤壓到多淺、要付多少年化」
    res["best_mdd_atL0"] = max(rows, key=lambda x: x["atL0"]["mdd"])
    return res


def main():
    txs = tx_series()
    fams = [f for f in ("F12", "F14", "F17", "F18") if not _ARGV or f in _ARGV]
    allres = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for fid in fams:
        try:
            res = run(fid, txs)
            b = res.get("best")
            if b:
                print(f"  同年化最好：{b['desc']} stop={b['stop']} L'={b['same_cagr']['L']} → {b['same_cagr']['cagr']:+.2%}／{b['same_cagr']['mdd']:.2%}", flush=True)
            else:
                print("  沒有避險版本在 L'≤3 下達到原版年化", flush=True)
        except Exception as e:  # noqa: BLE001 —— 單一家族失敗不影響其他家族
            print(f"::warning::{fid} 失敗：{e!r}")
            res = {"fid": fid, "error": repr(e)}
        allres[fid] = res
        allres["_generated_at"] = datetime.now().isoformat(timespec="seconds")
        OUT.write_text(json.dumps(allres, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
