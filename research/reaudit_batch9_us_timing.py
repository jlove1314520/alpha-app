# -*- coding: utf-8 -*-
"""先.一五五-3 第 9 批之二：美股時點類 3 族樣本內最優化（紙上優化軌，描述性，零請求）。

- var1018_v7_us_unemployment：ALFRED UNRATE 首次公布值年增（`research/data/raw/ALFRED_UNRATE_initial_release.json`），
  首次公布日下一個交易日起可用（同 V7）；risk-off 時 S&P 曝險降到 h。
- var1018_v2_turn_of_month：月底最後 k 個交易日～下月前 m 個交易日持有 S&P，其餘現金。交易日曆事先可知、不算偷看。
- HQ#66 us_tax_loss_selling：12 月第 d 個交易日收盤，挑 248 檔美股中當年至今報酬最差 N 檔，次一交易日收盤買、持有 H 日。
指數：`research/data/raw_yf/INDEX_SP500TR__1990-01-01__2024-12-31.parquet`（S&P 500 含息總報酬指數）；個股＝`reaudit_us_prices.pkl`。
**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（稅損族受影響最大：買跌最多的，宇宙只剩活下來的。）
曝險 t 收盤決定、t+1 報酬生效；成本 0.10%／單位曝險變動；槓桿借款 DTB3＋1.5%、現金收 DTB3；3× 超過 Reg T 只當參考；
止損：淨值自高點回落 s 退現金 21 日。期間到 2024-12-31（本機資料只到這裡）。
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
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch9_timing.json"
COST = 0.0010
SPREAD = 0.015
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21


def simulate(r, expo, rf, borrow, L, stop, i0):
    """r：標的日報酬；expo：t 日生效的曝險（0～1，已位移）；回傳日報酬序列（i0 起）。"""
    n = len(r)
    out = np.zeros(n)
    eq, peak, cool, prev = 1.0, 1.0, 0, 0.0
    for i in range(i0, n):
        e = L * expo[i]
        if cool > 0:
            cool -= 1
            e = 0.0
        cost = abs(e - prev) * COST
        prev = e
        if eq <= 0:
            ret = 0.0
        else:
            ret = e * r[i] - max(e - 1.0, 0.0) * borrow[i] + max(1.0 - e, 0.0) * rf[i] - cost
        eq = max(eq * (1 + ret), 0.0)
        out[i] = max(ret, -1.0)
        peak = max(peak, eq) if e > 0 else eq
        if stop is not None and e > 0 and eq < peak * (1 - stop):
            cool, peak = COOLDOWN, eq
    return out[i0:]


def stats(o, dates):
    yrs = (dates[-1] - dates[0]).days / 365.25
    c = np.cumprod(1 + o)
    cagr = c[-1] ** (1 / yrs) - 1 if c[-1] > 0 else -1.0
    mdd = float((c / np.maximum.accumulate(c) - 1).min())
    sd = o.std(ddof=1)
    return {"cagr": float(cagr), "mdd": mdd, "sharpe": float(o.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"), "violates_survival": bool(mdd < -0.5)}


def pick_best(rows):
    ok = [x for x in rows if not x["violates_survival"]]
    best = max(ok, key=lambda x: x["calmar"]) if ok else min(rows, key=lambda x: -x["mdd"])
    one = [x for x in rows if x["L"] == 1.0]
    return best, max(one, key=lambda x: x["calmar"])


def n_switches(expo):
    return int((np.diff((expo > 0).astype(int)) == 1).sum())


def main():
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    tr = pd.read_parquet(D / "raw_yf" / "INDEX_SP500TR__1990-01-01__2024-12-31.parquet")[["date", "close"]]
    tr["date"] = pd.to_datetime(tr["date"])
    tr = tr.sort_values("date").drop_duplicates("date").set_index("date")["close"]
    dates = tr.index
    r = tr.pct_change().fillna(0.0).to_numpy()
    rf_ann = LB.load_dtb3_annual(pd.Series(dates)).to_numpy() if hasattr(LB.load_dtb3_annual(pd.Series(dates)), "to_numpy") else np.asarray(LB.load_dtb3_annual(pd.Series(dates)))
    rf, borrow = rf_ann / 252.0, (rf_ann + SPREAD) / 252.0
    results = {}

    # ---- 失業率 ----
    obs = json.loads((D / "raw" / "ALFRED_UNRATE_initial_release.json").read_text(encoding="utf-8"))["observations"]
    u = pd.DataFrame(obs)
    u = u[u["value"] != "."].copy()
    u["month"] = pd.to_datetime(u["date"])
    u["released"] = pd.to_datetime(u["realtime_start"])
    u["value"] = u["value"].astype(float)
    u = u.sort_values("month").drop_duplicates("month").set_index("month")
    u["yoy"] = u["value"] - u["value"].shift(12)
    u["d3"] = u["value"] - u["value"].shift(3)
    u = u.dropna(subset=["yoy", "d3"])
    ser = pd.Series(dates)
    avail = []
    for m, row in u.iterrows():
        nxt = ser[ser > row["released"]]
        if len(nxt):
            avail.append((nxt.iloc[0], row["yoy"], row["d3"], row["value"]))
    a = pd.DataFrame(avail, columns=["date", "yoy", "d3", "lvl"]).sort_values("date").drop_duplicates("date", keep="last")
    sig = pd.merge_asof(pd.DataFrame({"date": dates}), a, on="date", direction="backward")
    # 「上市日下一交易日起可用」：用當日收盤決定、次日報酬生效 → 再位移 1
    i0 = int(np.argmax(dates >= pd.Timestamp("1991-01-02")))
    d_u = dates[i0:]
    rows = []
    lvl = sig["lvl"].to_numpy()
    lvl_min12 = pd.Series(lvl).rolling(252, min_periods=200).min().to_numpy()  # Sahm 風格：比過去一年低點
    rules = {}
    for th in (0.0, 0.3, 0.5, 1.0):
        rules[("yoy>", th)] = sig["yoy"].to_numpy() > th
    for th in (0.0, 0.2, 0.3):
        rules[("d3>", th)] = sig["d3"].to_numpy() > th
    for th in (0.3, 0.5):
        rules[("lvl-min12>", th)] = (lvl - lvl_min12) > th
    for (rk, th), off in rules.items():
        for h in (0.0, 0.5):
            ex = np.where(off, h, 1.0)
            ex = np.r_[1.0, ex[:-1]]
            for L, st in itertools.product(LEVS, STOPS):
                o = simulate(r, ex, rf, borrow, L, st, i0)
                rows.append({"rule": rk, "threshold": th, "riskoff_exposure": h, "L": L, "stop": st,
                             **stats(o, d_u), "riskoff_entries": n_switches((ex[i0:] < 1).astype(float))})
    best, b1 = pick_best(rows)
    results["var1018_v7_us_unemployment"] = {"n_grid": len(rows), "period": [str(d_u[0].date()), str(d_u[-1].date())],
                                             "best_by_calmar": best, "best_1x_by_calmar": b1}

    # ---- 月底月初 ----
    month = dates.to_period("M")
    dfm = pd.DataFrame({"m": month})
    pos_in_m = dfm.groupby("m").cumcount().to_numpy()
    cnt = dfm.groupby("m")["m"].transform("size").to_numpy()
    from_end = cnt - 1 - pos_in_m  # 0＝當月最後一個交易日
    rows = []
    for k, mm in itertools.product((1, 2, 3, 4), (1, 2, 3, 4, 5)):
        # 持有「報酬日」：當月最後 k-1..0（持有區間始於第 -k 日收盤 → 報酬日為最後 k-1 日起）＋次月前 mm 日
        hold_ret_day = (from_end <= k - 2) | (pos_in_m < mm)
        ex = hold_ret_day.astype(float)
        for L, st in itertools.product(LEVS, STOPS):
            o = simulate(r, ex, rf, borrow, L, st, i0)
            rows.append({"last_k_days_close_entry": k, "first_m_days": mm, "L": L, "stop": st, **stats(o, d_u),
                         "entries": n_switches(ex[i0:])})
    best, b1 = pick_best(rows)
    results["var1018_v2_turn_of_month"] = {"n_grid": len(rows), "period": [str(d_u[0].date()), str(d_u[-1].date())],
                                           "best_by_calmar": best, "best_1x_by_calmar": b1,
                                           "note": "k＝第 −k 個交易日收盤進場（k=1：月底最後一日收盤進）"}

    # ---- 稅損賣壓 ----
    px = pd.read_pickle(D / "reaudit_us_prices.pkl").drop(columns=["SPY"]).dropna(axis=1, how="all")
    pd_ = px.index
    R = pd.DataFrame({c: px[c].dropna().pct_change() for c in px.columns}).reindex(pd_).fillna(0.0).to_numpy()
    rf2 = np.asarray(LB.load_dtb3_annual(pd.Series(pd_))) / 252.0
    bor2 = rf2 + SPREAD / 252.0
    j0 = int(np.argmax(pd_ >= pd.Timestamp("2011-01-03")))
    d_t = pd_[j0:]
    pm = pd.DataFrame({"m": pd_.to_period("M")})
    pos = pm.groupby("m").cumcount().to_numpy()
    rows = []
    pxv = px.to_numpy()
    for dd, N, H in itertools.product((5, 10, 15), (10, 25), (10, 21, 42)):
        base = np.zeros(len(pd_))
        expo = np.zeros(len(pd_))
        events = 0
        for i in range(j0, len(pd_)):
            if pd_[i].month == 12 and pos[i] == dd - 1:
                y0 = np.where(pd_.year == pd_[i].year)[0][0] - 1
                ytd = pxv[i] / pxv[y0] - 1
                ok = ~np.isnan(ytd)
                idx = np.where(ok)[0]
                if len(idx) < N:
                    continue
                pick = idx[np.argsort(ytd[idx])[:N]]
                events += 1
                w = np.full(N, 1.0 / N)
                for t in range(i + 2, min(i + 2 + H, len(pd_))):  # i+1 收盤買 → 報酬自 i+2
                    day = float(w @ R[t, pick])
                    w = w * (1 + R[t, pick]) / (1 + day) if 1 + day > 0 else w
                    base[t] = day
                    expo[t] = 1.0
        for L, st in itertools.product(LEVS, STOPS):
            # base 已是持有部位報酬；以 expo 當曝險、r=base
            o = simulate(base, expo, rf2, bor2, L, st, j0)
            rows.append({"dec_trading_day": dd, "N": N, "hold_days": H, "L": L, "stop": st, **stats(o, d_t),
                         "events": events, "trades": events * N})
    best, b1 = pick_best(rows)
    results["HQ#66_us_tax_loss_selling"] = {"n_grid": len(rows), "period": [str(d_t[0].date()), str(d_t[-1].date())],
                                            "best_by_calmar": best, "best_1x_by_calmar": b1,
                                            "caveat": "每年只 1 次事件、其餘時間現金；Calmar 因長期空手偏高"}
    bh = stats(simulate(r, np.ones(len(r)), rf, borrow, 1.0, None, i0), d_u)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "benchmark_sp500tr_1991_2024": bh,
           "caveat": "存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。", "families": results}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("S&P500TR 1×", bh)
    for f, v in results.items():
        print(f, v["n_grid"], "\n  最佳", v["best_by_calmar"], "\n  1×", v["best_1x_by_calmar"])


if __name__ == "__main__":
    main()
