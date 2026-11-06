# -*- coding: utf-8 -*-
"""先.一五四-1a ① 紙上優化軌 F12（Weinstein 第二階段，B 崩盤段條件版）每日訊號產生器——研究帽產物，零外部請求。

策略（照 research/DRAWDOWN_FIX.md 1 節 F12 列＋reaudit_optimized_batch2_weinstein.py 最優格 `150_0_20_1.0`，這裡不調參）：
  底層（1×，逐條對照 research/backtest/engine.py run_backtest() 的流程重寫，因為引擎會擋 2025 起的資料、不能直接呼叫）：
    每個交易日依序 ①執行前一日排定的單（成交價＝當日還原收盤；買單遇鎖漲停、賣單遇鎖跌停、當天沒價格 → 順延一日；
    買進股數＝int(當下權益÷20 ÷ (價×(1+買方成本)))，現金不夠就放棄）②持股風控：還原收盤 < 自身 150 日均線 → 排隔日賣
    （個股停損不設＝引擎 stop_loss_pct=1.0）③換股日（起跑日起第 0、21、42… 個交易日）：分數＝60 日報酬，
    條件＝還原收盤 > MA150 且 MA150 > 10 個交易日前的 MA150；持股不在名單 → 排隔日賣；空位依分數高到低排隔日買，最多 20 檔
    （大盤閘門關）④以還原收盤 mark-to-market（當天沒價格用最近有效價）。
    成本照 validation.costs（手續費 0.1425%×兩邊、證交稅 normal、滑價 5bps，1×），同引擎預設。
  帳戶層（照 drawdown_fix.overlay()）：曝險＝2.0×崩盤條件係數（前一日資訊）；崩盤條件＝加權指數 < 120 日均線且
    距 252 日高點跌 > 20% → 係數 0（空手領無風險利率）；超過 1 倍的部分付融資 6.5%/年；帳戶自高點回撤 10% 清倉、停 21 個交易日。
宇宙〔沿用回測〕：#133 抽樣宇宙（research/data/reaudit_ssu_loaded.pkl 的 236 個代號，第一次跑時存成 research/data/paper_opt/f12_universe.json）。
  回測宇宙本身含 ETF／債券 ETF（例：00642U、00755B），照回測原樣保留，不另外濾掉。

資料（全部本機）：
  - 2025-10-28～2026-10-30：research/data/paper_9_lookback/{twse,tpex}/YYYYMMDD.json（官方全市場日檔，模擬 I 回看期已抓好）。
    還原報酬＝收盤÷(收盤−漲跌)−1（漲跌是相對除權息參考價，等於官方口徑的還原日報酬）。
  - 之後：data/price_history（每日排程，還原收盤 adj_close），日報酬＝adj_close 比值。
  - 兩段合併存 research/data/paper_opt/f12_bars.json（只存原始 OHLC＋日報酬；還原價位每次重新累乘，避免 price_history 因新除權息整段重縮放造成不一致）。
  - 加權指數：data/market_tw.json 近 60 日官方收盤＋research/data/paper_8_taiex_closes.json（模擬 H 已累積），併入
    research/data/paper_opt/taiex_closes.json 自己累積；〔自行裁量〕更早的日子沒有官方收盤，用 0050 原始收盤日報酬往前接
    （價格報酬、近似價格指數；只影響 120 日均線與 252 日高點的前段），存檔時標 proxy。
  - 無風險利率：data/rf_monthly.json 最新月份（央行一個月定存）。

輸出（append-only，已寫過的日期不改）：
  research/data/paper_opt/ledger_F12.jsonl  每個交易日一行（起跑日 2026-11-09 起；ret＝帳戶層日報酬，另記 1× 底層）
  research/data/paper_opt/state_F12.json    底層持股／排定單／帳戶層狀態
用法：python research/paper_opt_f12.py           每日跑（只處理還沒寫過的交易日）
      python research/paper_opt_f12.py --probe   只印「假設今天是換股日」的名單與崩盤條件，不寫帳
非投資建議。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
OUT = Path(os.environ.get("PAPER_OPT_OUT") or HERE / "data" / "paper_opt")  # 環境變數只給自測換暫存目錄
LOOKBACK = HERE / "data" / "paper_9_lookback"
LEDGER = OUT / "ledger_F12.jsonl"
STATE = OUT / "state_F12.json"
BARS = OUT / "f12_bars.json"
UNIV = OUT / "f12_universe.json"
TAIEX = OUT / "taiex_closes.json"

sys.path.insert(0, str(HERE))
from validation import costs as costmod  # noqa: E402  （只呼叫、不改）

START = "2026-11-09"
MA_N, RISE_LB, MOM_WIN, TOP_N, REBAL = 150, 10, 60, 20, 21
SLIP_BPS = 5.0
BUY_RATE = costmod.COMMISSION_RATE + SLIP_BPS / 10_000  # 同 engine.buy_leg_rate()（discount=1、cost_multiplier=1）
L, ACC_STOP, COOLDOWN = 2.0, 0.10, 21
CRASH_N, CRASH_X, CRASH_Y = 120, 0.20, 0.0
MARGIN_RATE = 0.065 / 252.0
INIT = 1_000_000.0
MIN_TRADED = 1000  # price_history 某日少於 1000 檔有成交不算完整交易日（同 paper_opt_pq）〔自行裁量〕


def _rj(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _wj(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


# ------------------------------------------------------------------ 宇宙
def universe() -> list[str]:
    u = _rj(UNIV, None)
    if u:
        return u["ids"]
    import pickle
    d = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    ids = sorted(d.keys())
    _wj(UNIV, {"source": "research/data/reaudit_ssu_loaded.pkl（#133 抽樣宇宙，同 F12 回測）", "ids": ids})
    return ids


# ------------------------------------------------------------------ 價格
def build_bars(ids: list[str]) -> tuple[dict, list[str]]:
    """回傳 ({代號: {日期: [o,h,l,c,ret]}}, 交易日曆)。ret＝還原日報酬（None＝該日沒前一筆可比）。"""
    want = set(ids) | {"0050"}
    cache = _rj(BARS, {"bars": {}, "calendar": []})
    bars: dict = cache["bars"]
    cal = set(cache["calendar"])
    if not cache["calendar"]:  # 第一次：讀模擬 I 回看期官方日檔
        for src in ("twse", "tpex"):
            for f in sorted(glob.glob(str(LOOKBACK / src / "*.json"))):
                j = json.loads(Path(f).read_text(encoding="utf-8"))
                if j.get("status") != "ok":
                    continue
                dt = j["date"]
                rows = j.get("rows") or {}
                if src == "twse" and len(rows) > 500:
                    cal.add(dt)
                for sid in want & rows.keys():
                    o, h, lo, c, _v, _t, chg = rows[sid]
                    if not c or c <= 0:
                        continue
                    ref = c - chg if chg is not None else None
                    ret = (c / ref - 1.0) if ref and ref > 0 else None
                    bars.setdefault(sid, {})[dt] = [o, h, lo, c, ret]
    # 之後每天：data/price_history
    ph: dict = {}
    for f in sorted(glob.glob(str(DATA / "price_history" / "b*.json"))):
        try:
            ph.update(json.loads(Path(f).read_text(encoding="utf-8"))["prices"])
        except Exception as e:  # 單一分片壞掉只略過
            print(f"[warn] 讀不到 {f}：{e}")
    cnt: dict[str, int] = {}
    for sid, rows in ph.items():
        for r in rows:
            if (r.get("close") or 0) > 0:
                cnt[r["date"]] = cnt.get(r["date"], 0) + 1
    last = max(cal) if cal else ""
    new_days = sorted(d for d, n in cnt.items() if n >= MIN_TRADED and d > last)
    for sid in want & ph.keys():
        rows = sorted((r for r in ph[sid] if r.get("date")), key=lambda r: r["date"])
        prev = None
        for r in rows:
            ok = (r.get("close") or 0) > 0 and (r.get("adj_close") or 0) > 0
            if ok and r["date"] in new_days:
                ret = (r["adj_close"] / prev["adj_close"] - 1.0) if prev else None
                bars.setdefault(sid, {})[r["date"]] = [r["open"], r["high"], r["low"], r["close"], ret]
            if ok:
                prev = r
    cal |= set(new_days)
    calendar = sorted(cal)
    _wj(BARS, {"note": "F12 紙上：原始 OHLC＋還原日報酬（見 paper_opt_f12.py 檔頭）", "calendar": calendar, "bars": bars})
    return bars, calendar


def adj_levels(b: dict) -> tuple[list[str], list[float]]:
    """把日報酬累乘成還原價位（起點＝第一天原始收盤）。缺前日可比的那天視為 0 報酬（只影響位階起點）。"""
    ds = sorted(b)
    lv, out = None, []
    for d in ds:
        o, h, lo, c, ret = b[d]
        lv = c if lv is None else lv * (1.0 + (ret if ret is not None else 0.0))
        out.append(lv)
    return ds, out


def indicators(bars: dict) -> dict:
    """{代號: {日期: (adj, ma150, score)}}——rolling 以該檔自己的列數計（同 weinstein prep()）。"""
    out = {}
    for sid, b in bars.items():
        ds, px = adj_levels(b)
        res = {}
        for i, d in enumerate(ds):
            ma = sum(px[i - MA_N + 1:i + 1]) / MA_N if i >= MA_N - 1 else None
            j = i - RISE_LB
            ma_prev = sum(px[j - MA_N + 1:j + 1]) / MA_N if j >= MA_N - 1 else None
            mom = px[i] / px[i - MOM_WIN] - 1.0 if i >= MOM_WIN else None
            ok = ma is not None and ma_prev is not None and mom is not None and px[i] > ma and ma > ma_prev
            res[d] = (px[i], ma, mom if ok else None)
        out[sid] = res
    return out


# ------------------------------------------------------------------ 加權指數（崩盤條件）
def taiex_series(bars: dict, calendar: list[str]) -> dict[str, list]:
    store = _rj(TAIEX, {"closes": {}})
    cl: dict = store["closes"]  # 日期 -> [收盤, 來源]
    try:
        p8 = _rj(HERE / "data" / "paper_8_taiex_closes.json", {}).get("closes") or {}
        for d, v in p8.items():
            cl.setdefault(d, [float(v), "official"])
    except Exception as e:
        print(f"[warn] 讀不到 paper_8_taiex_closes：{e}")
    try:
        t = json.loads((DATA / "market_tw.json").read_text(encoding="utf-8"))["taiex"]
        for d, v in zip(t.get("sparkline_60d_dates") or [], t.get("sparkline_60d") or []):
            cl[d] = [float(v), "official"]
        if t.get("data_date") and t.get("close"):
            cl[t["data_date"]] = [float(t["close"]), "official"]
    except Exception as e:
        print(f"[warn] 讀不到 market_tw taiex：{e}")
    off = sorted(d for d, v in cl.items() if v[1] == "official")
    if off:  # 官方最早一天之前，用 0050 原始收盤日報酬往前接〔自行裁量〕
        b = bars.get("0050", {})
        ds = [d for d in calendar if d < off[0] and d in b]
        lv = cl[off[0]][0]
        nxt = off[0]
        for d in reversed(ds):
            if nxt in b and b[nxt][3] and b[d][3]:
                lv = lv / (b[nxt][3] / b[d][3])
            cl[d] = [lv, "proxy_0050"]
            nxt = d
    _wj(TAIEX, {"note": "加權指數收盤：official＝官方（market_tw／paper_8 累積）；proxy_0050＝官方序列起點之前用 0050 原始收盤往前接〔自行裁量〕",
                "closes": dict(sorted(cl.items()))})
    return cl


def crash_flag(cl: dict, day: str) -> bool | None:
    ds = sorted(d for d in cl if d <= day)
    if len(ds) < CRASH_N:
        return None
    px = [cl[d][0] for d in ds]
    ma = sum(px[-CRASH_N:]) / CRASH_N
    hi = max(px[-252:])
    return px[-1] < ma and px[-1] / hi - 1.0 < -CRASH_X


def rf_daily() -> float:
    m = _rj(DATA / "rf_monthly.json", {}).get("monthly") or []
    return float(m[-1]["rf_rate_pct"]) / 100.0 / 252.0 if m else 0.0


# ------------------------------------------------------------------ 一日（底層引擎＋帳戶層）
def _locked(row, prev_close):
    if row is None or not prev_close:
        return costmod.LimitStatus(False, False)
    o, h, lo, c, _ = row
    return costmod.limit_status(o, h, lo, c, prev_close)


def step(day: str, s: dict, bars: dict, ind: dict, cl: dict, rf: float) -> dict:
    e = s["engine"]
    log = {"fills": [], "scheduled": []}

    def row(sid):
        return bars.get(sid, {}).get(day)

    def prev_close(sid):
        b = bars.get(sid, {})
        ps = [d for d in b if d < day]
        return b[max(ps)][3] if ps else None

    # ① 執行排定的單
    still = []
    for p in e["pending"]:
        sid = p["sid"]
        r = row(sid)
        adj = ind.get(sid, {}).get(day, (None,))[0] if r else None
        if r is None or adj is None or adj <= 0:
            still.append(p)
            continue
        lk = _locked(r, prev_close(sid))
        if (p["side"] == "buy" and lk.limit_up) or (p["side"] == "sell" and lk.limit_down):
            still.append(p)
            continue
        if p["side"] == "buy":
            alloc = e["last_equity"] / TOP_N
            sh = int(alloc // (adj * (1 + BUY_RATE)))
            if sh <= 0 or sid in e["pos"]:
                continue
            notional = sh * adj
            cost = notional * (costmod.COMMISSION_RATE + SLIP_BPS / 10_000)
            if notional + cost > e["cash"]:
                continue
            e["cash"] -= notional + cost
            e["pos"][sid] = {"shares": sh, "entry_price": adj, "entry_date": day}
            log["fills"].append({"sid": sid, "side": "buy", "px_adj": round(adj, 4), "raw_close": r[3], "reason": p["reason"]})
        else:
            pos = e["pos"].pop(sid, None)
            if pos is None:
                continue
            notional = pos["shares"] * adj
            cost = notional * (costmod.tax_rate("normal") + costmod.COMMISSION_RATE + SLIP_BPS / 10_000)
            e["cash"] += notional - cost
            log["fills"].append({"sid": sid, "side": "sell", "px_adj": round(adj, 4), "raw_close": r[3], "reason": p["reason"],
                                 "ret": round(adj / pos["entry_price"] - 1, 4)})
    e["pending"] = still

    def schedule(sid, side, reason):
        if any(p["sid"] == sid and p["side"] == side for p in e["pending"]):
            return
        e["pending"].append({"sid": sid, "side": side, "reason": reason, "scheduled": day})
        log["scheduled"].append({"sid": sid, "side": side, "reason": reason})

    # ② 持股風控（150 日均線出場；個股停損不設）
    for sid in list(e["pos"]):
        v = ind.get(sid, {}).get(day)
        if not v or v[0] is None or v[0] <= 0:
            continue
        e["last_valid"][sid] = v[0]
        if v[1] is not None and v[0] < v[1]:
            schedule(sid, "sell", "tier1_ma_exit")

    # ③ 換股日
    if e["day_i"] % REBAL == 0:
        sc = {sid: v[2] for sid, d in ind.items() if sid != "0050" and sid in s["universe_set"]
              for v in [d.get(day)] if v and v[2] is not None}
        ranked = sorted(sc.items(), key=lambda kv: kv[1], reverse=True)
        for sid in list(e["pos"]):
            if sid not in sc:
                schedule(sid, "sell", "rebalance_dropped")
        slots = TOP_N - len(e["pos"]) - sum(1 for p in e["pending"] if p["side"] == "buy")
        for sid, _ in ranked:
            if slots <= 0:
                break
            if sid in e["pos"] or any(p["sid"] == sid and p["side"] == "buy" for p in e["pending"]):
                continue
            schedule(sid, "buy", "rebalance_entry")
            slots -= 1
        log["rebalance"] = {"eligible": len(sc), "top": [k for k, _ in ranked[:TOP_N]]}

    # ④ mark to market
    mtm = e["cash"]
    for sid, pos in e["pos"].items():
        v = ind.get(sid, {}).get(day)
        px = v[0] if v and v[0] and row(sid) else e["last_valid"].get(sid, pos["entry_price"])
        mtm += pos["shares"] * px
    r1 = mtm / e["last_equity"] - 1.0
    e["last_equity"] = mtm
    e["day_i"] += 1

    # 帳戶層（drawdown_fix.overlay()：今日曝險用前一日崩盤條件）
    a = s["account"]
    expo = L * (CRASH_Y if a["crash_prev"] else 1.0)
    v0 = a["v"]
    held = a["in_pos"]
    if a["in_pos"]:
        a["v"] *= 1.0 + expo * r1 - max(expo - 1.0, 0.0) * MARGIN_RATE + max(1.0 - expo, 0.0) * rf
    else:
        a["v"] *= 1.0 + rf
    a["v"] = max(a["v"], 0.0)
    stop_evt = None
    if a["in_pos"]:
        a["peak"] = max(a["peak"], a["v"])
        if a["v"] < a["peak"] * (1 - ACC_STOP):
            a["in_pos"], a["cool"], stop_evt = False, COOLDOWN, "account_stop"
    else:
        a["cool"] -= 1
        if a["cool"] <= 0:
            a["in_pos"], a["peak"], stop_evt = True, a["v"], "reenter"
    cf = crash_flag(cl, day)
    if cf is None:
        print(f"[warn] {day} 加權指數不足 {CRASH_N} 日，崩盤條件視為不成立")
    a["crash_prev"] = bool(cf)
    return {"date": day, "ret": round(a["v"] / v0 - 1.0, 8), "ret_1x": round(r1, 8), "equity_1x": round(mtm, 2),
            "account": round(a["v"], 8), "exposure": expo if held else 0.0,
            "in_pos_next": a["in_pos"], "crash_today": cf, "account_event": stop_evt,
            "n_holdings": len(e["pos"]), "cash_frac": round(e["cash"] / mtm, 4) if mtm else None, **log}


def new_state(ids: list[str]) -> dict:
    return {"start": START, "engine": {"cash": INIT, "pos": {}, "pending": [], "day_i": 0, "last_equity": INIT, "last_valid": {}},
            "account": {"v": 1.0, "peak": 1.0, "cool": 0, "in_pos": True, "crash_prev": False},
            "last_date": None, "universe_n": len(ids)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    ids = universe()
    bars, calendar = build_bars(ids)
    ind = indicators(bars)
    cl = taiex_series(bars, calendar)
    rf = rf_daily()
    if a.probe:
        day = calendar[-1]
        sc = sorted(((sid, v[2]) for sid, d in ind.items() if sid in ids for v in [d.get(day)] if v and v[2] is not None),
                    key=lambda kv: -kv[1])
        n_ma = sum(1 for sid in ids if ind.get(sid, {}).get(day, (None, None))[1] is not None)
        print(f"最新交易日 {day}；宇宙 {len(ids)} 檔，有 150 日均線 {n_ma} 檔、符合第二階段 {len(sc)} 檔")
        print("假設今天換股，前 20：", [f"{k}:{v:+.1%}" for k, v in sc[:TOP_N]])
        ds = sorted(cl)[-5:]
        print("加權指數近 5 日：", [(d, round(cl[d][0], 2), cl[d][1]) for d in ds], "崩盤條件：", crash_flag(cl, day))
        print(f"無風險日利率 {rf:.6%}；交易日曆 {calendar[0]}～{calendar[-1]} 共 {len(calendar)} 天")
        return 0
    s = _rj(STATE, None) or new_state(ids)
    if a.start != START:
        s["start"] = a.start
    s["universe_set"] = set(ids)
    done = 0
    for day in calendar:
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        rec = step(day, s, bars, ind, cl, rf)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 1× {rec['ret_1x']:+.2%}　帳戶 {rec['ret']:+.2%}　持股 {rec['n_holdings']}　崩盤 {rec['crash_today']}")
    s.pop("universe_set", None)
    _wj(STATE, s)
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0，不拖垮排程
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f12 失敗：{e}")
        sys.exit(0)
