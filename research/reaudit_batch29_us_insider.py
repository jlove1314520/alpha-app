# -*- coding: utf-8 -*-
"""先.一五五-3 第 29 批：美股內部人公開市場買入事件（#75／#324／insider_event_level_shortwindow）事件後固定持有
（紙上優化軌，描述性，零請求）。

**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（本批事件來自 SEC DERA 歷史申報、不限今日在市，
但價格只覆蓋 4,965／14,306 個 ticker（34.7%），已下市股覆蓋偏低，結果只代表有價格的子樣本，偏樂觀。）

- 事件：`insider_event_level_shortwindow._load_transactions()／_build_events()` 只呼叫（code=P 且 acq_disp=A；
  同 issuer 同 filing_date＝一個事件；event_usd ≥ $1,000；止於 2024-12-01）。
- 價格：`data/dera_insider/prices/px_*.csv`（既有 yfinance adj_close 快取，到 2024-12-31）；對齊 SPY 交易日曆。
- 申報時點不明 → **filing_date 之後第一個交易日收盤進場**（同原腳本 PIT），持有 H 交易日。
- 篩選族：ALL、USD100K（事件金額 ≥$10 萬）、USD1M（≥$100 萬）、CLUSTER（同日 ≥2 位內部人）；
  另加「申報買價 ≥$5」去掉雞蛋水餃股（申報價＝原始成交價，非還原價）。
- 槽位 N 檔、等權、槽滿略過、同日事件金額大者優先；模擬／槓桿／止損／統計只呼叫第 28 批（成本 0.10%／邊、
  槓桿扣 DTB3＋1.5%、3× 超過 Reg T 只當參考）。
- 資料品質：單日 |報酬| > 75% 視為報價錯誤記 0（筆數照實揭露）。
- 期間 2010-01-04～2024-12-30（SPY 本機日曆快取從 2010 起，2006～2009 事件不計）；參數用全期挑，非樣本外。
"""
from __future__ import annotations

import reaudit_batch28_sp_addition as B28  # noqa: E402  （先 import：同時套用封網）

import itertools  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
import insider_event_level_shortwindow as IE  # noqa: E402

OUT_JSON = HERE / "data" / "reaudit_batch3_batch29.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
START = pd.Timestamp("2006-02-01")
BAD = 0.75


def load():
    raw = IE._load_transactions()
    pr = raw.groupby(["issuer_cik", "ticker", "filing_date"])["price"].median().rename("px_med")
    ev = IE._build_events(raw).merge(pr.reset_index(), on=["issuer_cik", "ticker", "filing_date"], how="left")
    ok = IE._price_ok_tickers()
    ev = ev[ev["ticker"].isin(ok) & (ev["filing_date"] >= START)]
    spy = B28._price_calendar("SPY")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date")["close"].astype(float)
    cal = spy.index[spy.index >= START - pd.Timedelta(days=10)]
    tick = sorted(ev["ticker"].unique())
    M = np.full((len(cal), len(tick)), np.nan, dtype=np.float32)
    keep = []
    for j, t in enumerate(tick):
        try:
            p = pd.read_csv(IE.PRICE_DIR / f"px_{t}.csv", parse_dates=["Date"]).set_index("Date")["adj_close"]
        except Exception as e:  # noqa: BLE001
            print(f"[警告] {t} 讀價失敗：{e}")
            continue
        p = p[~p.index.duplicated()].reindex(cal)
        M[:, j] = p.to_numpy(dtype=np.float32)
        keep.append(j)
    px = pd.DataFrame(M, index=cal, columns=tick)
    return ev, px, spy.reindex(cal)


def main():
    t0 = datetime.now()
    ev, px, spy = load()
    dates = px.index
    P = px.to_numpy(dtype=float)
    R = np.full_like(P, np.nan)
    for j in range(P.shape[1]):
        col = P[:, j]
        m = ~np.isnan(col)
        ii = np.flatnonzero(m)
        if len(ii) > 1:
            v = col[ii]
            R[ii[1:], j] = v[1:] / v[:-1] - 1
    nbad = int(np.nansum(np.abs(R) > BAD))
    R[np.abs(R) > BAD] = 0.0
    obs = np.searchsorted(dates, ev["filing_date"].to_numpy(), side="right") - 1  # 申報日（或之前最後交易日）
    evt = pd.DataFrame({"sid": ev["ticker"].to_numpy(), "obs": obs, "eff_prev": obs, "tier": -ev["event_usd"].to_numpy(),
                        "usd": ev["event_usd"].to_numpy(), "n_ins": ev["n_insiders"].to_numpy(),
                        "pxm": ev["px_med"].to_numpy()})
    evt = evt[(evt["obs"] >= 0) & (evt["pxm"] >= 5)]
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    rf_ann = np.asarray(LB.load_dtb3_annual(pd.Series(dates)), dtype=float)
    rf, borrow = rf_ann / 252, (rf_ann + B28.SPREAD) / 252
    spy_full = B28._price_calendar("SPY")
    spy_full["date"] = pd.to_datetime(spy_full["date"])
    ma = spy_full.set_index("date")["close"].astype(float).rolling(200, min_periods=200).mean().reindex(dates)
    gate = (spy > ma).to_numpy()
    print(f"事件 {len(evt)} 筆（{evt['sid'].nunique()} 檔，申報價≥$5）；報價錯誤記 0：{nbad} 格；載入 {(datetime.now()-t0).seconds}s")
    fams = {"ALL": evt, "USD100K": evt[evt["usd"] >= 1e5], "USD1M": evt[evt["usd"] >= 1e6],
            "CLUSTER": evt[evt["n_ins"] >= 2]}
    res = {}
    for fam, fe in fams.items():
        rows = []
        for H, nmax, ug in itertools.product((5, 10, 21, 63), (10, 20, 40), (False, True)):
            eq, n, w = B28.sim(px, None, R, rf, gate, fe, ("H", H), nmax, ug)
            for L, s in itertools.product(B28.LEVS, B28.STOPS):
                c, ns = B28.overlay(eq, rf, borrow, L, s)
                d = B28.st(dates, c)
                d.update({"hold": f"H{H}", "N": nmax, "gate": ug, "L": L, "stop": s, "trades": n, "win": float(w), "n_stop": ns})
                if L == 1.0 and s is None:
                    m = dates >= pd.Timestamp("2021-01-01")
                    d["from_2021"] = B28.st(dates[m], c[m] / c[m][0])
                rows.append(d)
        ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 100]
        best = max(ok, key=lambda r: r["calmar"]) if ok else None
        best1 = max([r for r in ok if r["L"] == 1.0], key=lambda r: r["calmar"], default=None)
        b12 = max([r for r in ok if r["L"] <= 2.0], key=lambda r: r["calmar"], default=None)
        res[fam] = {"n_events": int(len(fe)), "grid": len(rows), "best": best, "best_1x": best1, "best_le2x": b12,
                    "n_violate": sum(r["mdd"] <= -0.5 for r in rows)}
        print(fam, len(fe), {k: best[k] for k in ("cagr", "mdd", "calmar", "hold", "N", "gate", "L", "stop", "trades")} if best else None,
              f"{(datetime.now()-t0).seconds}s", flush=True)
    sc = spy.to_numpy() / spy.iloc[0]
    out = {"generated": datetime.now().isoformat(timespec="seconds"), "period": [str(dates[0].date()), str(dates[-1].date())],
           "n_events": int(len(evt)), "n_tickers": int(evt["sid"].nunique()), "n_bad_cells": nbad, "families": res,
           "spy": B28.st(dates, sc), "secs": (datetime.now() - t0).seconds}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    render(out)


def render(out):
    p = B28._p
    L = ["<!-- BATCH3-B29-BEGIN -->", "", "### 32. 第二批 第 29 批：美股內部人公開市場買入事件（#75／#324，零請求）", "",
         f"產生：{out['generated']}；期間 {out['period'][0]}～{out['period'][1]}；事件 {out['n_events']} 筆／{out['n_tickers']} 檔（申報買價 ≥$5）；"
         f"單日 |報酬|>75% 視為報價錯誤記 0：{out['n_bad_cells']} 格。腳本 `research/reaudit_batch29_us_insider.py`，明細 `research/data/reaudit_batch3_batch29.json`。",
         "", "> **存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** DERA 申報 ticker 只有 34.7% 有 yfinance 價格，下市股覆蓋偏低、偏樂觀。",
         "> 申報日之後第一個交易日收盤進場；成本 0.10%／邊；槓桿扣 DTB3＋1.5%；3× 超過 Reg T 只當參考；參數用全期挑，非樣本外。", "",
         "| 族 | 事件數 | 最佳組（MDD≤50%、交易≥100） | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | ≤2× 最佳 年化／MDD／Calmar | 1× 最佳 年化／MDD／Calmar |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam, r in out["families"].items():
        b = r["best"]
        if not b:
            L.append(f"| {fam} | {r['n_events']} | 無合格組 | | | | | | | | |")
            continue
        g = f"{b['hold']}、N={b['N']}、{'閘門' if b['gate'] else '不擇時'}、{b['L']}×、止損 {b['stop'] or '無'}"
        f = lambda x: f"{p(x['cagr'])}／{p(x['mdd'])}／{x['calmar']:.2f}（{x['hold']} N={x['N']} {x['L']}×）" if x else "—"
        L.append(f"| {fam} | {r['n_events']} | {g} | {p(b['cagr'])} | {p(b['mdd'])} | {b['sharpe']:.2f} | {b['calmar']:.2f} | {b['trades']} | {b['win']*100:.0f}% | {f(r['best_le2x'])} | {f(r['best_1x'])} |")
    s = out["spy"]
    L += ["", f"同期 SPY（價格，不含息）{p(s['cagr'])}／{p(s['mdd'])}（Calmar {s['calmar']:.2f}）。", "",
          "讀法：表上最佳組都是 2～3× 且 MDD 貼著 50%，脆弱；3× 超過 Reg T 只當參考。≤2× 最好是 USD100K 2×（Calmar 0.53），"
          "1× 最好是 CLUSTER 10 日 N=10 +15.1%／−38.1%（0.40），跟 SPY 價格指數（0.41，不含約 1.8% 股息）差不多。"
          "報價錯誤記 0 的格數不少（小型股、生技股真實暴漲暴跌也會被抹掉，方向不定），照實揭露。"
          "〔自行裁量〕不進候選欄（≤2× Calmar 未達 0.6）。", "", "<!-- BATCH3-B29-END -->"]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if "<!-- BATCH3-B29-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B29-BEGIN -->")
        z = txt.index("<!-- BATCH3-B29-END -->") + len("<!-- BATCH3-B29-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
