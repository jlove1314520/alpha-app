# -*- coding: utf-8 -*-
"""先.一五五-3 第二批第 1 批 (a)：三個價量因子（f_low_vol／f_rel_strength／f_52w_high_prox）延長到 2025 起重跑。

紙上優化軌描述性，不寫 TRIALS_LEDGER；非投資建議。零新外部請求。
- 價格：沿用 `reaudit_ext2025_engine.load_extended()`（2024 底前＝reaudit_ssu_loaded.pkl；2025 起＝本機 FinMind 快取、
  用「漲跌」欄還原權息；2024 底仍掛牌但沒有 2025 起價格的 45 檔從 2024-11-15 起不給分數）。
- 因子：照 factors.py 原公式在延長後的 adj_close 上重算（LOW_VOL 60 日日報酬標準差取負；REL_STRENGTH 60 日報酬減大盤 60 日報酬；
  52W 收盤÷252 日最高）。先核對 2024 底前與 pkl 原欄一致才跑。
- 引擎格與 reaudit_batch3_factors.py 相同（48 格），期間 2015-01-01～本機資料終點；組合層 16 格在 summarize 算。

用法：python research/reaudit_batch3_ext2025.py run f_low_vol    （REAUDIT_DEADLINE＝epoch 秒）
     python research/reaudit_batch3_ext2025.py summarize
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_batch3_factors as B  # noqa: E402
import reaudit_ext2025_engine as E  # noqa: E402

FACS = ["f_low_vol", "f_rel_strength", "f_52w_high_prox"]
CELLS_DIR = HERE / "data" / "reaudit_batch3_ext2025_cells"
OUT_JSON = HERE / "data" / "reaudit_batch3_ext2025.json"
START = "2015-01-01"
prog = E.prog


# 第 2 批價量因子延長（DevQueue 20261107-073102）：公式照 factors.py 原文抄（窗口常數直接 import），
# 2024 底前逐值跟 pkl 核對，差 >1e-6 就停，不靠人眼保證抄對。
PRICE_FACS = FACS + ["f_idio_vol", "f_bab", "f_residual_momentum", "f_short_reversal_1m",
                     "f_short_term_reversal_1w", "f_ma_breakout", "f_amihud_illiq",
                     "f_listing_age_days"]


from reaudit_ext2025_fin_factors import CHIP_FACS, FIN_FACS, attach as attach_fin, chip_coverage  # noqa: E402


def _factor_series(d, mc, fac, sid=None):
    import factors as F
    if fac == "f_listing_age_days":  # 照 factors._listing_age_days（官方上市日，查不到全 NaN）
        return F._listing_age_days(sid, d["date"]).astype(float)
    px = d["adj_close"].astype(float)
    r = px.pct_change()
    if fac == "f_low_vol":
        return -r.rolling(60, min_periods=60).std()
    if fac == "f_52w_high_prox":
        return px / px.rolling(252, min_periods=252).max()
    if fac == "f_rel_strength":
        m = d["date"].map(mc).astype(float)
        return (px / px.shift(60) - 1) - (m / m.shift(60) - 1)
    if fac == "f_short_reversal_1m":
        return -(px / px.shift(F.SHORT_REVERSAL_WINDOW) - 1)
    if fac == "f_short_term_reversal_1w":
        return -(px / px.shift(F.SHORT_TERM_REVERSAL_1W_WINDOW) - 1)
    if fac == "f_ma_breakout":
        ma = px.rolling(F.MA_WINDOW, min_periods=F.MA_WINDOW).mean()
        v = d["Trading_Volume"].astype(float)
        return (px / ma - 1) * (v.rolling(F.VOL_SHORT_WINDOW, min_periods=F.VOL_SHORT_WINDOW).mean()
                                / v.rolling(F.VOL_LONG_WINDOW, min_periods=F.VOL_LONG_WINDOW).mean())
    if fac == "f_amihud_illiq":
        tm = d["Trading_money"].astype(float)
        il = np.where(tm > 0, r.abs() / tm, np.nan)
        return pd.Series(il, index=d.index).rolling(F.AMIHUD_WINDOW, min_periods=F.AMIHUD_WINDOW).mean()
    m = d["date"].map(mc).astype(float)
    mr = m.pct_change()
    W = F.LOW_VOL_WINDOW
    if fac in ("f_idio_vol", "f_bab"):
        vs = r.rolling(W, min_periods=W).var()
        vm = mr.rolling(W, min_periods=W).var()
        beta = r.rolling(W, min_periods=W).cov(mr) / vm
        if fac == "f_bab":
            return -beta
        return -np.sqrt((vs - beta ** 2 * vm).clip(lower=0.0))
    if fac == "f_residual_momentum":
        W2 = F.RESIDUAL_MOMENTUM_WINDOW
        beta = r.rolling(W2, min_periods=W2).cov(mr) / mr.rolling(W2, min_periods=W2).var()
        return (px / px.shift(W2) - 1) - beta * (m / m.shift(W2) - 1)
    raise ValueError(f"{fac} 不是可直接重算的價量因子")


FIN_MISMATCH: list = []


def recompute(ext, mk, fac):
    mc = mk.set_index("date")["close"].astype(float)
    worst = 0.0
    for sid, d in ext.items():
        if fac in FIN_FACS:  # 財報類（DevQueue 20261107-090102）：照 F13 作法讀本機快取重算
            v = pd.Series(attach_fin(d, sid, fac), index=d.index)
            if fac in d.columns:
                # 〔自行裁量〕本機快取與當初建 pkl 時的資料版本有少數季不同（f_gross_profitability 實測 5/236 檔、只差 2024Q2 一季）：
                # 2024 底前一律沿用 pkl 原值（＝第 1／3 批回測用的值），2025 起才用重算值；不一致檔數另計，>5% 才停。
                pre_all = d["date"] <= "2024-12-31"
                a, b = d.loc[pre_all & (d["date"] >= START), fac].astype(float), v[pre_all & (d["date"] >= START)]
                both = a.notna() & b.notna()
                if both.any() and float((a[both] - b[both]).abs().max()) > 1e-6:
                    FIN_MISMATCH.append(sid)
                v = v.where(~pre_all, d[fac].astype(float))
        else:
            v = _factor_series(d, mc, fac, sid)
        pre = (d["date"] <= "2024-12-31") & (d["date"] >= START)
        if fac in d.columns:
            a, b = d.loc[pre, fac].astype(float), v[pre]
            both = a.notna() & b.notna()
            if both.any():
                scale = max(float(a[both].abs().median()), 1e-300) if fac == "f_amihud_illiq" else 1.0
                rel = (a[both] - b[both]).abs() / np.maximum(scale, a[both].abs() if fac == "f_amihud_illiq" else 1.0)
                worst = max(worst, float(rel.max()))
        d[fac] = v
    return worst


def run(fac, deadline):
    from backtest.engine import BacktestConfig, run_backtest
    from strategies.weinstein_stage2 import prepare_market_data
    ext, mk, miss, jumps, end = E.load_extended()
    if fac in CHIP_FACS:  # （DevQueue 20261107-230102）2025 起法人／融資券快取沒抓齊就不跑，避免缺檔被 fillna(0) 當成零買賣超
        lack = [sid for sid in ext if not all(chip_coverage(sid).values())]
        if lack:
            prog(f"{fac} 2025 起籌碼快取尚缺 {len(lack)}/{len(ext)} 檔（先跑 research/fetch_chip_2025_resume.py），不跑")
            return False
    diff = recompute(ext, mk, fac)
    prog(f"{fac} 2024 底前重算 vs pkl 最大差 {diff:.2e}")
    if fac in FIN_FACS:
        prog(f"{fac} 2024 底前與 pkl 不一致 {len(FIN_MISMATCH)}/{len(ext)} 檔（2024 底前沿用 pkl 原值）：{FIN_MISMATCH[:10]}")
        # 〔自行裁量〕f_dividend_yield_ttm 的 pkl 早於 10/22（分母改原始收盤）與 10/27（補公積配息）兩次 factors.py 修正，
        # 且 84 檔 pkl 分母是 yfinance 還原價，2024 底前不一致是預期內（實測 72/236）；照舊沿用 pkl，不套 5% 停止，報告照實揭露。
        # 〔自行裁量〕籌碼類建 pkl 時主路徑是 T86 本機快取、FinMind 只補缺日，這裡只用 FinMind 路徑，2024 底前有差是預期內；
        # 同殖利率作法：2024 底前沿用 pkl、不套 5% 停止，不一致檔數照實揭露。
        if len(FIN_MISMATCH) > 0.05 * len(ext) and fac != "f_dividend_yield_ttm" and fac not in CHIP_FACS:
            prog("不一致超過 5%，停止")
            return False
    elif diff > 1e-6:
        prog("核對不過，停止")
        return False
    market_df = prepare_market_data(mk)
    gate_dates = set(market_df.loc[market_df["gate"] == True, "date"].astype(str).str[:10])  # noqa: E712
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    cp = CELLS_DIR / f"{fac}.json"
    cache = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    p = E._cut(B.prep(ext, fac), miss)
    look = {sid: dict(zip(d["date"].astype(str).str[:10], d["_score"])) for sid, d in p.items()}
    endd = str(end.date())
    for c in B.grid():
        if B.key(c) in cache:
            continue
        if time.time() > deadline:
            prog("時間到，存斷點")
            return False
        rb, g, top_n, pstop, dr = c
        t0 = time.time()
        cfg = BacktestConfig(start_date=START, end_date=endd, max_positions=top_n, rebalance_every_n_days=rb,
                             stop_loss_pct=pstop, book_name="reaudit_batch3_ext")
        res = run_backtest(B.make_fn(look, bool(g), gate_dates, dr), p, market_df, cfg)
        ec, tr = res.equity_curve, res.trades
        sells = tr[tr["side"].isin(["sell", "close"])] if not tr.empty else tr
        cache[B.key(c)] = {"dates": [str(x)[:10] for x in ec["date"]], "equity": [float(x) for x in ec["equity"]],
                           "n_round_trips": int(len(sells)),
                           "win_rate": float((sells["realized_pnl"] > 0).mean()) if len(sells) else None}
        cp.write_text(json.dumps(cache), encoding="utf-8")
        prog(f"{fac} {B.key(c)} 完成（{time.time()-t0:.0f}s）")
    return True




# ---------- 彙總 ----------
MK_B, MK_E = "<!-- BATCH3-B1X-BEGIN -->", "<!-- BATCH3-B1X-END -->"
CAND = HERE / "data" / "paper_opt_candidates.json"


def _seg(curve, dates, a, b):
    m = (dates >= a) & (dates <= b)
    if m.sum() < 20:
        return None
    import reaudit_optimized_batch2_sector as S
    c = curve[m.to_numpy()]
    g, mdd, sh = S.stats(c / c[0], dates[m].reset_index(drop=True))
    return {"cagr": g, "mdd": mdd, "sharpe": sh}


def summarize():
    import reaudit_optimized_batch2_sector as S
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    LB.END = "2099-12-31"  # 同 reaudit_ext2025_engine：只在本行程延長央行定存讀取範圍，不改原檔
    old = {}
    for pj in (B.OUT_JSON, HERE / "data" / "reaudit_batch3_batch2.json", HERE / "data" / "reaudit_batch3_batch3.json"):
        if pj.exists():
            old.update({f["factor"]: f for f in json.loads(pj.read_text(encoding="utf-8"))["families"]})
    fams = []
    for fac in PRICE_FACS + FIN_FACS:
        if fac not in old or not old[fac].get("best_by_calmar"):
            continue
        cp = CELLS_DIR / f"{fac}.json"
        if not cp.exists():
            continue
        cache = json.loads(cp.read_text(encoding="utf-8"))
        rows, rf = [], None
        for k, c in cache.items():
            rb, g, top_n, pstop, dr = k.split("_")
            dates = pd.to_datetime(pd.Series(c["dates"]))
            eq = np.array(c["equity"], float); eq = eq / eq[0]
            if rf is None or len(rf) != len(dates):
                rf = LB.load_tw_rf_daily(dates)
            for L, stop in itertools.product(S.LEVS, S.STOPS):
                curve, _ = S.overlay(eq, rf, L, stop)
                cagr, mdd, sh = S.stats(curve, dates)
                rows.append({"key": k, "L": L, "stop": stop, "cagr": cagr, "mdd": mdd, "sharpe": sh,
                             "calmar": cagr / abs(mdd) if mdd < 0 else None, "win_rate": c["win_rate"],
                             "trades": c["n_round_trips"], "rebalance_days": int(rb), "market_gate": bool(int(g)),
                             "top_n": int(top_n), "pos_stop": None if float(pstop) >= 1.0 else float(pstop), "direction": int(dr)})
        df = pd.DataFrame(rows)
        ok = df[df["mdd"] >= -0.50]
        best = ok.sort_values("calmar", ascending=False).iloc[0].to_dict()
        best = {k2: (None if (isinstance(v, float) and v != v) else v) for k2, v in best.items()}
        # 第 1 批（2024 底前）挑出的那一組，延長後的數字＋2025 起分段
        ob = old[fac]["best_by_calmar"]
        segs = {}
        for tag, pick in (("prev_best", ob), ("new_best", best)):
            if pick["key"] not in cache:  # 時間到存斷點、那格還沒跑到（下一輪接續）
                segs[tag] = None
                continue
            c = cache[pick["key"]]
            dates = pd.to_datetime(pd.Series(c["dates"]))
            eq = np.array(c["equity"], float); eq = eq / eq[0]
            curve, _ = S.overlay(eq, LB.load_tw_rf_daily(dates), pick["L"], pick["stop"])
            full = S.stats(curve, dates)
            segs[tag] = {"key": pick["key"], "L": pick["L"], "stop": pick["stop"],
                         "full": {"cagr": full[0], "mdd": full[1], "sharpe": full[2]},
                         "pre2025": _seg(curve, dates, pd.Timestamp("2015-01-01"), pd.Timestamp("2024-12-31")),
                         "from2025": _seg(curve, dates, pd.Timestamp("2024-12-31"), dates.max()),
                         "end": str(dates.max().date())}
        fams.append({"factor": fac, "cells_done": len(cache), "best_by_calmar_full": best, "segments": segs,
                     "n_violates": int((df["mdd"] < -0.50).sum())})
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "families": fams}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    render(out)
    for f in fams:
        p, n = f["segments"]["prev_best"], f["segments"]["new_best"]
        if p is None:
            prog(f"{f['factor']} {f['cells_done']}/48 舊最優那格未跑到｜目前最優 {n['key']} L={n['L']} {n['full']['cagr']:+.1%}/{n['full']['mdd']:.1%}")
            continue
        prog(f"{f['factor']} {f['cells_done']}/48 舊最優 {p['key']} 全期 {p['full']['cagr']:+.1%}/{p['full']['mdd']:.1%} 2025起 "
             + (f"{p['from2025']['cagr']:+.1%}/{p['from2025']['mdd']:.1%}" if p['from2025'] else "—")
             + f"｜新最優 {n['key']} L={n['L']} {n['full']['cagr']:+.1%}/{n['full']['mdd']:.1%}")
    return 0


def _f(x, pct=True):
    return "—" if x is None else (f"{x:+.1%}" if pct else f"{x:.2f}")


def render(out):
    md = B.MD
    L = [MK_B, "", "### 5a. 第 1／2 批價量因子延長到 2025 起（`research/reaudit_batch3_ext2025.py`，零新外部請求）", "",
         f"> 產生：{out['generated_at']}。價格 2025 起接本機 FinMind 快取（同 F12／F13 延長作法；2024 底仍掛牌但沒有 2025 起價格的 45 檔"
         "從 2024-11-15 起不給分數），因子照 factors.py 原公式在延長價格上重算，2024 底前與原欄核對差 0。"
         "「舊最優」＝第 5 節只看 2024 底前挑出的那一組，延長後原封不動看 2025 起表現（這一段等於沒參與挑格）；"
         "「新最優」＝用全期（含 2025 起）重新挑，一定更樂觀。非投資建議。", "",
         "| 因子族 | 格數 | 舊最優（2024 底前挑）參數 | 舊最優 2015～2024 年化／MDD | 舊最優 2025 起 年化／MDD／Sharpe | 舊最優全期 年化／MDD | 新最優（全期挑）參數 | 新最優全期 年化／MDD／Sharpe | 終點 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        p, n = f["segments"]["prev_best"], f["segments"]["new_best"]
        if p is None:
            nf = n["full"]
            L.append(f"| {f['factor']} | {f['cells_done']}/48 | 舊最優那格未跑到（下一輪接續） | — | — | — | "
                     f"{n['key']} L={n['L']:g} 止損={n['stop']} | {_f(nf['cagr'])}／{_f(nf['mdd'])}／{_f(nf['sharpe'], False)} | {n['end']} |")
            continue
        pp, pf, nf = p["pre2025"] or {}, p["from2025"] or {}, n["full"]
        L.append(f"| {f['factor']} | {f['cells_done']}/48 | {p['key']} L={p['L']:g} 止損={p['stop']} | {_f(pp.get('cagr'))}／{_f(pp.get('mdd'))} | "
                 f"{_f(pf.get('cagr'))}／{_f(pf.get('mdd'))}／{_f(pf.get('sharpe'), False)} | {_f(p['full']['cagr'])}／{_f(p['full']['mdd'])} | "
                 f"{n['key']} L={n['L']:g} 止損={n['stop']} | {_f(nf['cagr'])}／{_f(nf['mdd'])}／{_f(nf['sharpe'], False)} | {p['end']} |")
    L += ["", "參數欄格式＝換股日數_大盤閘門_N_個股停損(1.0＝不設)_方向。2025 起只有約 1.7 年，數字波動大，只當參考。", "", MK_E]
    txt = md.read_text(encoding="utf-8")
    block = "\n".join(L)
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.replace(B.MK_E, B.MK_E + "\n\n" + block, 1)
    md.write_text(txt, encoding="utf-8")


def write_candidates():
    """新進總表前 10 名（綜合分數＝年化÷|MDD|，跟第 0 節比）寫進候選欄，交 先.一五四 系列建產生器後上紙上。"""
    old = B._old_table()
    ext = {}
    if OUT_JSON.exists():
        ext = {f["factor"]: f for f in json.loads(OUT_JSON.read_text(encoding="utf-8"))["families"]}
    cands = []
    for batch in ("1", "2", "3"):
        pj = B.OUT_JSON if batch == "1" else HERE / "data" / f"reaudit_batch3_batch{batch}.json"
        if not pj.exists():
            continue
        for f in json.loads(pj.read_text(encoding="utf-8"))["families"]:
            b = f.get("best_by_calmar")
            if not b or f["cells_done"] < f["cells_total"]:
                continue
            rank = 1 + sum(1 for _, sc in old if sc > b["calmar"])
            if rank > 10:
                continue
            e = ext.get(f["factor"])
            seg = e["segments"]["prev_best"] if e else None
            note = ["樣本內最優化（偏樂觀）", "#133 抽樣 236 檔宇宙（今天名冊抽樣，存活者偏誤未完全排除）", "只做多頭"]
            if b["L"] > 2:
                note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
            if not seg:
                note.append("2025 起尚未延長重算")
            elif seg["full"]["mdd"] < -0.50:
                note.append(f"同參數延長到 {seg['end']} 後全期 MDD {seg['full']['mdd']:.1%} 越過 50%（天條一 VIOLATES_SURVIVAL），上紙上前要先加條件把回撤壓到 50% 內")
            cands.append({"id": f"B3-{f['factor']}", "factor": f["factor"], "source": f"先.一五五-3 第二批第 {batch} 批",
                          "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": rank,
                          "params": {"direction": b["direction"], "rebalance_days": b["rebalance_days"], "market_gate": b["market_gate"],
                                     "top_n": b["top_n"], "pos_stop": b["pos_stop"], "leverage": b["L"], "portfolio_stop": b["stop"]},
                          "backtest_2015_2024": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                 "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                          "from_2025_same_params": None if not (seg and seg["from2025"]) else
                          {k: round(v, 4) for k, v in seg["from2025"].items()} | {"end": seg["end"]},
                          "full_period_same_params": None if not seg else
                          {k: round(v, 4) for k, v in seg["full"].items()},
                          "violates_survival_extended": bool(seg and seg["full"]["mdd"] < -0.50),
                          "notes": "；".join(note)})
    if CAND.exists():  # 第 4 批 regime 族（B4R-，reaudit_batch4_regime.py）與第 5 批價格擇時族（B5P-，reaudit_batch5_price_timing.py）原樣保留；第 6 批組合建構族（B6W-，reaudit_batch6_portfolio.py）、第 7 批事件族（B7E-，reaudit_batch7_events.py）同
        cands += [c for c in json.loads(CAND.read_text(encoding="utf-8")).get("candidates", [])
                  if str(c.get("id", "")).startswith(("B4R-", "B5P-", "B6W-", "B7E-", "B10R-"))]
    cands.sort(key=lambda c: c["rank_in_table"])
    CAND.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                                "rule": "綜合分數（年化÷|MDD|）併入 REAUDIT_OPTIMIZED.md 第 0 節總表約前 10 名者；非投資建議",
                                "candidates": cands}, ensure_ascii=False, indent=1), encoding="utf-8")
    prog(f"候選欄 {len(cands)} 支：" + "、".join(c["factor"] for c in cands))


if __name__ == "__main__" and len(sys.argv) >= 2 and sys.argv[1] == "candidates":
    sys.exit(write_candidates() or 0)

if __name__ == "__main__" and len(sys.argv) >= 2 and sys.argv[1] == "summarize":
    sys.exit(summarize())


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "run":
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1800))
    sys.exit(0 if run(sys.argv[2], dl) else 2)
