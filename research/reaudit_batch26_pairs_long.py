"""先.一五五-3 第 26 批：#16 同產業配對交易 → 只做多頭半邊（紙上優化軌，零請求）。

原 #16 是同產業配對、log 價差 z-score 偏離就做多低估腿＋放空高估腿；放空腿借券成本／可借量未接真實資料（放空腿硬規則），
所以這裡只做多頭半邊：
- 宇宙：#133 抽樣 236 檔（延長價格到 2026-09-24，第 7 批 `B7.load()` 只呼叫）；產業＝`pair_trading_sanity.build_industry_groups()`
  （今日的產業別，非時點資料，照實揭露）。
- 每個交易日 t，同產業每一對 (A,B)：只用 t 以前（含 t 收盤）的資料算 W 日報酬相關（rolling），≥ c 才算「配對」；
  log(A/B) 的 120 日 rolling z ≤ −Z（A 相對 B 偏低）→ 事件（觀察日 t，sid＝A，strength＝−z），下一交易日收盤買 A、持有 H 日。
- 模擬／成本／漲跌停／槓桿止損只呼叫第 7 批 sim、batch2 overlay。Z∈{2.0,2.5}×相關門檻 c∈{0.5,0.7}（W＝120）
  ＝4 族，各 512 格；期間 2015-01～2026-09-24（含 2025 起）。
不改核心檔、不寫試驗帳本。非投資建議。
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
    raise RuntimeError("第 26 批零請求：封鎖網路")


socket.socket.connect = _no_net
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reaudit_batch7_events as B7  # noqa: E402
import reaudit_batch22_material_news as B22  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
OUT = HERE / "data" / "reaudit_batch3_batch26.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
ZW = 120
CW = 120


def pair_events(px, groups, zthr, cthr):
    lp = np.log(px.where(px > 0))
    r = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    rows = []
    npairs = 0
    for ind, ids in groups.items():
        ids = [i for i in ids if i in px.columns]
        for a, b in itertools.combinations(ids, 2):
            npairs += 1
            corr = r[a].rolling(CW, min_periods=CW // 2).corr(r[b])
            sp = lp[a] - lp[b]
            z = (sp - sp.rolling(ZW, min_periods=ZW // 2).mean()) / sp.rolling(ZW, min_periods=ZW // 2).std()
            ok = corr >= cthr
            for low, hi, zz in ((a, b, z), (b, a, -z)):
                hit = ok & (zz <= -zthr) & ~((zz.shift(1) <= -zthr) & ok.shift(1, fill_value=False))  # 剛跨過門檻那天
                d = zz[hit]
                rows += [{"date": t, "sid": low, "strength": float(-v)} for t, v in d.items()]
    ev = pd.DataFrame(rows, columns=["date", "sid", "strength"])
    ev = ev.sort_values("strength", ascending=False).drop_duplicates(["date", "sid"])
    return ev, npairs


def main():
    import pair_trading_sanity as pts
    t0 = time.time()
    ext, px, gate, rf, miss = B7.load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    groups = pts.build_industry_groups(list(px.columns))
    end = str(px.index[-1].date())
    out = {"meta": {"start": B7.START, "end": end, "n_stocks": int(px.shape[1]), "n_groups": len(groups)}, "families": []}
    ew = ret[ret.index >= pd.Timestamp(B7.START)].mean(axis=1).fillna(0)
    out["bench_ew"] = B7.st(ew.index, (1 + ew).cumprod().to_numpy())
    for zthr, cthr in itertools.product((2.0, 2.5), (0.5, 0.7)):
        ev, npairs = pair_events(px, groups, zthr, cthr)
        ev = ev[ev["date"] >= pd.Timestamp(B7.START)]
        rows = []
        for H, n, g in itertools.product(B7.HS, B7.NS, (False, True)):
            dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, H, n, g, end)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, _ = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, c)
                s25 = B7.seg(dates, c, "2025-01-01", end)
                rows.append({"H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0,
                             "from_2025": s25})
        ok = [x for x in rows if x["mdd"] > -0.5 and x["trades"] >= 100]
        best = max(ok or rows, key=lambda x: x["calmar"])
        fam = f"P-long z≤−{zthr} corr≥{cthr}"
        out["families"].append({"family": fam, "z": zthr, "corr": cthr, "n_pairs": npairs, "n_events": int(len(ev)),
                                "n_stocks_with_event": int(ev["sid"].nunique()), "n_cells": len(rows), "best": best,
                                "meets_trade_floor": bool(ok), "violates_survival_cells": sum(x["mdd"] <= -0.5 for x in rows)})
        print(f"{fam} 配對 {npairs} 事件 {len(ev)} 最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} 交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    render(out)


def render(out):
    b = out["bench_ew"]
    lines = ["<!-- BATCH3-B26-BEGIN -->", "",
             "### 29. （#133 抽樣 236 檔）#16 同產業配對交易只做多頭半邊（`research/reaudit_batch26_pairs_long.py`，零請求）", "",
             f"做法：{out['meta']['n_groups']} 個產業群組內兩兩配對；t 收盤以前 120 日報酬相關 ≥ c 才算配對，log 價差 120 日 z 剛跌破 −Z 的那天＝"
             "觀察日，下一交易日收盤買偏低那一腿、持有 H 日（不做空高估腿：放空腿借券成本／可借量未接真實資料）；模擬／成本／漲跌停／槓桿止損沿用第 7 批，"
             f"每族 512 格，期間 {out['meta']['start']}～{out['meta']['end']}（含 2025 起）。產業別是今日資料、名冊有存活者偏誤，照實揭露。"
             f"同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。非投資建議。", "",
             "| 族 | 配對數 | 事件數（檔數） | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 2025 起 | 交易門檻 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r = f["best"]
        s25 = r.get("from_2025")
        t25 = f"{s25['cagr']:+.1%}／{s25['mdd']:.1%}" if s25 else "—"
        lines.append(f"| {f['family']} | {f['n_pairs']} | {f['n_events']}（{f['n_stocks_with_event']}） | {r['H']} | {r['N']} | "
                     f"{'開' if r['gate'] else '關'} | {r['L']}× | {B22.stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | "
                     f"{r['sharpe']:.2f} | {r['calmar']:.2f} | {r['trades']} | {r['win_rate']:.0%} | {t25} | {'達' if f['meets_trade_floor'] else '未達'} |")
    lines += ["", "<!-- BATCH3-B26-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    b0, b1 = "<!-- BATCH3-B26-BEGIN -->", "<!-- BATCH3-B26-END -->"
    if b0 in txt:
        txt = txt[:txt.index(b0)] + block + txt[txt.index(b1) + len(b1):]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


CAND = HERE / "data" / "paper_opt_candidates.json"


def candidates():
    """同一機制只取 Calmar 最高的一族（Calmar ≥0.6、交易 ≥100、MDD 在 50% 內）寫進候選欄，id 前綴 B26P-；只讀明細 JSON。"""
    out = json.loads(OUT.read_text(encoding="utf-8"))
    d = json.loads(CAND.read_text(encoding="utf-8"))
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B26P-")]
    ok = [f for f in out["families"] if f["best"]["calmar"] >= 0.6 and f["best"]["trades"] >= 100 and f["best"]["mdd"] > -0.5]
    new = []
    if ok:
        f = max(ok, key=lambda f: f["best"]["calmar"])
        b = f["best"]
        s2 = b.get("from_2025") or {}
        new.append({"id": f"B26P-pairs_long_z{f['z']}_c{f['corr']}", "factor": f["family"],
                    "source": "先.一五五-3 第二批第 26 批（#16 配對交易只做多頭半邊）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": 10,
                    "params": {"z": f["z"], "corr": f["corr"], "corr_window": CW, "z_window": ZW,
                               **{k: b[k] for k in ("H", "N", "gate", "L", "stop")}},
                    "backtest_period": f"{out['meta']['start']}～{out['meta']['end']}",
                    "from_2025_same_params": {"cagr": s2.get("cagr"), "mdd": s2.get("mdd"), "sharpe": s2.get("sharpe")} if s2 else None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False,
                    "notes": "樣本內最優化（參數用全期挑、含 2025 起，不是樣本外）；#133 抽樣 236 檔有存活者偏誤、產業別是今日資料；"
                             "年化低（多數時間空手收無風險利率），Calmar 高主要來自低曝險；只做多頭半邊"})
    d["candidates"] = keep + new
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候選欄：新增 {len(new)} 支 B26P-，共 {len(d['candidates'])} 支")


if __name__ == "__main__":
    if "candidates" in sys.argv:
        candidates()
    elif "render" in sys.argv:
        render(json.loads(OUT.read_text(encoding="utf-8")))
    else:
        main()
