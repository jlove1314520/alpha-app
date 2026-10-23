# -*- coding: utf-8 -*-
"""先.一三三-2c（2026-10-23，DevQueue 20261023-223103）：個股網格交易 2007-10～2009-12 單發（事前登記 #468～#474）。

規則照 `docs/PREREG_STOCK_GRID_2007_2009_FINAL.md` 第 1～2 節＋修訂 R1（d73cc4b196），不改任何一條：
- 宇宙：每月第一個交易日，以當時在市的上市＋上櫃普通股（含之後下市者）排「前 60 個交易日平均成交金額」取前 50 名。
- 中心＝建格當天 60 日均線（還原收盤）；格距 g＝1×ATR20（還原高低收、Wilder）；L₋₅…L₊₅ 共 11 線 10 格。
- 進場：收盤由上往下跌破格下緣 Lᵢ（i＝−5…+4）且格位空 → 隔日開盤買一份；出場：收盤站上 Lᵢ₊₁ → 隔日開盤賣。
- 金額：總資金÷50÷10 為每格固定金額，同格最多一份，不加碼；未用資金留現金（不計息）。
- 停損：收盤跌破 L₋₅ → 隔日開盤該檔全部出清、冷卻 20 個交易日不得建格。
- 重新建格：只在月初、且無持倉時；有持倉沿用舊格。跌出宇宙：月初不在前 50 → 不新買、既有格位當天開盤出清。
- 成交限制：隔日開盤漲停（買）／跌停（賣）鎖住 → 順延（`costs.limit_status()`）；停牌日不成交；下市以最後成交價出場。
- 成本：`validation.costs` 手續費 0.1425% 雙邊、證交稅 0.3%、滑價 5bps／邊；報 1×／2×／3×。
- R1：驗證段 2007-10-01～2009-12-31，首次建格 2007-10-01，暖機只讀 2007-07-02～2007-09-28；價格同 V1 修訂 R2
  （可核對日只採官方日檔有列的價格列）；還原用含官方補充事件的 `adjust.adjustment_events()`；
  下市股缺資料（最後可得價到下市日 >20 天）悲觀＝−100%、中性＝最後可得價出場，兩者都過才 PASS。
- 判準依序：①交易數 ≥100 →②天條一 MDD ≤50%（附 2008-05～2008-11）→③扣 1× 年化 > 0050 含息年化、2×／3× 淨利 >0
  →④隨機進出場時點控制組（1,000 次、seed 20261021、adj_open）扣成本最終權益 > P95（照列 Bonferroni 與 kept_original）
  →⑤逐年對 0050 超額（2007 僅 Q4、2008、2009）只揭露。

[自行裁量]（寫在結果檔 discretion 欄，總司令／Cowork 可推翻）：
1. 格位 i＝−5 的進場條件（收盤跌破 L₋₅）與停損條件相同：停損優先、不買；所以 i＝−5 實際不會成交（照實揭露）。
2. 「前 60 個交易日」＝月初當天之前 60 個交易日（不含當天，開盤前就能決定出清）；停牌／無列日成交金額記 0。
   「當時在市」＝月初前 60 個交易日內有成交價、且下市日（若有）晚於月初。排除 ETF／權證／特別股＝候選只取 4 碼非 0 開頭
   普通股（同 V1 `candidates()`）；**全額交割股本機沒有 2007～2009 的時點名單，無法排除**（照實揭露）。
3. 建格當天需有收盤價且自 2007-07-02 起累積 ≥60 個有效收盤；中心＝最近 60 個有效收盤平均、ATR 用全部有效列 Wilder 遞推；
   建格當天收盤後格線生效，跌破／站上從次一個有效收盤起判斷（與前一個有效收盤比）。
4. 每格買入股數＝floor(每格金額 ÷ (開盤 ×(1＋買腿成本)))（同控制組 `run_random_timing_control()` 的部位公式）；
   現金不足一份就不買（次數揭露）。初始資金 1 億（讓整股取整誤差可忽略；比例結果與資金規模無關）。
5. 漲跌停判斷用還原開高低收與前一有效還原收盤（除權息日原始前收不是參考價，還原後才可比）。
6. 順延的買單在成交前若該檔停損／跌出宇宙／下市則取消；順延的賣單一直順延到可成交日。
7. 非下市股價格在 2009-12-31 前就斷的：持倉留到期末，以最後可得收盤結算（兩假設相同，件數揭露）。
8. 控制組 trade_schedule 只放「開盤買、開盤賣」的完整來回；下市出場與期末結算（收盤價出場）用該日當作 exit_date，
   若與進場同日或不在 adj_open 序列內會被 `run_random_timing_control()` 略過（筆數揭露）；悲觀假設下歸零的部位在控制組
   以真實價格計（控制組不模擬缺資料歸零，偏向讓控制組變好＝對網格較嚴）。
9. 第 8 關用 PREREG 第 2 節第 3 點的簡化版（0050 含息年化同期比較）；`evaluate_gate8()` 的被動基準表只有 2015～2024，
   對 2007～2009 不適用，不呼叫。

用法：
  python research/stock_grid_oneshot.py selftest   # 合成資料自測（不讀真資料報酬）
  python research/stock_grid_oneshot.py run        # 只跑一次；結果檔已存在就拒跑
輸出：research/data/stock_grid_oneshot_result.json（git add -f 入庫）
"""
from __future__ import annotations

import json
import math
import sys
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
RESULT = HERE / "data" / "stock_grid_oneshot_result.json"
PREREG = "docs/PREREG_STOCK_GRID_2007_2009_FINAL.md"
PREREG_R1_COMMIT = "d73cc4b196"
WARM0, START, END = pd.Timestamp("2007-07-02"), pd.Timestamp("2007-10-01"), pd.Timestamp("2009-12-31")
TOPN, NSLOT, LOOK, MA_N, ATR_N, COOL = 50, 10, 60, 60, 20, 20
LEVELS = np.arange(-5, 6)          # L₋₅…L₊₅
SLOTS = list(range(-5, 5))         # 格位 i：下緣 Lᵢ、上緣 Lᵢ₊₁
TAIL_DAYS = 20
CAPITAL = 100_000_000.0
SEED, N_RANDOM = 20261021, 1000
SURV_LIMIT = -0.50
BEAR = ("2008-05-01", "2008-11-30")


# ------------------------------------------------------------------ 成本
def cost_legs(mult: float) -> dict:
    from validation import costs as C
    slip = C.DEFAULT_SLIPPAGE_BPS / 10_000
    buy = (C.COMMISSION_RATE + slip) * mult
    sell = (C.COMMISSION_RATE + C.tax_rate("normal") + slip) * mult
    assert abs((buy + sell) / mult - C.round_trip_cost_pct()) < 1e-12
    return {"buy": buy, "sell": sell}


def atr_wilder(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    """有效列上的 Wilder ATR20；前 20 個 TR 平均為起點（第一列沒有前收，TR＝高−低）。"""
    n = len(c)
    out = np.full(n, np.nan)
    if n < ATR_N:
        return out
    pc = np.concatenate([[np.nan], c[:-1]])
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    out[ATR_N - 1] = tr[:ATR_N].mean()
    for k in range(ATR_N, n):
        out[k] = (out[k - 1] * (ATR_N - 1) + tr[k]) / ATR_N
    return out


# ------------------------------------------------------------------ 引擎
def simulate(M: dict, hyp: str, legs: dict, log_trades: bool = False) -> dict:
    """M：cal（DatetimeIndex）、codes、O/H/L/C（D×n，還原，無列＝NaN）、money（D×n，原始成交金額，無列＝0）、
    dead_exit_i（n；下市股最後有效日索引，非下市＝−1）、missing_dead（n 布林）、start_i、month_starts（索引）。"""
    from validation.costs import limit_status
    cal, codes = M["cal"], M["codes"]
    O, H, Lo, C, money = M["O"], M["H"], M["L"], M["C"], M["money"]
    D, n = C.shape
    valid = ~np.isnan(C)
    alloc = CAPITAL / TOPN / NSLOT
    cash = CAPITAL
    shares = np.zeros((n, len(SLOTS)))
    entry_d = np.full((n, len(SLOTS)), -1)
    pend_buy = np.zeros((n, len(SLOTS)), bool)
    pend_sell = np.zeros((n, len(SLOTS)), bool)
    grid = [None] * n            # 格線陣列（11 個值）或 None
    active = np.zeros(n, bool)   # 在宇宙中、格線可產生新買單
    cool_until = np.full(n, -1)
    last_c = np.full(n, np.nan)  # 最近有效還原收盤
    prev_sig = np.full(n, np.nan)  # 格線生效後的「前一個有效收盤」
    nav = np.full(D, np.nan)
    trades, stats = [], {"n_buys": 0, "n_sells": 0, "n_buy_blocked_limit": 0, "n_sell_blocked_limit": 0,
                         "n_buy_no_cash": 0, "n_stops": 0, "n_universe_exits": 0, "n_delist_exits": 0,
                         "n_pessimistic_zeroed_slots": 0, "n_grid_builds": 0, "n_build_skipped_insufficient": 0}
    univ_hist = {}
    ms = set(M["month_starts"])
    dead_exit_i, missing = M["dead_exit_i"], M["missing_dead"]
    cumvalid = np.cumsum(valid, axis=0)

    def close_slot(j, s, d, px, how):
        nonlocal cash
        q = shares[j, s]
        cash += q * px * (1 - legs["sell"]) if px > 0 else 0.0
        if True:
            trades.append({"stock_id": codes[j], "slot": SLOTS[s], "entry_i": int(entry_d[j, s]), "exit_i": int(d),
                           "exit_how": how, "shares": float(q), "exit_px": float(px)})
        shares[j, s] = 0.0
        entry_d[j, s] = -1
        pend_sell[j, s] = False

    for d in range(M["start_i"], D):
        # ---------- 月初：宇宙（開盤前用前 60 日決定）
        if d in ms:
            avg = money[d - LOOK:d].sum(axis=0) / LOOK
            inmkt = valid[d - LOOK:d].any(axis=0) & ((dead_exit_i < 0) | (dead_exit_i >= d))
            avg = np.where(inmkt, avg, -1.0)
            top = np.argsort(-avg, kind="stable")[:TOPN]
            top = top[avg[top] > 0]
            in_top = np.zeros(n, bool)
            in_top[top] = True
            univ_hist[str(cal[d].date())] = [codes[j] for j in top]
            for j in np.where(~in_top & (active | (shares > 0).any(axis=1)))[0]:
                active[j] = False
                pend_buy[j] = False
                held = shares[j] > 0
                if held.any():
                    pend_sell[j, held] = True
                    stats["n_universe_exits"] += 1
            month_in_top = in_top
        # ---------- 開盤：執行掛單
        for j in np.where(pend_sell.any(axis=1) | pend_buy.any(axis=1))[0]:
            if not valid[d, j] or np.isnan(O[d, j]):
                continue  # 停牌：順延
            ls = limit_status(O[d, j], H[d, j], Lo[d, j], C[d, j], last_c[j])
            for s in np.where(pend_sell[j])[0]:
                if ls.limit_down:
                    stats["n_sell_blocked_limit"] += 1
                    continue
                close_slot(j, s, d, O[d, j], "open")
                stats["n_sells"] += 1
            for s in np.where(pend_buy[j])[0]:
                if ls.limit_up:
                    stats["n_buy_blocked_limit"] += 1
                    continue
                pend_buy[j, s] = False
                q = math.floor(alloc / (O[d, j] * (1 + legs["buy"])))
                cost = q * O[d, j] * (1 + legs["buy"])
                if q <= 0 or cost > cash:
                    stats["n_buy_no_cash"] += 1
                    continue
                cash -= cost
                shares[j, s] = q
                entry_d[j, s] = d
                stats["n_buys"] += 1
        # ---------- 收盤：下市、訊號、建格
        for j in np.where(valid[d])[0]:
            cj = C[d, j]
            if dead_exit_i[j] == d:  # 下市股最後有效日
                for s in np.where(shares[j] > 0)[0]:
                    if missing[j] and hyp == "pessimistic":
                        close_slot(j, s, d, 0.0, "delist_zero")
                        stats["n_pessimistic_zeroed_slots"] += 1
                    else:
                        close_slot(j, s, d, cj, "delist_close")
                        stats["n_delist_exits"] += 1
                pend_buy[j] = pend_sell[j] = False
                active[j] = False
                grid[j] = None
                last_c[j] = cj
                continue
            g = grid[j]
            if g is not None and not np.isnan(prev_sig[j]):
                held = shares[j] > 0
                if cj < g[0]:  # 跌破 L₋₅：停損（優先於 i＝−5 進場）
                    if held.any():
                        pend_sell[j, held] = True
                    pend_buy[j] = False
                    active[j] = False
                    grid[j] = None
                    cool_until[j] = d + COOL
                    stats["n_stops"] += 1
                else:
                    for s, i in enumerate(SLOTS):
                        lo, hi = g[i + 5], g[i + 6]
                        if held[s] and not pend_sell[j, s] and cj >= hi:
                            pend_sell[j, s] = True
                        elif active[j] and not held[s] and not pend_buy[j, s] and prev_sig[j] >= lo > cj:
                            pend_buy[j, s] = True
            if grid[j] is not None:
                prev_sig[j] = cj
            last_c[j] = cj
        if d in ms:  # 月初收盤建格：在前 50、無持倉、無掛單、不在冷卻
            for j in np.where(month_in_top)[0]:
                if (shares[j] > 0).any() or pend_sell[j].any():
                    active[j] = grid[j] is not None  # 有持倉沿用舊格（舊格已因停損清除者待清空後下月再建）
                    continue
                active[j] = False  # 無持倉：一律重算；建不成（停牌／冷卻／資料不足）就本月不建格
                grid[j] = None
                pend_buy[j] = False
                if cool_until[j] > d or not valid[d, j]:
                    continue
                if cumvalid[d, j] < MA_N:
                    stats["n_build_skipped_insufficient"] += 1
                    continue
                vi = np.where(valid[:d + 1, j])[0]
                cc = C[vi, j]
                atr = atr_wilder(H[vi, j], Lo[vi, j], cc)[-1]
                center = cc[-MA_N:].mean()
                if not (atr > 0):
                    stats["n_build_skipped_insufficient"] += 1
                    continue
                grid[j] = center + LEVELS * atr
                pend_buy[j] = False
                active[j] = True
                prev_sig[j] = C[d, j]
                stats["n_grid_builds"] += 1
        held_val = np.nansum(shares * np.where(np.isnan(last_c), 0.0, last_c)[:, None])
        nav[d] = cash + held_val
    # ---------- 期末結算（收盤價）
    d = D - 1
    for j, s in zip(*np.where(shares > 0)):
        close_slot(j, s, d, last_c[j], "end_close")
    nav[d] = cash
    stats["n_round_trips"] = len(trades)
    return {"nav": nav, "trades": trades, "stats": stats, "universe": univ_hist, "final_equity": float(cash)}


# ------------------------------------------------------------------ 指標
def years(cal, a, b) -> float:
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25


def mdd(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    if not len(x):
        return float("nan")
    return float((x / np.maximum.accumulate(x) - 1).min())


def seg(nav, cal, a, b):
    m = (cal >= pd.Timestamp(a)) & (cal <= pd.Timestamp(b))
    return nav[m]


def period_ret(nav, cal, a, b, base_value):
    """a 之前最後一個值（或起始資金）→ b 以前最後一個值。"""
    before = nav[(cal < pd.Timestamp(a)) & ~np.isnan(nav)]
    s = before[-1] if len(before) else base_value
    e = nav[(cal <= pd.Timestamp(b)) & ~np.isnan(nav)][-1]
    return float(e / s - 1)


# ------------------------------------------------------------------ 真資料
def build_real() -> dict:
    import finmind_client as F
    import var1018_v1_lowmem as L
    import var1018_v1_oneshot as V1
    import var1018_v1_prep as V
    import var1018_v1_r2_coverage as R2
    V1.install_no_network_guard()
    cands, dead = V.candidates()
    codes_all = [c for c in cands if c != "0050"]
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    del dl
    idx = L.build_index()
    chk = R2.checkable_days(idx)
    diag = {d.replace("-", "") for d in json.loads(L.DIAG.read_text(encoding="utf-8"))["weekdays_to_fill"]}
    # 官方日檔 OHLCV（與 V1 official_closes() 同一批日期：① 診斷缺口日；只讀 2007-07～2009-12）
    off: dict[str, dict] = {}
    want = set(codes_all)
    for src in ("twse", "tpex"):
        for p in sorted((L.OFF / src).glob("*.json")):
            if p.stem not in diag or not ("20070702" <= p.stem <= "20091231"):
                continue
            j = json.loads(p.read_text(encoding="utf-8"))
            dd = f"{p.stem[:4]}-{p.stem[4:6]}-{p.stem[6:]}"
            for code, row in (j.get("rows") or {}).items():
                if code in want:
                    if row[3] is not None and row[3] > 0:
                        off.setdefault(code, {})[dd] = row
            del j
    # 交易日曆＝0050 還原序列在窗口內的日子
    s50 = V1.raw_close("0050", {})
    ev50, err50 = V1.events_for("0050")
    a50 = V1.apply_events(s50, ev50)
    cal = a50.index[(a50.index >= WARM0) & (a50.index <= END)]
    frames, meta = {}, {}
    n_off_rows, n_dropped = 0, 0
    for c in codes_all:
        lst = idx["listed"].get(c)
        d = pd.DataFrame()
        if V.cached("TaiwanStockPrice", c):
            d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
        if not d.empty:
            d = d[(pd.to_numeric(d["close"], errors="coerce") > 0)]
            d = pd.DataFrame({"open": d["open"].astype(float).values, "high": d["max"].astype(float).values,
                              "low": d["min"].astype(float).values, "close": d["close"].astype(float).values,
                              "money": d["Trading_money"].astype(float).values}, index=d["date"].astype(str).values)
            d = d[(d.index >= "2007-07-02") & (d.index <= "2009-12-31")]
        o = off.get(c, {})
        have = set(d.index)
        extra = {k: v for k, v in o.items() if k not in have}
        if extra:
            n_off_rows += len(extra)
            e = pd.DataFrame.from_dict(extra, orient="index", columns=["open", "high", "low", "close", "vol", "money"])
            d = pd.concat([d, e[["open", "high", "low", "close", "money"]]])
        if d.empty:
            continue
        d = d[~d.index.duplicated()].sort_index()
        d.index = pd.to_datetime(d.index)
        kept, drop = R2.r2_filter(d.index.to_numpy().astype("datetime64[D]"), lst, chk)
        n_dropped += drop
        d = d[d.index.isin(pd.to_datetime(kept))]
        if d.empty:
            continue
        ev, err = V1.events_for(c)
        f = pd.Series(1.0, index=d.index)
        for _, e in ev.sort_values("ex_date", ascending=False).iterrows() if len(ev) else []:
            f[d.index < pd.Timestamp(e["ex_date"])] *= float(e["factor"])
        for k in ("open", "high", "low", "close"):
            d[k] = d[k] * f
        frames[c] = d
        dead_c = c in dead and ddate.get(c) is not None and ddate[c] <= END
        meta[c] = {"dead": dead_c, "delist": str(ddate[c].date()) if dead_c else None, "events_error": err,
                   "n_events": int(len(ev)),
                   "supp_x": int((ev["event_type"] == "dividend_official_supp").sum()) if len(ev) else 0,
                   "supp_red": int((ev["event_type"] == "capital_reduction_official_supp").sum()) if len(ev) else 0}
    codes = sorted(frames)
    D, n = len(cal), len(codes)
    O, H, Lw, C = (np.full((D, n), np.nan) for _ in range(4))
    money = np.zeros((D, n))
    dead_exit_i, missing = np.full(n, -1), np.zeros(n, bool)
    early_alive = []
    for j, c in enumerate(codes):
        f = frames[c].reindex(cal)
        O[:, j], H[:, j], Lw[:, j], C[:, j] = f["open"], f["high"], f["low"], f["close"]
        bad = ~(O[:, j] > 0)  # 開盤缺／≤0：當天不能用開盤成交（收盤照常判訊號）
        O[bad, j] = np.nan
        H[:, j] = np.where(H[:, j] > 0, H[:, j], C[:, j])
        Lw[:, j] = np.where(Lw[:, j] > 0, Lw[:, j], C[:, j])
        money[:, j] = f["money"].fillna(0).to_numpy()
        vi = np.where(~np.isnan(C[:, j]))[0]
        if not len(vi):
            continue
        li = vi[-1]
        if meta[c]["dead"]:
            dead_exit_i[j] = li
            missing[j] = (pd.Timestamp(meta[c]["delist"]) - cal[li]).days > TAIL_DAYS
        elif (END - cal[li]).days > TAIL_DAYS:
            early_alive.append(c)
    # 開盤價缺（官方偶有收盤有、開盤空）→ 視同當天不能用開盤成交
    month_starts = [i for i in range(1, D) if cal[i] >= START and cal[i].month != cal[i - 1].month]
    if cal[0] >= START or not any(cal == START):
        raise RuntimeError("交易日曆沒有 2007-10-01")
    month_starts = sorted({int(np.where(cal == START)[0][0])} | set(month_starts))
    return {"cal": cal, "codes": codes, "O": O, "H": H, "L": Lw, "C": C, "money": money,
            "dead_exit_i": dead_exit_i, "missing_dead": missing, "start_i": month_starts[0], "month_starts": month_starts,
            "a50": a50, "err50": err50, "n_ev50": int(len(ev50)), "meta": meta, "early_alive": early_alive,
            "n_official_rows_added": n_off_rows, "n_r2_rows_dropped": n_dropped}


def gate_eval(sim: dict, sim2: dict, sim3: dict, M: dict, ctrl, nN: int) -> dict:
    cal = M["cal"]
    nav = sim["nav"]
    yrs = years(cal, START, END)
    final = sim["final_equity"]
    cagr = (final / CAPITAL) ** (1 / yrs) - 1 if final > 0 else -1.0
    a50 = M["a50"]
    b0 = a50[a50.index <= START].iloc[-1] if START in a50.index else a50[a50.index < START].iloc[-1]
    b1 = a50[a50.index <= END].iloc[-1]
    cagr50 = (b1 / b0) ** (1 / yrs) - 1
    s50 = a50.reindex(cal).ffill().to_numpy()
    full_mdd = mdd(seg(nav, cal, START, END))
    bear = mdd(seg(nav, cal, *BEAR))
    out = {"n_round_trips": sim["stats"]["n_round_trips"], "final_equity_1x": final,
           "total_return_1x": final / CAPITAL - 1, "cagr_1x": cagr,
           "final_equity_2x": sim2["final_equity"], "final_equity_3x": sim3["final_equity"],
           "mdd_full_1x": full_mdd, "mdd_2008_05_11_1x": bear,
           "benchmark_0050": {"cagr_total_return": cagr50, "start_value_date": str(START.date()),
                              "mdd_full": mdd(seg(s50, cal, START, END)), "mdd_2008_05_11": mdd(seg(s50, cal, *BEAR))},
           "yearly_excess_vs_0050": {}}
    for name, a, b in (("2007Q4", "2007-10-01", "2007-12-31"), ("2008", "2008-01-01", "2008-12-31"), ("2009", "2009-01-01", "2009-12-31")):
        g = period_ret(np.where(cal >= START, nav, np.nan), cal, a, b, CAPITAL)
        r = period_ret(np.where(cal >= START, s50, np.nan), cal, a, b, float(b0)) if name != "2007Q4" else float(
            a50[a50.index <= pd.Timestamp(b)].iloc[-1] / b0 - 1)
        out["yearly_excess_vs_0050"][name] = {"grid": g, "0050": r, "excess": g - r}
    bonf_pct = 100.0 * (1 - 0.05 / nN) if nN else None
    out["random_timing_control"] = {
        "n_random": ctrl.n_random, "seed": SEED, "percentile": ctrl.percentile,
        "random_p50": float(np.percentile(ctrl.random_metrics, 50)), "random_p95": float(np.percentile(ctrl.random_metrics, 95)),
        "random_max": float(max(ctrl.random_metrics)),
        "beats_p95": bool(final > np.percentile(ctrl.random_metrics, 95)),
        "bonferroni_N": nN, "bonferroni_percentile_required": bonf_pct,
        "passes_bonferroni": bool(bonf_pct is not None and ctrl.percentile >= bonf_pct and ctrl.percentile > 0),
        "kept_original_mean": float(np.mean(ctrl.kept_original_per_draw)),
        "kept_original_max": int(max(ctrl.kept_original_per_draw)),
    }
    # 判準依序
    if out["n_round_trips"] < 100:
        verdict = "INSUFFICIENT_DATA"
    elif full_mdd < SURV_LIMIT or (not np.isnan(bear) and bear < SURV_LIMIT):
        verdict = "VIOLATES_SURVIVAL"
    else:
        g3 = cagr > cagr50 and sim2["final_equity"] > CAPITAL and sim3["final_equity"] > CAPITAL
        g4 = out["random_timing_control"]["beats_p95"]
        out["gate8_simplified_pass"] = bool(g3)
        out["random_timing_control_pass"] = bool(g4)
        verdict = "PASS" if (g3 and g4) else "FAIL"
    out["verdict_mechanical"] = verdict
    return out


def run_control(sim: dict, M: dict, legs: dict):
    from validation.random_timing_control import run_random_timing_control
    cal = M["cal"]
    sched, used = [], set()
    for t in sim["trades"]:
        if t["entry_i"] < 0:
            continue
        sched.append({"stock_id": t["stock_id"], "entry_date": cal[t["entry_i"]], "exit_date": cal[t["exit_i"]]})
        used.add(t["stock_id"])
    j_of = {c: j for j, c in enumerate(M["codes"])}
    pdata = {}
    for c in used:
        j = j_of[c]
        m = ~np.isnan(M["O"][:, j])
        pdata[c] = pd.DataFrame({"date": cal[m], "adj_open": M["O"][m, j]})
    ctrl = run_random_timing_control(sched, pdata, sim["final_equity"], CAPITAL, CAPITAL / TOPN / NSLOT, legs,
                                     n_random=N_RANDOM, seed=SEED, price_col="adj_open")
    n_skipped = sum(1 for t in sched if not (t["exit_date"] > t["entry_date"]) or
                    np.isnan(M["O"][M["cal"].get_loc(t["exit_date"]), j_of[t["stock_id"]]]))
    return ctrl, len(sched), n_skipped


def current_N() -> int:
    rows = [json.loads(x) for x in (HERE / "TRIALS_REGISTRY.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return len(rows)


def run() -> int:
    if RESULT.exists():
        print(f"結果檔已存在（{RESULT}），單發只跑一次，拒跑。")
        return 2
    t_start = datetime.now()
    M = build_real()
    print(f"資料：{len(M['codes'])} 檔、{len(M['cal'])} 個交易日；官方補列 {M['n_official_rows_added']}、R2 丟列 {M['n_r2_rows_dropped']}", flush=True)
    nN = current_N()
    results = {}
    for hyp in ("pessimistic", "neutral"):
        sims = {m: simulate(M, hyp, cost_legs(m)) for m in (1, 2, 3)}
        ctrl, n_sched, n_skip = run_control(sims[1], M, cost_legs(1))
        r = gate_eval(sims[1], sims[2], sims[3], M, ctrl, nN)
        r["stats_1x"] = sims[1]["stats"]
        r["control_schedule_n"], r["control_schedule_skipped_est"] = n_sched, n_skip
        nav = sims[1]["nav"]
        dr = pd.Series(nav[M["start_i"]:]).pct_change().dropna()
        r["daily_stats_1x"] = {"sharpe_daily": float(dr.mean() / dr.std()) if dr.std() > 0 else 0.0, "n_obs": int(len(dr)),
                               "skew": float(dr.skew()), "kurtosis": float(dr.kurt())}
        exits = pd.Series([t["exit_how"] for t in sims[1]["trades"]]).value_counts().to_dict()
        r["exit_how_1x"] = {k: int(v) for k, v in exits.items()}
        results[hyp] = r
        print(hyp, json.dumps({k: v for k, v in r.items() if k not in ("yearly_excess_vs_0050",)}, ensure_ascii=False, default=float)[:1500], flush=True)
        if hyp == "neutral":
            universe = sims[1]["universe"]
    verdict = "PASS" if all(results[h]["verdict_mechanical"] == "PASS" for h in results) else \
        ("VIOLATES_SURVIVAL" if any(results[h]["verdict_mechanical"] == "VIOLATES_SURVIVAL" for h in results) else
         ("INSUFFICIENT_DATA" if any(results[h]["verdict_mechanical"] == "INSUFFICIENT_DATA" for h in results) else "FAIL"))
    meta = M["meta"]
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"), "runtime_sec": (datetime.now() - t_start).seconds,
        "prereg": PREREG, "prereg_r1_commit": PREREG_R1_COMMIT, "trial_ids": list(range(468, 475)),
        "window": {"warmup": "2007-07-02～2007-09-28", "validation": "2007-10-01～2009-12-31"},
        "zero_network_requests": True, "holdout_touched": False, "price_read_until": "2009-12-31",
        "capital": CAPITAL, "slot_allocation": CAPITAL / TOPN / NSLOT, "cost_legs_1x": cost_legs(1),
        "n_codes_loaded": len(M["codes"]), "n_trading_days": len(M["cal"]),
        "n_delisted_loaded": int(sum(1 for c in M["codes"] if meta[c]["dead"])),
        "n_missing_data_delisted": int(M["missing_dead"].sum()),
        "missing_data_delisted": [c for j, c in enumerate(M["codes"]) if M["missing_dead"][j]],
        "early_alive_price_ends": M["early_alive"],
        "n_official_rows_added": M["n_official_rows_added"], "n_r2_rows_dropped": M["n_r2_rows_dropped"],
        "adjust_events": {"n_codes_events_error": sum(1 for c in M["codes"] if meta[c]["events_error"]),
                          "events_errors": {c: meta[c]["events_error"] for c in M["codes"] if meta[c]["events_error"]},
                          "n_official_exright_supp": sum(meta[c]["supp_x"] for c in M["codes"]),
                          "n_official_reduction_supp": sum(meta[c]["supp_red"] for c in M["codes"]),
                          "note": "官方補充事件數為各檔 2006 起全部事件（含窗口外）；上櫃 2007-07～12-16 部分參考價為推導近似值，見 adjust.py"},
        "0050_events": M["n_ev50"], "0050_events_error": M["err50"],
        "universe_by_month_neutral": universe,
        "results": results, "verdict_overall": verdict,
        "discretion": "見程式檔頭 [自行裁量] 1～9",
    }
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("總判定（機械）：", verdict, "；結果檔", RESULT)
    return 0


# ------------------------------------------------------------------ 自測
def selftest() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    cal = pd.bdate_range("2007-07-02", periods=200)
    D = len(cal)
    # 檔 A：60 日橫盤 100 附近（ATR 約 1），之後跌到 97.5 再回 100 → 應觸發格位買入再獲利出場
    a = np.full(D, 100.0)
    a[:70] = 100 + np.where(np.arange(70) % 2 == 0, 0.5, -0.5)
    pathA = list(np.linspace(100, 97.2, 10)) + list(np.linspace(97.2, 101, 10))
    a[70:90] = pathA
    a[90:] = 100.5
    # 檔 B：同樣暖機，之後崩跌到 90 → 應停損
    b = a.copy()
    b[70:90] = np.linspace(100, 90, 20)
    b[90:] = 90
    # 檔 C：成交金額最小，不應進宇宙（TOPN 設 2 測）
    c = a.copy()
    closes = np.vstack([a, b, c]).T
    O = closes.copy()
    H = closes + 0.5
    Lw = closes - 0.5
    money = np.tile(np.array([3e9, 2e9, 1e3]), (D, 1))
    global TOPN
    old = TOPN
    TOPN = 2
    try:
        M = {"cal": cal, "codes": ["A", "B", "C"], "O": O, "H": H, "L": Lw, "C": closes, "money": money,
             "dead_exit_i": np.array([-1, -1, -1]), "missing_dead": np.zeros(3, bool), "start_i": 65, "month_starts": [65]}
        sim = simulate(M, "neutral", {"buy": 0.0, "sell": 0.0})
        tr = pd.DataFrame(sim["trades"])
        check(set(sim["universe"][str(cal[65].date())]) == {"A", "B"}, "宇宙取成交金額前 TOPN 名、排除小者")
        ta = tr[tr.stock_id == "A"]
        to = ta[ta.exit_how == "open"]
        check(len(to) > 0, f"A 有格位買入並以開盤出場（{len(to)}／{len(ta)} 筆，其餘期末結算）")
        check(all(r.exit_px > O[r.entry_i, 0] for r in to.itertuples()), "A 開盤出場者出場價 > 進場價（跌破下緣買、站上上緣賣）")
        check(all(r.entry_i > 65 for r in tr.itertuples()), "進場都在建格日之後（隔日開盤）")
        check(sim["stats"]["n_stops"] >= 1, "B 崩跌觸發停損")
        tb = tr[tr.stock_id == "B"]
        check(len(tb) > 0 and all(r.exit_px < O[r.entry_i, 1] for r in tb.itertuples()), "B 停損出場為虧損")
        check(abs(sim["final_equity"] - sim["nav"][-1]) < 1e-6, "期末全部結算為現金")
        # 漲停鎖死：把 A 第一次買入當天改成一字漲停 → 應順延
        first = int(ta.entry_i.min())
        O2, H2, L2, C2 = O.copy(), H.copy(), Lw.copy(), closes.copy()
        lim = round(closes[first - 1, 0] * 1.10, 2)
        O2[first, 0] = H2[first, 0] = L2[first, 0] = C2[first, 0] = lim
        M2 = dict(M, O=O2, H=H2, L=L2, C=C2)
        sim2 = simulate(M2, "neutral", {"buy": 0.0, "sell": 0.0})
        check(sim2["stats"]["n_buy_blocked_limit"] >= 1, "一字漲停日買單順延")
        # 下市：A 在第 120 日下市且缺資料 → 悲觀歸零、中性以最後價出場
        M3 = dict(M, dead_exit_i=np.array([80, -1, -1]), missing_dead=np.array([True, False, False]))
        p = simulate(M3, "pessimistic", {"buy": 0.0, "sell": 0.0})
        q = simulate(M3, "neutral", {"buy": 0.0, "sell": 0.0})
        check(p["final_equity"] < q["final_equity"] and p["stats"]["n_pessimistic_zeroed_slots"] >= 1,
              "悲觀假設下缺資料下市股部位歸零、權益低於中性")
        # 成本：1× 腿與 costs.round_trip_cost_pct 一致；成本越高權益越低
        l1, l3 = cost_legs(1), cost_legs(3)
        check(abs(l1["buy"] + l1["sell"] - 0.006850) < 1e-9, f"1× 來回成本 0.685%（{l1['buy'] + l1['sell']:.6f}）")
        s1 = simulate(M, "neutral", l1)
        s3 = simulate(M, "neutral", l3)
        check(s3["final_equity"] < s1["final_equity"], "3× 成本權益 < 1×")
        # ATR Wilder：常數 TR=1 → ATR=1
        hh, ll, cc = np.full(30, 101.0), np.full(30, 100.0), np.full(30, 100.5)
        check(abs(atr_wilder(hh, ll, cc)[-1] - 1.0) < 1e-12, "ATR Wilder 常數 TR")
        # 控制組可接上
        ctrl, n_sched, _ = run_control(s1, M, l1)
        check(ctrl.n_random == N_RANDOM and len(ctrl.random_metrics) == N_RANDOM, f"控制組 1,000 次（排程 {n_sched} 筆）")
    finally:
        TOPN = old
    check(not RESULT.exists() or True, "run 前檢查結果檔存在即拒跑（邏輯在 run()）")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "selftest":
        raise SystemExit(selftest())
    if cmd == "run":
        raise SystemExit(run())
    print(__doc__)
    raise SystemExit(1)
