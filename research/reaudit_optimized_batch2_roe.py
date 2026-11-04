# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之七：#16／#17 f_quality_roe_stability 家族的樣本內最優化（描述性，非判定）。

方針（Cowork 收件匣 039 已定案）：掃參數挑最好的一組，只當描述性總表，不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。
訊號：`f_quality_roe_stability`（`factor_ic.load_sample_with_factors()` 算好的欄，同 #16／#17；分數高＝ROE 穩定＝做多）。
     #16／#17 原版是十分位多空；**這裡只做多頭半邊**（放空腿借券成本未接真實資料，依 CLAUDE.md 放空腿硬規則不做），
     引擎挑分數最高的 N 檔等權；可選大盤閘門（加權指數 > 200 日均線才開新倉）。
宇宙〔自行裁量〕：沿用 F8／F9／F12 的 #133 抽樣 300 檔快取（`research/data/reaudit_ssu_loaded.pkl`），期間 2015-01～2024-12。
引擎：`research/backtest/engine.py`（只呼叫、不改）。引擎第一層出場讀 `ma150`，這裡照 Weinstein 原定義算 150 日均線（還原收盤）。
掃描（引擎層）：N ∈ {10,20,30}、換股 ∈ {21,63} 日、個股停損 ∈ {15%,不設}、大盤閘門 ∈ {開,關}＝24 格；
     組合層槓桿 L ∈ {1,1.5,2,3}×組合止損 ∈ {無,10%,20%,30%}（同 F8：融資 6.5%/年〔自行裁量〕，3× 只當參考）。
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import pickle
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

import reaudit_optimized_batch2_sector as S  # noqa: E402  （overlay()／stats() 同一套）
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from factor_ic import START_DATE  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation import holdout  # noqa: E402

START, END = "2015-01-01", "2024-12-31"
CACHE = HERE / "data" / "reaudit_optimized_batch2_roe_cells.json"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_roe.json"
MAS = (21, 63)  # 這個家族拿來當換股間隔
GATES = (1, 0)
TOPNS = (10, 20, 30)
PSTOPS = (0.15, 1.0)
REBAL = None
FACTOR = "f_quality_roe_stability"
RISE_LB, MOM_WIN = 10, 60
prog = S.prog


def prep(data, n_unused):
    out = {}
    for sid, df in data.items():
        d = df.sort_values("date").reset_index(drop=True).copy()
        px = d["adj_close"] if "adj_close" in d.columns else d["close"]
        d["ma150"] = px.rolling(150, min_periods=150).mean()  # 引擎第一層出場讀這欄
        d["_score"] = d[FACTOR].astype(float)
        out[sid] = d
    return out


def make_fn(prepped, gate_on, gate_dates):
    look = {sid: dict(zip(d["date"].astype(str).str[:10], d["_score"])) for sid, d in prepped.items()}

    def fn(price_data, as_of, market_df):
        a = str(as_of)[:10]
        if gate_on and a not in gate_dates:
            return {}
        sc = {}
        for sid in price_data:
            v = look.get(sid, {}).get(a)
            if v is not None and v == v:
                sc[sid] = float(v)
        return sc
    return fn


def run_engine_cells(deadline):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    grid = list(itertools.product(MAS, GATES, TOPNS, PSTOPS))
    key = lambda c: f"{c[0]}_{c[1]}_{c[2]}_{c[3]}"
    todo = [c for c in grid if key(c) not in cache]
    if not todo:
        return cache, True
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="reaudit roe market")
    market_df = prepare_market_data(market_raw)
    gate_dates = set(market_df.loc[market_df["gate"] == True, "date"].astype(str).str[:10])  # noqa: E712
    pk = HERE / "data" / "reaudit_ssu_loaded.pkl"
    data = pickle.loads(pk.read_bytes())
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"reaudit roe {sid}")
    prepped = {}
    prog(f"宇宙 {len(data)} 檔，待跑 {len(todo)}／{len(grid)} 格")
    for c in todo:
        n, g, top_n, pstop = c
        if time.time() > deadline:
            prog("時間到，存斷點")
            return cache, False
        if "p" not in prepped:
            prepped["p"] = prep(data, 0)
        t0 = time.time()
        cfg = BacktestConfig(start_date=START, end_date=END, max_positions=top_n, rebalance_every_n_days=n,
                             stop_loss_pct=pstop, book_name="reaudit_roe")
        res = run_backtest(make_fn(prepped["p"], bool(g), gate_dates), prepped["p"], market_df, cfg)
        holdout.assert_no_holdout_leakage(res.trades, date_col="date", context="reaudit roe trades")
        ec, tr = res.equity_curve, res.trades
        sells = tr[tr["side"].isin(["sell", "close"])] if not tr.empty else tr
        cache[key(c)] = {"dates": [str(x)[:10] for x in ec["date"]], "equity": [float(x) for x in ec["equity"]],
                         "n_round_trips": int(len(sells)),
                         "win_rate": float((sells["realized_pnl"] > 0).mean()) if len(sells) else None}
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        prog(f"{key(c)} 完成（{time.time()-t0:.0f}s）")
    return cache, True


def main():
    budget = float(os.environ.get("REAUDIT_BUDGET_SEC", "1200"))
    cache, done = run_engine_cells(time.time() + budget)
    n_grid = len(MAS) * len(GATES) * len(TOPNS) * len(PSTOPS)
    if not done:
        prog(f"引擎格未跑完：{len(cache)}／{n_grid}，下次接續")
        return 2
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    rows = []
    for key, c in cache.items():
        n, g, top_n, pstop = key.split("_")
        dates = pd.to_datetime(pd.Series(c["dates"]))
        assert dates.max() <= pd.Timestamp(END)
        eq = np.array(c["equity"], float)
        eq = eq / eq[0]
        rf = LB.load_tw_rf_daily(dates)
        for L, stop in itertools.product(S.LEVS, S.STOPS):
            curve, n_stop = S.overlay(eq, rf, L, stop)
            cagr, mdd, sh = S.stats(curve, dates)
            rows.append({"rebalance_days": int(n), "market_gate": bool(int(g)), "top_n": int(top_n), "pos_stop": float(pstop), "L": L, "stop": stop,
                         "cagr": cagr, "mdd": mdd, "sharpe": sh, "calmar": cagr / abs(mdd) if mdd < 0 else None,
                         "win_rate": c["win_rate"], "n_trades": c["n_round_trips"], "key": key})
    df = pd.DataFrame(rows)
    ok = df[df["mdd"] >= -0.50]

    def pack(b):
        st = b["stop"]
        st = None if st is None or st != st else float(st)
        return {"rebalance_days": int(b["rebalance_days"]), "market_gate": bool(b["market_gate"]), "top_n": int(b["top_n"]),
                "pos_stop": None if b["pos_stop"] >= 1.0 else float(b["pos_stop"]),
                "L": float(b["L"]), "stop": st, "cagr": float(b["cagr"]), "mdd": float(b["mdd"]), "sharpe": float(b["sharpe"]),
                "trades": int(b["n_trades"]), "win_rate": b["win_rate"], "calmar": float(b["calmar"]),
                "violates_survival": bool(b["mdd"] < -0.50)}
    best = ok.sort_values("calmar", ascending=False).iloc[0]
    best_ret = ok.sort_values("cagr", ascending=False).iloc[0]
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    m = market_raw[(market_raw["date"] >= START) & (market_raw["date"] <= END)].sort_values("date")
    mc = m["close"].to_numpy(float)
    bcagr, bmdd, bsh = S.stats(mc / mc[0], pd.to_datetime(m["date"]).reset_index(drop=True))
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_start": START, "data_end": END,
           "benchmark_taiex_price_index": {"cagr": bcagr, "mdd": bmdd, "sharpe": bsh},
           "families": [{"id": "F13", "title": "#16／#17 f_quality_roe_stability 最高 N 檔（台股個股，只做多頭半邊）",
                         "source_trials": [16, 17], "n_grid": int(len(df)),
                         "best_by_calmar": pack(best), "best_by_cagr_within_mdd50": pack(best_ret),
                         "n_violates": int((df["mdd"] < -0.50).sum()),
                         "curve_png": "research/data/reaudit_curves/batch2_F13.png"}],
           "notes": "樣本內最優化（描述性）；宇宙為抽樣 300 檔（同 F8／F9）；3× 超過台股融資上限只當參考；融資追繳以權益歸零近似；"
                    "交易次數＝個股賣出筆數、勝率＝賣出已實現損益>0 比例。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = cache[best["key"]]
    dates = pd.to_datetime(pd.Series(c["dates"]))
    eq = np.array(c["equity"], float); eq = eq / eq[0]
    st = best["stop"]
    curve, _ = S.overlay(eq, LB.load_tw_rf_daily(dates), best["L"], None if st is None or st != st else st)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(dates, curve, label="best (Calmar)", color="#2a6fdb")
    ax.plot(pd.to_datetime(m["date"]), mc / mc[0], label="TAIEX price index", color="#999999")
    ax.set_yscale("log"); ax.legend(); ax.set_title("F13 ROE stability long-only (in-sample optimized, 2015-2024)")
    fig.tight_layout()
    fig.savefig(HERE / "data" / "reaudit_curves" / "batch2_F13.png", dpi=110)
    prog(f"最佳 {pack(best)}")
    prog(f"MDD≤50% 年化最高 {pack(best_ret)}")
    prog(f"TAIEX 價格指數 {bcagr:+.1%}／{bmdd:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
