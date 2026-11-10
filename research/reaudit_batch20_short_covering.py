"""先.一五五-3 第二批 第 20 批：融券強制回補事件（HQ#51 子事件 1，forced_short_covering_gate1）→ 事件交易（紙上優化軌，零請求）。

原試驗只做 IC（融券部位大小 vs 強制回補窗口內超額報酬）；這裡轉成可交易規則：
- 事件：現金除息（本機 TaiwanStockDividend 快取 `CashExDividendTradingDate`）。停止過戶日＝除息日後第 2 個交易日
  （公式照 forced_short_covering_gate1._stop_transfer_and_window，交易日用該股自己的有價日）。
- 進場：停止過戶日前 e 個交易日收盤（e∈{6,10}）；出場：停止過戶日前 x 個交易日收盤（x∈{3,1}；x=3＝原試驗窗口終點，
  x=1＝除息日當天收盤，含除息——價格是還原價，股利已在報酬裡）。持有 H＝e−x 個交易日。
- 只用當時看得到的資料：進場前一個交易日（觀察日）收盤的融券餘額÷融券限額（原試驗 short_ratio 口徑，本機 FinMind
  TaiwanStockMarginPurchaseShortSale 快取，as-of）；除息公告日（AnnouncementDate）必須 ≤ 觀察日，否則跳過（不偷看）。
- 門檻：short_ratio ≥ q（q∈{0, 0.005, 0.02, 0.05}，固定絕對值，不用全樣本分位數以免偷看）；同日多筆依 short_ratio 由高到低。
- 模擬只呼叫第 7 批 `reaudit_batch7_events`（load／sim／st／seg，漲跌停、成本、槽位、無風險利率同第 7 批）與 batch2 overlay
  （槓桿 1/1.5/2/3×、組合止損 4 種）。宇宙＝#133 抽樣 236 檔（今天還在者，有存活者偏誤），期間 2015-01-02～延長價格終點。
- 參數用全期挑（含 2025 起），2025 起分段不是樣本外。核心檔只呼叫不改。
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


def _blocked(*a, **k):
    raise OSError("本批零請求：socket 已封鎖")


socket.socket.connect = _blocked
socket.create_connection = _blocked

import reaudit_batch7_events as B7  # noqa: E402
from reaudit_ext2025_fin_factors import _chip_raw  # noqa: E402

D = HERE / "data"
RAW = D / "raw"
OUT_JSON = D / "reaudit_batch3_batch20.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
ENTRY = (6, 10)
EXIT = (3, 1)
QS = (0.0, 0.005, 0.02, 0.05)
NS = (10, 20)


def _div(sid):
    fs = sorted(RAW.glob(f"TaiwanStockDividend__{sid}__*.parquet"))
    parts = [pd.read_parquet(f) for f in fs]
    parts = [x for x in parts if not x.empty and "CashExDividendTradingDate" in x.columns]
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    x["ex"] = x["CashExDividendTradingDate"].astype(str).str[:10]
    x = x[x["ex"].str.match(r"\d{4}-\d{2}-\d{2}")]
    x["ann"] = x.get("AnnouncementDate", pd.Series("", index=x.index)).astype(str).str[:10]
    return x.drop_duplicates("ex")[["ex", "ann"]]


def _short_ratio(sid):
    raw = _chip_raw("TaiwanStockMarginPurchaseShortSale", sid, ["date"])
    if raw.empty or not {"ShortSaleTodayBalance", "ShortSaleLimit"} <= set(raw.columns):
        return pd.Series(dtype=float)
    b = pd.to_numeric(raw["ShortSaleTodayBalance"], errors="coerce")
    lim = pd.to_numeric(raw["ShortSaleLimit"], errors="coerce")
    s = pd.Series(np.where(lim > 0, b / lim, np.nan), index=pd.to_datetime(raw["date"])).sort_index()
    return s[~s.index.duplicated(keep="first")].dropna()


def build_events(px):
    """回傳 {(e,x): DataFrame(date＝觀察日, sid, strength＝short_ratio)}。"""
    out = {k: [] for k in itertools.product(ENTRY, EXIT)}
    uidx = px.index
    n_ex = n_skip_ann = 0
    for sid in px.columns:
        dv = _div(sid)
        if dv.empty:
            continue
        own = px[sid].dropna().index
        pos = {d: i for i, d in enumerate(own)}
        sr = _short_ratio(sid)
        if sr.empty:
            continue
        for _, r in dv.iterrows():
            ex = pd.Timestamp(r["ex"])
            if ex not in pos:
                continue
            n_ex += 1
            stop = pos[ex] + 2
            for e, x in out:
                ie = stop - e
                if ie < 1 or stop - x >= len(own):
                    continue
                entry = own[ie]
                ku = int(np.searchsorted(uidx, entry))
                if ku < 1:
                    continue
                obs = uidx[ku - 1]
                ann = r["ann"]
                if not (len(ann) == 10 and ann[0].isdigit() and pd.Timestamp(ann) <= obs):
                    n_skip_ann += 1
                    continue
                j = int(sr.index.searchsorted(obs, side="right")) - 1
                if j < 0 or (obs - sr.index[j]).days > 10:
                    continue
                out[(e, x)].append({"date": obs, "sid": sid, "strength": float(sr.iloc[j])})
    print(f"除息事件 {n_ex} 筆（各進出場組合公告晚於觀察日而略過合計 {n_skip_ann} 次）")
    return {k: pd.DataFrame(v) for k, v in out.items()}


def main():
    t0 = time.time()
    ext, px, gate, rf, miss = B7.load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    print(f"樣本 {px.shape[1]} 檔、{px.index[0].date()}～{px.index[-1].date()}（{time.time()-t0:.0f}s）", flush=True)
    evs = build_events(px)
    for k, v in evs.items():
        if not v.empty:
            print(k, len(v), "short_ratio 分位", v["strength"].quantile([0.25, 0.5, 0.75, 0.9]).round(4).to_dict())
    rows = []
    for (e, x), q, n, g in itertools.product(evs, QS, NS, (False, True)):
        ev = evs[(e, x)]
        ev = ev[ev["strength"] >= q] if not ev.empty else ev
        if ev.empty:
            continue
        dates, eq, tr, wr = B7.sim(px, ret, gate, rf, ev, e - x, n, g)
        rfa = rf.reindex(dates).to_numpy()
        for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
            c, n_stop = B7.S.overlay(eq, rfa, L, stop)
            s = B7.st(dates, c)
            rows.append({"entry_before_stop": e, "exit_before_stop": x, "q": q, "N": n, "gate": g, "L": L, "stop": stop, **s,
                         "trades": tr, "win_rate": wr, "n_events": int(len(ev)), "n_stop": n_stop,
                         "seg_2015_2024": B7.seg(dates, c, "2015-01-01", "2024-12-31"),
                         "seg_2025": B7.seg(dates, c, "2025-01-01", "2026-12-31"),
                         "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
        print(f"e={e} x={x} q={q} N={n} gate={g} 交易 {tr}（{time.time()-t0:.0f}s）", flush=True)
    ok = [r for r in rows if r["mdd"] > -0.5 and r["trades"] >= 100]
    best = max(ok or rows, key=lambda r: r["calmar"])
    best_l2 = max([r for r in ok if r["L"] <= 2.0] or rows, key=lambda r: r["calmar"])
    base1 = max([r for r in rows if r["L"] == 1.0 and r["stop"] is None and not r["gate"]], key=lambda r: r["calmar"])
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "cycle": "20261111-000101", "n_stocks": int(px.shape[1]),
           "period": [B7.START, str(px.index[-1].date())], "n_cells": len(rows), "best": best, "best_L2": best_l2,
           "best_1x_plain": base1, "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows),
           "caveat": "#133 抽樣 236 檔（今天還在者）有存活者偏誤；只做多；2025 起缺價日報酬記 0。", "rows": rows}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    for k in ("best", "best_L2", "best_1x_plain"):
        r = out[k]
        print(k, {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in r.items() if not kk.startswith("seg")},
              "2015-2024", r["seg_2015_2024"], "2025起", r["seg_2025"])
    print(f"完成 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
