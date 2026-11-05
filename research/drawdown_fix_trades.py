# -*- coding: utf-8 -*-
"""先.一五二-1b ①② F12 Weinstein 個股層回撤歸因＋引擎新格（個股停損 10%、產業上限）。樣本內描述性，不是判定。

① 從引擎重跑 F12 最優格（MA150、閘門關、前 20 檔、不設個股停損、21 日換股），留下 trades，
   用 trades 重建每日持股（股數），以 adj_close 日變動算每檔每日損益；在帳戶曲線（原版 L=2、帳戶停損 10%）
   最深 5 段回撤裡，列：前 3 檔拖累（佔段起點 1× 權益比例）、產業集中（虧損最多的產業與佔比）、
   跳空（開盤 vs 前收 ≤ −5% 那幾天的損失佔比）、跌停賣不掉（引擎 trades note／賣單延後）、換股太慢（段內單檔跌 >20% 仍持有）。
② 新格（引擎只呼叫、不改）：個股停損 10%（引擎第三層硬停損，觸發隔日開盤成交＝跳空照實吃）、
   產業上限每產業最多 2 檔／3 檔（在 signal_fn 內挑分數前 20 檔時限制，非引擎修改）；
   每格再照 drawdown_fix 同一套：原版帳戶停損／不停損 × L' 掃到年化 ≥ 原版，比 MDD。
宇宙同 REAUDIT F12（`reaudit_ssu_loaded.pkl` 抽樣，2015～2024），holdout 未讀，零外部請求。
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_ARGV = sys.argv[1:]  # drawdown_fix 匯入時會改寫 sys.argv，先存
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drawdown_fix as D  # noqa: E402
import reaudit_optimized_batch2_weinstein as W  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from factor_ic import START_DATE  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation import holdout  # noqa: E402

OUT = D.OUT_DIR / "trades_F12.json"
CELLS = {  # key: (個股停損, 每產業上限, 是否截到前 20 名)
    # 注意：引擎換股日會賣掉「不在 signal_fn 回傳名單內」的持股（engine.py rebalance_dropped），
    # 所以「截到前 20 名」本身就會強迫換股；ind2／ind3 混了這個效果，用 top20 對照、ind2n／ind3n（不截名次）分離。
    "base": (1.0, None, False),
    "stop10": (0.10, None, False),
    "ind2": (1.0, 2, True),
    "ind3": (1.0, 3, True),
    "top20": (1.0, None, True),
    "ind2n": (1.0, 2, False),
    "ind3n": (1.0, 3, False),
}
MA_N, TOP_N = 150, 20


def industry_map():
    c = json.loads((HERE.parent / "data" / "company_info.json").read_text(encoding="utf-8"))["companies"]
    return {k: (v.get("industry") or "未分類") for k, v in c.items()}


def make_fn(prepped, cap, ind, trunc=True):
    look = {sid: dict(zip(d["date"].astype(str).str[:10], d["_score"])) for sid, d in prepped.items()}

    def fn(price_data, as_of, market_df):
        a = str(as_of)[:10]
        sc = {}
        for sid in price_data:
            v = look.get(sid, {}).get(a)
            if v is not None and v == v:
                sc[sid] = float(v)
        if cap is None and not trunc:
            return sc
        out, cnt = {}, {}
        for sid, v in sorted(sc.items(), key=lambda x: -x[1]):
            g = ind.get(str(sid), "未分類")
            if cap is not None and cnt.get(g, 0) >= cap:
                continue
            cnt[g] = cnt.get(g, 0) + 1
            out[sid] = v
            if trunc and len(out) >= TOP_N:
                break
        return out
    return fn


def attribution(trades, prepped, dates, eq1x, curve, ind):
    """每日持股 × adj_close 變動 → 每檔每日損益（元）；在帳戶最深 5 段回撤裡彙總。"""
    tr = trades.copy()
    tr["date"] = pd.to_datetime(tr["date"]).dt.normalize()
    tr["sgn"] = np.where(tr["side"] == "buy", 1, np.where(tr["side"].isin(["sell", "close"]), -1, 0))
    tr = tr[tr["sgn"] != 0]
    idx = pd.DatetimeIndex(dates)
    pnl, gap = {}, {}
    for sid, g in tr.groupby("stock_id"):
        d = prepped.get(sid)
        if d is None:
            continue
        px = pd.Series(d["adj_close"].to_numpy(float), index=pd.to_datetime(d["date"]).dt.normalize()).reindex(idx).ffill()
        op = pd.Series(d["adj_open"].to_numpy(float) if "adj_open" in d else d["open"].to_numpy(float),
                       index=pd.to_datetime(d["date"]).dt.normalize()).reindex(idx)
        chg = (g["sgn"] * g["shares"]).groupby(g["date"]).sum().reindex(idx).fillna(0.0)
        # 成交在當日（開盤）→ 當日起持有；以前一日收盤持股算當日損益（近似：成交日當日損益以收盤價計）
        sh = chg.cumsum()
        dp = px.diff().fillna(0.0)
        pnl[sid] = (sh.shift(1).fillna(0.0) * dp).to_numpy()
        gp = (op / px.shift(1) - 1).to_numpy()
        gap[sid] = np.where(np.isfinite(gp) & (gp <= -0.05), (sh.shift(1).fillna(0.0) * (op - px.shift(1))).to_numpy(), 0.0)
    P = pd.DataFrame(pnl, index=idx).fillna(0.0)
    G = pd.DataFrame(gap, index=idx).fillna(0.0)
    notes = tr["note"].astype(str) if "note" in tr else pd.Series([], dtype=str)
    eps = D.episodes(curve, pd.Series(idx))
    out = []
    eq_abs = eq1x  # 1× 引擎權益（元）
    for e in eps:
        a, b = e["peak_i"], e["trough_i"]
        w = P.iloc[a + 1:b + 1]
        base = float(eq_abs[a])
        by = w.sum().sort_values()
        tot = float(by.sum())
        top3 = [{"sid": str(s), "name_ind": ind.get(str(s), "未分類"), "pnl_pct_of_equity": float(v / base)}
                for s, v in by.head(3).items()]
        byind = by.groupby(lambda s: ind.get(str(s), "未分類")).sum().sort_values()
        loss_total = float(by[by < 0].sum())
        gap_loss = float(G.iloc[a + 1:b + 1].sum().sum())
        held = w.columns[(w != 0).any()]
        # 換股太慢：段內任一檔持有期間累積跌 >20%（以段內損益 ÷ 段起點 1× 權益 ×20 檔近似單檔部位）
        slow = [str(s) for s in held if by.get(s, 0.0) / (base / TOP_N) < -0.20]
        d0, d1 = idx[a], idx[b]
        lim = tr[(tr["date"] >= d0) & (tr["date"] <= d1) & notes.reindex(tr.index).fillna("").str.contains("limit|跌停|lock", case=False)]
        out.append({"peak": str(d0.date()), "trough": str(d1.date()), "acct_depth": e["depth"],
                    "engine_1x_ret": float(eq_abs[b] / eq_abs[a] - 1), "pnl_sum_pct": tot / base,
                    "top3": top3, "top3_share_of_loss": float(by.head(3).sum() / loss_total) if loss_total < 0 else None,
                    "worst_industry": str(byind.index[0]) if len(byind) else None,
                    "worst_industry_share_of_loss": float(byind.iloc[0] / loss_total) if loss_total < 0 and len(byind) else None,
                    "gap_loss_share": float(gap_loss / loss_total) if loss_total < 0 else None,
                    "n_held": int(len(held)), "slow_exit_n": len(slow), "slow_exit": slow[:8],
                    "limit_locked_trades": int(len(lim))})
    return out


def scan(r, dates, stop0, cagr0, L0):
    rf = D.LB.load_tw_rf_daily(dates)
    rows = []
    for stop in ({None, stop0}):
        best = None
        for L in D.L_GRID:
            cv, _ = D.overlay(r, rf, np.full(len(r), L), stop)
            cg, md, sh = D.stats(cv, dates)
            if cg >= cagr0 - 1e-9:
                best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh}
                break
        cv1, _ = D.overlay(r, rf, np.full(len(r), L0), stop)
        cg1, md1, sh1 = D.stats(cv1, dates)
        rows.append({"stop": stop, "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1}, "same_cagr": best})
    return rows


def main():
    budget = float(os.environ.get("DDFIX_BUDGET_SEC", "1500"))
    deadline = time.time() + budget
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    F = D.load_family("F12")
    stop0 = None if F["stop"] is None or F["stop"] != F["stop"] else float(F["stop"])
    ind = industry_map()
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="ddfix F12 market")
    market_df = prepare_market_data(market_raw)
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"ddfix F12 {sid}")
    prepped = W.prep(data, MA_N)
    for key, (pstop, cap, trunc) in CELLS.items():
        if key in res and "error" not in res[key]:
            continue
        if time.time() > deadline:
            W.prog(f"時間到，{key} 以後留下一輪")
            break
        t0 = time.time()
        cfg = BacktestConfig(start_date=W.START, end_date=W.END, max_positions=TOP_N, rebalance_every_n_days=W.REBAL,
                             stop_loss_pct=pstop, book_name="ddfix_weinstein")
        bt = run_backtest(make_fn(prepped, cap, ind, trunc), prepped, market_df, cfg)
        holdout.assert_no_holdout_leakage(bt.trades, date_col="date", context="ddfix F12 trades")
        ec = bt.equity_curve
        dates = pd.to_datetime(ec["date"]).reset_index(drop=True)
        eq = ec["equity"].to_numpy(float)
        r = np.zeros(len(eq))
        r[1:] = eq[1:] / eq[:-1] - 1.0
        rf = D.LB.load_tw_rf_daily(dates)
        cur, _ = D.overlay(r, rf, np.full(len(r), F["L"]), stop0)
        cg, md, sh = D.stats(cur, dates)
        item = {"pstop": pstop, "ind_cap": cap, "truncate_top20": trunc, "secs": round(time.time() - t0),
                "n_trades": int(len(bt.trades)), "at_orig": {"L": F["L"], "stop": stop0, "cagr": cg, "mdd": md, "sharpe": sh},
                "scan": scan(r, dates, stop0, F["cagr0"], F["L"]),
                "attribution": attribution(bt.trades, prepped, dates, eq, cur, ind)}
        if key == "base":
            item["reproduced"] = abs(cg - F["cagr0"]) < 0.002 and abs(md - F["mdd0"]) < 0.002
            bt.trades.to_csv(D.OUT_DIR / "trades_F12_base.csv", index=False)
        res[key] = item
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        W.prog(f"{key} 完成（{item['secs']}s）：原版 L／停損下 年化 {cg:+.2%}／MDD {md:.2%}")


def main_f14():
    """F14 ML 價量選股 HGB 最優格（H=63、閘門關、前 30 檔、個股停損 15%）只做 ① 歸因（分數用 REAUDIT 快取，零重訓）。"""
    import reaudit_optimized_batch2_ml as M
    out = D.OUT_DIR / "trades_F14.json"
    F = D.load_family("F14")
    stop0 = None if F["stop"] is None or F["stop"] != F["stop"] else float(F["stop"])
    ind = industry_map()
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="ddfix F14 market")
    market_df = prepare_market_data(market_raw)
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"ddfix F14 {sid}")
    scores = pickle.loads(M.SCORES.read_bytes())
    lk = {}
    df = scores[63]
    for dt, sid, sc in zip(df["date"], df["stock_id"], df["score"]):
        lk.setdefault(dt, {})[sid] = float(sc)
    M.R.FACTOR = "f_low_vol"
    prepped = M.R.prep(data, 0)
    cfg = BacktestConfig(start_date=M.START, end_date=M.END, max_positions=30, rebalance_every_n_days=63,
                         stop_loss_pct=0.15, book_name="ddfix_ml")
    t0 = time.time()
    bt = run_backtest(M.make_fn(lk, False, set()), prepped, market_df, cfg)
    holdout.assert_no_holdout_leakage(bt.trades, date_col="date", context="ddfix F14 trades")
    ec = bt.equity_curve
    dates = pd.to_datetime(ec["date"]).reset_index(drop=True)
    eq = ec["equity"].to_numpy(float)
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    rf = D.LB.load_tw_rf_daily(dates)
    cur, _ = D.overlay(r, rf, np.full(len(r), F["L"]), stop0)
    cg, md, sh = D.stats(cur, dates)
    global TOP_N
    TOP_N = 30
    item = {"secs": round(time.time() - t0), "n_trades": int(len(bt.trades)),
            "reproduced": abs(cg - F["cagr0"]) < 0.002 and abs(md - F["mdd0"]) < 0.002,
            "at_orig": {"L": F["L"], "stop": stop0, "cagr": cg, "mdd": md, "sharpe": sh},
            "attribution": attribution(bt.trades, prepped, dates, eq, cur, ind)}
    out.write_text(json.dumps({"base": item}, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    W.prog(f"F14 完成（{item['secs']}s）：年化 {cg:+.2%}／MDD {md:.2%}，重建 {'對上' if item['reproduced'] else '對不上'}")


if __name__ == "__main__":
    main_f14() if "F14" in _ARGV else main()
