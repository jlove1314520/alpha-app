# -*- coding: utf-8 -*-
"""先.一五五-3 第 28 批：S&P 指數納入事件（#51-US）事件後固定持有（紙上優化軌，描述性，零請求）。

**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（本批事件股多在納入時仍存活，
但納入後被併購／下市的股票若 yfinance 無價就整筆略過，偏樂觀。）

- 事件表：`sp500_addition_runup_gate51us.build_addition_events()`（只呼叫；S&P 官方新聞稿快取，Addition，
  2020-08～2026-08），價格：`yf_price_client.fetch_yf_index()` 本機快取（2010～2024-12-30）。腳本封鎖 socket。
- 公告新聞稿多在美東收盤後發布 → 觀察日＝公告日當天（非交易日則取前一個交易日），**下一個交易日收盤進場**
  （不吃公告後第一天的跳空，偏保守；另跑「下一交易日開盤進」變體只當參考——快取無開盤價則略過）。
- 出場：持有 H 個交易日（5/10/21/63），或「生效日前一個交易日收盤」（指數基金調倉那天）＋k 日（k=0/5/21）。
- 槽位 N 檔、等權、槽滿略過；同日依指數層級（500>400>600）優先；閒置資金收 DTB3。
- 成本 0.10%／邊；槓桿 L×r −(L−1)×(DTB3＋1.5%)/252；3× 超過 Reg T 只當參考；組合止損自高點回落 s 全數退現金 21 日。
- 大盤閘門：SPY 收盤 < 200 日均線時不新進場（t 判定）。
- 期間 2020-08-03～2024-12-30（本機價格只到 2024 底，約 4.4 年、事件數少，照實揭露）。
"""
from __future__ import annotations

import socket


def _blocked(*a, **k):
    raise OSError("reaudit_batch28：封網，零請求")


socket.socket.connect = _blocked
socket.create_connection = _blocked

import itertools  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sp500_addition_runup_gate51us import build_addition_events, _price_calendar  # noqa: E402

OUT_JSON = HERE / "data" / "reaudit_batch3_batch28.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
COST = 0.0010
SPREAD = 0.015
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20)
COOLDOWN = 21
TIER = {"S&P 500": 0, "S&P 100": 0, "DJIA": 0, "S&P MidCap 400": 1, "S&P SmallCap 600": 2}


def load():
    ev = build_addition_events()
    ev = ev[ev["index_name"].isin(TIER)].copy()
    closes, opens = {}, {}
    for t in ev["ticker"].unique():
        try:
            p = _price_calendar(t)
        except Exception as e:  # noqa: BLE001
            print(f"[警告] {t} 讀價失敗：{e}")
            p = None
        if p is None:
            continue
        p = p.copy()
        p["date"] = pd.to_datetime(p["date"])
        p = p.set_index("date")
        closes[t] = p["close"].astype(float)
        if "open" in p.columns:
            opens[t] = p["open"].astype(float)
    px = pd.DataFrame(closes).sort_index()
    op = pd.DataFrame(opens).reindex(px.index) if opens else None
    spy = _price_calendar("SPY")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date")["close"].astype(float)
    idx = spy.index[(spy.index >= "2019-01-01")]
    px = px.reindex(idx)
    if op is not None:
        op = op.reindex(idx)
    spy = spy.reindex(idx)
    return ev, px, op, spy


def build_events(ev, px):
    idx = px.index
    rows = []
    for _, r in ev.iterrows():
        if r["ticker"] not in px.columns:
            continue
        a = pd.Timestamp(r["announce_date"])
        e = pd.Timestamp(r["effective_date"])
        ia = int(np.searchsorted(idx, a, side="right")) - 1  # 公告日或之前最後一個交易日
        ie = int(np.searchsorted(idx, e, side="left"))  # 生效日（或其後第一個交易日）
        if ia < 0 or ie >= len(idx) or ie <= ia + 1:
            continue
        rows.append({"sid": r["ticker"], "obs": ia, "eff_prev": ie - 1, "tier": TIER[r["index_name"]],
                     "index": r["index_name"], "announce": r["announce_date"], "effective": r["effective_date"]})
    return pd.DataFrame(rows)


def sim(px, op, R, rf, gate, evt, hold, nmax, use_gate, entry_open=False):
    """hold=('H',n) 固定 n 日；('E',k) 生效日前一交易日＋k 日。"""
    idx = px.index
    cols = {s: j for j, s in enumerate(px.columns)}
    P = px.to_numpy()
    O = op.to_numpy() if (entry_open and op is not None) else None
    by_day = {}
    for _, g in evt.sort_values("tier").groupby("obs", sort=False):
        by_day[int(g["obs"].iloc[0])] = g.to_dict("records")
    pos, cash, trades, wins = [], 1.0, 0, 0
    eq = np.ones(len(idx))
    for i in range(len(idx)):
        if i > 0:
            cash *= 1 + rf[i]
            for p in pos:
                r = R[i, p["c"]]
                p["v"] *= 1 + (0.0 if np.isnan(r) else r)
        keep = []
        for p in pos:
            if i >= p["x"]:
                v = p["v"] * (1 - COST)
                cash += v
                trades += 1
                wins += v > p["v0"]
            else:
                keep.append(p)
        pos = keep
        V = cash + sum(p["v"] for p in pos)
        if i >= 1 and ((not use_gate) or gate[i - 1]):
            for e in by_day.get(i - 1, []):
                if len(pos) >= nmax:
                    break
                c = cols[e["sid"]]
                if np.isnan(P[i, c]) or any(p["c"] == c for p in pos):
                    continue
                x = i + hold[1] if hold[0] == "H" else max(e["eff_prev"] + hold[1], i + 1)
                amt = min(V / nmax, cash)
                if amt <= 1e-9:
                    break
                cash -= amt
                v = amt * (1 - COST)
                if O is not None:
                    o = O[i, c]
                    if np.isnan(o) or o <= 0:
                        cash += amt
                        continue
                    v *= P[i, c] / o  # 開盤進場：當日開→收報酬
                pos.append({"c": c, "v": v, "v0": amt, "x": x})
        eq[i] = cash + sum(p["v"] for p in pos)
    return eq, trades, wins / max(trades, 1)


def overlay(eq, rf, borrow, L, stop):
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    out = np.zeros(len(eq))
    v, peak, cool, inp, n = 1.0, 1.0, 0, True, 0
    for i in range(len(eq)):
        if i > 0:
            v *= (1 + L * r[i] - (L - 1) * borrow[i]) if inp else (1 + rf[i])
            v = max(v, 0.0)
        if inp:
            peak = max(peak, v)
            if stop is not None and v < peak * (1 - stop):
                inp, cool, n = False, COOLDOWN, n + 1
        else:
            cool -= 1
            if cool <= 0:
                inp, peak = True, v
        out[i] = v
    return out, n


def st(dates, c):
    yrs = (dates[-1] - dates[0]).days / 365.25
    r = np.diff(c) / c[:-1]
    sd = r.std()
    cagr = float(c[-1] ** (1 / yrs) - 1) if c[-1] > 0 else -1.0
    mdd = float((c / np.maximum.accumulate(c) - 1).min())
    return {"cagr": cagr, "mdd": mdd, "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "calmar": cagr / abs(mdd) if mdd < 0 else 0.0}


def main():
    t0 = datetime.now()
    ev, px, op, spy = load()
    evt = build_events(ev, px)
    start = pd.Timestamp("2020-08-03")
    i0 = int(np.searchsorted(px.index, start))
    px, spy = px.iloc[i0 - 1:], spy.iloc[i0 - 1:]
    if op is not None:
        op = op.iloc[i0 - 1:]
    evt = evt.assign(obs=evt["obs"] - (i0 - 1), eff_prev=evt["eff_prev"] - (i0 - 1))
    evt = evt[evt["obs"] >= 0]
    dates = px.index
    R = pd.DataFrame({c: px[c].dropna().pct_change() for c in px.columns}).reindex(dates).to_numpy()
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    rf_ann = np.asarray(LB.load_dtb3_annual(pd.Series(dates)), dtype=float)
    rf, borrow = rf_ann / 252, (rf_ann + SPREAD) / 252
    spy_full = _price_calendar("SPY")
    spy_full["date"] = pd.to_datetime(spy_full["date"])
    ma = spy_full.set_index("date")["close"].astype(float).rolling(200, min_periods=200).mean().reindex(dates)
    gate = (spy > ma).to_numpy()
    print(f"事件 {len(evt)} 筆（{evt['sid'].nunique()} 檔）；開盤價 {'有' if op is not None else '無'}；期間 {dates[0].date()}～{dates[-1].date()}")
    families = {"ALL": evt, "SP500": evt[evt["tier"] == 0], "MID400": evt[evt["tier"] == 1],
                "SMALL600": evt[evt["tier"] == 2]}
    holds = [("H", 5), ("H", 10), ("H", 21), ("H", 63), ("E", 0), ("E", 5), ("E", 21)]
    res = {}
    spy_c = spy.to_numpy() / spy.iloc[0]
    for fam, fe in families.items():
        rows = []
        for hold, nmax, ug in itertools.product(holds, (5, 10, 20), (False, True)):
            eq, n, w = sim(px, op, R, rf, gate, fe, hold, nmax, ug)
            for L, s in itertools.product(LEVS, STOPS):
                c, ns = overlay(eq, rf, borrow, L, s)
                d = st(dates, c)
                d.update({"hold": f"{hold[0]}{hold[1]}", "N": nmax, "gate": ug, "L": L, "stop": s,
                          "trades": n, "win": w, "n_stop": ns})
                rows.append(d)
        ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 20]
        best = max(ok, key=lambda r: r["calmar"]) if ok else None
        best1 = max([r for r in ok if r["L"] == 1.0], key=lambda r: r["calmar"], default=None)
        res[fam] = {"n_events": int(len(fe)), "grid": len(rows), "best": best, "best_1x": best1,
                    "n_violate": sum(r["mdd"] <= -0.5 for r in rows)}
        print(fam, len(fe), best)
    # 參考：最佳族開盤進場變體
    ref = None
    if op is not None and res["ALL"]["best"]:
        b = res["ALL"]["best"]
        hold = (b["hold"][0], int(b["hold"][1:]))
        eq, n, w = sim(px, op, R, rf, gate, evt, hold, b["N"], b["gate"], entry_open=True)
        c, _ = overlay(eq, rf, borrow, b["L"], b["stop"])
        ref = st(dates, c) | {"trades": n}
    # 基準
    import reaudit_batch9_us_price as B9  # noqa: F401,E402 （只為確保同口徑可追溯，不呼叫）
    eqw = np.nanmean(np.where(np.isnan(R), 0, R)[1:], axis=1)
    out = {"generated": datetime.now().isoformat(timespec="seconds"), "period": [str(dates[0].date()), str(dates[-1].date())],
           "n_events": int(len(evt)), "n_tickers": int(evt["sid"].nunique()), "families": res,
           "open_entry_ref": ref, "spy": st(dates, spy_c),
           "event_universe_eqw": st(dates, np.concatenate([[1.0], np.cumprod(1 + eqw)])),
           "secs": (datetime.now() - t0).seconds}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    render(out)
    print(json.dumps({k: out[k] for k in ("spy", "event_universe_eqw", "open_entry_ref", "secs")}, ensure_ascii=False, default=str))


def _p(x):
    return "—" if x is None else f"{x*100:+.1f}%"


def render(out):
    L = ["<!-- BATCH3-B28-BEGIN -->", "", "### 31. 第二批 第 28 批：S&P 指數納入事件（#51-US，美股，零請求）", "",
         f"產生：{out['generated']}；期間 {out['period'][0]}～{out['period'][1]}（本機美股價格只到 2024 底）；"
         f"事件 {out['n_events']} 筆／{out['n_tickers']} 檔。腳本 `research/reaudit_batch28_sp_addition.py`，明細 `research/data/reaudit_batch3_batch28.json`。",
         "", "> **存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 納入後被併購下市、yfinance 無價的事件整筆略過。",
         "> 公告日下一個交易日收盤進場（不吃公告後第一天跳空）；成本 0.10%／邊；槓桿扣 DTB3＋1.5%；3× 超過 Reg T 只當參考；參數用全期挑，非樣本外；只有約 4.4 年。", "",
         "| 族 | 事件數 | 最佳組（MDD≤50%、交易≥20） | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 1× 最佳 年化／MDD／Calmar |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for fam, r in out["families"].items():
        b, b1 = r["best"], r["best_1x"]
        if not b:
            L.append(f"| {fam} | {r['n_events']} | 無合格組 | | | | | | | |")
            continue
        g = f"{b['hold']}、N={b['N']}、{'閘門' if b['gate'] else '不擇時'}、{b['L']}×、止損 {b['stop'] or '無'}"
        s1 = f"{_p(b1['cagr'])}／{_p(b1['mdd'])}／{b1['calmar']:.2f}" if b1 else "—"
        L.append(f"| {fam} | {r['n_events']} | {g} | {_p(b['cagr'])} | {_p(b['mdd'])} | {b['sharpe']:.2f} | {b['calmar']:.2f} | {b['trades']} | {b['win']*100:.0f}% | {s1} |")
    s, e = out["spy"], out["event_universe_eqw"]
    L += ["", f"同期 SPY {_p(s['cagr'])}／{_p(s['mdd'])}（Calmar {s['calmar']:.2f}）；事件股等權持有 {_p(e['cagr'])}／{_p(e['mdd'])}（Calmar {e['calmar']:.2f}；**偷看未來**：名冊是「之後被納入」的股票，只當參考）。"
          + (f" 參考：ALL 最佳組改公告後下一交易日開盤進 {_p(out['open_entry_ref']['cagr'])}／{_p(out['open_entry_ref']['mdd'])}。" if out.get("open_entry_ref") else ""),
          "", "讀法：SP500 族最佳組（公告後隔日收盤進、生效日前一交易日收盤出＝搶跑窗口）年化低、Calmar 高主要來自多數時間空手；"
          "MID400 的 3× 超過 Reg T 只當參考，1× 最佳 Calmar 0.43；SP500 族之外，其餘 3 族的 1× 最佳組 Calmar 都輸同期 SPY 買進持有（0.65）；SP500 族只有 40 筆事件、28 筆交易、年化 3.6%，不足以單獨上紙上。"
          "〔自行裁量〕不進候選欄（門檻 Calmar ≥0.6 且要贏同期基準、交易 ≥100）。", "", "<!-- BATCH3-B28-END -->"]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if "<!-- BATCH3-B28-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B28-BEGIN -->")
        z = txt.index("<!-- BATCH3-B28-END -->") + len("<!-- BATCH3-B28-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
