# -*- coding: utf-8 -*-
"""模擬 N：個股網格「只在區間市啟動」前向紙上追蹤（先.一三六-B7；日頻）。

規則照 `docs/PREREG_STOCK_GRID_V2_RANGE_FORWARD_FINAL.md`（宇宙 50／MA60／N＝20 共用／10 格／濾網 1×g，一次定死），
其餘語意沿用 #468 `research/stock_grid_oneshot.py`（L₋₅…L₊₅、i＝−5 進場與停損同條件時停損優先、順延規則）。
- 每月第一個交易日：當天在市普通股排「前 60 個交易日平均成交金額」（不含當天；無列記 0）取前 50；跌出者既有格位當天開盤出清。
  在前 50、無持倉、不在冷卻者重建格：中心＝前一交易日的 60 日均線（還原收盤）、g＝ATR20（Wilder，還原高低收）；
  濾網 |MA60(t) − MA60(t−20)| ≤ g（t＝前一交易日）不符 → 本月不建格。格線在建格當天收盤後生效（同 #468）。
- 收盤由上往下跌破格下緣 Lᵢ 且格位空 → 隔日開盤買一份；收盤站上 Lᵢ₊₁ → 隔日開盤賣；收盤跌破 L₋₅ → 隔日開盤全出、冷卻 20 個交易日。
- 每格固定金額＝100 萬 ÷ 50 ÷ 10；現金不足一份不買；開盤一字漲停（買）／跌停（賣）鎖死 → 買單取消、賣單順延
  （`costs.limit_status()`，還原開高低收對前一還原收盤）；停牌日不成交、掛單順延；下市以最後可得價出場。
- 影子網格（不加濾網，只記帳不判定，PREREG §4-5 控制組用）：research/data/paper_14_shadow_log.jsonl。
- 帳本每個交易日一列（nav／cash／positions 與共用框架同格式，另含 grid_state 供下一次接續）；月初列另記
  eligible_nofilter（不看濾網會建格的股票）與 built（實際建格），判定時的濾網控制組由它抽樣。
資料只讀 data/price_history（還原收盤、原始開高低收）＋data/listed_universe.json，零額外外部請求。自身失敗只警告、exit 0。

[自行裁量]（總司令／Cowork 可推翻）：
1. 前向 price_history 只留約 90 個交易日，無法每次從起跑日重播 → 逐日增量，狀態存在帳本最後一列。
2. 部位用小數單位（同共用框架），不做整股取整。
3. 還原開高低＝原始值 ×（還原收盤 ÷ 原始收盤）。
"""
from __future__ import annotations

import paper_forward_common as C
from validation.costs import limit_status

ROOT = C.ROOT
TOPN, MA_N, N, NSLOT = 50, 60, 20, 10
LOOK = 60
SLOTS = list(range(-5, 5))
ALLOC = C.INITIAL / TOPN / NSLOT
START = "2027-01-04"
JUDGE = "2029-01-02"
PREREG = "docs/PREREG_STOCK_GRID_V2_RANGE_FORWARD_FINAL.md"
TRIAL_NO = 485  # register_trial() #485（2026-10-27 互動視窗 先.一三七-1 登記）


def adj_ohlc(px: C.Px, code: str, d: str):
    i = (px.idx.get(code) or {}).get(d)
    if i is None:
        return None
    r = px.rows[code][i]
    c, ac = r.get("close"), r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
    if not c or ac is None or any(r.get(k) is None for k in ("open", "high", "low")):
        return None
    f = float(ac) / float(c)
    return float(r["open"]) * f, float(r["high"]) * f, float(r["low"]) * f, float(ac)


def hist(px: C.Px, code: str, upto: str) -> list:
    """≤upto 的有效還原 (h, l, c) 列。"""
    out = []
    for r in px.rows.get(code) or []:
        if r["date"] > upto:
            break
        v = adj_ohlc(px, code, r["date"])
        if v:
            out.append(v[1:])
    return out


def atr_wilder(rows: list):
    if len(rows) < N + 1:
        return None
    tr = [rows[0][0] - rows[0][1]] + [max(h - l, abs(h - rows[k - 1][2]), abs(l - rows[k - 1][2]))
                                      for k, (h, l, _c) in enumerate(rows) if k > 0]
    a = sum(tr[:N]) / N
    for t in tr[N:]:
        a = (a * (N - 1) + t) / N
    return a


def grid_params(px: C.Px, code: str, t: str):
    """t＝建格日前一交易日。回傳 (center, g, drift) 或 None（資料不足）。"""
    rows = hist(px, code, t)
    if len(rows) < MA_N + N:
        return None
    cs = [r[2] for r in rows]
    ma_t = sum(cs[-MA_N:]) / MA_N
    ma_tn = sum(cs[-MA_N - N:-N]) / MA_N
    g = atr_wilder(rows)
    if not g or g <= 0:
        return None
    return ma_t, g, abs(ma_t - ma_tn)


def month_universe(px: C.Px, d: str, active: set) -> list:
    cal = px.calendar
    i = cal.index(d)
    win = cal[max(0, i - LOOK):i]
    avg = {}
    for code in active:
        if not C.is_common(code):
            continue
        idx = px.idx.get(code) or {}
        tot = sum(float(px.rows[code][idx[x]].get("turnover") or 0) for x in win if x in idx)
        if tot > 0:
            avg[code] = tot / LOOK
    return [c for c, _ in sorted(avg.items(), key=lambda kv: (-kv[1], kv[0]))[:TOPN]]


def empty_state() -> dict:
    return {"cash": C.INITIAL, "grids": {}, "cells": {}, "pend_buy": {}, "pend_sell": {}, "cool_left": {},
            "last_c": {}, "month": None, "universe": []}


def _close_cell(st, code, s, d, px_, how, closed):
    cell = st["cells"][code].pop(s)
    st["cash"] += cell["units"] * px_ * (1 - C.SELL)
    closed.append({"stock_id": code, "slot": int(s), "entry_date": cell["entry_date"], "exit_date": d,
                   "entry_px": cell["entry_px"], "exit_px": round(px_, 6),
                   "ret_gross": round(px_ / cell["entry_px"] - 1, 6) if cell["entry_px"] else None, "exit_reason": how})
    if not st["cells"][code]:
        st["cells"].pop(code)
    sp = st["pend_sell"].get(code) or []
    if s in sp:
        sp.remove(s)


def process_day(px: C.Px, d: str, st: dict, active: set, use_filter: bool) -> dict:
    """處理交易日 d（開盤執行掛單 → 收盤訊號 → 月初收盤建格），就地更新 st，回傳帳本列。"""
    cal = px.calendar
    prev = px.prev_trading_day(d)
    closed, info = [], {}
    st["cells"] = {c: {int(k): v for k, v in cs.items()} for c, cs in st["cells"].items()}
    for k in ("pend_buy", "pend_sell"):
        st[k] = {c: [int(s) for s in v] for c, v in st[k].items() if v}
    for c in list(st["cool_left"]):
        st["cool_left"][c] -= 1
        if st["cool_left"][c] <= 0:
            st["cool_left"].pop(c)
    month_start = st["month"] != d[:7]
    if month_start:  # 月初開盤前：宇宙；跌出者既有格位當天開盤出清
        uni = month_universe(px, d, active)
        info["universe_n"] = len(uni)
        for c in set(st["grids"]) | set(st["cells"]):
            if c not in uni:
                st["grids"].pop(c, None)
                st["pend_buy"].pop(c, None)
                if st["cells"].get(c):
                    st["pend_sell"][c] = sorted(st["cells"][c])
        st["universe"], st["month"] = uni, d[:7]
    # 開盤：執行掛單
    for c in sorted(set(st["pend_sell"]) | set(st["pend_buy"])):
        o = adj_ohlc(px, c, d)
        if not o:
            if c not in active and px.close_on(c, d) is None and not any(r["date"] > d for r in px.rows.get(c) or []):
                for s in list((st["cells"].get(c) or {})):  # 下市：最後可得價出場
                    _close_cell(st, c, s, d, px.close_le(c, d) or st["cells"][c][s]["entry_px"], "delisted", closed)
                st["pend_buy"].pop(c, None)
                st["pend_sell"].pop(c, None)
            continue  # 停牌：順延
        ls = limit_status(o[0], o[1], o[2], o[3], st["last_c"].get(c) or 0)
        for s in list(st["pend_sell"].get(c) or []):
            if ls.limit_down or s not in (st["cells"].get(c) or {}):
                continue
            _close_cell(st, c, s, d, o[0], "open", closed)
        if not st["pend_sell"].get(c):
            st["pend_sell"].pop(c, None)
        for s in st["pend_buy"].pop(c, []):
            if ls.limit_up:
                info["buy_blocked_limit"] = info.get("buy_blocked_limit", 0) + 1
                continue
            cost = ALLOC
            if cost > st["cash"] + 1e-9:
                info["buy_no_cash"] = info.get("buy_no_cash", 0) + 1
                continue
            st["cash"] -= cost
            st["cells"].setdefault(c, {})[s] = {"units": ALLOC / (o[0] * (1 + C.BUY)), "entry_date": d, "entry_px": round(o[0], 6)}
    # 收盤：訊號
    for c in sorted(set(st["grids"]) | set(st["cells"])):
        o = adj_ohlc(px, c, d)
        if not o:
            continue
        cj = o[3]
        g = st["grids"].get(c)
        if g and g.get("prev_sig") is not None:
            lines = g["lines"]
            held = st["cells"].get(c) or {}
            if cj < lines[0]:  # 停損（優先於 i＝−5 進場）
                if held:
                    st["pend_sell"][c] = sorted(held)
                st["pend_buy"].pop(c, None)
                st["grids"].pop(c)
                st["cool_left"][c] = N
                info["stops"] = info.get("stops", 0) + 1
            else:
                for s in SLOTS:
                    lo, hi = lines[s + 5], lines[s + 6]
                    if s in held and s not in (st["pend_sell"].get(c) or []) and cj >= hi:
                        st["pend_sell"].setdefault(c, []).append(s)
                    elif s not in held and s not in (st["pend_buy"].get(c) or []) and g["prev_sig"] >= lo > cj:
                        st["pend_buy"].setdefault(c, []).append(s)
        if c in st["grids"]:
            st["grids"][c]["prev_sig"] = cj
        st["last_c"][c] = cj
    if month_start and prev:  # 月初收盤建格
        elig, built = [], []
        for c in st["universe"]:
            if st["cells"].get(c) or st["pend_sell"].get(c):
                continue  # 有持倉沿用舊格
            st["grids"].pop(c, None)
            st["pend_buy"].pop(c, None)
            if c in st["cool_left"] or px.close_on(c, d) is None:
                continue
            gp = grid_params(px, c, prev)
            if not gp:
                continue
            center, gg, drift = gp
            elig.append(c)
            if use_filter and drift > gg:
                continue
            st["grids"][c] = {"lines": [round(center + k * gg, 6) for k in range(-5, 6)], "prev_sig": adj_ohlc(px, c, d)[3],
                              "built": d, "g": round(gg, 6)}
            built.append(c)
        info.update({"eligible_nofilter": elig, "built": built})
    for c in list(st["last_c"]):
        if c not in st["grids"] and c not in st["cells"]:
            st["last_c"].pop(c)
    positions, val = {}, 0.0
    for c, cs in st["cells"].items():
        v = px.close_on(c, d) or px.close_le(c, d) or 0.0
        u = sum(x["units"] for x in cs.values())
        val += u * v
        positions[c] = {"units": u, "entry_date": min(x["entry_date"] for x in cs.values()),
                        "entry_px": round(sum(x["units"] * x["entry_px"] for x in cs.values()) / u, 6) if u else None}
    used = sum(len(cs) for cs in st["cells"].values())
    rec = {"date": d, "event": "rebalance" if month_start else ("trade" if closed or info else "mark"),
           "nav": round(st["cash"] + val, 2), "cash": round(st["cash"], 2), "positions": positions,
           "closed_trades": closed, "cells_used": used, "capital_use_pct": round(val / (st["cash"] + val) * 100, 2) if st["cash"] + val else None,
           **info, "grid_state": st}
    if month_start:
        rec["rebalance_month"] = d[:7]
    return rec


def make_spec(shadow: bool) -> C.Spec:
    key = "paper_14_shadow" if shadow else "paper_14"
    return C.Spec(key=key, label="模擬 N 影子網格（不加濾網，控制組用）" if shadow else "模擬 N 個股網格（只在區間市啟動）",
                  note=("同規則但不看區間市濾網；只記帳、不判定" if shadow else
                        "成交值前 50 檔、月初中心 MA60、格距 ATR20、上下各 5 格；MA60 近 20 日漂移 ≤ 1 格才建格；每日收盤判斷、隔日開盤成交；成本 1×"),
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="grid", top_n=TOPN,
                  log_path=ROOT / "research" / "data" / f"{key}_log.jsonl",
                  out_path=(ROOT / "research" / "data" / "paper_14_shadow.json") if shadow else (ROOT / "data" / "paper_14.json"),
                  judge_text=("2029-01-02 後判一次：已平倉（格位一進一出）≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20270104）；"
                              "濾網控制組 200 次（seed 20261024）> 第 95 百分位"),
                  known_limit="日頻需每日排程，漏跑照實記實際成交日、不回補；24 個月交易數可能不足；前向段不一定出現單邊趨勢")


def run_one(spec: C.Spec, px: C.Px, active: set, use_filter: bool) -> dict:
    log = C.read_log(spec)
    day = px.latest_date()
    if not day or day < spec.start_not_before:
        C.write_summary(spec, px, log, {"why_not_started": f"{spec.start_not_before} 起跑（PREREG 寫死，不倒填）"})
        return {"state": "NOT_STARTED", "day": day, "start": spec.start_not_before}
    last = log[-1] if log else None
    st = (last or {}).get("grid_state") or empty_state()
    done = []
    for d in [x for x in px.calendar if x >= spec.start_not_before and (not last or x > last["date"])]:
        rec = process_day(px, d, st, active, use_filter)
        if not log and not done:
            rec["event"] = "inception"
        C._append(spec, rec)
        st = rec["grid_state"]
        done.append((d, rec["event"]))
    C.write_summary(spec, px, C.read_log(spec))
    return {"state": "PROCESSED" if done else "HOLD", "day": day, "processed": done}


def step() -> dict:
    px = C.load_px()
    active = set((C.load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    return {"main": run_one(make_spec(False), px, active, True), "shadow": run_one(make_spec(True), px, active, False)}


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 N"))
