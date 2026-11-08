# -*- coding: utf-8 -*-
"""先.一五五-3 第 9 批：美股價量因子 2 族（f_us_momentum_12m、f_us_reversal_1m）樣本內最優化（紙上優化軌，描述性）。

做法完全沿用 `reaudit_optimized_batch2_us_lowvol.py`（F15）：
- 價格：本機 `research/data/reaudit_us_prices.pkl`（yfinance auto_adjust，248 檔＋SPY，2010～2024-12-31），**零請求**。
  **存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 這份宇宙是「今天還在」的分層抽樣名冊，偏樂觀。
- 只做多（原 #… 十分位多空的放空腿不做；放空腿借券成本未接真實資料）。
- 訊號只用第 t 日收盤以前的資料，t+1 收盤成交（報酬 t+2 起算）。
- 成本 0.10%／單位換手；槓桿 L×r −(L−1)×(DTB3＋1.5%)/252；3× 超過 Reg T 2× 只當參考。
- 止損：淨值自高點回落 s 全數退現金，21 日後重進；大盤閘門＝SPY 收盤 < 200 日均線時空手（t 判定、t+1 生效）。
- 動能：過去 lb 日報酬、跳過最近 skip 日；反轉：過去 lb 日報酬最低者。
- 期間 2011-01-03～2024-12-31（本機價格只到 2024 底；延長要再一次 yfinance 批次，另案）。
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

CACHE = HERE / "data" / "reaudit_us_prices.pkl"
OUT_JSON = HERE / "data" / "reaudit_batch3_batch9.json"
SIM_START = "2011-01-03"
COST = 0.0010
SPREAD = 0.015
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21


def main():
    px = pd.read_pickle(CACHE)
    spy = px["SPY"]
    stocks = px.drop(columns=["SPY"]).dropna(axis=1, how="all")
    # 逐檔在自己有價日上算報酬（第 7 批教訓：全樣本聯集日期的零星缺日不可讓 pct_change 跨缺口）
    R = pd.DataFrame({c: stocks[c].dropna().pct_change() for c in stocks.columns}).reindex(stocks.index)
    logp = np.log(stocks.ffill())
    dates = R.index
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    rf_ann = LB.load_dtb3_annual(pd.Series(dates))
    rf = rf_ann / 252.0
    borrow = (rf_ann + SPREAD) / 252.0
    i0 = int(np.argmax(dates >= SIM_START))
    Rv = R.to_numpy()
    n = len(dates)
    yrs = (dates[-1] - dates[i0]).days / 365.25
    spy_ma = spy.rolling(200, min_periods=200).mean()
    gate_on = (spy > spy_ma).to_numpy()  # t 收盤判定

    # 有效價格（當日有收盤）才可被選
    has_px = stocks.notna().to_numpy()

    def score_mom(lb, skip):
        s = (logp.shift(skip) - logp.shift(lb)).to_numpy().copy()
        # 需要 lb 日前有價
        s[~stocks.shift(lb).notna().to_numpy()] = np.nan
        return s

    def score_rev(lb):
        s = -(logp - logp.shift(lb)).to_numpy().copy()
        s[~stocks.shift(lb).notna().to_numpy()] = np.nan
        return s

    base_cache = {}

    def base_returns(key, S, N, reb, gate):
        if key in base_cache:
            return base_cache[key]
        ret = np.zeros(n)
        wts = np.zeros(Rv.shape[1])
        hlog, pending = [], None
        for i in range(i0, n):
            r = np.nan_to_num(Rv[i], nan=0.0)
            day = float(wts @ r)
            if wts.sum() > 0:
                g = wts * (1 + r)
                wts = g / (1 + day) if (1 + day) > 0 else g
            cost = 0.0
            if pending is not None:
                cost = float(np.abs(pending - wts).sum()) * COST
                wts = pending
                pending = None
            ret[i] = day - cost
            reb_day = (i - i0) % reb == 0
            if gate and not gate_on[i] and wts.sum() > 0:
                pending = np.zeros_like(wts)  # 閘門關：明日收盤全數出場
                continue
            if reb_day or (gate and gate_on[i] and wts.sum() == 0 and pending is None):
                if gate and not gate_on[i]:
                    continue
                v = S[i]
                ok = ~np.isnan(v) & has_px[i]
                idx = np.where(ok)[0]
                if len(idx) >= N:
                    pick = idx[np.argsort(-v[idx])[:N]]
                    tgt = np.zeros_like(wts)
                    tgt[pick] = 1.0 / N
                    pending = tgt
                    hlog.append(set(pick.tolist()))
        base_cache[key] = (ret, hlog)
        return base_cache[key]

    def overlay(base, L, stop):
        out = np.zeros(n)
        eq, peak, cool, in_pos = 1.0, 1.0, 0, False
        for i in range(i0, n):
            e = L
            if cool > 0:
                cool -= 1
                e = 0.0
            if eq <= 0:
                ret = 0.0
            elif e > 0:
                ret = L * base[i] - (L - 1.0) * borrow[i]
            else:
                ret = rf[i]
            in_pos = e > 0
            eq = max(eq * (1 + ret), 0.0)
            out[i] = max(ret, -1.0)
            peak = max(peak, eq) if in_pos else eq
            if stop is not None and in_pos and eq < peak * (1 - stop):
                cool, peak = COOLDOWN, eq
        return out

    def metrics(out, reb):
        o = out[i0:]
        curve = np.cumprod(1 + o)
        cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
        mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
        sd = o.std(ddof=1)
        per = [np.prod(1 + o[k:k + reb]) - 1 for k in range(0, len(o), reb)]
        return {"cagr": float(cagr), "mdd": mdd, "sharpe": float(o.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
                "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
                "violates_survival": bool(mdd < -0.5), "win_rate_period": float(np.mean([p > 0 for p in per]))}

    fams = {
        "f_us_momentum_12m": [({"lookback": lb, "skip": sk}, ("mom", lb, sk)) for lb in (126, 252) for sk in (0, 21)],
        "f_us_reversal_1m": [({"lookback": lb}, ("rev", lb)) for lb in (5, 21, 63)],
    }
    rebs = {"f_us_momentum_12m": (21, 63), "f_us_reversal_1m": (5, 21)}
    score_cache = {}
    results = {}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    spy_r = np.nan_to_num(spy.pct_change(fill_method=None).to_numpy())
    sc = np.cumprod(1 + spy_r[i0:])
    bench = {"cagr": float(sc[-1] ** (1 / yrs) - 1), "mdd": float((sc / np.maximum.accumulate(sc) - 1).min())}
    ew = np.nan_to_num(np.nanmean(Rv[i0:], axis=1))
    ec = np.cumprod(1 + ew)
    bench_ew = {"cagr": float(ec[-1] ** (1 / yrs) - 1), "mdd": float((ec / np.maximum.accumulate(ec) - 1).min())}
    for fam, specs in fams.items():
        rows, best = [], None
        for p, sk in specs:
            if sk not in score_cache:
                score_cache[sk] = score_mom(sk[1], sk[2]) if sk[0] == "mom" else score_rev(sk[1])
            S = score_cache[sk]
            for N, reb, gate in itertools.product((10, 25, 50), rebs[fam], (False, True)):
                base, hlog = base_returns((sk, N, reb, gate), S, N, reb, gate)
                trades = sum(len(a - b) for a, b in zip(hlog[:-1], hlog[1:])) + (len(hlog[-1]) if hlog else 0)
                for L, st in itertools.product(LEVS, STOPS):
                    out = overlay(base, L, st)
                    met = metrics(out, reb)
                    met["trades"] = int(trades)
                    q = {**p, "N": N, "rebalance_days": reb, "spy_200d_gate": gate, "L": L, "stop": st}
                    rows.append({**q, **met})
                    ok = not met["violates_survival"]
                    key = (ok, met["calmar"] if ok else -met["mdd"])
                    if best is None or key > best[0]:
                        best = (key, q, met, out)
        top = max((x for x in rows if not x["violates_survival"]), key=lambda x: x["cagr"], default=None)
        d = dates[i0:]
        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
        ax.plot(d, np.cumprod(1 + best[3][i0:]), color="#2a6fdb", lw=1.6, label="最優化版本")
        ax.plot(d, sc, color="#9aa0a6", lw=1.2, label="SPY 持有（含息）")
        ax.set_yscale("log")
        ax.set_title(f"第 9 批 {fam}（只做多，樣本內最優化，2011～2024，非投資建議）", fontsize=10)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        fig.tight_layout()
        cd = HERE / "data" / "reaudit_curves"
        cd.mkdir(parents=True, exist_ok=True)
        png = cd / f"batch3_b9_{fam}.png"
        fig.savefig(png)
        plt.close(fig)
        results[fam] = {"n_grid": len(rows), "best_by_calmar": {**best[1], **best[2]},
                        "best_by_cagr_within_mdd50": top,
                        "best_1x_by_calmar": max((x for x in rows if x["L"] == 1.0), key=lambda x: x["calmar"]),
                        "n_violates": sum(x["violates_survival"] for x in rows),
                        "curve_png": f"research/data/reaudit_curves/{png.name}"}
        print(fam, len(rows), "最佳", best[1], {k: round(v, 4) if isinstance(v, float) else v for k, v in best[2].items()})
        print("  MDD≤50% 年化最高", top)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "period": [str(dates[i0].date()), str(dates[-1].date())],
           "benchmark_spy": bench, "benchmark_equal_weight_universe_1x_no_cost": bench_ew, "n_stocks": int(stocks.shape[1]),
           "caveat": "存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。",
           "families": results}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SPY", bench, "等權宇宙", bench_ew)
    for f, r in results.items():
        print(f, "1×最佳", r["best_1x_by_calmar"])


if __name__ == "__main__":
    main()
