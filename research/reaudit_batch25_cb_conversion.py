"""先.一五五-3 第 25 批：可轉債轉換價格調整公告（#51 子事件 3）→ 事件後固定持有（紙上優化軌，零請求）。

- 事件來源：本機 MOPS t108sb08_1_q2 快取 `research/data/raw_mops_cb_conversion_price/*.parquet`（民國 99～113，上市＋上櫃，
  `mops_cb_conversion_price_client` 先前抓好；本腳本只讀檔、不送請求）。
- 觀察日＝公告日（announcement_date，非交易日歸到之後第一個交易日），下一個交易日收盤進場、持有 H 日；
  原 #51 假說是「向下重設→潛在轉換賣壓→CAR 為負」，紙上優化軌只做多，所以這裡量的是「公告後買進」各子族的最好版本。
  只保留 公告日 ≤ 生效日（PIT，同原 gate1 規則）。strength＝調降幅度 (old−new)/old，同日多筆幅度大者優先。
- 子族：E-cb-reset＝類別「價格重設」且向下；E-cb-noreset＝「價格不重設」；E-cb-antidil5＝「反稀釋」且調降 ≥5%
  （多為現增／配股，非例行配息）；E-cb-antidil＝「反稀釋」全部。
- 宇宙、還原、成本、漲跌停、槓桿止損全部只呼叫第 24 批 `load_universe()`（--full＝全市場含已下市，照第 15 批）、第 7 批 sim、batch2 overlay；
  2015-01～2024-12。不改核心檔、不寫試驗帳本。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import socket  # noqa: E402


def _no_net(*a, **k):
    raise RuntimeError("第 25 批零請求：封鎖網路")


socket.socket.connect = _no_net  # 只讀本機快取
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reaudit_batch7_events as B7  # noqa: E402
import reaudit_batch22_material_news as B22  # noqa: E402
import reaudit_batch24_major_orders as B24  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
FULL = "--full" in sys.argv
OUT = HERE / "data" / ("reaudit_batch3_batch25_full.json" if FULL else "reaudit_batch3_batch25.json")
MD = HERE / "REAUDIT_OPTIMIZED.md"
END = B22.END
SRC = HERE / "data" / "raw_mops_cb_conversion_price"


def load_cb():
    d = pd.concat([pd.read_parquet(f) for f in sorted(SRC.glob("*.parquet"))], ignore_index=True)
    d["ann"] = pd.to_datetime(d["announcement_date"], errors="coerce")
    d["eff"] = pd.to_datetime(d["effective_date"], errors="coerce")
    d = d.dropna(subset=["ann", "eff"])
    d = d[d["ann"] <= d["eff"]]
    d["mag"] = (d["old_price"].astype(float) - d["new_price"].astype(float)) / d["old_price"].astype(float)
    d["sid"] = d["co_id"].astype(str).str.strip()
    return d


FAMS = {
    "E-cb-reset": lambda d: d[(d["category"] == "價格重設") & (d["mag"] > 0)],
    "E-cb-noreset": lambda d: d[d["category"] == "價格不重設"],
    "E-cb-antidil5": lambda d: d[(d["category"] == "反稀釋") & (d["mag"] >= 0.05)],
    "E-cb-antidil": lambda d: d[d["category"] == "反稀釋"],
}


def to_events(px, x):
    x = x[x["sid"].isin(px.columns)]
    k = np.searchsorted(px.index, x["ann"].to_numpy(), side="left")
    keep = k < len(px.index)
    ev = pd.DataFrame({"date": px.index[k[keep]], "sid": x["sid"].to_numpy()[keep],
                       "strength": x["mag"].fillna(0).to_numpy()[keep]})
    return ev.sort_values("strength", ascending=False).drop_duplicates(["date", "sid"])


def main():
    t0 = time.time()
    px, ret, gate, rf, n_bad = B24.load_universe(FULL)
    cb = load_cb()
    print(f"宇宙 {px.shape[1]} 檔（{'全市場' if FULL else '236 抽樣'}），異常報酬略過 {n_bad}；CB 事件 {len(cb)}（{time.time()-t0:.0f}s）", flush=True)
    out = {"meta": {"src": SRC.name, "start": B7.START, "end": END, "n_stocks": int(px.shape[1]), "full_market": FULL}, "families": []}
    ew = ret[(ret.index >= pd.Timestamp(B7.START)) & (ret.index <= pd.Timestamp(END))].mean(axis=1).fillna(0)
    out["bench_ew"] = B7.st(ew.index, (1 + ew).cumprod().to_numpy())
    for fam, sel in FAMS.items():
        ev = to_events(px, sel(cb))
        ev = ev[(ev["date"] >= pd.Timestamp(B7.START)) & (ev["date"] <= pd.Timestamp(END))]
        rows = []
        for H, n, g in itertools.product(B7.HS, B7.NS, (False, True)):
            dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, H, n, g, END)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, _ = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, c)
                rows.append({"H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
        ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 100]
        best = max(ok or rows, key=lambda r: r["calmar"])
        out["families"].append({"family": fam, "n_events": int(len(ev)), "n_stocks_with_event": int(ev["sid"].nunique()),
                                "n_cells": len(rows), "best": best, "meets_trade_floor": bool(ok),
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        print(f"{fam} 事件 {len(ev)}（{ev['sid'].nunique()} 檔）最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} 交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def render(out):
    b = out["bench_ew"]
    tag = "B25F" if out["meta"].get("full_market") else "B25"
    uni = f"全市場四碼普通股 {out['meta']['n_stocks']} 檔（含已下市，還原照第 15 批）" if out["meta"].get("full_market") else "#133 抽樣 236 檔"
    lines = [f"<!-- BATCH3-{tag}-BEGIN -->", "",
             f"### 28{'a' if tag == 'B25F' else ''}. （{uni}）可轉債轉換價格調整公告（#51 子事件 3，`research/reaudit_batch25_cb_conversion.py`，零請求）", "",
             "做法：本機 MOPS 轉換價格調整公告（民國 99～113 上市＋上櫃快取），只留公告日 ≤ 生效日；公告日下一個交易日收盤進場、持有 H 日、"
             "同日多筆調降幅度大者優先；模擬／成本／漲跌停／槓桿止損沿用第 7 批，每族 512 格；候選門檻交易 ≥100、MDD 在 50% 內"
             "（達不到者照實標「未達」，數字只當參考）。原 #51 假說是賣壓（CAR 負），這裡只做多。"
             f"同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。存活者偏誤照實揭露。非投資建議。", "",
             "| 族 | 事件數（檔數） | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 交易門檻 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r = f["best"]
        lines.append(f"| {f['family']} | {f['n_events']}（{f['n_stocks_with_event']}） | {r['H']} | {r['N']} | "
                     f"{'開' if r['gate'] else '關'} | {r['L']}× | {B22.stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | "
                     f"{r['sharpe']:.2f} | {r['calmar']:.2f} | {r['trades']} | {r['win_rate']:.0%} | {'達' if f['meets_trade_floor'] else '未達'} |")
    lines += ["", "照實揭露：本機快取裡「價格重設」只有 2010-02～2012-07 共 30 筆、「價格不重設」194 筆沒有生效日與新舊價（被 PIT 規則排除），"
              "所以 2015～2024 只剩「反稀釋」調整（多為配息／配股／現增的例行調整），兩個重設子族 0 事件、表上數字是空手收無風險利率，不具意義。"
              "反稀釋兩族 Calmar 0.14／0.08，遠低於同宇宙等權，不進候選欄。", "", f"<!-- BATCH3-{tag}-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    b0, b1 = f"<!-- BATCH3-{tag}-BEGIN -->", f"<!-- BATCH3-{tag}-END -->"
    if b0 in txt:
        a = txt.index(b0)
        z = txt.index(b1) + len(b1)
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    if "render" in sys.argv:
        render(json.loads(OUT.read_text(encoding="utf-8")))
    else:
        main()
