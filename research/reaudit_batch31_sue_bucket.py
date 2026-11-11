"""先.一五五-3 第二批 第 31 批：HQ#368 月營收 SUE 產業中性化（bucket 中性）→事件後固定持有（DevQueue 20261111-120104，紙上優化軌，零請求）。

原試驗（monthly_revenue_sue_continuous_bucket_v1.py）是事件層 IC 檢定（季度×產業×市值五分位 bucket 內去均值後，
連續 SUE 對 20 日報酬 Spearman IC），不是可交易規則。這裡轉成可交易規則：
- 事件＝f_revenue_surprise 新一期出現那天（同第 7 批 E-rev，因子值用 reaudit_ext2025_fin_factors.attach() 重算）。
- 強度＝事件當日「同產業」as-of 值的橫斷面百分位（R-ind，q≥0.8／0.9）或同產業 z 分數（Z-ind，z≥1.0／1.5）；
  只用當日以前已公布的值（panel 往後帶），不用同月之後才公布的公司，不偷看。
  〔自行裁量〕市值五分位 bucket 不做（本機抽樣沒有逐日 PIT 市值），只做產業中性；產業別是今日資料，照實揭露。
- 模擬／成本／漲跌停／槓桿止損只呼叫第 7 批 sim 與 batch2 overlay；#133 抽樣 236 檔（存活者偏誤照實揭露）；
  參數用全期挑（含 2025 起），2025 起分段不是樣本外。非投資建議。
"""
from __future__ import annotations

import mem_guard  # noqa: F401

import itertools
import json
import socket
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _no_net(*a, **k):
    raise RuntimeError("第 31 批零請求：封鎖網路")


socket.socket.connect = _no_net  # type: ignore[assignment]

import reaudit_batch7_events as B7  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402
import reaudit_batch22_material_news as B22  # noqa: E402
from reaudit_ext2025_fin_factors import attach as attach_fin  # noqa: E402

OUT = HERE / "data" / "reaudit_batch3_batch31.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"


def events(ext, px, groups):
    vals = {}
    for sid, d in ext.items():
        v = pd.Series(attach_fin(d, sid, "f_revenue_surprise"), index=pd.to_datetime(d["date"].astype(str).str[:10]))
        vals[sid] = v[~v.index.duplicated()]
    panel = pd.DataFrame(vals).sort_index()
    panel = panel[~panel.index.duplicated()].reindex(px.index).ffill()
    prev = panel.shift(1)
    new = panel.notna() & prev.notna() & panel.ne(prev)
    pct = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    z = pct.copy()
    for ind, ids in groups.items():
        ids = [i for i in ids if i in panel.columns]
        if len(ids) < 3:
            continue
        sub = panel[ids]
        pct[ids] = sub.rank(axis=1, pct=True)
        mu, sd = sub.mean(axis=1), sub.std(axis=1)
        z[ids] = sub.sub(mu, axis=0).div(sd.replace(0, np.nan), axis=0)

    def mk(m):
        s = m.where(new).stack().dropna()
        return s.rename("strength").reset_index().rename(columns={"level_0": "date", "level_1": "sid"})
    return mk(pct), mk(z), int(new.sum().sum())


def main():
    import pair_trading_sanity as pts
    t0 = time.time()
    ext, px, gate, rf, miss = B7.load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    groups = {k: v for k, v in pts.build_industry_groups(list(px.columns)).items() if len(v) >= 3}
    end = str(px.index[-1].date())
    out = {"meta": {"cycle": "20261111-120104", "start": B7.START, "end": end, "n_stocks": int(px.shape[1]),
                    "n_groups": len(groups), "n_in_groups": sum(len(v) for v in groups.values())}, "families": []}
    ew = ret[ret.index >= pd.Timestamp(B7.START)].mean(axis=1).fillna(0)
    out["bench_ew"] = B7.st(ew.index, (1 + ew).cumprod().to_numpy())
    pe, ze, n_new = events(ext, px, groups)
    out["meta"]["n_new_values"] = n_new
    print(f"樣本 {px.shape[1]} 檔、產業 {len(groups)} 群、新值 {n_new}（{time.time()-t0:.0f}s）", flush=True)
    variants = [("R-ind", q, pe[pe["strength"] >= q]) for q in (0.8, 0.9)] + \
               [("Z-ind", q, ze[ze["strength"] >= q]) for q in (1.0, 1.5)]
    for fam, q, ev in variants:
        ev = ev[ev["date"] >= pd.Timestamp("2014-12-01")]
        rows = []
        for H, n, g in itertools.product(B7.HS, B7.NS, (False, True)):
            dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, H, n, g, end)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, _ = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, c)
                rows.append({"H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0,
                             "seg_2015_2024": B7.seg(dates, c, "2015-01-01", "2024-12-31"),
                             "from_2025": B7.seg(dates, c, "2025-01-01", end)})
        ok = [x for x in rows if x["mdd"] > -0.5 and x["trades"] >= 100]
        best = max(ok or rows, key=lambda x: x["calmar"])
        best_l2 = max([x for x in ok if x["L"] <= 2.0] or rows, key=lambda x: x["calmar"])
        out["families"].append({"family": f"{fam} {'q' if fam == 'R-ind' else 'z'}≥{q}", "kind": fam, "q": q,
                                "n_events": int(len(ev)), "n_stocks_with_event": int(ev["sid"].nunique()),
                                "n_cells": len(rows), "best": best, "best_L2": best_l2, "meets_trade_floor": bool(ok),
                                "violates_survival_cells": sum(x["mdd"] <= -0.5 for x in rows)})
        print(f"{fam} {q} 事件 {len(ev)} 最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} Calmar {best['calmar']:.2f} "
              f"交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    render(out)


def _sg(x):
    return f"{x['cagr']:+.1%}／{x['mdd']:.1%}" if x else "—"


def render(out):
    b = out["bench_ew"]
    m = out["meta"]
    lines = ["<!-- BATCH3-B31-BEGIN -->", "",
             "### 34. （#133 抽樣 236 檔）HQ#368 月營收 SUE 產業中性→事件後固定持有（`research/reaudit_batch31_sue_bucket.py`，零請求）", "",
             "做法：f_revenue_surprise 新一期出現那天＝事件（同第 7 批 E-rev），強度改成事件當日**同產業** as-of 值的百分位（R-ind）或 z 分數（Z-ind），"
             f"只用當日以前已公布的值；{m['n_groups']} 個產業群（≥3 檔，共 {m['n_in_groups']} 檔）。下一交易日收盤進、持有 H 日；"
             "模擬／成本／漲跌停／槓桿止損沿用第 7 批，每族 512 格，"
             f"期間 {m['start']}～{m['end']}（含 2025 起，參數用全期挑、不是樣本外）。市值五分位 bucket 沒做（本機無 PIT 市值）；"
             f"產業別是今日資料、名冊有存活者偏誤，照實揭露。同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}；"
             "對照第 7 批 E-rev（全樣本百分位 q≥0.9）+25.3%／−27.9%（Calmar 0.91）。非投資建議。", "",
             "| 族 | 事件數（檔數） | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 2015～2024 | 2025 起 | ≤2× 最佳 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r, r2 = f["best"], f["best_L2"]
        lines.append(f"| {f['family']} | {f['n_events']}（{f['n_stocks_with_event']}） | {r['H']} | {r['N']} | {'開' if r['gate'] else '關'} | "
                     f"{r['L']}× | {B22.stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | {r['sharpe']:.2f} | {r['calmar']:.2f} | "
                     f"{r['trades']} | {r['win_rate']:.0%} | {_sg(r.get('seg_2015_2024'))} | {_sg(r.get('from_2025'))} | "
                     f"{r2['L']}× {r2['cagr']:+.1%}／{r2['mdd']:.1%}（{r2['calmar']:.2f}） |")
    lines += ["", "<!-- BATCH3-B31-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    b0, b1 = "<!-- BATCH3-B31-BEGIN -->", "<!-- BATCH3-B31-END -->"
    if b0 in txt:
        txt = txt[:txt.index(b0)] + block + txt[txt.index(b1) + len(b1):]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    if "render" in sys.argv:
        render(json.loads(OUT.read_text(encoding="utf-8")))
    else:
        main()
