# -*- coding: utf-8 -*-
"""先.一五五-3 第 18 批：#457／#458 高股息 ETF 換股事件 → 可交易規則最優化（紙上優化軌，描述性）。

紙上優化軌：不寫 TRIALS_LEDGER、不呼叫 register_trial；多重比較只當參考。非投資建議。零外部請求。
- 事件：`research/data/etf_rebalance_events.csv`（0056／00713／00878／00919／00929／00940，公告日與生效日都有的才用），
  2022～2026（含 2025 起，先.一五五-1 保留資料已開放）。同股同生效日只算一次；同日一加一刪剔除。
- 價格：本機 FinMind 快取 `data/raw/TaiwanStockPrice__{代號}__*.parquet` 全部檔合併（2025 起檔到 2026-10-01）；
  日報酬用「漲跌」欄＝收盤÷(收盤−漲跌)−1（同 reaudit_ext2025_engine.load_extended，已含權息參考價）。
- 進場（PIT）：公告多在盤後，主口徑＝公告後第一個交易日開盤（next_open）或收盤（next_close）；
  公告日收盤（ann_close）只當參考列，標「可能偷看」。鎖漲停（開高低收同價且漲 ≥9.5%）買不到→該筆不做；
  出場日鎖跌停賣不掉→順延到第一個賣得掉的交易日。
- 出場：生效日前一交易日收盤（eff-1，ETF 實際買賣多在此）、生效日收盤（eff0）、生效日後 5／10／20 個交易日收盤。
- 組合：同時持有的部位每日等權；成本＝round_trip_cost_pct()（1×，滑價 5bps）在進場日依權重扣；
  槓桿 L：日報酬×L，借款 (L−1)×6.5%/年 只在有部位的日子計；空手日 0。
- 只做多（ADD 買進、DEL「反向」也是買進＝賭被刪除後反彈）；不做放空腿（借券資料缺陷，見 CLAUDE.md 七之三⑩）。
用法：python research/reaudit_batch18_etf_rebal.py
"""
from __future__ import annotations

import csv
import glob
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from validation.costs import round_trip_cost_pct  # noqa: E402

RAW = HERE / "data" / "raw"
EVENTS_CSV = HERE / "data" / "etf_rebalance_events.csv"
OUT_JSON = HERE / "data" / "reaudit_batch3_batch18.json"
FIN_RATE = 0.065
COST = round_trip_cost_pct()

_cache: dict[str, pd.DataFrame] = {}


def daily(code: str) -> pd.DataFrame:
    if code in _cache:
        return _cache[code]
    fs = glob.glob(str(RAW / f"TaiwanStockPrice__{code}__*.parquet"))
    parts = []
    for f in fs:
        x = pd.read_parquet(f)
        if not x.empty and "date" in x.columns:
            parts.append(x)
    if not parts:
        d = pd.DataFrame(columns=["date", "open", "high", "low", "close", "ret", "ref"])
    else:
        x = pd.concat(parts, ignore_index=True)
        x["date"] = pd.to_datetime(x["date"])
        x = x[x["close"].astype(float) > 0].drop_duplicates("date").sort_values("date").reset_index(drop=True)
        c = x["close"].astype(float).to_numpy()
        ref = c - x["spread"].astype(float).to_numpy()
        d = pd.DataFrame({"date": x["date"], "open": x["open"].astype(float), "high": x["max"].astype(float),
                          "low": x["min"].astype(float), "close": c, "ref": ref,
                          "ret": np.where(ref > 0, c / np.where(ref > 0, ref, 1) - 1.0, 0.0)})
        d = d.set_index("date")
    _cache[code] = d
    return d


def pinned(row, up: bool) -> bool:
    o, h, l, c, ref = row["open"], row["high"], row["low"], row["close"], row["ref"]
    if ref <= 0 or not (abs(o - h) < 1e-9 and abs(h - l) < 1e-9 and abs(l - c) < 1e-9):
        return False
    chg = c / ref - 1
    return chg >= 0.095 if up else chg <= -0.095


def load_events():
    rows = list(csv.DictReader(open(EVENTS_CSV, encoding="utf-8-sig")))
    rows = [r for r in rows if r["announce_date"][:4].isdigit() and r["effective_date"][:4].isdigit()]
    acts = defaultdict(set)
    for r in rows:
        acts[(r["effective_date"], r["stock_code"])].add(r["action"])
    ev, seen = [], set()
    for r in sorted(rows, key=lambda r: (r["effective_date"], r["stock_code"])):
        k = (r["effective_date"], r["stock_code"])
        if k in seen or len(acts[k]) > 1:
            continue
        seen.add(k)
        ev.append({"ann": pd.Timestamp(r["announce_date"]), "eff": pd.Timestamp(r["effective_date"]),
                   "code": r["stock_code"], "act": r["action"], "etf": r["etf"]})
    return ev


def build_trades(events, cal, side, entry, exit_, stop):
    """回傳 trades：每筆 {code, d_in, d_out, path(日報酬序列, index 為日期)}；進場日報酬依 entry 口徑。"""
    trades, drop = [], defaultdict(int)
    cal_idx = {d: i for i, d in enumerate(cal)}
    for e in events:
        if side != "BOTH" and e["act"] != side:
            continue
        d = daily(e["code"])
        if d.empty:
            drop["無價格"] += 1
            continue
        a = [t for t in cal if t >= e["ann"]]
        if not a:
            drop["公告日超出資料"] += 1
            continue
        t_ann = a[0] if a[0] == e["ann"] else None
        nxt = [t for t in cal if t > e["ann"]]
        effs = [t for t in cal if t >= e["eff"]]
        if not nxt or not effs:
            drop["日期超出資料"] += 1
            continue
        t_eff = effs[0]
        ie = cal_idx[t_eff]
        exit_map = {"eff-1": ie - 1, "eff0": ie, "eff+5": ie + 5, "eff+10": ie + 10, "eff+20": ie + 20}
        io = exit_map[exit_]
        if entry == "ann_close":
            if t_ann is None:
                drop["公告日非交易日"] += 1
                continue
            t_in, buy_px_col = t_ann, "close"
        else:
            t_in, buy_px_col = nxt[0], ("open" if entry == "next_open" else "close")
        ii = cal_idx[t_in]
        if io >= len(cal):
            drop["出場日超出資料"] += 1
            continue
        if io <= ii or (io == ii and buy_px_col == "close"):
            drop["出場不晚於進場"] += 1
            continue
        if t_in not in d.index:
            drop["進場日無價"] += 1
            continue
        r_in = d.loc[t_in]
        if pinned(r_in, up=True):
            drop["鎖漲停買不到"] += 1
            continue
        px_in = float(r_in[buy_px_col])
        rets, dates, cum = [], [], 1.0
        # 進場日：開盤買→當日報酬＝收盤/開盤；收盤買→當日 0
        if buy_px_col == "open":
            r0 = float(r_in["close"]) / px_in - 1
            rets.append(r0); dates.append(t_in); cum *= 1 + r0
        j = ii + 1
        stopped = False
        while j < len(cal):
            t = cal[j]
            if t in d.index:
                rr = float(d.loc[t, "ret"])
                rets.append(rr); dates.append(t); cum *= 1 + rr
                done = j >= io or (stop is not None and cum - 1 <= -stop)
                if done:
                    if pinned(d.loc[t], up=False):
                        j += 1
                        continue  # 鎖跌停賣不掉，順延
                    stopped = j < io
                    break
            j += 1
        if not dates:
            drop["持有期無價"] += 1
            continue
        trades.append({"code": e["code"], "act": e["act"], "eff": e["eff"], "d_in": t_in,
                       "d_out": dates[-1], "rets": pd.Series(rets, index=dates), "gross": cum - 1,
                       "stopped": stopped})
    return trades, dict(drop)


def portfolio(trades, cal, L):
    by_day = defaultdict(list)
    entry_day = defaultdict(int)
    for k, t in enumerate(trades):
        for dt, r in t["rets"].items():
            by_day[dt].append(r)
        entry_day[t["rets"].index[0]] += 1
    eq, curve = 1.0, []
    for dt in cal:
        rs = by_day.get(dt)
        if rs:
            n = len(rs)
            r = float(np.mean(rs)) - COST * entry_day.get(dt, 0) / n
            r = L * r - (L - 1) * FIN_RATE / 252
        else:
            r = 0.0
        eq *= 1 + r
        curve.append(eq)
    s = pd.Series(curve, index=cal)
    return s


def stats(s: pd.Series, trades):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    ann = s.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 and s.iloc[-1] > 0 else -1.0
    mdd = float((s / s.cummax() - 1).min())
    dr = s.pct_change().dropna()
    sh = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    net = [t["gross"] - COST for t in trades]
    return {"ann": ann, "mdd": mdd, "sharpe": sh, "calmar": ann / abs(mdd) if mdd < 0 else None,
            "n_trades": len(trades), "win": float(np.mean([x > 0 for x in net])) if net else None,
            "mean_trade_net": float(np.mean(net)) if net else None,
            "exposure_days": int((s.pct_change().fillna(0) != 0).sum())}


def main() -> int:
    events = load_events()
    bench = daily("0050")
    cal = [t for t in bench.index if t >= pd.Timestamp("2022-05-01")]
    print(f"事件（去重後）{len(events)} 筆，ADD {sum(e['act']=='ADD' for e in events)}／DEL {sum(e['act']=='DEL' for e in events)}；"
          f"日曆 {cal[0].date()}～{cal[-1].date()}，成本 {COST:.4%}")
    grid = list(itertools.product(["ADD", "DEL", "BOTH"], ["next_open", "next_close", "ann_close"],
                                  ["eff-1", "eff0", "eff+5", "eff+10", "eff+20"], [None, 0.10], [1.0, 1.5, 2.0, 3.0]))
    res, tcache = [], {}
    for side, entry, ex, stop, L in grid:
        k = (side, entry, ex, stop)
        if k not in tcache:
            tcache[k] = build_trades(events, cal, side, entry, ex, stop)
        trades, drop = tcache[k]
        if not trades:
            continue
        s = portfolio(trades, cal, L)
        st = stats(s, trades)
        st2025 = stats(s[s.index >= pd.Timestamp("2025-01-01")] / s[s.index < pd.Timestamp("2025-01-01")].iloc[-1],
                       [t for t in trades if t["d_in"] >= pd.Timestamp("2025-01-01")])
        res.append({"side": side, "entry": entry, "exit": ex, "stop": stop, "L": L, **st,
                    "ann_2025on": st2025["ann"], "mdd_2025on": st2025["mdd"], "n_2025on": st2025["n_trades"],
                    "lookahead_risk": entry == "ann_close", "drops": drop,
                    "survival": "VIOLATES_SURVIVAL" if st["mdd"] < -0.5 else "OK"})
    b = bench.loc[cal, "ret"].fillna(0)
    bc = (1 + b).cumprod()
    bst = stats(bc, [])
    df = pd.DataFrame(res)
    ok = df[(~df.lookahead_risk) & (df.survival == "OK") & (df.n_trades >= 30)]
    best = ok.sort_values("calmar", ascending=False).head(10)
    best_ann = ok.sort_values("ann", ascending=False).head(5)
    out = {"generated_by": "research/reaudit_batch18_etf_rebal.py", "network_requests": 0,
           "cost_round_trip": COST, "n_events": len(events), "calendar": [str(cal[0].date()), str(cal[-1].date())],
           "bench_0050": bst, "n_cells": len(df), "top_calmar": best.to_dict("records"),
           "top_ann": best_ann.to_dict("records"),
           "ref_lookahead_best": df[df.lookahead_risk].sort_values("calmar", ascending=False).head(3).to_dict("records"),
           "all": df.drop(columns=["drops"]).to_dict("records")}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pd.set_option("display.width", 220)
    cols = ["side", "entry", "exit", "stop", "L", "ann", "mdd", "sharpe", "calmar", "n_trades", "win",
            "mean_trade_net", "exposure_days", "ann_2025on", "mdd_2025on", "n_2025on"]
    print("0050 同期：", {k: round(v, 4) if isinstance(v, float) else v for k, v in bst.items()})
    print(best[cols].to_string())
    print(best_ann[cols].to_string())
    print("drops 範例：", tcache[("ADD", "next_open", "eff-1", None)][1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
