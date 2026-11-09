"""先.一五五-3 第二批第 17 批：HQ#23 Piotroski F-score（台股）→ 前 N 檔等權（零新外部請求）。

做法：因子值 `reaudit_ext2025_fin_factors.fin_pit(sid, "f_piotroski_fscore")`（本機財報快取，PIT＝法定申報期限；
CFO 年初累計值還原單季、NaN 比較不當 0、NetIncome／CFO 欄名跨年份合併，見該函式註解），
回測格子由 `python research/reaudit_batch3_ext2025.py run f_piotroski_fscore` 產生（#133 抽樣 236 檔、`research/backtest/` 引擎只呼叫、
只做多、順向反向都掃，48 格，2015-01～2026-09-24，含 2025 起）；本支只讀格子，套第二批共用的槓桿 1/1.5/2/3×組合止損 overlay，
挑 Calmar 最好（MDD≤50%）一組，寫 REAUDIT_OPTIMIZED.md 第 20 節、明細 JSON、符合門檻就寫候選欄（id 前綴 B17F-）。
參數用全期（含 2025 起）挑，2025 起分段不是樣本外；樣本內最優化偏樂觀；有存活者偏誤（抽樣名冊）。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAC = "f_piotroski_fscore"
CELLS = HERE / "data" / "reaudit_batch3_ext2025_cells" / f"{FAC}.json"
OUT = HERE / "data" / "reaudit_batch3_batch17.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
CAND = HERE / "data" / "paper_opt_candidates.json"
MK_B, MK_E = "<!-- BATCH3-B17-BEGIN -->", "<!-- BATCH3-B17-END -->"


def seg(curve, dates, a, b, S):
    m = ((dates >= a) & (dates <= b)).to_numpy()
    if m.sum() < 20:
        return None
    c = curve[m]
    g, mdd, sh = S.stats(c / c[0], dates[m].reset_index(drop=True))
    return {"cagr": g, "mdd": mdd, "sharpe": sh}


def main():
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    LB.END = "2099-12-31"  # 同 reaudit_batch3_ext2025.summarize：只在本行程延長央行定存讀取範圍，不改原檔
    import reaudit_optimized_batch2_sector as S
    cache = json.loads(CELLS.read_text(encoding="utf-8"))
    rows, rf = [], {}
    for k, c in cache.items():
        rb, g, top_n, pstop, dr = k.split("_")
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float)
        eq = eq / eq[0]
        dk = (str(dates.iloc[0]), len(dates))
        if dk not in rf:
            rf[dk] = LB.load_tw_rf_daily(dates)
        for L, stop in itertools.product(S.LEVS, S.STOPS):
            curve, _ = S.overlay(eq, rf[dk], L, stop)
            cagr, mdd, sh = S.stats(curve, dates)
            rows.append({"key": k, "rebalance_days": int(rb), "market_gate": bool(int(g)), "top_n": int(top_n),
                         "pos_stop": None if float(pstop) >= 1.0 else float(pstop), "direction": int(dr), "L": L, "stop": stop,
                         "cagr": cagr, "mdd": mdd, "sharpe": sh, "calmar": cagr / abs(mdd) if mdd < 0 else None,
                         "win_rate": c["win_rate"], "trades": c["n_round_trips"], "_curve": curve, "_dates": dates})
    df = pd.DataFrame(rows)
    ok = df[df["mdd"] >= -0.50].sort_values("calmar", ascending=False)
    b = ok.iloc[0]
    b1 = df[(df["L"] == 1.0) & df["stop"].isna() & (df["mdd"] >= -0.50)].sort_values("calmar", ascending=False).iloc[0]

    def pack(r):
        d = {k2: (None if (isinstance(v, float) and v != v) else v) for k2, v in r.items() if not str(k2).startswith("_")}
        d["segments"] = {"2015_2024": seg(r["_curve"], r["_dates"], "2015-01-01", "2024-12-31", S),
                         "2025_on": seg(r["_curve"], r["_dates"], "2025-01-01", "2026-12-31", S)}
        return d
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "factor": FAC, "cells": len(cache),
           "n_grid": int(len(df)), "n_violates": int((df["mdd"] < -0.50).sum()),
           "best_by_calmar": pack(b), "best_1x_nostop": pack(b1),
           "notes": "樣本內最優化（描述性）；#133 抽樣 236 檔（有分數 153 檔）；只做多；參數用全期挑，2025 起不是樣本外；非投資建議。"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    def p(x):
        return "—" if not x else f"{x['cagr']:+.1%}／{x['mdd']:.1%}"
    bb, bn = out["best_by_calmar"], out["best_1x_nostop"]
    par = lambda r: (f"{r['rebalance_days']} 日換股，{'擇時' if r['market_gate'] else '不擇時'}，N={r['top_n']}，個股停損 {r['pos_stop'] or '不設'}，"
                     f"{'順向（分數高買）' if r['direction'] == 1 else '反向（分數低買）'}，{r['L']:g}×，組合止損 {r['stop'] or '不設'}")
    lines = [MK_B, "", "## 20. 第二批第 17 批 Piotroski F-score（台股，HQ#23）→ 前 N 檔等權（先.一五五-3 ③，`research/reaudit_batch17_piotroski.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；2015-01～2026-09-24（含 2025 起），#133 抽樣 236 檔中有分數 153 檔（其餘多為 ETF／金融業無毛利欄）；"
             "因子照 `piotroski_fscore_sanity._fscore_components` 9 項，照實修正三處：現金流量表年初累計值還原單季、NaN 比較不再記成 0（原版 n_components 永遠 9）、"
             "NetIncome／營運現金流欄名跨年份合併（原版 2022 前 CFO、近年淨利都是空的）。PIT＝法定申報期限。48 格 × 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%；"
             "**參數用全期挑，2025 起分段不是樣本外**；樣本內最優化偏樂觀；有存活者偏誤（抽樣名冊）；多重比較只當參考。非投資建議。", "",
             "| 版本 | 參數 | 全期年化／MDD | Sharpe | 勝率 | 交易次數 | Calmar | 2015～2024 | 2025 起 | 越線格數 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in (("Calmar 最好（MDD≤50%）", bb), ("1× 不設組合止損最好", bn)):
        lines.append(f"| {name} | {par(r)} | {p(r)} | {r['sharpe']:.2f} | {'—' if r['win_rate'] is None else f'{r['win_rate']:.0%}'} | {r['trades']} | "
                     f"{r['calmar']:.2f} | {p(r['segments']['2015_2024'])} | {p(r['segments']['2025_on'])} | {out['n_violates']}/{out['n_grid']} |")
    lines += ["", "同期加權價格指數（2015～2024）+9.5%／−31.6%（第 5 節）。", "", MK_E]
    txt = MD.read_text(encoding="utf-8")
    blk = "\n".join(lines)
    txt = (txt.split(MK_B)[0] + blk + txt.split(MK_E, 1)[1]) if MK_B in txt else (txt.rstrip("\n") + "\n\n" + blk + "\n")
    MD.write_text(txt, encoding="utf-8")

    d = json.loads(CAND.read_text(encoding="utf-8"))
    keep = [c for c in d["candidates"] if not str(c.get("id", "")).startswith("B17F-")]
    new = []
    # 候選門檻同第 6／15 批：Calmar ≥0.6、交易 ≥100、MDD≤50%
    if bb["calmar"] >= 0.6 and bb["trades"] >= 100:
        note = ["樣本內最優化（偏樂觀）", "#133 抽樣名冊有存活者偏誤"]
        if bb["L"] > 2:
            note.append(f"{bb['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": "B17F-f_piotroski_fscore", "factor": FAC, "source": "先.一五五-3 第二批第 17 批（Piotroski F-score）",
                    "status": "候選（待 先.一五四 系列上紙上）", "rank_in_table": 8,
                    "params": {k: bb[k] for k in ("rebalance_days", "market_gate", "top_n", "pos_stop", "direction", "L", "stop")},
                    "backtest_period": "2015-01-01～2026-09-24", "backtest_2015_2024": bb["segments"]["2015_2024"],
                    "from_2025_same_params": bb["segments"]["2025_on"],
                    "full_period_same_params": {"cagr": round(bb["cagr"], 4), "mdd": round(bb["mdd"], 4), "sharpe": round(bb["sharpe"], 2),
                                                "win_rate": bb["win_rate"], "trades": bb["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{FAC} {len(cache)} 格；最好 {par(bb)} → {p(bb)} Sh {bb['sharpe']:.2f} Calmar {bb['calmar']:.2f}；"
          f"2015～2024 {p(bb['segments']['2015_2024'])}、2025 起 {p(bb['segments']['2025_on'])}；1× 不止損最好 {p(bn)}；候選新增 {len(new)}，共 {len(d['candidates'])}")


if __name__ == "__main__":
    main()
