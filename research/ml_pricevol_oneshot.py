# -*- coding: utf-8 -*-
"""先.一三三-2d（2026-10-23，DevQueue 20261023-230101）：台股個股 ML 價量版歷史單發（事前登記 #475）。

規則照 `docs/PREREG_ML_PRICEVOL_2006_2012_FINAL.md` 第 1～5 節＋修訂 R1＋修訂 R2（70／30），不改任何一條：
- 資料窗 2006-01-02～2012-12-31（還原權息，`adjust.adjustment_events()` 含官方補充事件）；2013 只讀第一個交易日開盤（期末出場）。
- 每月第一個交易日開盤調整、持有到下月第一個交易日開盤；測試年 2008～2012（5 折）；每年 1 月重訓一次，
  訓練樣本＝標籤在前一年 11 月 30 日以前已實現的月份（擴張視窗，自 2006 年第一個有特徵的月份起）。
- 模型 `HistGradientBoostingRegressor` 全預設、random_state=20261021；缺值交給模型；標籤＝當月持有期報酬橫斷面百分位。
- 特徵 10 個（定義同 `research/factors.py::prepare_factors()`），特徵日＝調整日前一個交易日收盤。
- 宇宙：調整日前一個交易日在市的上市＋上櫃普通股（含之後下市者）、前 20 日平均成交金額 ≥3,000 萬元。
- 組合（R2）：持股部位固定占淨值 70%、30% 現金不計息；部位內前 30 名等權、已持有者跌出前 90 名才賣、不足 30 檔由
  未持有最高分補滿；每月調整日拉回 70%。開盤漲停不買、跌停不賣（`costs.limit_status()`）；停牌不成交；下市以最後成交價出場。
- 價格（R1）：可核對日（上市、上櫃官方日檔皆 ok）只採官方日檔有列的價格列；沒有官方日檔的日子沿用 FinMind。
- 下市股缺資料（最後可得價到下市日 >20 天）：悲觀 −100%／中性最後可得價出場，兩者都過才 PASS。
- 成本 `validation.costs`，報 1×／2×／3×。
- 判準依序：①交易數 ≥100 →②天條一（含現金總淨值 MDD ≤50%，附 2008-05～11）→③第 8 關簡化版（扣 1× 年化 > 0050 含息年化、
  2×／3× 淨利 >0）→④隨機標籤控制組 100 次（每月橫斷面打亂標籤、整套重訓、同 70／30）> P95，照列 Bonferroni
  →⑤第 7 關「每兩個月調整」超額與月頻同號 →⑥逐年超額只排序。

[自行裁量]（寫進結果檔 discretion，總司令／Cowork 可推翻）：
1. 特徵公式逐字照 `factors.py::prepare_factors()`（同窗口常數），但不呼叫該函式：它會順帶抓三大法人（網路請求），
   本單發零請求；每檔在「自己的有效列」上滾動（同 factors.py 的列序滾動），大盤＝FinMind TAIEX 收盤（同 factor_ic.py）。
   特徵取「調整日前一個交易日（含）以前最後一個有效列」的值。
2. 「在市」＝調整日前一個交易日以前 20 個交易日內至少有 1 個有效列、且下市日（若有）晚於該日；成交金額無列記 0。
   候選＝4 碼非 0 開頭代號（同 V1 `candidates()`）：V1 候選 ∪ 官方基本資料上市／上櫃日 ≤2012-12-31 ∪ 2006～2012 下市
   ∪ 官方日檔 2006-12-26～2012-12-31 出現過的代號。全額交割股無時點名單，無法排除（照實揭露）。
3. 標籤：進場＝調整日還原開盤（缺就不進訓練樣本）；出場＝下個調整日還原開盤，缺則用該日以前最後有效收盤
   （下市股即最後成交價，訓練標籤一律用中性處理，悲觀／中性只影響組合帳）。至少 1 個特徵非缺值的列才進訓練。
4. 組合以淨值比例記帳（可分割股數）；每個目標檔目標市值＝調整日開盤淨值×70%÷30；先賣後買，現金不足按比例縮買。
   跌出宇宙（流動性不足／不在市）視同跌出前 90 名；漲停／無開盤而補不進的高分股跳過、往下一名補。
   賣不掉（跌停／停牌）的部位續抱，可能讓檔數 >30 或部位偏離 70%（次數揭露）。
5. 期末 2013 第一個交易日以開盤價全數出清（不判漲跌停：判斷需要當天高低收，PREREG 只允許讀開盤）；當天無開盤者用最後收盤。
6. 第 7 關「每兩個月調整」用同一批年度模型、在 1、3、5、7、9、11 月第一個交易日調整（相位從 2008-01 起）。
7. 第 8 關 0050 含息年化＝還原收盤 2007-12-31 → 2012-12-28（策略為 2008-01-02 開盤 → 2013-01-02 開盤，同為 5 年）；
   `evaluate_gate8()` 的被動基準表只有 2015～2024，不適用、不呼叫（同 #462／#468）。
8. 隨機標籤控制組：draw k 用 `np.random.default_rng(20261021 + k)`，每月訓練樣本內打亂標籤；模型 random_state 不變；
   比較量＝扣 1× 成本期末淨值（同一 0050 基準下等價於超額）；兩假設各比一次。
9. `costs.limit_status()` 寫死 ±10%（2015-06 前實為 ±7%，見 先.一三三-2c-限），照 PREREG 原樣使用、照實揭露。
10. 「交易數」＝新建倉次數＋全數出清次數（不含同檔加減碼）。

用法：
  python research/ml_pricevol_oneshot.py selftest       # 合成資料自測（不讀真資料報酬）
  python research/ml_pricevol_oneshot.py estimate       # 只建資料＋量 1 次 walk-forward 耗時（不算任何報酬、不寫結果檔）
  python research/ml_pricevol_oneshot.py run            # 只跑一次；結果檔已存在就拒跑；控制組每 10 次存斷點，可續跑
輸出：research/data/ml_pricevol_oneshot_result.json（git add -f 入庫）
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULT = HERE / "data" / "ml_pricevol_oneshot_result.json"
CKPT = HERE / "data" / "ml_pricevol_oneshot_ckpt.pkl"
PREREG = "docs/PREREG_ML_PRICEVOL_2006_2012_FINAL.md"
TRIAL_ID = 475
D0, LAST = pd.Timestamp("2006-01-02"), pd.Timestamp("2012-12-31")
TEST_YEARS = list(range(2008, 2013))
SEED = 20261021
N_RANDOM = 100
TOPN, BUFFER, EQUITY_W = 30, 90, 0.70
LIQ_MIN, LIQ_N = 3.0e7, 20
TAIL_DAYS = 20
SURV_LIMIT = -0.50
BEAR = ("2008-05-01", "2008-11-30")
FEATURES = ["f_low_vol", "f_idio_vol", "f_bab", "f_short_reversal_1m", "f_short_term_reversal_1w", "f_amihud_illiq",
            "f_52w_high_prox", "f_residual_momentum", "f_rel_strength", "f_ma_breakout"]
LOOKBACK_MAX = 253  # 最長特徵（252 日）＋1 列 pct_change


# ------------------------------------------------------------------ 成本
def cost_legs(mult: float) -> dict:
    from validation import costs as C
    slip = C.DEFAULT_SLIPPAGE_BPS / 10_000
    buy = (C.COMMISSION_RATE + slip) * mult
    sell = (C.COMMISSION_RATE + C.tax_rate("normal") + slip) * mult
    assert abs((buy + sell) / mult - C.round_trip_cost_pct()) < 1e-12
    return {"buy": buy, "sell": sell}


# ------------------------------------------------------------------ 特徵（公式同 factors.py::prepare_factors）
def stock_features(adj_close: np.ndarray, volume: np.ndarray, money: np.ndarray, mkt_close: np.ndarray) -> pd.DataFrame:
    """輸入為該檔「有效列」序列（列序＝時間序）。回傳 10 個特徵欄（同長度）。"""
    import factors as FC
    d = pd.DataFrame({"adj_close": adj_close, "Trading_Volume": volume, "Trading_money": money, "mkt_close": mkt_close})
    out = pd.DataFrame(index=d.index)
    ret60 = d["adj_close"] / d["adj_close"].shift(FC.REL_STRENGTH_WINDOW) - 1
    mkt_ret60 = d["mkt_close"] / d["mkt_close"].shift(FC.REL_STRENGTH_WINDOW) - 1
    out["f_rel_strength"] = ret60 - mkt_ret60
    ma60 = d["adj_close"].rolling(FC.MA_WINDOW, min_periods=FC.MA_WINDOW).mean()
    above_ma_pct = d["adj_close"] / ma60 - 1
    vol20 = d["Trading_Volume"].rolling(FC.VOL_SHORT_WINDOW, min_periods=FC.VOL_SHORT_WINDOW).mean()
    vol60 = d["Trading_Volume"].rolling(FC.VOL_LONG_WINDOW, min_periods=FC.VOL_LONG_WINDOW).mean()
    out["f_ma_breakout"] = above_ma_pct * (vol20 / vol60)
    daily_ret = d["adj_close"].pct_change()
    out["f_low_vol"] = -daily_ret.rolling(FC.LOW_VOL_WINDOW, min_periods=FC.LOW_VOL_WINDOW).std()
    out["f_short_reversal_1m"] = -(d["adj_close"] / d["adj_close"].shift(FC.SHORT_REVERSAL_WINDOW) - 1)
    illiq_daily = np.where(d["Trading_money"] > 0, daily_ret.abs() / d["Trading_money"], np.nan)
    out["f_amihud_illiq"] = pd.Series(illiq_daily, index=d.index).rolling(FC.AMIHUD_WINDOW, min_periods=FC.AMIHUD_WINDOW).mean()
    mkt_ret = d["mkt_close"].pct_change()
    W = FC.LOW_VOL_WINDOW
    roll_var_stock = daily_ret.rolling(W, min_periods=W).var()
    roll_var_mkt = mkt_ret.rolling(W, min_periods=W).var()
    roll_cov = daily_ret.rolling(W, min_periods=W).cov(mkt_ret)
    beta_60 = roll_cov / roll_var_mkt
    idio_var = (roll_var_stock - beta_60 ** 2 * roll_var_mkt).clip(lower=0.0)
    out["f_idio_vol"] = -np.sqrt(idio_var)
    out["f_bab"] = -beta_60
    R = FC.RESIDUAL_MOMENTUM_WINDOW
    ret_252 = d["adj_close"] / d["adj_close"].shift(R) - 1
    mkt_ret_252 = d["mkt_close"] / d["mkt_close"].shift(R) - 1
    roll_var_mkt_252 = mkt_ret.rolling(R, min_periods=R).var()
    roll_cov_252 = daily_ret.rolling(R, min_periods=R).cov(mkt_ret)
    beta_252 = roll_cov_252 / roll_var_mkt_252
    out["f_residual_momentum"] = ret_252 - beta_252 * mkt_ret_252
    out["f_52w_high_prox"] = d["adj_close"] / d["adj_close"].rolling(FC.HIGH_52W_WINDOW, min_periods=FC.HIGH_52W_WINDOW).max()
    out["f_short_term_reversal_1w"] = -(d["adj_close"] / d["adj_close"].shift(FC.SHORT_TERM_REVERSAL_1W_WINDOW) - 1)
    return out[FEATURES].replace([np.inf, -np.inf], np.nan)


# ------------------------------------------------------------------ 樣本（特徵×標籤×宇宙）
def build_panel(M: dict) -> dict:
    """回傳每個調整日的宇宙、特徵、標籤。M 需要：cal、O、C、V、money、mkt（D）、dead_exit_i、delist_i、rebal_all（全部月初索引）、end_i。"""
    cal, O, C, Vv, money, mkt = M["cal"], M["O"], M["C"], M["V"], M["money"], M["mkt"]
    D, n = C.shape
    valid = ~np.isnan(C)
    rebal = M["rebal_all"]
    feat_at = {t: np.full((n, len(FEATURES)), np.nan) for t in rebal}
    for j in range(n):
        vi = np.where(valid[:, j])[0]
        if len(vi) < 6:
            continue
        F = stock_features(C[vi, j], Vv[vi, j], money[vi, j], mkt[vi]).to_numpy()
        for t in rebal:
            k = np.searchsorted(vi, t - 1, side="right") - 1  # 調整日前一天（含）以前最後有效列
            if k >= 0:
                feat_at[t][j] = F[k]
    # 最後有效收盤（as-of）
    lastc = pd.DataFrame(C).ffill().to_numpy()
    nexts = list(rebal[1:]) + [M["end_i"]]
    panel = {}
    for t, t2 in zip(rebal, nexts):
        lo = max(0, t - LIQ_N)
        avg_money = money[lo:t].sum(axis=0) / LIQ_N
        recent = valid[lo:t].any(axis=0)
        alive = (M["delist_i"] < 0) | (M["delist_i"] > t - 1)
        univ = recent & alive & (avg_money >= LIQ_MIN) & (t >= LIQ_N)
        entry = O[t]
        ex = np.where(np.isnan(O[t2]), lastc[t2], O[t2])
        de = M["dead_exit_i"]
        gone = (de >= 0) & (de < t2) & (de >= t)
        ex = np.where(gone, lastc[np.clip(de, 0, D - 1), np.arange(n)], ex)
        lab_raw = ex / entry - 1
        X = feat_at[t]
        has_feat = ~np.isnan(X).all(axis=1)
        usable = univ & has_feat & ~np.isnan(lab_raw)
        lab = np.full(n, np.nan)
        if usable.sum() > 1:
            lab[usable] = pd.Series(lab_raw[usable]).rank(pct=True).to_numpy()
        panel[t] = {"univ": univ, "X": X, "label": lab, "usable": usable, "exit_i": t2}
    return panel


def fold_train_rows(M: dict, panel: dict, year: int) -> list[int]:
    cut = pd.Timestamp(f"{year - 1}-11-30")
    return [t for t in M["rebal_all"] if M["cal"][panel[t]["exit_i"]] <= cut and panel[t]["usable"].any()]


def walk_forward(M: dict, panel: dict, rng: np.random.Generator | None = None) -> dict:
    """回傳 {調整日索引: 分數陣列（宇宙外＝NaN）}，只含測試年。rng 非 None＝隨機標籤控制組。"""
    from sklearn.ensemble import HistGradientBoostingRegressor
    scores = {}
    for y in TEST_YEARS:
        tr = fold_train_rows(M, panel, y)
        Xs, ys = [], []
        for t in tr:
            u = panel[t]["usable"]
            lab = panel[t]["label"][u]
            if rng is not None:
                lab = rng.permutation(lab)
            Xs.append(panel[t]["X"][u])
            ys.append(lab)
        X, yv = np.vstack(Xs), np.concatenate(ys)
        mdl = HistGradientBoostingRegressor(random_state=SEED).fit(X, yv)
        for t in M["rebal_all"]:
            if M["cal"][t].year == y:
                s = np.full(len(M["codes"]), np.nan)
                u = panel[t]["univ"]
                if u.any():
                    s[u] = mdl.predict(panel[t]["X"][u])
                scores[t] = s
    return scores


# ------------------------------------------------------------------ 組合
def simulate(M: dict, scores: dict, rebal: list[int], hyp: str, legs: dict) -> dict:
    from validation.costs import limit_status
    cal, O, H, Lo, C = M["cal"], M["O"], M["H"], M["L"], M["C"]
    D, n = C.shape
    end_i = M["end_i"]
    lastc = M["lastc"]
    prevc = M["prevc"]
    de, miss = M["dead_exit_i"], M["missing_dead"]
    sh = np.zeros(n)
    cash = 1.0
    nav = np.full(D, np.nan)
    st = {"n_entries": 0, "n_full_exits": 0, "n_sell_blocked": 0, "n_buy_skipped": 0, "n_buy_scaled": 0,
          "n_delist_close": 0, "n_pessimistic_zeroed": 0, "max_holdings": 0, "turnover": 0.0}
    rs = set(rebal)
    start = rebal[0]
    for d in range(start, end_i + 1):
        px_open = np.where(np.isnan(O[d]), lastc[d - 1], O[d])
        if d == end_i:  # 期末：開盤全數出清（[自行裁量]5）
            held = sh > 0
            v = float((sh[held] * px_open[held]).sum())
            cash += v * (1 - legs["sell"])
            st["turnover"] += v
            st["n_full_exits"] += int(held.sum())
            sh[:] = 0
            nav[d] = cash
            break
        if d in rs:
            val = np.where(sh > 0, sh * px_open, 0.0)
            V = cash + float(val.sum())
            s = scores[d]
            elig = ~np.isnan(s)
            order = np.where(elig)[0][np.argsort(-s[elig], kind="stable")]
            rank = np.full(n, 10 ** 9)
            rank[order] = np.arange(len(order))
            can_open = ~np.isnan(O[d])
            lim_up = np.zeros(n, bool)
            lim_dn = np.zeros(n, bool)
            for j in np.where(can_open & ((sh > 0) | (rank < BUFFER + TOPN)))[0]:
                ls = limit_status(O[d, j], H[d, j], Lo[d, j], C[d, j], prevc[d, j])
                lim_up[j], lim_dn[j] = ls.limit_up, ls.limit_down
            held = sh > 0
            keep = held & (rank < BUFFER)
            target = list(np.where(keep)[0])
            for j in order:
                if len(target) >= TOPN:
                    break
                if held[j]:
                    continue
                if not can_open[j] or lim_up[j]:
                    st["n_buy_skipped"] += 1
                    continue
                target.append(j)
            tset = np.zeros(n, bool)
            tset[target] = True
            w = V * EQUITY_W / TOPN
            # 先賣
            for j in np.where(held)[0]:
                want = w if tset[j] else 0.0
                if val[j] > want + 1e-15:
                    if not can_open[j] or lim_dn[j]:
                        st["n_sell_blocked"] += 1
                        continue
                    q = (val[j] - want) / px_open[j]
                    cash += q * px_open[j] * (1 - legs["sell"])
                    st["turnover"] += q * px_open[j]
                    sh[j] -= q
                    if want == 0.0:
                        sh[j] = 0.0
                        st["n_full_exits"] += 1
            # 後買
            buys = {}
            for j in target:
                cur = sh[j] * px_open[j]
                if w > cur + 1e-15 and can_open[j] and not lim_up[j]:
                    buys[j] = w - cur
            need = sum(buys.values()) * (1 + legs["buy"])
            scale = 1.0
            if need > cash > 0:
                scale = cash / need
                st["n_buy_scaled"] += 1
            elif cash <= 0:
                scale = 0.0
            for j, amt in buys.items():
                a = amt * scale
                if a <= 0:
                    continue
                if sh[j] == 0:
                    st["n_entries"] += 1
                sh[j] += a / px_open[j]
                cash -= a * (1 + legs["buy"])
                st["turnover"] += a
            st["max_holdings"] = max(st["max_holdings"], int((sh > 0).sum()))
        # 收盤：下市出場
        for j in np.where((de == d) & (sh > 0))[0]:
            if miss[j] and hyp == "pessimistic":
                st["n_pessimistic_zeroed"] += 1
            else:
                cash += sh[j] * C[d, j] * (1 - legs["sell"])
                st["turnover"] += sh[j] * C[d, j]
                st["n_delist_close"] += 1
            st["n_full_exits"] += 1
            sh[j] = 0.0
        nav[d] = cash + float(np.nansum(sh * lastc[d]))
    st["n_trades"] = st["n_entries"] + st["n_full_exits"]
    return {"nav": nav, "final": float(nav[end_i]), "stats": st}


# ------------------------------------------------------------------ 指標
def mdd(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    return float((x / np.maximum.accumulate(x) - 1).min()) if len(x) else float("nan")


def seg(nav, cal, a, b):
    m = (cal >= pd.Timestamp(a)) & (cal <= pd.Timestamp(b))
    return nav[m]


def years_span(M) -> float:
    return (M["cal"][M["end_i"]] - M["cal"][M["rebal_test"][0]]).days / 365.25


def cagr_of(final: float, M) -> float:
    return final ** (1 / years_span(M)) - 1 if final > 0 else -1.0


def bench_0050(M) -> dict:
    a50, cal = M["a50"], M["cal"]
    b0 = float(a50[a50.index < M["cal"][M["rebal_test"][0]]].iloc[-1])
    b1 = float(a50[a50.index <= LAST].iloc[-1])
    s50 = a50.reindex(cal).ffill().to_numpy()
    s = seg(s50, cal, "2008-01-01", "2012-12-31")
    yrs = years_span(M)
    out = {"cagr_total_return": (b1 / b0) ** (1 / yrs) - 1, "base": "還原收盤 2007-12-31 → 2012-12-28",
           "mdd_full": mdd(s), "mdd_2008_05_11": mdd(seg(s50, cal, *BEAR)), "yearly": {}}
    for y in TEST_YEARS:
        a = a50[a50.index < pd.Timestamp(f"{y}-01-01")].iloc[-1]
        b = a50[a50.index <= pd.Timestamp(f"{y}-12-31")].iloc[-1]
        out["yearly"][str(y)] = float(b / a - 1)
    return out


def yearly_returns(nav, M) -> dict:
    cal = M["cal"]
    out = {}
    for y in TEST_YEARS:
        before = nav[(cal < pd.Timestamp(f"{y}-01-01")) & ~np.isnan(nav)]
        s = before[-1] if len(before) else 1.0
        e = nav[(cal <= pd.Timestamp(f"{y}-12-31")) & ~np.isnan(nav)][-1]
        out[str(y)] = float(e / s - 1)
    return out


# ------------------------------------------------------------------ 真資料
def build_real() -> dict:
    import finmind_client as F
    import var1018_v1_oneshot as V1
    import var1018_v1_prep as V
    import var1018_v1_lowmem as L
    V1.install_no_network_guard()
    t0 = time.time()
    # 交易日曆＝TAIEX（FinMind，同 factor_ic.py 的大盤來源）
    tx = V1.local_load_dev("TaiwanStockPrice", "TAIEX", "2006-01-01")
    tx["date"] = pd.to_datetime(tx["date"])
    tx = tx[(tx["date"] >= D0) & (tx["close"] > 0)].drop_duplicates("date").sort_values("date")
    first13 = tx[tx["date"] > LAST]["date"].min()
    if pd.isna(first13) or first13.year != 2013:
        raise RuntimeError("找不到 2013 第一個交易日")
    tx = tx[tx["date"] <= first13]
    cal = pd.DatetimeIndex(tx["date"].to_numpy())
    mkt = tx["close"].astype(float).to_numpy().copy()
    mkt[-1] = np.nan  # 2013 第一天只讀開盤：大盤收盤不使用
    D = len(cal)
    pos = {d: i for i, d in enumerate(cal)}
    # 候選代號（[自行裁量]2）
    cands, dead = V.candidates()
    lst = V.official_listing_dates()
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    four = re.compile(r"[1-9]\d{3}")
    codes_set = {c for c in cands if four.fullmatch(c)}
    codes_set |= {c for c, (lt, it) in lst.items() if four.fullmatch(c) and lt is not None and lt <= LAST}
    codes_set |= {c for c, dd in ddate.items() if four.fullmatch(str(c)) and D0 <= dd <= LAST}
    # 官方日檔：掃一次（2006-12-26～2012-12-31），記可核對日與當日有列代號
    off_rows: dict[int, dict] = {}
    listed_day: dict[int, set] = {}
    status: dict[int, list] = {}
    otc_codes: set[str] = set()
    for si, src in enumerate(("twse", "tpex")):
        for p in sorted((L.OFF / src).glob("*.json")):
            if not ("20061226" <= p.stem <= "20121231"):
                continue
            ts = pd.Timestamp(f"{p.stem[:4]}-{p.stem[4:6]}-{p.stem[6:]}")
            j = json.loads(p.read_text(encoding="utf-8"))
            if ts not in pos:
                continue
            i = pos[ts]
            status.setdefault(i, [None, None])[si] = j.get("status")
            rows = j.get("rows") or {}
            listed_day.setdefault(i, set()).update(rows.keys())
            for code, row in rows.items():
                if four.fullmatch(code):
                    codes_set.add(code)
                    if si == 1:
                        otc_codes.add(code)
                    if row[3] is not None and row[3] > 0:
                        off_rows.setdefault(i, {})[code] = row
            del j
    chk_days = {i for i, s in status.items() if s[0] == "ok" and s[1] == "ok"}
    codes = sorted(codes_set)
    n = len(codes)
    jof = {c: k for k, c in enumerate(codes)}
    O, H, Lw, C, Vv = (np.full((D, n), np.nan) for _ in range(5))
    money = np.zeros((D, n))
    src_fm = np.zeros((D, n), bool)
    n_fm_files = 0
    for c in codes:
        d = V1.local_load_dev("TaiwanStockPrice", c, "2006-01-01")
        if d is None or d.empty:
            continue
        n_fm_files += 1
        d = d[pd.to_numeric(d["close"], errors="coerce") > 0]
        dt = pd.to_datetime(d["date"])
        m = dt.isin(cal)
        d, dt = d[m.values], dt[m.values]
        ii = np.array([pos[x] for x in dt], dtype=int)
        k = jof[c]
        O[ii, k] = d["open"].astype(float).values
        H[ii, k] = d["max"].astype(float).values
        Lw[ii, k] = d["min"].astype(float).values
        C[ii, k] = d["close"].astype(float).values
        Vv[ii, k] = d["Trading_Volume"].astype(float).values
        money[ii, k] = d["Trading_money"].astype(float).values
        src_fm[ii, k] = True
    n_off_added, n_dropped = 0, 0
    for i, rows in off_rows.items():
        for code, row in rows.items():
            k = jof[code]
            if np.isnan(C[i, k]):
                O[i, k], H[i, k], Lw[i, k], C[i, k], Vv[i, k], money[i, k] = row[0], row[1], row[2], row[3], row[4], row[5] or 0.0
                n_off_added += 1
    for i in chk_days:  # R1／V1 R2：可核對日只留官方有列者
        on = listed_day.get(i, set())
        for k in np.where(~np.isnan(C[i]))[0]:
            if codes[k] not in on:
                O[i, k] = H[i, k] = Lw[i, k] = C[i, k] = Vv[i, k] = np.nan
                money[i, k] = 0.0
                n_dropped += 1
    end_i = D - 1
    # 2013 第一天只保留開盤
    H[end_i] = Lw[end_i] = C[end_i] = Vv[end_i] = np.nan
    money[end_i] = 0.0
    for X in (O, H, Lw):
        X[~(X > 0)] = np.nan
    # 還原權息
    meta = {}
    for k, c in enumerate(codes):
        has = ~np.isnan(C[:, k]) | ~np.isnan(O[:, k])
        if not has.any():
            meta[c] = None
            continue
        ev, err = V1.events_for(c)
        f = np.ones(D)
        for _, e in (ev.sort_values("ex_date", ascending=False).iterrows() if len(ev) else []):
            f[cal < pd.Timestamp(e["ex_date"])] *= float(e["factor"])
        for X in (O, H, Lw, C):
            X[:, k] *= f
        meta[c] = {"events_error": err, "n_events": int(len(ev)),
                   "supp_x": int((ev["event_type"] == "dividend_official_supp").sum()) if len(ev) else 0,
                   "supp_red": int((ev["event_type"] == "capital_reduction_official_supp").sum()) if len(ev) else 0}
    keep = np.array([meta[c] is not None for c in codes])
    codes = [c for c in codes if meta[c] is not None]
    O, H, Lw, C, Vv, money, src_fm = (X[:, keep] for X in (O, H, Lw, C, Vv, money, src_fm))
    n = len(codes)
    H = np.where(np.isnan(H) & ~np.isnan(C), C, H)
    Lw = np.where(np.isnan(Lw) & ~np.isnan(C), C, Lw)
    dead_exit_i, delist_i, missing = np.full(n, -1), np.full(n, -1), np.zeros(n, bool)
    for k, c in enumerate(codes):
        dd = ddate.get(c)
        if dd is not None and D0 <= dd <= LAST:
            delist_i[k] = int(np.searchsorted(cal, dd, side="left"))
            vi = np.where(~np.isnan(C[:end_i, k]))[0]
            if len(vi):
                dead_exit_i[k] = vi[-1]
                missing[k] = (dd - cal[vi[-1]]).days > TAIL_DAYS
    rebal_all = [i for i in range(1, end_i) if cal[i].month != cal[i - 1].month]
    rebal_all = [0] + rebal_all if cal[0].month == 1 else rebal_all
    rebal_test = [i for i in rebal_all if cal[i].year >= 2008]
    lastc = pd.DataFrame(C).ffill().to_numpy()
    prevc = np.vstack([np.full(n, np.nan), lastc[:-1]])
    s50 = V1.raw_close("0050", {})
    ev50, err50 = V1.events_for("0050")
    a50 = V1.apply_events(s50, ev50)
    a50 = a50[a50.index <= LAST]
    otc = np.array([c in otc_codes for c in codes])
    print(f"[build] {n} 檔、{D} 交易日、FinMind 檔 {n_fm_files}、官方補列 {n_off_added}、R2 丟列 {n_dropped}、"
          f"{time.time() - t0:.0f} 秒", flush=True)
    return {"cal": cal, "codes": codes, "O": O, "H": H, "L": Lw, "C": C, "V": Vv, "money": money, "mkt": mkt,
            "dead_exit_i": dead_exit_i, "delist_i": delist_i, "missing_dead": missing, "rebal_all": rebal_all,
            "rebal_test": rebal_test, "end_i": end_i, "lastc": lastc, "prevc": prevc, "a50": a50, "err50": err50,
            "n_ev50": int(len(ev50)), "meta": {c: meta[c] for c in codes}, "otc": otc,
            "n_official_rows_added": n_off_added, "n_r2_rows_dropped": n_dropped, "n_checkable_days": len(chk_days)}


def unverifiable_share(M: dict, panel: dict) -> dict:
    """R1 第 4 點：每折訓練樣本中，特徵回看期落在官方不可佐證區（2006 全年、2007-01～06 上櫃）的列數比例。"""
    cal = M["cal"]
    out = {}
    for y in TEST_YEARS:
        tot = bad = 0
        for t in fold_train_rows(M, panel, y):
            u = panel[t]["usable"]
            start = cal[max(0, t - 1 - LOOKBACK_MAX)]
            k = int(u.sum())
            tot += k
            if start < pd.Timestamp("2007-01-01"):
                bad += k
            elif start < pd.Timestamp("2007-07-01"):
                bad += int((u & M["otc"]).sum())
        out[str(y)] = {"train_rows": tot, "rows_lookback_in_unverifiable": bad, "share": bad / tot if tot else None}
    return out


def evaluate(M, sims: dict, sims_bi: dict, ctrl: list[float], nN: int, bench: dict) -> dict:
    s1 = sims[1]
    nav = s1["nav"]
    cal = M["cal"]
    out = {"n_trades_1x": s1["stats"]["n_trades"], "stats_1x": s1["stats"],
           "final_1x": s1["final"], "final_2x": sims[2]["final"], "final_3x": sims[3]["final"],
           "cagr_1x": cagr_of(s1["final"], M), "cagr_2x": cagr_of(sims[2]["final"], M), "cagr_3x": cagr_of(sims[3]["final"], M),
           "mdd_full_1x": mdd(seg(nav, cal, "2008-01-01", "2013-01-31")), "mdd_2008_05_11_1x": mdd(seg(nav, cal, *BEAR)),
           "yearly_1x": yearly_returns(nav, M)}
    out["excess_cagr_1x"] = out["cagr_1x"] - bench["cagr_total_return"]
    out["yearly_excess_vs_0050"] = {y: out["yearly_1x"][y] - bench["yearly"][y] for y in out["yearly_1x"]}
    bi = sims_bi[1]
    out["bimonthly"] = {"final_1x": bi["final"], "cagr_1x": cagr_of(bi["final"], M),
                        "excess_cagr_1x": cagr_of(bi["final"], M) - bench["cagr_total_return"],
                        "mdd_full_1x": mdd(seg(bi["nav"], cal, "2008-01-01", "2013-01-31")), "stats_1x": bi["stats"]}
    arr = np.array(ctrl)
    pct = float((arr < s1["final"]).mean() * 100) if len(arr) else None
    bonf = 100.0 * (1 - 0.05 / nN) if nN else None
    out["random_label_control"] = {
        "n_random": len(arr), "percentile": pct, "p50": float(np.percentile(arr, 50)) if len(arr) else None,
        "p95": float(np.percentile(arr, 95)) if len(arr) else None, "max": float(arr.max()) if len(arr) else None,
        "beats_p95": bool(len(arr) and s1["final"] > np.percentile(arr, 95)),
        "bonferroni_N": nN, "bonferroni_percentile_required": bonf,
        "passes_bonferroni": bool(pct is not None and bonf is not None and pct >= bonf),
        "note": "100 次的百分位解析度為 1%，Bonferroni 門檻在此次數下無法達到，只列出"}
    if out["n_trades_1x"] < 100:
        v = "INSUFFICIENT_DATA"
    elif out["mdd_full_1x"] < SURV_LIMIT or out["mdd_2008_05_11_1x"] < SURV_LIMIT:
        v = "VIOLATES_SURVIVAL"
    else:
        g8 = out["cagr_1x"] > bench["cagr_total_return"] and sims[2]["final"] > 1 and sims[3]["final"] > 1
        g4 = out["random_label_control"]["beats_p95"]
        g7 = np.sign(out["bimonthly"]["excess_cagr_1x"]) == np.sign(out["excess_cagr_1x"])
        out["gate8_simplified_pass"], out["random_label_control_pass"], out["gate7_pass"] = bool(g8), bool(g4), bool(g7)
        v = "PASS" if (g8 and g4 and g7) else "FAIL"
    out["verdict_mechanical"] = v
    return out


def current_N() -> int:
    txt = (HERE / "SELECTION_BIAS_LEDGER.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*全體（總N[^|]*\|\s*(\d+)\s*\|", txt)
    return int(m.group(1)) if m else 0


def _ckpt_load() -> dict:
    if CKPT.exists():
        return pickle.loads(CKPT.read_bytes())
    return {}


def _ckpt_save(st: dict) -> None:
    tmp = CKPT.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(st))
    os.replace(tmp, CKPT)


def run(deadline: float | None) -> int:
    if RESULT.exists():
        print(f"結果檔已存在（{RESULT}），單發只跑一次，拒跑。")
        return 2
    t_start = time.time()
    st = _ckpt_load()
    M = build_real()
    panel = build_panel(M)
    rebal_bi = [t for t in M["rebal_test"] if M["cal"][t].month % 2 == 1]
    if "real" not in st:
        sc = walk_forward(M, panel)
        st["real"] = {h: {m: simulate(M, sc, M["rebal_test"], h, cost_legs(m)) for m in (1, 2, 3)} for h in ("pessimistic", "neutral")}
        st["real_bi"] = {h: {1: simulate(M, sc, rebal_bi, h, cost_legs(1))} for h in ("pessimistic", "neutral")}
        st["ctrl"] = {"pessimistic": [], "neutral": []}
        st["started_at"] = datetime.now().isoformat(timespec="seconds")
        _ckpt_save(st)
        print(f"[real] 完成（{time.time() - t_start:.0f} 秒）", flush=True)
    legs1 = cost_legs(1)
    while len(st["ctrl"]["neutral"]) < N_RANDOM:
        if deadline is not None and time.time() > deadline:
            _ckpt_save(st)
            print(f"[ckpt] 時間到，控制組完成 {len(st['ctrl']['neutral'])}/{N_RANDOM}，斷點已存 {CKPT}", flush=True)
            return 3
        k = len(st["ctrl"]["neutral"])
        sc = walk_forward(M, panel, rng=np.random.default_rng(SEED + k))
        for h in ("pessimistic", "neutral"):
            st["ctrl"][h].append(simulate(M, sc, M["rebal_test"], h, legs1)["final"])
        if (k + 1) % 5 == 0:
            _ckpt_save(st)
            print(f"[ctrl] {k + 1}/{N_RANDOM}（{time.time() - t_start:.0f} 秒）", flush=True)
    nN = current_N()
    bench = bench_0050(M)
    results = {h: evaluate(M, st["real"][h], st["real_bi"][h], st["ctrl"][h], nN, bench) for h in ("pessimistic", "neutral")}
    vs = [results[h]["verdict_mechanical"] for h in results]
    verdict = "PASS" if all(v == "PASS" for v in vs) else next(
        (x for x in ("VIOLATES_SURVIVAL", "INSUFFICIENT_DATA") if x in vs), "FAIL")
    meta = M["meta"]
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"), "trial_id": TRIAL_ID, "prereg": PREREG,
        "real_started_at": st.get("started_at"), "zero_network_requests": True, "holdout_touched": False,
        "price_read_until": "2012-12-31（另讀 2013 第一個交易日開盤）",
        "n_codes": len(M["codes"]), "n_trading_days": len(M["cal"]), "end_day": str(M["cal"][M["end_i"]].date()),
        "n_rebal_test": len(M["rebal_test"]), "n_rebal_bimonthly": len(rebal_bi),
        "n_delisted_in_window": int((M["delist_i"] >= 0).sum()), "n_missing_data_delisted": int(M["missing_dead"].sum()),
        "missing_data_delisted": [c for k, c in enumerate(M["codes"]) if M["missing_dead"][k]],
        "n_official_rows_added": M["n_official_rows_added"], "n_r2_rows_dropped": M["n_r2_rows_dropped"],
        "n_checkable_days": M["n_checkable_days"],
        "universe_size_by_rebal": {str(M["cal"][t].date()): int(panel[t]["univ"].sum()) for t in M["rebal_all"]},
        "training_unverifiable_share_by_fold": unverifiable_share(M, panel),
        "adjust_events": {"n_codes_events_error": sum(1 for c in M["codes"] if meta[c]["events_error"]),
                          "n_official_exright_supp": sum(meta[c]["supp_x"] for c in M["codes"]),
                          "n_official_reduction_supp": sum(meta[c]["supp_red"] for c in M["codes"]),
                          "note": "官方補充事件數為各檔 2006 起全部事件（含窗口外）；2006-01～2007-06 只有 FinMind"},
        "0050_events": M["n_ev50"], "0050_events_error": M["err50"],
        "benchmark_0050": bench, "cost_legs_1x": cost_legs(1),
        "results": results, "verdict_overall": verdict, "discretion": "見程式檔頭 [自行裁量] 1～10",
        "limit_note": "costs.limit_status() 寫死 ±10%，2015-06 前實為 ±7%（先.一三三-2c-限），照 PREREG 原樣使用",
    }
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("總判定（機械）：", verdict, "；結果檔", RESULT)
    return 0


def estimate() -> int:
    t0 = time.time()
    M = build_real()
    t1 = time.time()
    panel = build_panel(M)
    t2 = time.time()
    walk_forward(M, panel, rng=np.random.default_rng(0))  # 隨機標籤，不看真實結果
    t3 = time.time()
    rows = {y: sum(int(panel[t]["usable"].sum()) for t in fold_train_rows(M, panel, y)) for y in TEST_YEARS}
    print(json.dumps({"build_sec": round(t1 - t0), "panel_sec": round(t2 - t1), "one_walk_forward_sec": round(t3 - t2, 1),
                      "train_rows_by_fold": rows, "est_total_min": round(((t3 - t2) * 101 + (t2 - t0)) / 60, 1)},
                     ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ 自測
def selftest() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and bool(cond)

    rng = np.random.default_rng(1)
    # 1. 特徵：同 factors.py 定義（手算對照）
    N = 300
    c = np.cumprod(1 + rng.normal(0, 0.02, N)) * 50
    mk = np.cumprod(1 + rng.normal(0, 0.01, N)) * 7000
    vol = rng.uniform(1e5, 1e6, N)
    mon = vol * c
    F = stock_features(c, vol, mon, mk)
    check(abs(F["f_short_term_reversal_1w"].iloc[-1] + (c[-1] / c[-6] - 1)) < 1e-12, "1w 反轉＝−5 日報酬")
    check(abs(F["f_short_reversal_1m"].iloc[-1] + (c[-1] / c[-22] - 1)) < 1e-12, "1m 反轉＝−21 日報酬")
    check(abs(F["f_52w_high_prox"].iloc[-1] - c[-1] / c[-252:].max()) < 1e-12, "52 週高點接近度")
    r = pd.Series(c).pct_change()
    check(abs(F["f_low_vol"].iloc[-1] + r.iloc[-60:].std()) < 1e-12, "低波動＝−60 日報酬標準差")
    check(np.isnan(F["f_residual_momentum"].iloc[251]) and not np.isnan(F["f_residual_momentum"].iloc[-1]), "殘差動量 252 日才有值")
    check(F["f_52w_high_prox"].isna().sum() == 251, "52 週需 252 列")
    # 2. 合成市場：一檔「真訊號」股（特徵高→下月漲）讓模型與組合流程跑通
    D, n = 1300, 60
    cal = pd.bdate_range("2006-01-02", periods=D)
    mkt = np.cumprod(1 + rng.normal(0.0003, 0.01, D)) * 6000
    Cc = np.cumprod(1 + rng.normal(0.0003, 0.02, (D, n)), axis=0) * 30
    Oo = Cc * (1 + rng.normal(0, 0.003, (D, n)))
    M = {"cal": cal, "codes": [f"{1000 + k}" for k in range(n)], "O": Oo, "H": np.maximum(Oo, Cc) * 1.01,
         "L": np.minimum(Oo, Cc) * 0.99, "C": Cc, "V": np.full((D, n), 1e6), "money": np.full((D, n), 5e7), "mkt": mkt,
         "dead_exit_i": np.full(n, -1), "delist_i": np.full(n, -1), "missing_dead": np.zeros(n, bool)}
    M["C"][900:, 5] = np.nan
    M["O"][900:, 5] = np.nan
    M["dead_exit_i"][5], M["delist_i"][5], M["missing_dead"][5] = 899, 930, True
    M["end_i"] = D - 1
    M["rebal_all"] = [i for i in range(1, D - 1) if cal[i].month != cal[i - 1].month]
    M["rebal_test"] = [i for i in M["rebal_all"] if cal[i].year >= 2008]
    M["lastc"] = pd.DataFrame(M["C"]).ffill().to_numpy()
    M["prevc"] = np.vstack([np.full(n, np.nan), M["lastc"][:-1]])
    M["otc"] = np.zeros(n, bool)
    panel = build_panel(M)
    t = M["rebal_test"][0]
    check(panel[t]["univ"].sum() == n, "宇宙：流動性 5,000 萬全入選")
    tlate = [x for x in M["rebal_all"] if x > 935][0]
    check(not panel[tlate]["univ"][5], "下市後不在宇宙")
    lab = panel[t]["label"][panel[t]["usable"]]
    check(lab.min() > 0 and lab.max() == 1.0, "標籤為橫斷面百分位")
    tr = fold_train_rows(M, panel, 2008)
    check(all(cal[panel[x]["exit_i"]] <= pd.Timestamp("2007-11-30") for x in tr) and len(tr) >= 15, "2008 折只用 2007-11-30 以前已實現標籤")
    check(not any(cal[x].year >= 2008 for x in tr), "訓練不含測試年")
    sc = walk_forward(M, panel)
    check(set(sc) == set(M["rebal_test"]), "每個測試調整日都有分數")
    sc2 = walk_forward(M, panel)
    check(all(np.allclose(sc[k], sc2[k], equal_nan=True) for k in sc), "同 random_state 可重現")
    scr = walk_forward(M, panel, rng=np.random.default_rng(SEED))
    check(any(not np.allclose(sc[k], scr[k], equal_nan=True) for k in sc), "隨機標籤控制組改變模型")
    sim = simulate(M, sc, M["rebal_test"], "neutral", cost_legs(1))
    nav = sim["nav"]
    t0 = M["rebal_test"][0]
    check(sim["stats"]["max_holdings"] <= TOPN, "持股 ≤30")
    check(sim["stats"]["n_trades"] > 0 and not np.isnan(sim["final"]), "組合有交易、期末淨值有值")
    check(abs(nav[t0 - 1] - 1.0) < 1e-12 if not np.isnan(nav[t0 - 1]) else True, "開始前淨值 1")
    # 0 成本、所有股票價格不動 → 淨值恆 1
    M2 = dict(M)
    flat = np.full((D, n), 10.0)
    M2.update({"O": flat, "C": flat, "H": flat, "L": flat, "lastc": flat, "prevc": flat, "dead_exit_i": np.full(n, -1),
               "missing_dead": np.zeros(n, bool)})
    s0 = simulate(M2, sc, M["rebal_test"], "neutral", {"buy": 0.0, "sell": 0.0})
    check(np.nanmax(np.abs(s0["nav"][t0:] - 1)) < 1e-9, "價格不動＋零成本 → 淨值恆 1")
    # 股價全部 +10%（一次跳）→ 70% 部位 → 淨值 +7%
    M3 = dict(M2)
    up = flat.copy()
    up[t0 + 3:] = 11.0
    M3.update({"O": up, "C": up, "H": up, "L": up, "lastc": up, "prevc": np.vstack([up[:1], up[:-1]])})
    s3 = simulate(M3, sc, M["rebal_test"][:2], "neutral", {"buy": 0.0, "sell": 0.0})
    check(abs(s3["nav"][t0 + 5] - 1.07) < 1e-9, "70／30：股票 +10% → 淨值 +7%")
    # 悲觀：持有缺資料下市股 → 歸零；中性 → 最後價
    sc_force = {k: np.where(np.arange(n) == 5, 10.0, v) for k, v in sc.items()}
    M4 = dict(M)
    M4["rebal_test"] = [x for x in M["rebal_test"] if x < 899]
    pz = simulate(M4, sc_force, M4["rebal_test"], "pessimistic", cost_legs(1))
    nz = simulate(M4, sc_force, M4["rebal_test"], "neutral", cost_legs(1))
    check(pz["stats"]["n_pessimistic_zeroed"] >= 1 and nz["stats"]["n_delist_close"] >= 1 and pz["final"] < nz["final"],
          "下市缺資料：悲觀歸零、中性最後價出場")
    # 指標
    check(abs(mdd(np.array([1, 2, 1, 3])) + 0.5) < 1e-12, "MDD")
    check(cost_legs(2)["buy"] == 2 * cost_legs(1)["buy"], "成本倍數")
    print("selftest:", "ALL PASS" if ok else "有 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        sys.exit(selftest())
    if cmd == "estimate":
        sys.exit(estimate())
    if cmd == "run":
        dl = float(sys.argv[2]) if len(sys.argv) > 2 else None  # 牆鐘秒數截止（epoch）
        sys.exit(run(dl))
    print(__doc__)
    sys.exit(1)
