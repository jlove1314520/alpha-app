"""先.一五五-3 第 24 批：重大訂單／得標／簽約公告（#72）→ 事件後固定持有（紙上優化軌，零請求）。

- 事件來源同第 22 批 25b 節：本機 MOPS 重大訊息 `mops_material_news_events_classified.parquet`（2015～2024）。
  分類器沒有「訂單」類，這裡用主旨關鍵字從全部類別切（排除「代」開頭的子公司代公告、含法院／判決／訴訟／起訴／
  更正／補充／解除／終止字樣者）：
  E-order＝主旨含「訂單｜得標｜取得.*標案」；E-contract＝主旨含「簽訂.*(合約|契約|協議)」且非處分資產／增減資／併購類；
  E-build＝主旨含「承攬」（多為建商發包工程，方向不明，照實列出）。
- 觀察日＝公告日（非交易日歸到之後第一個交易日），下一個交易日收盤進場；模擬／成本／漲跌停／槓桿止損全部只呼叫
  第 7 批 `reaudit_batch7_events`、batch2 overlay；宇宙＝#133 抽樣 236 檔（存活者偏誤照實揭露）；2015-01～2024-12。
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
import reaudit_batch22_material_news as B22  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = B7.S
OUT = HERE / "data" / "reaudit_batch3_batch24.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
END = B22.END
BAD = "法院|判決|訴訟|起訴|更正|補充|解除|終止|支付命令"
FAMS = {
    "E-order": ("訂單|得標|取得.*標案", None),
    "E-contract": ("簽訂.*(合約|契約|協議)", ("處分資產", "增減資", "併購")),
    "E-build": ("承攬", None),
}


def kw_events(px, pat, drop_types):
    x = pd.read_parquet(B22.SRC, columns=["stock_id", "date", "type", "subject"])
    x = x[x["stock_id"].astype(str).isin(px.columns)].copy()
    subj = x["subject"].astype(str)
    m = subj.str.contains(pat) & ~subj.str.startswith("代") & ~subj.str.contains(BAD)
    if drop_types:
        m &= ~x["type"].isin(drop_types)
    x = x[m]
    x["date"] = pd.to_datetime(x["date"].astype(str), format="%Y%m%d", errors="coerce")
    x = x.dropna(subset=["date"])
    k = np.searchsorted(px.index, x["date"].to_numpy(), side="left")
    keep = k < len(px.index)
    return pd.DataFrame({"date": px.index[k[keep]], "sid": x["stock_id"].astype(str).to_numpy()[keep], "strength": 1.0}) \
        .drop_duplicates(["date", "sid"])


def load_full():
    """全市場四碼普通股（含已下市）：價格、除權息／減資還原報酬、閘門、rf 全部照第 15 批（只呼叫）。"""
    import reaudit_batch15_fullmkt_events as B15
    px = B15.load_prices()
    cash, stk = B15.load_divs(set(px.columns))
    red = B15.load_reductions()
    ret, n_bad = B15.build_returns(px, cash, stk, red)
    _, _, gate236, _, _ = B7.load()
    gate = gate236.reindex(px.index).ffill().fillna(False)
    rfm = json.loads((HERE.parent / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rs = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in rfm}).sort_index()
    per = px.index.to_period("M")
    rf = pd.Series(per.map(lambda p: rs[rs.index <= p].iloc[-1] if (rs.index <= p).any() else rs.iloc[0]),
                   index=px.index).astype(float) / 100 / 252
    return px, ret, gate, rf, int(n_bad)


def load_universe(full):
    if full:
        return load_full()
    ext, px, gate, rf, miss = B7.load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    return px, ret, gate, rf, 0


FULL = "--full" in sys.argv
if FULL:
    OUT = HERE / "data" / "reaudit_batch3_batch24_full.json"


def main():
    t0 = time.time()
    px, ret, gate, rf, n_bad = load_universe(FULL)
    print(f"宇宙 {px.shape[1]} 檔（{'全市場' if FULL else '236 抽樣'}），異常報酬略過 {n_bad}（{time.time()-t0:.0f}s）", flush=True)
    out = {"meta": {"src": B22.SRC.name, "start": B7.START, "end": END, "n_stocks": int(px.shape[1]), "full_market": FULL}, "families": []}
    ew = ret[(ret.index >= pd.Timestamp(B7.START)) & (ret.index <= pd.Timestamp(END))].mean(axis=1).fillna(0)
    out["bench_ew"] = B7.st(ew.index, (1 + ew).cumprod().to_numpy())
    for fam, (pat, drop_types) in FAMS.items():
        ev = kw_events(px, pat, drop_types)
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
        out["families"].append({"family": fam, "pattern": pat, "n_events": int(len(ev)), "n_stocks_with_event": int(ev["sid"].nunique()),
                                "n_cells": len(rows), "best": best, "meets_trade_floor": bool(ok),
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        print(f"{fam} 事件 {len(ev)}（{ev['sid'].nunique()} 檔）最佳 {best['cagr']:+.1%}/{best['mdd']:.1%} 交易 {best['trades']}（{time.time()-t0:.0f}s）", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def render(out):
    b = out["bench_ew"]
    tag = "B24F" if out["meta"].get("full_market") else "B24"
    uni = f"全市場四碼普通股 {out['meta']['n_stocks']} 檔（含已下市，還原照第 15 批）" if out["meta"].get("full_market") else "#133 抽樣 236 檔"
    lines = [f"<!-- BATCH3-{tag}-BEGIN -->", "",
             f"### 27{'a' if tag == 'B24F' else ''}. （{uni}）重大訂單／得標／簽約公告（#72，`research/reaudit_batch24_major_orders.py`，零請求）", "",
             "做法：本機 MOPS 重大訊息 2015～2024 用主旨關鍵字切（排除代子公司公告、法院／訴訟／更正／補充／解除／終止），"
             "公告日的下一個交易日收盤進場、持有 H 日；模擬／成本／漲跌停／槓桿止損沿用第 7 批，每族 512 格；候選門檻交易 ≥100、MDD 在 50% 內"
             "（達不到交易門檻者表上照實標「未達」，數字只當參考）。"
             f"同期同宇宙等權（不扣成本）{b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}。存活者偏誤照實揭露。非投資建議。", "",
             "| 族 | 關鍵字 | 事件數（檔數） | H | N | 閘門 | 槓桿 | 止損 | 年化 | MDD | Sharpe | Calmar | 交易 | 勝率 | 交易門檻 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        r = f["best"]
        pat = f["pattern"].replace("|", "／")
        lines.append(f"| {f['family']} | `{pat}` | {f['n_events']}（{f['n_stocks_with_event']}） | {r['H']} | {r['N']} | "
                     f"{'開' if r['gate'] else '關'} | {r['L']}× | {B22.stop_txt(r['stop'])} | {r['cagr']:+.1%} | {r['mdd']:.1%} | "
                     f"{r['sharpe']:.2f} | {r['calmar']:.2f} | {r['trades']} | {r['win_rate']:.0%} | {'達' if f['meets_trade_floor'] else '未達'} |")
    lines += ["", f"<!-- BATCH3-{tag}-END -->"]
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
    main()
