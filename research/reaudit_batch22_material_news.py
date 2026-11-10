"""先.一五五-3 第 22 批（第二族）：MOPS 重大訊息分類事件（#52 material_news_car）→ 事件後固定持有（紙上優化軌，零請求）。

- 事件來源：本機 `research/data/mops_material_news_events_classified.parquet`（2015～2024，backfill_material_news.py 抓、
  已依主旨關鍵字分類 type）。只取類別明確的 6 類：併購／處分資產／訴訟／法說會／增減資／停復牌（「其他／財務／人事」太雜不做）。
- 觀察日＝公告日（非交易日歸到之後第一個交易日）；不論盤中或盤後公告，一律**觀察日的下一個交易日收盤進場**（偏保守，不偷看）。
- 模擬、成本、漲跌停、槓桿／組合止損全部只呼叫第 7 批 `reaudit_batch7_events`（load／sim／st／seg）與 batch2 overlay。
- 宇宙＝#133 抽樣 236 檔（有存活者偏誤，照實揭露）；期間 2015-01～2024-12（事件資料只到 2024 底）。
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
SRC = HERE / "data" / "mops_material_news_events_classified.parquet"
OUT = HERE / "data" / "reaudit_batch3_batch22_news.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
TYPES = ("併購", "處分資產", "訴訟", "法說會", "增減資", "停復牌", "增減資:現金增資", "增減資:減資", "增減資:私募")
# 「類別:關鍵字」＝類別內主旨含關鍵字者；排除「代」開頭（代子公司公告）
END = "2024-12-31"


def news_events(px, typ):
    typ, _, kw = typ.partition(":")
    x = pd.read_parquet(SRC, columns=["stock_id", "date", "type", "subject"])
    x = x[(x["type"] == typ) & x["stock_id"].astype(str).isin(px.columns)].copy()
    if kw:
        subj = x["subject"].astype(str)
        x = x[subj.str.contains(kw) & ~subj.str.startswith("代")]
    x["date"] = pd.to_datetime(x["date"].astype(str), format="%Y%m%d", errors="coerce")
    x = x.dropna(subset=["date"]).drop_duplicates(["date", "stock_id"])
    k = np.searchsorted(px.index, x["date"].to_numpy(), side="left")
    x = x[k < len(px.index)].copy()
    x["date"] = px.index[k[k < len(px.index)]]
    return pd.DataFrame({"date": x["date"].to_numpy(), "sid": x["stock_id"].astype(str).to_numpy(), "strength": 1.0}) \
        .drop_duplicates(["date", "sid"])


def main():
    t0 = time.time()
    ext, px, gate, rf, miss = B7.load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    out = {"meta": {"src": SRC.name, "start": B7.START, "end": END, "n_stocks": int(px.shape[1])}, "families": []}
    # 對照：同期 236 檔等權買進持有（每日再平衡近似，不扣成本）
    ew = ret[(ret.index >= pd.Timestamp(B7.START)) & (ret.index <= pd.Timestamp(END))].mean(axis=1).fillna(0)
    ewc = (1 + ew).cumprod().to_numpy()
    out["bench_ew"] = B7.st(ew.index, ewc)
    for typ in TYPES:
        ev = news_events(px, typ)
        rows = []
        for H, n, g in itertools.product(B7.HS, B7.NS, (False, True)):
            dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, H, n, g, END)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, n_stop = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, c)
                rows.append({"H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "n_events": int(len(ev)), "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
        ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 100]
        best = max(ok or rows, key=lambda r: r["calmar"])
        out["families"].append({"family": f"E-news-{typ}", "n_events": int(len(ev)), "n_cells": len(rows), "best": best,
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        print(f"{typ} 事件 {len(ev)} 最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} 交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def stop_txt(s):
    return "無" if s is None else f"{s:.0%}"


def render(out):
    b = out["bench_ew"]
    lines = ["<!-- BATCH3-B22N-BEGIN -->", "",
             "### 25b. 重大訊息分類事件（#52 material_news_car，`research/reaudit_batch22_material_news.py`，零請求）", "",
             "做法：MOPS 重大訊息（本機 2015～2024、已分類）取 6 類，公告日的下一個交易日收盤進場、持有 H 日；模擬／成本／漲跌停／槓桿止損全部沿用第 7 批。"
             "每族 512 格（H 5/10/21/63×N 10/20×大盤閘門×槓桿 1/1.5/2/3×止損 4 種）；候選門檻交易 ≥100、MDD 在 50% 內。"
             f"同期 236 檔等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。存活者偏誤照實揭露。非投資建議。", "",
             "| 族 | 事件數 | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 越過天條一格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r = f["best"]
        lines.append(f"| {f['family']} | {f['n_events']} | {r['H']} | {r['N']} | {'開' if r['gate'] else '關'} | {r['L']}× | "
                     f"{stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | "
                     f"{r['sharpe']:.2f} | {r['calmar']:.2f} | {r['trades']} | {r['win_rate']:.0%} | {f['violates_survival_cells']} |")
    lines += ["", "<!-- BATCH3-B22N-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if "<!-- BATCH3-B22N-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B22N-BEGIN -->")
        z = txt.index("<!-- BATCH3-B22N-END -->") + len("<!-- BATCH3-B22N-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")
    print(block)


if __name__ == "__main__":
    main()
