# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之九：#64／#151 f_us_low_vol（美股低波動）的樣本內最優化（描述性，非判定）。

原版：十分位多空（含放空腿，借券成本未接真實資料→放空腿硬規則：數字屬資料缺陷、不得採信），
     價格走 FinMind `USStockPrice`（台灣資料商）。
本版：
- 價格改走美股原生來源 yfinance（CLAUDE.md 七節），一次批次 `download(248 檔＋SPY, 2010-01-01～2024-12-31)`，
  結果存本機 `research/data/reaudit_us_prices.pkl`，之後零請求。auto_adjust=True（還原股息與分割）。
- 宇宙：#151 同一份 `data/us_stratified_universe_sample.csv`（usable==True，248 檔，當下名冊分層抽樣）。
  **存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 這份宇宙更是「今天還在」的名冊，偏樂觀。
- 只做多頭半邊（買波動最低的 N 檔、等權），沒有放空腿。
- 訊號：第 t 日收盤以前 w 日日報酬標準差（需 w 日完整資料），t+1 日收盤成交（報酬從 t+2 起算）。
- 成本〔自行裁量〕：每單位換手 0.10% 滑價＋佣金（單邊），美股無證交稅、無漲跌停。
- 槓桿：每日再平衡合成 L×r −(L−1)×(美國 3 月國庫券 DTB3＋1.5%)/252〔自行裁量，接近券商融資利率〕；
  3× 超過 Reg T 初始 2× 上限，只當參考。權益跌到 0 停在 0。
- 止損：淨值自持倉高點回落 s 全數退現金（現金收 DTB3），21 個交易日後才重新進場（同 batch1）。
- holdout：資料截到 2024-12-31，未讀 2025 以後。
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

END = "2024-12-31"
START_DL = "2010-01-01"
SIM_START = "2011-01-03"
CACHE = HERE / "data" / "reaudit_us_prices.pkl"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_us_lowvol.json"
UNIVERSE_CSV = HERE / "data" / "us_stratified_universe_sample.csv"
COST = 0.0010
SPREAD = 0.015
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21


def load_prices() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    import yfinance as yf
    u = pd.read_csv(UNIVERSE_CSV)
    ids = u[u["usable"] == True]["stock_id"].astype(str).tolist()  # noqa: E712
    tick = sorted(set(t.replace(".", "-") for t in ids)) + ["SPY"]
    # 一次批次請求（yfinance 未公布上限，同 build_us_screener 用量級別）；end 為不含，設 2025-01-01 取到 2024-12-31
    df = yf.download(tick, start=START_DL, end="2025-01-01", auto_adjust=True, progress=False, threads=True)
    px = df["Close"].copy()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px[px.index <= END]
    px.to_pickle(CACHE)
    return px


def main():
    px = load_prices()
    assert px.index.max() <= pd.Timestamp(END)
    spy = px["SPY"]
    stocks = px.drop(columns=["SPY"]).dropna(axis=1, how="all")
    print(f"價格：{stocks.shape[1]} 檔有資料，{px.index.min().date()}～{px.index.max().date()}")
    R = stocks.pct_change(fill_method=None)
    dates = R.index
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    rf_ann = LB.load_dtb3_annual(pd.Series(dates))
    rf = rf_ann / 252.0
    borrow = (rf_ann + SPREAD) / 252.0
    sim_mask = dates >= SIM_START
    i0 = int(np.argmax(sim_mask))
    Rv = R.to_numpy()
    n = len(dates)
    yrs = (dates[-1] - dates[i0]).days / 365.25

    vol_cache = {}

    def vols(w):
        if w not in vol_cache:
            vol_cache[w] = R.rolling(w, min_periods=w).std().to_numpy()
        return vol_cache[w]

    base_cache = {}

    def base_returns(w, N, reb):
        """1× 無止損的多頭組合日報酬（已扣換手成本）與每日換手。"""
        key = (w, N, reb)
        if key in base_cache:
            return base_cache[key]
        V = vols(w)
        ret = np.zeros(n)
        wts = np.zeros(Rv.shape[1])
        holdings_log = []
        pending = None
        for i in range(i0, n):
            r = np.nan_to_num(Rv[i], nan=0.0)
            # 已持有部位今天的報酬（缺價當天以 0 計，下市股本宇宙無，見但書）
            day = float(wts @ r)
            # 權重漂移
            if wts.sum() > 0:
                g = wts * (1 + r)
                wts = g / (1 + day) if (1 + day) > 0 else g
            cost = 0.0
            if pending is not None:  # 前一日收盤決定、今日收盤成交
                cost = float(np.abs(pending - wts).sum()) * COST
                wts = pending
                pending = None
            ret[i] = day - cost
            if (i - i0) % reb == 0:
                v = V[i]
                ok = ~np.isnan(v) & ~np.isnan(Rv[i])
                idx = np.where(ok)[0]
                if len(idx) >= N:
                    pick = idx[np.argsort(v[idx])[:N]]
                    tgt = np.zeros_like(wts)
                    tgt[pick] = 1.0 / N
                    pending = tgt
                    holdings_log.append(set(pick.tolist()))
        base_cache[key] = (ret, holdings_log)
        return base_cache[key]

    def overlay(base, L, stop):
        out = np.zeros(n)
        eq, peak, cool = 1.0, 1.0, 0
        trades, in_pos, entry = [], False, 1.0
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
            now_in = e > 0
            if now_in and not in_pos:
                entry = eq
            eq = max(eq * (1 + ret), 0.0)
            if in_pos and not now_in:
                trades.append((entry, eq))
            in_pos = now_in
            out[i] = max(ret, -1.0)
            peak = max(peak, eq) if in_pos else eq
            if stop is not None and in_pos and eq < peak * (1 - stop):
                cool, peak = COOLDOWN, eq
        if in_pos:
            trades.append((entry, eq))
        o = out[i0:]
        curve = np.cumprod(1 + o)
        cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
        mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
        sd = o.std(ddof=1)
        return out, {"cagr": float(cagr), "mdd": mdd, "sharpe": float(o.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
                     "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
                     "violates_survival": bool(mdd < -0.5)}, trades

    def stock_trades(hlog, base):
        """個股層級：每次換股被賣出的持股算一筆；勝率另以「組合在該持有期是否賺錢」近似不可得，改報換股期勝率。"""
        return sum(len(a - b) for a, b in zip(hlog[:-1], hlog[1:])) + (len(hlog[-1]) if hlog else 0)

    rows, best = [], None
    for w, N, reb, L, st in itertools.product((20, 60, 120, 250), (10, 25, 50), (21, 63), LEVS, STOPS):
        base, hlog = base_returns(w, N, reb)
        out, met, _ = overlay(base, L, st)
        # 勝率＝換股期（reb 日）組合報酬>0 的比例（個股逐筆損益未追蹤，照實揭露）
        o = out[i0:]
        per = [np.prod(1 + o[k:k + reb]) - 1 for k in range(0, len(o), reb)]
        met["win_rate"] = float(np.mean([p > 0 for p in per]))
        met["trades"] = int(stock_trades(hlog, base))
        p = {"vol_window": w, "N": N, "rebalance_days": reb, "L": L, "stop": st}
        rows.append({**p, **met})
        ok = not met["violates_survival"]
        key = (ok, met["calmar"] if ok else -met["mdd"])
        if best is None or key > best[0]:
            best = (key, p, met, out)
    top = max((x for x in rows if not x["violates_survival"]), key=lambda x: x["cagr"], default=None)

    spy_r = spy.pct_change(fill_method=None).fillna(0).to_numpy()
    sr = spy_r[i0:]
    sc = np.cumprod(1 + sr)
    s_cagr = sc[-1] ** (1 / yrs) - 1
    s_mdd = float((sc / np.maximum.accumulate(sc) - 1).min())
    bench = {"cagr": float(s_cagr), "mdd": s_mdd, "sharpe": float(sr.mean() / sr.std(ddof=1) * np.sqrt(252)),
             "calmar": float(s_cagr / abs(s_mdd))}
    # 等權全宇宙對照
    ew = np.nanmean(Rv[i0:], axis=1)
    ew = np.nan_to_num(ew)
    ec = np.cumprod(1 + ew)
    e_cagr = ec[-1] ** (1 / yrs) - 1
    e_mdd = float((ec / np.maximum.accumulate(ec) - 1).min())

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    d = dates[i0:]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(d, np.cumprod(1 + best[3][i0:]), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(d, sc, color="#9aa0a6", lw=1.2, label="SPY 持有（含息）")
    ax.set_yscale("log")
    ax.set_title("F15 #64／#151 美股低波動（只做多，樣本內最優化，2011～2024，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    cd = HERE / "data" / "reaudit_curves"
    cd.mkdir(parents=True, exist_ok=True)
    fig.savefig(cd / "batch2_F15.png")
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": END,
           "data_start": str(d[0].date()), "benchmark_spy": bench,
           "benchmark_equal_weight_universe": {"cagr": float(e_cagr), "mdd": e_mdd},
           "n_stocks_with_prices": int(stocks.shape[1]),
           "families": [{"id": "F15", "title": "#64／#151 f_us_low_vol 美股低波動（只做多）", "source_trials": [64, 151],
                         "n_grid": len(rows), "best_by_calmar": {**best[1], **best[2]}, "best_by_cagr_within_mdd50": top,
                         "n_violates": sum(x["violates_survival"] for x in rows),
                         "curve_png": "research/data/reaudit_curves/batch2_F15.png"}]}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SPY", bench)
    print("等權宇宙", e_cagr, e_mdd)
    print("最佳", best[1], best[2])
    print("MDD≤50% 年化最高", top)


if __name__ == "__main__":
    main()
