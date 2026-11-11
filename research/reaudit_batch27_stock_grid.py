"""先.一五五-3 第 27 批：個股網格交易（stock_grid，原 #468～#482）2015 起全期掃格（紙上優化軌，零請求）。

原試驗（`stock_grid_oneshot.py`）只跑 2007-10～2009-12 單發。這裡改用 #133 抽樣 236 檔延長價格（2015-01～2026-09-24，含 2025 起），
規則沿用原 PREREG 第 1～2 節的骨架，只把可調的地方攤開掃：
- 宇宙：每月第一個交易日，236 檔中「前 60 個交易日平均成交金額」前 K 名（K∈{20,50}）；跌出宇宙 → 當天開盤出清既有格位。
- 建格（月初、且該檔無持倉才重建）：中心＝60 日均線（還原收盤）；格距 g＝m×ATR20（Wilder，還原高低收），m∈{0.5,1.0,1.5}；
  L₋₅…L₊₅ 共 10 格。
- 進場：收盤由上往下跌破格下緣 Lᵢ（i＝−4…+4，i＝−5 與停損相同不買）且格位空 → 隔日開盤買一份；出場：收盤站上 Lᵢ₊₁ → 隔日開盤賣。
- 停損：收盤跌破 L₋₅ → 隔日開盤該檔全部出清、冷卻 20 個交易日；另掃「不停損」版（跌破 L₋₅ 只停止新買）。
- 每份金額＝前一日組合淨值 ÷K ÷10；現金不足就不買；未用資金收台灣無風險利率。
- 成交限制：隔日開盤相對前一還原收盤漲 ≥9.5% 不買（取消）、跌 ≤−9.5% 不賣（順延）；個股價格斷了（2025 起缺價）以最後收盤出清。
- 成本：買 0.1425%＋滑價 5bps；賣 0.1425%＋證交稅 0.3%＋滑價 5bps（同第 6／7 批）。
- 槓桿／組合止損只呼叫 batch2 overlay（同第 7 批 `S.overlay`）。
共 5（m∈{0.5,1,1.5,2,2.5}）×2（K）×2（停損）＝20 次模擬 ×16 overlay＝320 格。名冊有存活者偏誤（照實揭露）。不改核心檔、不寫試驗帳本。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import socket
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


def _no_net(*a, **k):
    raise RuntimeError("第 27 批零請求：封鎖網路")


socket.socket.connect = _no_net
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reaudit_batch7_events as B7  # noqa: E402
import reaudit_batch22_material_news as B22  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
OUT = HERE / "data" / "reaudit_batch3_batch27.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
CAND = HERE / "data" / "paper_opt_candidates.json"
BUY_C = 0.001425 + 0.0005
SELL_C = 0.001425 + 0.003 + 0.0005
MA_N, ATR_N, LOOK, COOL = 60, 20, 60, 20


def wide(ext, col, idx):
    return pd.DataFrame({sid: pd.Series(d[col].astype(float).to_numpy(), index=pd.to_datetime(d["date"].astype(str).str[:10]))
                         for sid, d in ext.items()}).sort_index().loc[lambda x: ~x.index.duplicated()].reindex(idx)


def prep(ext, px):
    idx = px.index
    O, H, L, C = (wide(ext, c, idx) for c in ("adj_open", "adj_high", "adj_low", "adj_close"))
    TM = wide(ext, "Trading_money", idx).fillna(0.0)
    ma, atr = {}, {}
    for sid in C.columns:
        c = C[sid].dropna()
        h, l = H[sid].reindex(c.index), L[sid].reindex(c.index)
        tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
        atr[sid] = tr.ewm(alpha=1 / ATR_N, adjust=False, min_periods=ATR_N).mean().reindex(idx)
        ma[sid] = c.rolling(MA_N, min_periods=MA_N).mean().reindex(idx)
    tm60 = TM.shift(1).rolling(LOOK, min_periods=LOOK // 2).mean()  # 月初之前 60 日（不含當天）
    return O, C, pd.DataFrame(ma), pd.DataFrame(atr), tm60


def simulate(O, C, MA, ATR, tm60, rf, m, K, use_stop, start, end):
    idx = C.index
    sel = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
    dates = idx[sel]
    cols = list(C.columns)
    o, c, ma, atr = O.to_numpy(), C.to_numpy(), MA.to_numpy(), ATR.to_numpy()
    t60 = tm60.to_numpy()
    rfa = rf.reindex(idx).to_numpy()
    pos0 = np.where(sel)[0][0]
    ns = len(cols)
    shares = np.zeros((ns, 10))
    grid = np.full((ns, 11), np.nan)
    cool = np.zeros(ns, dtype=int)
    in_univ = np.zeros(ns, dtype=bool)
    pend_buy = [set() for _ in range(ns)]
    pend_sell = [set() for _ in range(ns)]
    pend_all = np.zeros(ns, dtype=bool)
    last_c = np.full(ns, np.nan)
    cash = 1.0
    nav_prev = 1.0
    eq, trades, wins = [], 0, 0
    cost_basis = np.zeros((ns, 10))
    month = None
    for t in range(pos0, pos0 + len(dates)):
        ct, ot = c[t], o[t]
        # 1) 開盤成交（前一日收盤決定的指令）
        for j in range(ns):
            prevc = last_c[j]
            op = ot[j]
            if not np.isfinite(op) or not np.isfinite(prevc):
                continue
            up_lock = op >= prevc * 1.095
            dn_lock = op <= prevc * 0.905
            sell_slots = set(range(10)) if pend_all[j] else set(pend_sell[j])
            if sell_slots and not dn_lock:
                for s in sell_slots:
                    if shares[j, s] > 0:
                        cash += shares[j, s] * op * (1 - SELL_C)
                        trades += 1
                        wins += int(op * (1 - SELL_C) > cost_basis[j, s])
                        shares[j, s] = 0.0
                pend_sell[j].clear()
                pend_all[j] = False
            if pend_buy[j]:
                if not up_lock:
                    amt = nav_prev / K / 10
                    for s in sorted(pend_buy[j]):
                        if shares[j, s] == 0 and cash >= amt:
                            shares[j, s] = amt / (op * (1 + BUY_C))
                            cost_basis[j, s] = op * (1 + BUY_C)
                            cash -= amt
                pend_buy[j].clear()
        # 2) 個股價格斷了（2025 起缺價等）：以最後收盤出清
        for j in range(ns):
            if shares[j].sum() > 0 and not np.isfinite(ct[j]) and t + 1 < len(idx) and not np.isfinite(c[min(t + 5, len(idx) - 1), j]):
                cash += shares[j].sum() * last_c[j] * (1 - SELL_C)
                trades += int((shares[j] > 0).sum())
                shares[j] = 0.0
        # 3) 月初：宇宙＋建格
        mo = idx[t].to_period("M")
        if mo != month:
            month = mo
            v = t60[t]
            ok = np.isfinite(v) & np.isfinite(ct) & (v > 0)
            order = np.argsort(-np.where(ok, v, -1))[:K]
            new_u = np.zeros(ns, dtype=bool)
            new_u[order[ok[order]]] = True
            for j in range(ns):
                if in_univ[j] and not new_u[j] and shares[j].sum() > 0:
                    pend_all[j] = True
                if new_u[j] and shares[j].sum() == 0 and cool[j] <= 0 and np.isfinite(ma[t, j]) and np.isfinite(atr[t, j]) and atr[t, j] > 0:
                    grid[j] = ma[t, j] + m * atr[t, j] * np.arange(-5, 6)
                elif not new_u[j] and shares[j].sum() == 0:
                    grid[j] = np.nan
            in_univ = new_u
        # 4) 收盤判斷（明日開盤執行）
        for j in range(ns):
            cj, pj = ct[j], last_c[j]
            if np.isfinite(cj):
                cool[j] -= 1
            if not (np.isfinite(cj) and np.isfinite(pj)) or not np.isfinite(grid[j, 0]):
                if np.isfinite(cj):
                    last_c[j] = cj
                continue
            g = grid[j]
            if cj < g[0]:
                if use_stop and shares[j].sum() > 0:
                    pend_all[j] = True
                    cool[j] = COOL
                    grid[j] = np.nan
                elif use_stop:
                    cool[j] = COOL
                    grid[j] = np.nan
                last_c[j] = cj
                continue
            for s in range(10):
                lo, hi = g[s], g[s + 1]
                if shares[j, s] > 0 and cj > hi and pj <= hi:
                    pend_sell[j].add(s)
                elif shares[j, s] == 0 and s >= 1 and in_univ[j] and pj >= lo > cj:
                    pend_buy[j].add(s)
            last_c[j] = cj
        cash *= 1 + (rfa[t] if np.isfinite(rfa[t]) else 0.0)
        hold = np.nansum(shares.sum(axis=1) * np.where(np.isfinite(ct), ct, last_c))
        nav = cash + hold
        eq.append(nav)
        nav_prev = nav
    return dates, np.array(eq), trades, (wins / trades if trades else 0.0)


def main():
    t0 = time.time()
    ext, px, gate, rf, miss = B7.load()
    O, C, MA, ATR, tm60 = prep(ext, px)
    end = str(px.index[-1].date())
    start = "2015-01-02"
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    ew = ret[ret.index >= pd.Timestamp(start)].mean(axis=1).fillna(0)
    out = {"meta": {"start": start, "end": end, "n_stocks": int(px.shape[1])}, "bench_ew": B7.st(ew.index, (1 + ew).cumprod().to_numpy()),
           "families": []}
    for K in (20, 50):
        rows = []
        for m, use_stop in itertools.product((0.5, 1.0, 1.5, 2.0, 2.5), (True, False)):
            dates, eq, tr, wr = simulate(O, C, MA, ATR, tm60, rf, m, K, use_stop, start, end)
            rfa = rf.reindex(dates).to_numpy()
            base = B7.st(dates, eq)
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                cc, _ = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, cc)
                rows.append({"m": m, "grid_stop": use_stop, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0,
                             "from_2025": B7.seg(dates, cc, "2025-01-01", end),
                             "to_2024": B7.seg(dates, cc, start, "2024-12-31")})
            print(f"K={K} m={m} 停損={use_stop} 1× {base['cagr']:+.1%}/{base['mdd']:.1%} 交易 {tr}（{time.time()-t0:.0f}s）", flush=True)
        ok = [x for x in rows if x["mdd"] > -0.5 and x["trades"] >= 100]
        best = max(ok or rows, key=lambda x: x["calmar"])
        best1 = max([x for x in rows if x["L"] == 1.0 and x["stop"] is None], key=lambda x: x["calmar"])
        out["families"].append({"family": f"grid K={K}", "K": K, "n_cells": len(rows), "best": best, "best_1x_nostop": best1,
                                "violates_survival_cells": sum(x["mdd"] <= -0.5 for x in rows), "meets_trade_floor": bool(ok)})
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    render(out)


def _s(x):
    return f"{x['cagr']:+.1%}／{x['mdd']:.1%}" if x else "—"


def render(out):
    b = out["bench_ew"]
    lines = ["<!-- BATCH3-B27-BEGIN -->", "",
             "### 30. （#133 抽樣 236 檔）個股網格交易 stock_grid 2015 起全期掃格（`research/reaudit_batch27_stock_grid.py`，零請求）", "",
             "做法：原 #468～#482 只跑 2007-10～2009-12 單發；這裡沿用原 PREREG 骨架（月初選成交金額前 K 名、60 日均線為中心、"
             "格距 m×ATR20、L₋₅…L₊₅ 10 格、收盤跌破格下緣隔日開盤買一份、站上上緣隔日開盤賣、跌破 L₋₅ 停損冷卻 20 日），"
             f"掃 K∈{{20,50}}×m∈{{0.5,1,1.5,2,2.5}}×停損開關×槓桿 1～3×組合止損 4 種＝每族 160 格；期間 {out['meta']['start']}～{out['meta']['end']}"
             "（含 2025 起；參數用全期挑、2025 起分段不是樣本外）。每份＝前日淨值÷K÷10、閒置資金收無風險利率；隔日開盤漲 ≥9.5% 不買、跌 ≤−9.5% 順延賣。"
             f"名冊有存活者偏誤，照實揭露。同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。非投資建議。", "",
             "| 族 | m | 格停損 | 槓桿 | 組合止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 2015～2024 | 2025 起 | 1× 不設組合止損最好 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r, r1 = f["best"], f["best_1x_nostop"]
        lines.append(f"| {f['family']} | {r['m']} | {'開' if r['grid_stop'] else '關'} | {r['L']}× | {B22.stop_txt(r['stop'])} | "
                     f"{r['cagr']:+.1%} | {r['mdd']:.1%} | {r['sharpe']:.2f} | {r['calmar']:.2f} | {r['trades']} | {r['win_rate']:.0%} | "
                     f"{_s(r.get('to_2024'))} | {_s(r.get('from_2025'))} | m={r1['m']} 停損{'開' if r1['grid_stop'] else '關'} "
                     f"{r1['cagr']:+.1%}／{r1['mdd']:.1%}（Calmar {r1['calmar']:.2f}） |")
    lines += ["", "<!-- BATCH3-B27-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    b0, b1 = "<!-- BATCH3-B27-BEGIN -->", "<!-- BATCH3-B27-END -->"
    if b0 in txt:
        txt = txt[:txt.index(b0)] + block + txt[txt.index(b1) + len(b1):]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        render(json.loads(OUT.read_text(encoding="utf-8")))
    else:
        main()
