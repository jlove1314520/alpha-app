"""先.一五五-3 墓園重審第二批 第 22 批：irb130 董監質押比（HQ#48）→ 前 N 檔等權月換股（紙上優化軌）。

零外部請求：只讀本機 `research/data/irb130_pledge_signal_panel.csv`（irb130_pledge_gate.py 產出）。
- PIT：月資料的可得日＝該月再往後一個月的月底（官方約次月 22 日公布，見 irb130_pledge_gate.py）。
- 報酬：fwd_return＝可得日之後第一個交易日收盤進場、持有 20 個交易日（還原價；下市 −100% 有照實記入）。
  每月一期，期與期之間約 0～2 個交易日沒算到（照實揭露）。
- 宇宙：#133 同批 seed=20260822 抽樣中有質押資料的 196 檔（有存活者偏誤，照實揭露）；2015-02～2024-11。
- 成本：換手比例 ×來回 0.685%（手續費 0.1425%×2 不打折＋證交稅 0.3%＋滑價 5bps×2）。
- 槓桿：L×月報酬 −(L−1)×融資年息 6.5%／12（〔自行裁量〕用台股融資常見年息，偏保守）；3× 超過融資上限只當參考。
- MDD 用月報酬算，會低估日內／日頻回撤（照實揭露）。
不改核心檔、不寫試驗帳本。非投資建議。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
PANEL = HERE / "data" / "irb130_pledge_signal_panel.csv"
OUT = HERE / "data" / "reaudit_batch3_batch22.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
RT_COST = 0.00685
FIN_RATE = 0.065


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 12:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1.0
    mdd = float((eq / eq.cummax() - 1).min())
    sh = float(r.mean() / r.std() * np.sqrt(12)) if r.std() > 0 else 0.0
    return {"cagr": float(cagr), "mdd": mdd, "sharpe": sh, "calmar": float(cagr / abs(mdd)) if mdd < 0 else None,
            "win": float((r > 0).mean()), "months": int(len(r))}


def pick(g: pd.DataFrame, col: str, rule: str, n: int, rng: np.random.Generator) -> list:
    g = g.dropna(subset=[col])
    if rule == "zero":  # 質押比為 0 的全部等權（n 不用）
        return g.loc[g[col] == 0, "stock_id"].tolist()
    tb = rng.random(len(g))  # 固定種子隨機破同分（質押比大量為 0）
    g = g.assign(_tb=tb).sort_values([col, "_tb"], ascending=[rule == "low", True])
    return g["stock_id"].head(n).tolist()


def run_one(p: pd.DataFrame, col: str, rule: str, n: int, L: float) -> tuple[pd.Series, int]:
    rng = np.random.default_rng(20261111)
    rets, prev, trades = {}, set(), 0
    for d, g in p.groupby("as_of"):
        names = pick(g, col, rule, n, rng)
        if not names:
            rets[d] = 0.0
            prev = set()
            continue
        cur = set(names)
        turn = 1.0 if not prev else len(cur - prev) / len(cur)
        trades += len(cur - prev)
        gross = float(g.set_index("stock_id").loc[names, "fwd_return"].mean())
        net = gross - turn * RT_COST
        rets[d] = L * net - (L - 1) * FIN_RATE / 12
        prev = cur
    return pd.Series(rets).sort_index(), trades


def main() -> None:
    p = pd.read_csv(PANEL, parse_dates=["as_of"])
    bench = p.groupby("as_of")["fwd_return"].mean().sort_index()
    rows = []
    for col in ("pledge_level", "pledge_mom"):
        for rule in ("low", "high", "zero"):
            if rule == "zero" and col != "pledge_level":
                continue
            for n in ((0,) if rule == "zero" else (10, 20, 30)):
                for L in (1.0, 1.5, 2.0, 3.0):
                    r, trades = run_one(p, col, rule, n, L)
                    s = stats(r)
                    s.update({"signal": col, "rule": rule, "N": n, "L": L, "trades": trades,
                              "train_2015_2020": stats(r[r.index <= "2020-12-31"]),
                              "late_2021_2024": stats(r[r.index > "2020-12-31"])})
                    rows.append(s)
    bstats = stats(bench)
    ok = [x for x in rows if x.get("mdd", -1) > -0.5 and x.get("calmar") is not None]
    ok.sort(key=lambda x: x["calmar"], reverse=True)
    best_by = {}
    for x in ok:
        best_by.setdefault((x["signal"], x["rule"]), x)
    OUT.write_text(json.dumps({"bench_equal_weight_universe": bstats, "cells": rows,
                               "best_by_family": [best_by[k] for k in best_by]}, ensure_ascii=False, indent=1,
                              default=str), encoding="utf-8")
    lines = ["<!-- BATCH3-B22-BEGIN -->", "",
             f"共 {len(rows)} 格（訊號 2 種×方向×N 10/20/30×槓桿 1/1.5/2/3×；另加「質押比為 0 的全部」）。期間 2015-02～2024-11（月頻 {bstats.get('months')} 期）。",
             f"同名冊 196 檔等權（不扣成本）：年化 {bstats['cagr']:+.1%}／MDD {bstats['mdd']:.1%}／Sh {bstats['sharpe']:.2f}／Calmar {bstats['calmar']:.2f}。",
             "", "| 訊號 | 規則 | N | 槓桿 | 年化 | MDD（月頻） | Sharpe | Calmar | 勝率（月） | 換入次數 | 2015～2020 年化／MDD | 2021～2024 年化／MDD |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in best_by.values():
        a, b = x["train_2015_2020"], x["late_2021_2024"]
        lines.append(f"| {x['signal']} | {x['rule']} | {x['N'] or '全部'} | {x['L']}× | {x['cagr']:+.1%} | {x['mdd']:.1%} | {x['sharpe']:.2f} | {x['calmar']:.2f} | {x['win']:.0%} | {x['trades']} | "
                     f"{a.get('cagr', float('nan')):+.1%}／{a.get('mdd', float('nan')):.1%} | {b.get('cagr', float('nan')):+.1%}／{b.get('mdd', float('nan')):.1%} |")
    lines += ["", "<!-- BATCH3-B22-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if "<!-- BATCH3-B22-BEGIN -->" in txt:
        s, e = txt.index("<!-- BATCH3-B22-BEGIN -->"), txt.index("<!-- BATCH3-B22-END -->") + len("<!-- BATCH3-B22-END -->")
        txt = txt[:s] + block + txt[e:]
    else:
        txt = txt.rstrip("\n") + "\n\n## 25. 第二批第 22 批 董監質押比（HQ#48 irb130）→ 前 N 檔等權月換股（先.一五五-3 ③，`research/reaudit_batch22_pledge.py`，零新外部請求）\n\n" \
              "做法：可得日＝資料月再往後一個月的月底（晚於官方約次月 22 日公布）；可得日下一交易日收盤進、持有 20 個交易日；成本換手×來回 0.685%；槓桿扣融資年息 6.5%。" \
              "宇宙＝#133 抽樣中有質押資料的 196 檔（存活者偏誤照實揭露）；MDD 為月頻、會低估日頻回撤；未延長到 2025 起（面板只到 2024-11）。非投資建議。\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    main()
