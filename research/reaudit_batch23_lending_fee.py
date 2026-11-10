"""先.一五五-3 第 23 批：借券費率異常（#63 f_lending_fee_spike）→ 事件後固定持有（紙上優化軌，零請求）。

- 資料：本機 `research/data/raw_twse_lending_fee/LENDING_FEE_*.parquet`（2012～2024，`twse_lending_fee_client.load_all_cached()` 只呼叫）。
- z-score 口徑逐字照 `lending_fee_gate63.py` 事前綁定規格：只取競價／議借、同股同日依成交量加權費率、
  該股自己「前 60 次有成交的觀測」（shift(1) 不含當日、min_periods=20）算均值／標準差；std<=0 排除。
- 原假說是「費率急升→之後下跌」（放空方向）。紙上優化軌只做多，所以測：
  E-lend-spike（z≥門檻後買進＝原假說的反向）、E-lend-drop（z≤−門檻後買進＝費率驟降、放空壓力消退）。
- 借券成交盤後公布：觀察日＝成交日，**下一個交易日收盤進場**（第 7 批 sim 既有規則，偏保守）。
- 模擬、成本、漲跌停、槓桿／組合止損全部只呼叫第 7 批 `reaudit_batch7_events` 與 batch2 overlay；
  宇宙＝#133 抽樣 236 檔（有存活者偏誤，照實揭露）；期間 2015-01～2024-12（費率快取只到 2024 底；2012～2014 只當 z-score 暖機）。
不改核心檔、不寫試驗帳本。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reaudit_batch7_events as B7  # noqa: E402
import twse_lending_fee_client as LF  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
OUT = HERE / "data" / "reaudit_batch3_batch23.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
END = "2024-12-31"
ZS = (2.0, 3.0)


def lending_z():
    raw = LF.load_all_cached()
    raw = raw[raw["trade_type"].isin(["競價", "議借"])].copy()
    raw = raw[(raw["volume"] > 0) & raw["fee_rate"].notna()]
    raw["fv"] = raw["fee_rate"] * raw["volume"]
    g = raw.groupby(["stock_id", "date"], as_index=False).agg(fv=("fv", "sum"), vol=("volume", "sum"))
    g["fee"] = g["fv"] / g["vol"]
    g = g.sort_values(["stock_id", "date"])
    prior = g.groupby("stock_id")["fee"].shift(1)
    grp = prior.groupby(g["stock_id"])
    g["mu"] = grp.transform(lambda s: s.rolling(60, min_periods=20).mean())
    g["sd"] = grp.transform(lambda s: s.rolling(60, min_periods=20).std())
    g = g[g["sd"] > 0].copy()
    g["z"] = (g["fee"] - g["mu"]) / g["sd"]
    g["date"] = pd.to_datetime(g["date"])
    return g[["stock_id", "date", "fee", "z"]]


def events(px, z, kind, thr):
    x = z[z["stock_id"].astype(str).isin(px.columns)]
    x = x[x["z"] >= thr] if kind == "spike" else x[x["z"] <= -thr]
    k = np.searchsorted(px.index, x["date"].to_numpy(), side="left")
    m = k < len(px.index)
    return pd.DataFrame({"date": px.index[k[m]], "sid": x["stock_id"].astype(str).to_numpy()[m],
                         "strength": np.abs(x["z"].to_numpy()[m])}).drop_duplicates(["date", "sid"])


FULL = "--full" in sys.argv
if FULL:
    OUT = HERE / "data" / "reaudit_batch3_batch23_full.json"


def main():
    t0 = time.time()
    import reaudit_batch24_major_orders as B24  # 全市場載入（第 15 批還原）只呼叫
    px, ret, gate, rf, n_bad = B24.load_universe(FULL)
    print(f"宇宙 {px.shape[1]} 檔（{'全市場' if FULL else '236 抽樣'}），異常報酬略過 {n_bad}", flush=True)
    z = lending_z()
    print(f"z 列數 {len(z)}、股票 {z['stock_id'].nunique()}、{z['date'].min().date()}～{z['date'].max().date()}", flush=True)
    out = {"meta": {"src": "raw_twse_lending_fee 2012～2024", "start": B7.START, "end": END, "n_stocks": int(px.shape[1]), "full_market": FULL},
           "families": []}
    ew = ret[(ret.index >= pd.Timestamp(B7.START)) & (ret.index <= pd.Timestamp(END))].mean(axis=1).fillna(0)
    out["bench_ew"] = B7.st(ew.index, (1 + ew).cumprod().to_numpy())
    for kind, thr in itertools.product(("spike", "drop"), ZS):
        ev = events(px, z, kind, thr)
        ev = ev[ev["date"] >= pd.Timestamp(B7.START)]
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
        fam = f"E-lend-{kind}-z{thr:g}"
        out["families"].append({"family": fam, "n_events": int(len(ev)), "n_cells": len(rows), "best": best,
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        print(f"{fam} 事件 {len(ev)} 最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} 交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def stop_txt(s):
    return "無" if s is None else f"{s:.0%}"


def render(out):
    b = out["bench_ew"]
    tag = "B23F" if out["meta"].get("full_market") else "B23"
    uni = f"全市場四碼普通股 {out['meta']['n_stocks']} 檔（含已下市，還原照第 15 批）" if out["meta"].get("full_market") else "#133 抽樣 236 檔"
    lines = [f"<!-- BATCH3-{tag}-BEGIN -->", "",
             f"### 26{'a' if tag == 'B23F' else ''}. （{uni}）借券費率異常（#63 f_lending_fee_spike，`research/reaudit_batch23_lending_fee.py`，零請求）", "",
             "做法：本機 TWSE 借券成交 2012～2024（競價／議借、同日量加權），z-score 照 lending_fee_gate63 事前規格（該股前 60 次有成交觀測、不含當日）。"
             "只做多：費率急升後買（原放空假說的反向）、費率驟降後買；成交日的下一個交易日收盤進場，模擬／成本／漲跌停／槓桿止損沿用第 7 批，"
             "每族 512 格；候選門檻交易 ≥100、MDD 在 50% 內。"
             f"同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。存活者偏誤照實揭露。非投資建議。", "",
             "| 族 | 事件數 | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 越過天條一格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r = f["best"]
        lines.append(f"| {f['family']} | {f['n_events']} | {r['H']} | {r['N']} | {'開' if r['gate'] else '關'} | {r['L']}× | "
                     f"{stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | {r['sharpe']:.2f} | {r['calmar']:.2f} | "
                     f"{r['trades']} | {r['win_rate']:.0%} | {f['violates_survival_cells']} |")
    lines += ["", f"<!-- BATCH3-{tag}-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    b0, b1 = f"<!-- BATCH3-{tag}-BEGIN -->", f"<!-- BATCH3-{tag}-END -->"
    if b0 in txt:
        a = txt.index(b0)
        zz = txt.index(b1) + len(b1)
        txt = txt[:a] + block + txt[zz:]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    main()
