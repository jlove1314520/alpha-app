"""先.一五五-3 第二批 第 15 批：庫藏股／減資事件改用全市場宇宙（DevQueue 20261108-143101，紙上優化軌，零請求）。

第 7／8 批在 #133 抽樣 236 檔裡只有庫藏股 164 筆、減資 11 筆，事件太少、Calmar 虛高；本批改用本機全部
FinMind TaiwanStockPrice 快取（四碼普通股，含已下市股）＝全市場宇宙。

價格與報酬（照實、不偷看未來）：
- 原始收盤（FinMind TaiwanStockPrice，本機快取 2010 起＋2025 起延長檔，同代號依起日由早到晚合併、重複日期舊檔優先）。
- 日報酬＝收盤／前一有價日收盤−1；除息日加回現金股利（CashEarningsDistribution＋CashStatutorySurplus）／前收；
  除權日乘回 1＋股票股利／10（本機 TaiwanStockDividend 快取，公告後才發生的事件，只用來還原報酬，不當訊號）。
- 減資恢復買賣日：報酬＝收盤／恢復買賣參考價−1（現金減資的退款已含在參考價裡，持有者財富不變）。
- 其餘日子 |報酬|>10.5%（非新上市前 5 日）視為資料異常、記缺值（報酬 0），筆數照實揭露。
- 下市：最後一個有價日之後報酬記 0（持有到期以最後價出場；非下市清算模型），照實揭露。

事件（觀察日之後的下一個交易日收盤進場，模擬沿用第 7 批 sim／overlay，只呼叫不改）：
- E-buyback-full：MOPS 庫藏股董事會決議日（本機 data/raw_mops_buyback，民國 104H1～114H1，只算到 2025-06-30）。
  q：all／big（預定買回總金額 ≥ 當年度事件中位數，只用當年度至決議日以前的事件算中位數＝expanding，不偷看）。
- E-reduct-full：減資恢復買賣日（觀察日＝恢復日前一交易日，恢復日收盤進場）。q：cash／loss。
  第 7 批只比對英文原因字（Cash／losses），漏掉中文「現金減資／彌補虧損」約 220 筆；本批兩種寫法都認。
期間：庫藏股 2015-01-02～2025-06-30；減資 2011-01-03～最新。
"""
from __future__ import annotations

import mem_guard  # noqa: F401

import glob
import itertools
import json
import re
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
    raise RuntimeError("本批零請求：封鎖網路")


socket.socket.connect = _no_net  # type: ignore[assignment]

import reaudit_batch7_events as B7  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402

D = HERE / "data"
RAW = D / "raw"
OUT_JSON = D / "reaudit_batch3_batch15.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
CAND = D / "paper_opt_candidates.json"


def load_prices():
    files = {}
    for f in glob.glob(str(RAW / "TaiwanStockPrice__*.parquet")):
        m = re.match(r"TaiwanStockPrice__(\d{4})__(\d{4}-\d{2}-\d{2})__", Path(f).name)
        if m:
            files.setdefault(m.group(1), []).append((m.group(2), f))
    cols = {}
    for sid, fl in files.items():
        parts = []
        for _, f in sorted(fl):
            x = pd.read_parquet(f)
            if len(x) and {"date", "close"} <= set(x.columns):  # 空表快取沒有欄位，略過
                parts.append(x[["date", "close"]])
        if not parts:
            continue
        x = pd.concat(parts).drop_duplicates("date", keep="first")
        s = pd.Series(x["close"].astype(float).to_numpy(), index=pd.to_datetime(x["date"].astype(str).str[:10]))
        s = s[s > 0].sort_index()
        s = s[s.index >= pd.Timestamp("2010-06-01")]
        if len(s) > 20:
            cols[sid] = s
    return pd.DataFrame(cols).sort_index()


def load_divs(sids):
    cash, stk = {}, {}
    for f in glob.glob(str(RAW / "TaiwanStockDividend__*.parquet")):
        sid = Path(f).name.split("__")[1]
        if sid not in sids:
            continue
        x = pd.read_parquet(f)
        if x.empty:
            continue
        for _, r in x.iterrows():
            c = float(r.get("CashEarningsDistribution") or 0) + float(r.get("CashStatutorySurplus") or 0)
            cd = str(r.get("CashExDividendTradingDate") or "").strip()
            if c > 0 and cd:
                cash[(pd.Timestamp(cd[:10]), sid)] = c
            s_ = float(r.get("StockEarningsDistribution") or 0) + float(r.get("StockStatutorySurplus") or 0)
            sd = str(r.get("StockExDividendTradingDate") or "").strip()
            if s_ > 0 and sd:
                stk[(pd.Timestamp(sd[:10]), sid)] = s_
    return cash, stk


def load_reductions():
    fs = glob.glob(str(RAW / "TaiwanStockCapitalReductionReferencePrice__*.parquet"))
    x = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    x = x[x["stock_id"].astype(str).str.fullmatch(r"\d{4}")].drop_duplicates(["date", "stock_id"])
    reason = x["ReasonforCapitalReduction"].astype(str)
    x["kind"] = np.where(reason.str.contains("Cash|現金"), "cash", np.where(reason.str.contains("losses|彌補虧損|虧損"), "loss", "other"))
    x["date"] = pd.to_datetime(x["date"])
    return x


def build_returns(px, cash, stk, red):
    P = px.to_numpy()
    R = np.full(P.shape, np.nan)
    idx = px.index
    colpos = {s: j for j, s in enumerate(px.columns)}
    first = {}
    n_bad = 0
    special = set()
    for (d, sid), v in cash.items():
        special.add((d, sid))
    for (d, sid), v in stk.items():
        special.add((d, sid))
    redref = {(r.date, r.stock_id): float(r.PostReductionReferencePrice) for r in red.itertuples() if r.PostReductionReferencePrice > 0}
    for sid, j in colpos.items():
        col = P[:, j]
        ok = np.where(~np.isnan(col))[0]
        if len(ok) < 2:
            continue
        for a, b in zip(ok[:-1], ok[1:]):
            d = idx[b]
            prev, cur = col[a], col[b]
            key = (d, sid)
            if key in redref:
                R[b, j] = cur / redref[key] - 1
                continue
            r = cur / prev - 1
            if key in stk:
                r = cur * (1 + stk[key] / 10) / prev - 1
            if key in cash:
                r = (cur * (1 + stk.get(key, 0) / 10) + cash[key]) / prev - 1
            if abs(r) > 0.105 and key not in special and (b - ok[0]) > 5:
                n_bad += 1
                continue
            R[b, j] = r
    return pd.DataFrame(R, index=idx, columns=px.columns), n_bad


def buyback_events(px, q):
    ev = B7.buyback_events(px)
    if q == "big":
        ev = ev.sort_values("date").copy()
        yr = ev["date"].dt.year
        med = ev.groupby(yr)["strength"].transform(lambda s: s.expanding().median().shift(1))
        ev = ev[med.notna() & (ev["strength"] >= med)]
    return ev


def reduction_events(px, red, kind):
    x = red[(red["kind"] == kind) & red["stock_id"].isin(px.columns)]
    rows = []
    for r in x.itertuples():
        k = int(np.searchsorted(px.index, r.date, side="left"))
        if 1 <= k < len(px.index):
            rows.append({"date": px.index[k - 1], "sid": r.stock_id, "strength": 1.0})
    return pd.DataFrame(rows, columns=["date", "sid", "strength"])


FAMS = [("E-buyback-full", "庫藏股決議（全市場，buyback_car／HQ#40，2015～2025-06）", "2015-01-02", "2025-06-30"),
        ("E-reduct-full", "減資恢復買賣（全市場，capital_reduction_car／#71，2011 起）", "2011-01-03", None)]


def main():
    t0 = time.time()
    px = load_prices()
    print(f"價格 {px.shape[1]} 檔、{px.index[0].date()}～{px.index[-1].date()}（{time.time()-t0:.0f}s）", flush=True)
    cash, stk = load_divs(set(px.columns))
    red = load_reductions()
    ret, n_bad = build_returns(px, cash, stk, red)
    print(f"報酬完成：除息 {len(cash)}、除權 {len(stk)}、減資 {len(red)}、異常略過 {n_bad}（{time.time()-t0:.0f}s）", flush=True)
    _, px236, gate236, rf236, _ = B7.load()
    gate = gate236.reindex(px.index).ffill().fillna(False)
    # rf：rf_monthly 對全期
    rfm = json.loads((HERE.parent / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rs = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in rfm}).sort_index()
    per = px.index.to_period("M")
    rf = pd.Series(per.map(lambda p: rs[rs.index <= p].iloc[-1] if (rs.index <= p).any() else rs.iloc[0]), index=px.index).astype(float) / 100 / 252
    gate_start = gate236.index[0]
    out = {"meta": {"cycle": "20261108-143101", "n_stocks": int(px.shape[1]), "end": str(px.index[-1].date()),
                    "n_cash_div": len(cash), "n_stock_div": len(stk), "n_reductions": int(len(red)), "n_bad_returns_dropped": int(n_bad),
                    "gate_note": f"大盤閘門用第 7 批同一序列（{gate_start.date()} 起，之前視為關閉＝不進場）",
                    "cost": {"buy": B7.BUY_C, "sell": B7.SELL_C}}, "families": []}
    for fid, title, start, end in FAMS:
        B7.START = start
        if fid == "E-buyback-full":
            variants = {q: buyback_events(px, q) for q in ("all", "big")}
        else:
            variants = {q: reduction_events(px, red, q) for q in ("cash", "loss")}
        rows = []
        for (q, ev), H, n, g in itertools.product(variants.items(), B7.HS, (10, 20, 40), (False, True)):
            dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, H, n, g, end)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, n_stop = S.overlay(eq, rfa, L, stop)
                s = B7.st(dates, c)
                rows.append({"q": q, "H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "n_events": int(len(ev)), "n_stop": n_stop,
                             "seg_early": B7.seg(dates, c, start, "2024-12-31"),
                             "seg_2025": B7.seg(dates, c, "2025-01-01", "2026-12-31"),
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
            print(f"{fid} q={q} 事件 {len(ev)} H={H} N={n} gate={g} 交易 {tr}（{time.time()-t0:.0f}s）", flush=True)
        ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 100]
        best = max(ok or rows, key=lambda r: r["calmar"])
        best_l2 = max([r for r in ok if r["L"] <= 2.0] or rows, key=lambda r: r["calmar"])
        base1 = max([r for r in rows if r["L"] == 1.0 and r["stop"] is None and not r["gate"]], key=lambda r: r["calmar"])
        out["families"].append({"family": fid, "title": title, "start": start, "period_end": end or out["meta"]["end"],
                                "n_cells": len(rows), "best": best, "best_L2": best_l2, "best_1x_plain": base1,
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)
    print(f"完成 {time.time()-t0:.0f}s")


def _p(x):
    return "—" if x is None else f"{x*100:+.1f}%"


def render(out):
    m = out["meta"]
    lines = ["<!-- BATCH3-B15-BEGIN -->", "", "## 18. 第二批 第 15 批：庫藏股／減資改全市場宇宙（DevQueue 20261108-143101 寫碼、20261110-040101 實跑）", "",
             f"宇宙＝本機 FinMind 全部四碼普通股價格快取 {m['n_stocks']} 檔（含已下市股），到 {m['end']}。報酬用原始收盤＋除息加回現金股利"
             f"（{m['n_cash_div']} 筆）＋除權還原（{m['n_stock_div']} 筆）＋減資恢復日用參考價（{m['n_reductions']} 筆）；其餘單日 |報酬|>10.5% 視為異常記 0"
             f"（{m['n_bad_returns_dropped']} 筆）。下市後報酬記 0（非下市清算模型）。{m['gate_note']}。"
             "事件觀察日的下一個交易日收盤進場、持有 H 日；漲 ≥9.5% 買不到、跌 ≤−9.5% 延後賣；成本同第 7 批。"
             "最佳組另要求交易數 ≥100。參數用全期挑（2025 起不是樣本外）。", "",
             "| 族 | 最佳組（Calmar，MDD 在 50% 內、交易 ≥100） | 年化 | MDD | Sharpe | 勝率 | 交易數 | 2024 底前 | 2025 起 | ≤2× 最佳 | 1× 無止損不擇時最佳 | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b, b2, b1 = f["best"], f["best_L2"], f["best_1x_plain"]
        pr = f"q={b['q']}、持有 {b['H']} 日、N={b['N']}、{'大盤閘門' if b['gate'] else '不擇時'}、{b['L']}×、止損 {b['stop'] or '無'}"
        s1, s2 = b["seg_early"] or {}, b["seg_2025"] or {}
        lines.append(f"| {f['title']} | {pr} | {_p(b['cagr'])} | {_p(b['mdd'])} | {b['sharpe']:.2f} | {b['win_rate']*100:.0f}% | {b['trades']} | "
                     f"{_p(s1.get('cagr'))}／{_p(s1.get('mdd'))} | {_p(s2.get('cagr'))}／{_p(s2.get('mdd'))} | "
                     f"{b2['L']}× {_p(b2['cagr'])}／{_p(b2['mdd'])} | {_p(b1['cagr'])}／{_p(b1['mdd'])} | "
                     f"{f['violates_survival_cells']}／{f['n_cells']} |")
    lines += ["", "明細 `research/data/reaudit_batch3_batch15.json`（本機）。3× 超過融資上限只當參考。",
              "**順帶發現（照實記錄）**：第 7／8 批的減資事件只比對英文原因字（Cash／losses），FinMind 表裡另有中文「現金減資／彌補虧損」約 220 筆被漏掉；"
              "本批兩種寫法都認，第 11 節 E-reduct（236 檔）數字未重跑。",
              "", "<!-- BATCH3-B15-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if "<!-- BATCH3-B15-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B15-BEGIN -->")
        z = txt.index("<!-- BATCH3-B15-END -->") + len("<!-- BATCH3-B15-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip() + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def candidates():
    """Calmar ≥0.6、交易 ≥100、MDD 在 50% 內的族寫進候選欄（id 前綴 B15E-，同第 7 批作法）；只讀明細 JSON、不重跑模擬。"""
    out = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    d = json.loads(CAND.read_text(encoding="utf-8"))
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B15E-")]
    new = []
    for f in out["families"]:
        b = f["best"]
        if not (b["calmar"] >= 0.6 and b["trades"] >= 100 and b["mdd"] > -0.5):
            continue
        s1, s2 = b["seg_early"] or {}, b["seg_2025"] or {}
        new.append({"id": f"B15E-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 15 批（事件類，全市場宇宙）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": 8,
                    "params": {k: b[k] for k in ("q", "H", "N", "gate", "L", "stop")},
                    "backtest_period": f"{f['start']}～{f['period_end']}",
                    "backtest_2015_2024": {"cagr": s1.get("cagr"), "mdd": s1.get("mdd"), "sharpe": s1.get("sharpe")},
                    "from_2025_same_params": {"cagr": s2.get("cagr"), "mdd": s2.get("mdd"), "sharpe": s2.get("sharpe")} if s2 else None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False,
                    "notes": "樣本內最優化（偏樂觀，參數用全期挑）；全市場四碼普通股（含已下市）事件後固定持有；下市後報酬記 0（非清算模型）"})
    d["candidates"] = keep + new
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候選欄：新增 {len(new)} 支 B15E-，共 {len(d['candidates'])} 支")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "candidates":
        candidates()
    else:
        main()
