# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之三：#282（#73）產業金流加速度輪動家族的樣本內最優化（描述性，非判定）。

方針（Cowork 收件匣 039 已定案）：掃參數挑最好的一組，只當描述性總表，不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。
訊號：三大法人產業淨買賣（`data/sector_flow_daily_gate73.parquet`，同 #282）的加速度＝(MA快−MA慢)÷|流量| 120 日均值，
     換股日當天收盤以前的值（T86 盤後公布，引擎隔日開盤成交）；取加速度前 top_frac 的產業，產業內個股以產業加速度當分數，
     引擎挑前 N 檔等權。產業分類＝`data/company_info.json` 靜態快照（非 PIT，同 #282 照實揭露）。
宇宙〔自行裁量〕：沿用 F8 已載入的 #133 抽樣 300 檔（`research/data/reaudit_ssu_loaded.pkl`），期間 2015-01～2024-12；
     #282 原本用 yfinance 還原價、靜態成分股、缺 25.8%，改用引擎版才能照實處理下市與漲跌停，代價是產業內只剩抽樣到的個股。
引擎：`research/backtest/engine.py`（只呼叫、不改）——下一交易日開盤成交、漲跌停鎖住不成交、下市／缺價照引擎處理、成本照引擎。
掃描（引擎層）：加速度均線 (快,慢) ∈ {(5,20),(20,60)}、top_frac ∈ {0.2,0.3}、N ∈ {15,30}、換股間隔 ∈ {21,42} 交易日、
     個股停損 ∈ {15%,不設}＝32 格；組合層槓桿 L ∈ {1,1.5,2,3}×組合止損 ∈ {無,10%,20%,30%}（同 F8：融資 6.5%/年〔自行裁量〕，
     3× 超過台股融資上限只當參考，追繳以權益歸零近似偏樂觀）。
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import portfolio_backtest_v2 as pbv2  # noqa: E402
import sector_rotation_accel_gate73_sanity as SEC  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_with_factors, sample_universe_ids  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation import holdout  # noqa: E402

START, END = "2015-01-01", "2024-12-31"
CACHE = HERE / "data" / "reaudit_optimized_batch2_sector_cells.json"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_sector.json"
WINS = ((5, 20), (20, 60))
FRACS = (0.2, 0.3)
TOPNS = (15, 30)
REBALS = (21, 42)
PSTOPS = (0.15, 1.0)  # 1.0＝不設個股停損
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21
MARGIN_RATE = 0.065 / 252.0


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def accel(wide, fast, slow):
    a = wide.rolling(fast, min_periods=fast).mean() - wide.rolling(slow, min_periods=slow).mean()
    sc = wide.abs().rolling(SEC.SCALE_WINDOW, min_periods=SEC.SCALE_MIN).mean()
    return a / sc.where(sc > 0)


def make_fn(acc, sector_of, frac):
    idx = list(acc.index)

    def fn(price_data, as_of, market_df):
        d = str(as_of)[:10]
        j = int(np.searchsorted(idx, d, side="right")) - 1  # 當天（含）以前最後一筆 T86
        if j < 0:
            return {}
        row = acc.iloc[j].dropna()
        held = {sector_of[s] for s in price_data if s in sector_of}
        row = row[[c for c in row.index if c in held]]
        if len(row) < 5:
            return {}
        k = max(1, round(frac * len(row)))
        top = row.sort_values(ascending=False, kind="mergesort").iloc[:k]
        return {s: float(top[sector_of[s]]) for s in price_data if sector_of.get(s) in top.index}
    return fn


def run_engine_cells(deadline):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    grid = list(itertools.product(WINS, FRACS, TOPNS, REBALS, PSTOPS))
    key = lambda c: f"{c[0][0]}-{c[0][1]}_{c[1]}_{c[2]}_{c[3]}_{c[4]}"
    todo = [c for c in grid if key(c) not in cache]
    if not todo:
        return cache, True
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="reaudit ssu market")
    market_df = prepare_market_data(market_raw)
    import pickle
    pk = HERE / "data" / "reaudit_ssu_loaded.pkl"  # 載入 300 檔因子要 10 分鐘以上，存本機快取讓下一輪直接接續（不進 repo）
    if pk.exists():
        data = pickle.loads(pk.read_bytes())
    else:
        sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
        data = load_sample_with_factors(sample_ids, market_df)
        pk.write_bytes(pickle.dumps(data))
        prog("載入完成，已存 reaudit_ssu_loaded.pkl")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"reaudit ssu {sid}")
    wide = pd.read_parquet(SEC.ALL)
    wide = wide[wide.index <= END]
    comp = json.loads(SEC.COMPANY_INFO.read_text(encoding="utf-8"))["companies"]
    sector_of = {s: (comp.get(s) or {}).get("industry") for s in data}
    sector_of = {s: v for s, v in sector_of.items() if v in wide.columns}
    accs = {w: accel(wide, *w) for w in WINS}
    prog(f"宇宙 {len(data)} 檔（有產業 {len(sector_of)}），待跑 {len(todo)}／{len(grid)} 格")
    for c in todo:
        (fast, slow), frac, top_n, rebal, pstop = c
        if time.time() > deadline:
            prog("時間到，存斷點")
            return cache, False
        t0 = time.time()
        cfg = BacktestConfig(start_date=START, end_date=END, max_positions=top_n, rebalance_every_n_days=rebal,
                             stop_loss_pct=pstop, book_name="reaudit_sector")
        res = run_backtest(make_fn(accs[(fast, slow)], sector_of, frac), data, market_df, cfg)
        holdout.assert_no_holdout_leakage(res.trades, date_col="date", context="reaudit sector trades")
        ec = res.equity_curve
        tr = res.trades
        sells = tr[tr["side"].isin(["sell", "close"])] if not tr.empty else tr
        cache[key(c)] = {
            "dates": [str(x)[:10] for x in ec["date"]], "equity": [float(x) for x in ec["equity"]],
            "n_round_trips": int(len(sells)),
            "win_rate": float((sells["realized_pnl"] > 0).mean()) if len(sells) else None,
        }
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        prog(f"{key(c)} 完成（{time.time()-t0:.0f}s）")
    return cache, True


def overlay(eq, rf, L, stop):
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    out = np.zeros(len(eq))
    v, peak, cool, in_pos, n_stop = 1.0, 1.0, 0, True, 0
    for i in range(len(eq)):
        if i > 0:
            if in_pos:
                v *= 1.0 + L * r[i] - (L - 1.0) * MARGIN_RATE
            else:
                v *= 1.0 + rf[i]
            v = max(v, 0.0)
        if in_pos:
            peak = max(peak, v)
            if stop is not None and v < peak * (1 - stop):
                in_pos, cool, n_stop = False, COOLDOWN, n_stop + 1
        else:
            cool -= 1
            if cool <= 0:
                in_pos, peak = True, v
        out[i] = v
    return out, n_stop


def stats(curve, dates):
    yrs = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    dr = np.diff(curve) / np.where(curve[:-1] > 0, curve[:-1], np.nan)
    dr = dr[~np.isnan(dr)]
    sh = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    return cagr, mdd, sh


def main():
    budget = float(os.environ.get("REAUDIT_BUDGET_SEC", "1500"))
    cache, done = run_engine_cells(time.time() + budget)
    if not done:
        prog(f"引擎格未跑完：{len(cache)}／32，下次接續")
        return 2
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    rows = []
    for key, c in cache.items():
        win, frac, top_n, rebal, pstop = key.split("_")
        dates = pd.to_datetime(pd.Series(c["dates"]))
        assert dates.max() <= pd.Timestamp(END)
        eq = np.array(c["equity"], float)
        eq = eq / eq[0]
        rf = LB.load_tw_rf_daily(dates)
        for L, stop in itertools.product(LEVS, STOPS):
            curve, n_stop = overlay(eq, rf, L, stop)
            cagr, mdd, sh = stats(curve, dates)
            rows.append({"accel_ma": win, "top_frac": float(frac), "top_n": int(top_n), "rebalance_days": int(rebal), "pos_stop": float(pstop), "L": L, "stop": stop,
                         "cagr": cagr, "mdd": mdd, "sharpe": sh, "calmar": cagr / abs(mdd) if mdd < 0 else None,
                         "win_rate": c["win_rate"], "n_trades": c["n_round_trips"], "n_portfolio_stops": n_stop})
    df = pd.DataFrame(rows)
    ok = df[df["mdd"] >= -0.50]
    best = ok.sort_values("calmar", ascending=False).iloc[0].to_dict()
    best_ret = ok.sort_values("cagr", ascending=False).iloc[0].to_dict()
    # 對照：同期 TAIEX 報酬指數近似（大盤價格指數＋不含息，只當參考）
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    m = market_raw[(market_raw["date"] >= START) & (market_raw["date"] <= END)].sort_values("date")
    mc = m["close"].to_numpy(float)
    bcagr, bmdd, bsh = stats(mc / mc[0], pd.to_datetime(m["date"]).reset_index(drop=True))
    def pack(b):
        st = b["stop"]
        st = None if st is None or st != st else float(st)
        return {"accel_ma": b["accel_ma"], "top_frac": float(b["top_frac"]), "top_n": int(b["top_n"]), "rebalance_days": int(b["rebalance_days"]),
                "pos_stop": None if b["pos_stop"] >= 1.0 else float(b["pos_stop"]), "L": float(b["L"]), "stop": st,
                "cagr": float(b["cagr"]), "mdd": float(b["mdd"]), "sharpe": float(b["sharpe"]),
                "trades": int(b["n_trades"]), "win_rate": b["win_rate"], "calmar": float(b["calmar"]),
                "violates_survival": bool(b["mdd"] < -0.50)}
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_start": START, "data_end": END,
           "benchmark_taiex_price_index": {"cagr": bcagr, "mdd": bmdd, "sharpe": bsh},
           "families": [{"id": "F9", "title": "#282（#73）產業金流加速度輪動（台股個股，引擎版）",
                         "source_trials": [282], "n_grid": int(len(df)),
                         "best_by_calmar": pack(best), "best_by_cagr_within_mdd50": pack(best_ret),
                         "n_violates": int((df["mdd"] < -0.50).sum()),
                         "curve_png": "research/data/reaudit_curves/batch2_F9.png"}],
           "notes": "樣本內最優化（描述性）；產業分類為靜態快照非 PIT；宇宙為抽樣 300 檔；3× 超過台股融資上限只當參考；融資追繳以權益歸零近似；"
                    "交易次數＝個股賣出筆數、勝率＝賣出已實現損益>0 比例（組合層止損不另計）。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    # 曲線圖
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    k = f"{best['accel_ma']}_{best['top_frac']}_{int(best['top_n'])}_{int(best['rebalance_days'])}_{best['pos_stop']}"
    c = cache[k]
    dates = pd.to_datetime(pd.Series(c["dates"]))
    eq = np.array(c["equity"], float); eq = eq / eq[0]
    curve, _ = overlay(eq, LB.load_tw_rf_daily(dates), best["L"], best["stop"] if best["stop"] == best["stop"] else None)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(dates, curve, label="best (Calmar)", color="#2a6fdb")
    ax.plot(pd.to_datetime(m["date"]), mc / mc[0], label="TAIEX price index", color="#999999")
    ax.set_yscale("log"); ax.legend(); ax.set_title("F9 sector flow acceleration rotation (in-sample optimized, 2015-2024)")
    fig.tight_layout()
    png = HERE / "data" / "reaudit_curves" / "batch2_F9.png"
    fig.savefig(png, dpi=110)
    prog(f"最佳 {best}")
    prog(f"MDD≤50% 年化最高 {best_ret}")
    prog(f"TAIEX 價格指數 {bcagr:+.1%}／{bmdd:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
