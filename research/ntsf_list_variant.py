# -*- coding: utf-8 -*-
"""先.一五六-2a ① 國安基金事件策略：PQ／F12 名單版本（紙上優化軌，研究帽產物）。零外部請求。

做法：
- 事件與進場日照 research/ntsf_event_study.py（宣布後下一交易日收盤進場；宣布日查不到用首日進場日當參考日，保守）。
- 名單在「參考日收盤後」決定（只用當時看得到的資料）：
  * PQ：research/panic_pq_backtest.py 的 list_on(strict, peak 濾網, 前 20 檔)，財報可得日照該檔 avail 欄（PIT）。
  * F12：Weinstein 第二階段條件（還原收盤 > MA150 且 MA150 > 10 日前 MA150），依 60 日報酬取前 20 檔。
    [自行裁量] 宇宙用 panic_pq 價格矩陣的 1,509 檔（不是 F12 回測的 236 檔抽樣宇宙），也不套 F12 的大盤崩盤閘門
    ——國安基金事件幾乎都落在崩盤閘門關閉期間，套閘門等於永遠不進場。
- 組合：進場日收盤等權買進（名單不足 20 檔的部分留現金；進場日鎖漲停的那檔買不到、留現金），買後各檔權重自然漂移。
  出場規則同 NTSF：移動停利（組合槓桿後淨值自高點回撤 p）或固定持有，最多 250 日；槓桿 {1, 1.5, 2}，
  超過 1 倍部分付融資 6.5%/年（同 panic_pq）。
- 成本：買 手續費 0.1425%＋滑價 0.05%；賣 手續費＋證交稅 0.3%＋滑價 0.05%（同 panic_pq）。
- 限制（照實）：出場日個股鎖跌停仍假設以收盤賣出（偏樂觀）；個股停牌／下市期間日報酬記 0、以最後價值計（偏樂觀）。
- 價格矩陣只到 2024-12-31，所以只涵蓋事件 4～8（2008、2011、2015、2020、2022）；2025 事件沒有還原日報酬，本批未做。
  對照：同 5 次事件的 NTSF-A（指數 2× 停利 15%）／NTSF-B（指數 3× 停利 10%），用 ntsf_event_study 的同一套函式。
輸出：research/data/ntsf_list_variant.json（本機）。非投資建議。
"""
from __future__ import annotations

import json
import pickle
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ntsf_event_study as ne  # noqa: E402
import panic_pq_backtest as pp  # noqa: E402

OUT = HERE / "data" / "ntsf_list_variant.json"
FIN = 0.065
FEE, TAX, SLIP = 0.001425, 0.003, 0.0005
BUY_C, SELL_C = FEE + SLIP, FEE + TAX + SLIP
N = 20
MAX_HOLD = 250


def f12_list(adj: np.ndarray, t: int, ids: list[str], n: int = N) -> list[int]:
    if t < 170:
        return []
    win = adj[t - 160:t + 1]
    ma_now = np.nanmean(adj[t - 149:t + 1], axis=0)
    ma_prev = np.nanmean(adj[t - 159:t - 9], axis=0)
    cnt = np.sum(~np.isnan(adj[t - 149:t + 1]), axis=0)
    ret60 = adj[t] / adj[t - 60] - 1
    ok = (cnt >= 140) & (adj[t] > ma_now) & (ma_now > ma_prev) & ~np.isnan(ret60) & ~np.isnan(win[-1])
    # 只取 4 碼普通股
    stock = np.array([len(s) == 4 and s[0] != "0" for s in ids])
    ok &= stock
    js = np.where(ok)[0]
    return js[np.argsort(-ret60[js])][:n].tolist()


def run_basket(P, js: list[int], ent: int, L: float, kind: str, p: float) -> dict | None:
    C, R, LK = P["C"], P["R"], P["LK"]
    T = len(P["cal"])
    if not js:
        return None
    buy = [j for j in js if not np.isnan(C[ent, j]) and not LK[ent, j]]
    w = np.zeros(len(buy)) + (1.0 - BUY_C) / N
    cash = 1.0 - len(buy) / N
    inv = len(buy) / N
    nav = 1.0
    peak, mdd, held, i = 1.0, 0.0, 0, ent
    exited = False
    while i + 1 < T and held < MAX_HOLD:
        i += 1
        held += 1
        rr = R[i, buy]
        rr = np.where(np.isnan(rr), 1.0, rr)
        prev = w.sum() + cash
        w = w * rr
        r1 = (w.sum() + cash) / prev - 1
        nav *= 1 + L * r1 - (L - 1) * FIN / 252 * inv
        peak = max(peak, nav)
        mdd = min(mdd, nav / peak - 1)
        if kind == "trail" and nav / peak - 1 <= -p:
            exited = True
            break
        if kind == "fixed" and held >= p:
            exited = True
            break
    # 賣出成本：持股部分 × 槓桿
    stock_frac = w.sum() / (w.sum() + cash)
    nav *= 1 - SELL_C * stock_frac * L
    return {"ret": nav - 1, "mdd": mdd, "days": held, "closed": exited or held >= MAX_HOLD,
            "n_names": len(js), "n_bought": len(buy), "exit_date": P["cal"][i]}


def main() -> int:
    P = pickle.loads((HERE / "data" / "panic_pq" / "prices_wide.pkl").read_bytes())
    ids, cal = P["ids"], P["cal"]
    pos = {s: j for j, s in enumerate(ids)}
    adj = np.cumprod(np.where(np.isnan(P["R"]), 1.0, P["R"]), axis=0)
    adj[np.isnan(P["C"])] = np.nan
    pq = pp.pq_table()
    cal_np = np.array(pd.to_datetime(cal).values)

    tx = ne.load_taiex()
    tdates = tx["date"].values
    tclose = tx["close"].values.astype(float)
    tma = {w: pd.Series(tclose).rolling(w).mean().values for w in (20, 60)}

    events = [r for r in ne.load_events() if r["no"] != "10"]
    lists = {}
    for r in events:
        ref_day = pd.Timestamp(r["announce_date"] or r["first_entry_date"])
        t = int(np.searchsorted(cal_np, np.datetime64(ref_day), side="left"))
        if t + 1 >= len(cal) or pd.Timestamp(cal[t]) - ref_day > pd.Timedelta(days=7) or t < 200:
            continue
        ds = cal[t]
        pq_ids = pp.list_on(pq, ds, "strict", "peak", P["C"][t], pos, N)
        lists[r["no"]] = {"ref": ds, "ent": t + 1, "PQ": [pos[s] for s in pq_ids], "F12": f12_list(adj, t, ids)}
    print("涵蓋事件", {k: (v["ref"], len(v["PQ"]), len(v["F12"])) for k, v in lists.items()})

    exits = [("fixed", 250), ("fixed", 120), ("trail", 0.10), ("trail", 0.15), ("trail", 0.20)]
    grid = []
    for name, L, (kind, p) in product(["PQ", "F12"], [1.0, 1.5, 2.0], exits):
        trades = []
        for no, v in lists.items():
            t = run_basket(P, v[name], v["ent"], L, kind, p)
            if t:
                t["no"] = int(no)
                t["entry_date"] = cal[v["ent"]]
                trades.append(t)
        rets = [t["ret"] for t in trades]
        grid.append({"list": name, "lev": L, "exit": f"{kind}_{p}", "n": len(trades),
                     "compound": round(float(np.prod([1 + x for x in rets]) - 1), 4) if rets else None,
                     "win": round(float(np.mean([x > 0 for x in rets])), 3) if rets else None,
                     "worst_trade": round(min(rets), 4) if rets else None,
                     "worst_dd": round(min(t["mdd"] for t in trades), 4) if trades else None,
                     "days": sum(t["days"] for t in trades),
                     "violates_survival": bool(trades) and min(t["mdd"] for t in trades) < -0.5,
                     "trades": [{k: (round(x, 4) if isinstance(x, float) else x) for k, x in t.items()} for t in trades]})

    # 對照：同一批事件的指數版（NTSF-A／B 與 1× 抱 250 日）
    bench = {}
    for lab, L, x in [("NTSF-A 指數2×停利15%", 2.0, ("trail", 0.15)), ("NTSF-B 指數3×停利10%", 3.0, ("trail", 0.10)),
                      ("指數1×抱250日", 1.0, ("fixed", 250)), ("指數2×停利20%", 2.0, ("trail", 0.20))]:
        tr = []
        for r in events:
            if r["no"] not in lists:
                continue
            ref, ent = ne.event_anchor(r, tdates)
            t = ne.run_trade(tclose, tma, ent, L, x)
            tr.append({"no": int(r["no"]), "ret": round(t["ret"], 4), "mdd": round(t["mdd"], 4), "days": t["days"]})
        rets = [t["ret"] for t in tr]
        bench[lab] = {"n": len(tr), "compound": round(float(np.prod([1 + x for x in rets]) - 1), 4),
                      "win": round(float(np.mean([x > 0 for x in rets])), 3), "worst_trade": min(rets),
                      "worst_dd": min(t["mdd"] for t in tr), "days": sum(t["days"] for t in tr), "trades": tr}

    out = {"note": "先.一五六-2a ①；零外部請求；價格矩陣 2007～2024（panic_pq），只涵蓋事件 4～8",
           "lists": {k: {"ref": v["ref"], "PQ": [ids[j] for j in v["PQ"]], "F12": [ids[j] for j in v["F12"]]} for k, v in lists.items()},
           "grid": grid, "bench": bench}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    for g in sorted(grid, key=lambda g: -(g["compound"] or -9)):
        print({k: g[k] for k in ("list", "lev", "exit", "n", "compound", "win", "worst_trade", "worst_dd", "days", "violates_survival")})
    print("— 指數對照（同事件）")
    for k, b in bench.items():
        print(k, {kk: b[kk] for kk in ("n", "compound", "win", "worst_trade", "worst_dd", "days")}, [(t["no"], t["ret"]) for t in b["trades"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
