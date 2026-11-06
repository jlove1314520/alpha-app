# -*- coding: utf-8 -*-
"""先.一五五-2 墓園重審補跑 2025 起：個股引擎家族（目前 F12 Weinstein；Cowork 收件匣 039 已定案）。

性質：紙上優化軌描述性，不寫 TRIALS_LEDGER；非投資建議。零新外部請求。

資料接法〔自行裁量〕：
- 2024-12-31 以前：沿用第二批同一份 `research/data/reaudit_ssu_loaded.pkl`（#133 抽樣宇宙 236 檔）。
- 2025 起：讀本機 FinMind 快取 `research/data/raw/TaiwanStockPrice__{代號}__2025-01-01__latest.parquet`（原始價），
  還原權息用「漲跌」欄：當日報酬＝close／(close−spread)−1（TWSE 漲跌是對除權息參考價算的；0050 2025-06-18
  分割日 47.57−0.41＝47.16＝官方參考價，已核對），從 2024 年最後一筆 adj_close 往後連乘。
- 2024 底仍掛牌但本機沒有 2025 起價格的標的（45 檔，多為 ETF／債券 ETF），從 CUTOFF_MISSING 起不再給分數，
  讓它們在 2024-12 的換股就被賣出（不會卡在沒有價格的持股上）；這使「2024 底前」數字與第二批原表略有差異，照實列出。
- TAIEX：`TaiwanStockPrice__TAIEX__2015-01-01__latest.parquet`。
- 引擎 `research/backtest/engine.py` 只呼叫不改；組合層槓桿／止損沿用 F8 的 overlay()（融資 6.5%/年）。

- F13（ROE 穩定度）：2024 底以前沿用原 pkl 的 f_quality_roe_stability；2025 起用 reaudit_ext2025_roe_factor.py
  以本機財報快取照原公式重算（PIT＝法定期限），零新請求〔自行裁量：重算值在 4 檔 2024 下半年與原值有小差，
  所以 2024 底前不覆蓋，保持與原表可比〕。

用法：python research/reaudit_ext2025_engine.py F12｜F13
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

import reaudit_optimized_batch2_ssu as S  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402

RAW = HERE / "data" / "raw"
SEG_START = "2025-01-01"
CUTOFF_MISSING = "2024-11-15"
OUT = HERE / "data" / "reaudit_ext2025_engine.json"


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def load_extended():
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    ext, missing, jumps = {}, [], []
    for sid, d in data.items():
        d = d.sort_values("date").reset_index(drop=True)
        d["date"] = pd.to_datetime(d["date"])
        f = RAW / f"TaiwanStockPrice__{sid}__2025-01-01__latest.parquet"
        if not f.exists():
            if str(d["date"].max())[:10] >= "2024-12-20":
                missing.append(sid)
            ext[sid] = d
            continue
        x = pd.read_parquet(f)
        if x.empty or "date" not in x.columns:  # 空快取（FinMind 回 0 列）＝當作沒有 2025 起價格
            if str(d["date"].max())[:10] >= "2024-12-20":
                missing.append(sid)
            ext[sid] = d
            continue
        x["date"] = pd.to_datetime(x["date"])
        x = x[(x["date"] > d["date"].max()) & (x["close"].astype(float) > 0)].sort_values("date").reset_index(drop=True)
        if x.empty:
            ext[sid] = d
            continue
        c = x["close"].astype(float).to_numpy()
        ref = c - x["spread"].astype(float).to_numpy()
        r = np.where(ref > 0, c / ref - 1.0, 0.0)
        if (np.abs(r) > 0.105).any():
            jumps.append((sid, int((np.abs(r) > 0.105).sum())))
        adj = float(d["adj_close"].iloc[-1]) * np.cumprod(1.0 + r)
        k = adj / c
        new = pd.DataFrame({
            "date": x["date"], "stock_id": sid,
            "open": x["open"].astype(float), "high": x["max"].astype(float), "low": x["min"].astype(float),
            "close": c, "max": x["max"].astype(float), "min": x["min"].astype(float),
            "volume": x["Trading_Volume"].astype(float), "Trading_Volume": x["Trading_Volume"].astype(float),
            "Trading_money": x["Trading_money"].astype(float), "source": "finmind_cache_2025",
            "adj_close": adj, "adj_open": x["open"].astype(float).to_numpy() * k,
            "adj_high": x["max"].astype(float).to_numpy() * k, "adj_low": x["min"].astype(float).to_numpy() * k,
        })
        ext[sid] = pd.concat([d, new], ignore_index=True)
    m1 = pd.read_parquet(RAW / "TaiwanStockPrice__TAIEX__2015-01-01__latest.parquet")
    m0 = pd.read_parquet(RAW / "TaiwanStockPrice__TAIEX__2000-01-01__2024-12-31.parquet")
    mk = pd.concat([m0, m1[pd.to_datetime(m1["date"]) > "2024-12-31"]], ignore_index=True)
    mk["date"] = pd.to_datetime(mk["date"])
    mk = mk.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    end = min(mk["date"].max(), max(v["date"].max() for v in ext.values()))
    for sid in ext:  # 引擎與第二批原本都用字串日期，保持一致
        ext[sid]["date"] = ext[sid]["date"].dt.strftime("%Y-%m-%d")
    mk["date"] = mk["date"].dt.strftime("%Y-%m-%d")
    prog(f"宇宙 {len(ext)} 檔；2025 起缺價（2024 底仍掛牌）{len(missing)} 檔；還原後單日 >10.5% 的檔 {len(jumps)}；終點 {end.date()}")
    return ext, mk, missing, jumps, end


# ---------- 家族設定 ----------
def fam_cfg(fam):
    if fam == "F12":
        import reaudit_optimized_batch2_weinstein as W
        prev_p, name = "reaudit_optimized_batch2_weinstein.json", "Weinstein 第二階段"
        fk = lambda pb: f"{pb['ma']}_{int(pb['market_gate'])}_{pb['top_n']}_{1.0 if pb['pos_stop'] is None else pb['pos_stop']}"
        rebal = lambda c: W.REBAL
        prep = lambda ext, c, miss, mk: _cut(W.prep(ext, c[0]), miss)
        mkfn = lambda p, c, gd: (p, W.make_fn(p, bool(c[1]), gd))
        prep_key = lambda c: c[0]
    elif fam == "F13":
        import reaudit_optimized_batch2_roe as W
        import reaudit_ext2025_roe_factor as RF
        prev_p, name = "reaudit_optimized_batch2_roe.json", "ROE 穩定度（只做多頭半邊）"
        fk = lambda pb: f"{pb['rebalance_days']}_{int(pb['market_gate'])}_{pb['top_n']}_{1.0 if pb['pos_stop'] is None else pb['pos_stop']}"
        rebal = lambda c: c[0]
        prep_key = lambda c: "p"

        mkfn = lambda p, c, gd: (p, W.make_fn(p, bool(c[1]), gd))

        def prep(ext, c, miss, mk):
            for sid, d in ext.items():
                v = RF.attach(d, sid)
                old = d["f_quality_roe_stability"].to_numpy(float)
                post = (d["date"] >= SEG_START).to_numpy()
                d["f_quality_roe_stability"] = np.where(post, v, old)
            return _cut(W.prep(ext, 0), miss)
    elif fam == "F14":
        import reaudit_optimized_batch2_ml as W
        import reaudit_optimized_batch2_roe as R
        prev_p, name = "reaudit_optimized_batch2_ml.json", "ML 價量選股（HGB 逐年重訓）"
        fk = lambda pb: f"{pb['horizon_eq_rebalance_days']}_{int(pb['market_gate'])}_{pb['top_n']}_{1.0 if pb['pos_stop'] is None else pb['pos_stop']}"
        W.GRID_A = W.HS
        rebal = lambda c: c[0]
        prep_key = lambda c: "p"
        prep = lambda ext, c, miss, mk: _f14_prep(W, R, ext, miss, mk)
        mkfn = lambda p, c, gd: (p[0], W.make_fn(p[1][c[0]], bool(c[1]), gd))
    else:
        raise SystemExit(f"未知家族 {fam}")
    grid = list(itertools.product(getattr(W, "GRID_A", getattr(W, "MAS", None)), W.GATES, W.TOPNS, W.PSTOPS))
    return dict(W=W, prev_p=prev_p, name=name, fk=fk, rebal=rebal, prep=prep, prep_key=prep_key, grid=grid, mkfn=mkfn,
                key=lambda c: f"{c[0]}_{c[1]}_{c[2]}_{c[3]}")


def _cut(p, miss):
    for sid in miss:
        dd = p[sid]
        dd.loc[dd["date"] >= CUTOFF_MISSING, "_score"] = np.nan
    return p


def _f14_prep(W, R, ext, miss, mk):
    """F14：延長 10 個價量特徵（核對過 2024 底前與原欄一致）→ 2015～2024 沿用原分數檔，2025、2026 測試年
    照原規則（只用標籤到期日 < Y-01-01 的樣本、2011 起擴張視窗）重訓 HGB 預測。"""
    import reaudit_ext2025_ml_feats as MF
    from sklearn.ensemble import HistGradientBoostingRegressor
    mc = mk.set_index("date")["close"]
    frames = []
    for sid, d in ext.items():
        d = d.sort_values("date").reset_index(drop=True)
        f = MF.compute(d, mc)
        f["date"] = pd.to_datetime(d["date"])
        f["stock_id"] = sid
        px = d["adj_close"].astype(float)
        for h in W.HS:
            f[f"fwd{h}"] = px.shift(-h) / px - 1
            f[f"lab_end{h}"] = f["date"].shift(-h)
        frames.append(f)
    P = pd.concat(frames, ignore_index=True)
    first_days = set(P.groupby(P["date"].dt.to_period("M"))["date"].min())
    month_first = P["date"].isin(first_days)
    old = pickle.loads(W.SCORES.read_bytes())
    looks = {}
    for h in W.HS:
        S_ = P[month_first & P[f"fwd{h}"].notna()].copy()
        S_["label"] = S_.groupby("date")[f"fwd{h}"].rank(pct=True)
        res = [old[h]]
        for y in (2025, 2026):
            tr = S_[(S_[f"lab_end{h}"] < pd.Timestamp(f"{y}-01-01")) & (S_["date"] >= pd.Timestamp("2011-01-01"))]
            m = HistGradientBoostingRegressor(random_state=20261021).fit(tr[MF.FEATURES], tr["label"])
            te = P[(P["date"] >= pd.Timestamp(f"{y}-01-01")) & (P["date"] <= pd.Timestamp(f"{y}-12-31"))]
            res.append(pd.DataFrame({"date": te["date"].dt.strftime("%Y-%m-%d"), "stock_id": te["stock_id"],
                                     "score": m.predict(te[MF.FEATURES])}))
            prog(f"F14 H={h} 測試年 {y}：訓練 {len(tr)} 列、預測 {len(te)} 列")
        df = pd.concat(res, ignore_index=True)
        lk = {}
        for dt, sid, sc in zip(df["date"], df["stock_id"], df["score"]):
            if sid in miss and dt >= CUTOFF_MISSING:
                continue
            if sc == sc:
                lk.setdefault(dt, {})[sid] = float(sc)
        looks[h] = lk
    R.FACTOR = "f_low_vol"  # prep() 只用來補 ma150
    return R.prep(ext, 0), looks


def run_family(fam, deadline):
    F = fam_cfg(fam)
    W, grid, key = F["W"], F["grid"], F["key"]
    prev = json.loads((HERE / "data" / F["prev_p"]).read_text(encoding="utf-8"))
    pb = prev["families"][0]["best_by_calmar"]
    fixed_key = F["fk"](pb)
    cache_p = HERE / "data" / f"reaudit_ext2025_{fam}_cells.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    todo = [c for c in grid if key(c) not in cache]
    todo.sort(key=lambda c: key(c) != fixed_key)  # 原最優組先跑
    if todo:
        ext, mk, missing, jumps, end = load_extended()
        market_df = prepare_market_data(mk)
        gate_dates = set(market_df.loc[market_df["gate"] == True, "date"].astype(str).str[:10])  # noqa: E712
        miss = set(missing)
        prepped = {}
        for c in todo:
            if time.time() > deadline:
                prog("時間到，存斷點")
                return cache, False, fixed_key, pb
            n, g, top_n, pstop = c
            pk = F["prep_key"](c)
            if pk not in prepped:
                prepped[pk] = F["prep"](ext, c, miss, mk)
            t0 = time.time()
            cfg = BacktestConfig(start_date=W.START, end_date=str(end.date()), max_positions=top_n,
                                 rebalance_every_n_days=F["rebal"](c), stop_loss_pct=pstop, book_name=f"reaudit_ext2025_{fam.lower()}")
            edata, fn = F["mkfn"](prepped[pk], c, gate_dates)
            res = run_backtest(fn, edata, market_df, cfg)
            ec, tr = res.equity_curve, res.trades
            sells = tr[tr["side"].isin(["sell", "close"])] if not tr.empty else tr
            held_missing_2025 = sorted(set(tr.loc[(pd.to_datetime(tr["date"]) >= SEG_START) & tr["stock_id"].isin(miss), "stock_id"])) if not tr.empty else []
            n_buy_2025 = int(((pd.to_datetime(tr["date"]) >= SEG_START) & (tr["side"] == "buy")).sum()) if not tr.empty else 0
            cache[key(c)] = {"dates": [str(x)[:10] for x in ec["date"]], "equity": [float(x) for x in ec["equity"]],
                             "n_round_trips": int(len(sells)), "n_buy_2025": n_buy_2025,
                             "win_rate": float((sells["realized_pnl"] > 0).mean()) if len(sells) else None,
                             "missing_traded_2025": held_missing_2025, "n_missing": len(miss), "jumps": jumps}
            cache_p.write_text(json.dumps(cache), encoding="utf-8")
            prog(f"{fam} {key(c)} 完成（{time.time()-t0:.0f}s）")
    return cache, True, fixed_key, pb


def seg(curve, dates, a, b=None):
    m = (dates >= a) if b is None else ((dates >= a) & (dates <= b))
    m = m.to_numpy()
    cv = curve[m] / curve[m][0]
    return S.stats(cv, dates[m].reset_index(drop=True))


def summarize(fam, cache, fixed_key, pb, done):
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    LB.END = "2099-12-31"  # 只在本行程延長央行定存讀取範圍（rf_monthly.json 本機已到 2026-10），不改原檔
    rows, fixed = [], None
    for k, c in cache.items():
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float); eq = eq / eq[0]
        rf = LB.load_tw_rf_daily(dates)
        for L, stop in itertools.product(S.LEVS, S.STOPS):
            curve, _ = S.overlay(eq, rf, L, stop)
            cagr, mdd, sh = S.stats(curve, dates)
            row = {"key": k, "L": L, "stop": stop, "cagr": cagr, "mdd": mdd, "sharpe": sh,
                   "calmar": cagr / abs(mdd) if mdd < 0 else None, "trades": c["n_round_trips"]}
            rows.append((row, curve, dates))
            if k == fixed_key and L == pb["L"] and ((stop is None and pb["stop"] is None) or stop == pb["stop"]):
                fixed = (row, curve, dates)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "family": fam, "grid_done": done,
           "n_cells_engine": len(cache), "fixed_params": pb}
    if fixed:
        r, cv, d = fixed
        out["fixed_full"] = {k: r[k] for k in ("cagr", "mdd", "sharpe", "trades")}
        out["fixed_pre2025"] = dict(zip(("cagr", "mdd", "sharpe"), seg(cv, d, "1900-01-01", "2024-12-31")))
        out["fixed_seg2025"] = dict(zip(("cagr", "mdd", "sharpe"), seg(cv, d, SEG_START)))
        out["end"] = str(d.iloc[-1].date())
        c = cache[fixed_key]
        out["missing_note"] = {"n_missing": c["n_missing"], "traded_2025": c["missing_traded_2025"], "jumps": c["jumps"]}
    if done:
        ok = [x for x in rows if x[0]["mdd"] >= -0.5]
        b = max(ok, key=lambda x: x[0]["calmar"] or -9)
        out["reopt"] = b[0]
        out["reopt_seg2025"] = dict(zip(("cagr", "mdd", "sharpe"), seg(b[1], b[2], SEG_START)))
        out["n_grid"] = len(rows)
        out["n_violates"] = sum(x[0]["mdd"] < -0.5 for x in rows)
    _plot(fam, fixed, b if done else None)
    out_p = HERE / "data" / f"reaudit_ext2025_engine_{fam}.json"
    out_p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    prog(f"寫入 {out_p}")
    print(json.dumps(out, ensure_ascii=False, default=float)[:1500])


def _plot(fam, fixed, best):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    if fixed:
        ax.plot(fixed[2], fixed[1], color="#2a6fdb", lw=1.6, label="原最優組（2024 底前挑、不重調）")
    if best:
        ax.plot(best[2], best[1], color="#e8710a", lw=1.1, ls="--", label="全期重新優化")
    m = pd.read_parquet(RAW / "TaiwanStockPrice__TAIEX__2015-01-01__latest.parquet")
    m["date"] = pd.to_datetime(m["date"]); m = m[m["date"] >= "2015-01-01"].sort_values("date")
    ax.plot(m["date"], m["close"] / m["close"].iloc[0], color="#9aa0a6", lw=1.1, label="加權指數（價格，不含息）")
    ax.axvline(pd.Timestamp(SEG_START), color="#5f6368", lw=0.8, ls=":")
    ax.set_yscale("log"); ax.grid(alpha=0.25); ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"{fam} {fam_cfg(fam)['name']}（延長到 2025 起，虛線右邊＝沒拿來調參的一段，非投資建議）", fontsize=9)
    fig.tight_layout()
    p = HERE / "data" / "reaudit_curves" / f"ext2025_{fam}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p); plt.close(fig)


def main():
    budget = float(os.environ.get("REAUDIT_BUDGET_SEC", "1200"))
    fam = sys.argv[1] if len(sys.argv) > 1 else "F12"
    cache, done, fk, pb = run_family(fam, time.time() + budget)
    if fk in cache:
        summarize(fam, cache, fk, pb, done)
    return 0 if done else 2


if __name__ == "__main__":
    sys.exit(main())
