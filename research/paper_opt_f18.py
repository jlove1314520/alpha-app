# -*- coding: utf-8 -*-
"""先.一五四-1a ② 紙上優化軌 F18（零股委託簿失衡度，只調槓桿版）每日訊號產生器——研究帽產物，零外部請求。

策略（照 research/data/reaudit_optimized_batch2_oddlot.json 最優格＋paper_opt_track.SINGLES["F18"]，這裡不調參）：
  底層（1×，逐條對照 research/backtest/engine.py run_backtest() 重寫，因為引擎會擋 2025 起的資料、不能直接呼叫；
  寫法同 paper_opt_f12.py）：
    每個交易日依序 ①執行前一日排定的單（成交價＝當日還原收盤；買單遇鎖漲停、賣單遇鎖跌停、當天沒價格 → 順延一日；
    買進股數＝int(當下權益÷30 ÷ (價×(1+買方成本)))，現金不夠就放棄）②持股風控：還原收盤 ≤ 進場價×(1−15%) → 排隔日賣
    （引擎 tier3_hard_stop；回測資料沒有 ma150 欄，所以沒有均線出場）③換股日（起跑日起第 0、21、42… 個交易日）：
    訊號＝odd_lot_imbalance_portfolio_v1 的 composite（TWTC7U 最後揭示買賣量失衡度 (買−賣)/(買+賣)，同產業 z-score，
    score._zscore_within_group），資格池排除 20 日均成交金額後 10% 分位（portfolio_backtest_v2 同口徑，缺值保留），
    方向＝「高失衡」（composite 由高到低）取前 30 檔；持股不在名單 → 排隔日賣；空位依序排隔日買
    ④以還原收盤 mark-to-market（當天沒價格用最近有效價）。成本照 validation.costs（同引擎預設、1×）。
  帳戶層：曝險 2.85×（paper_opt_track 定義的「只調槓桿版」；回測最優格是 3×，3× 超過台股融資上限只當參考），
    超過 1 倍的部分付融資 6.5%/年；帳戶自高點回撤 10% 清倉、停 21 個交易日；不加崩盤條件。
宇宙〔沿用回測〕：factor_ic.sample_universe_ids(300, 20260822)（第一次跑時封網重建、存成 research/data/paper_opt/f18_universe.json）。
  TWTC7U 只有上市股；上櫃股沒有失衡度＝回測裡也是 NaN、不會入選，照原樣保留。

資料（全部本機）：
  - 價格：同 paper_opt_f12（2025-10-28～2026-10-30 模擬 I 回看期官方日檔＋之後 data/price_history），另存成交金額算流動性。
  - 零股：research/data/raw_twse_odd_lot/TWTC7U_YYYYMMDD.parquet（fetch_paper_opt_odd_lot.py 每日 1 次，不回補）。
    〔自行裁量〕換股日當天沒有 TWTC7U 檔（抓取失敗或還沒抓）→ 換股順延到有檔的那一天（不拿舊日資料頂替），
    順延期間 day_i 照常累加，下一次換股仍照「上一次實際換股日＋21」計。
  〔自行裁量〕起跑日＝2026-11-10：11/09 沒有 TWTC7U（每日抓取 11/10 才上線、不回補），第一天就是換股日，沒有訊號就開不了倉。

輸出（append-only，已寫過的日期不改）：
  research/data/paper_opt/ledger_F18.jsonl  每個交易日一行（ret＝帳戶層日報酬，另記 1× 底層）
  research/data/paper_opt/state_F18.json    底層持股／排定單／帳戶層狀態
用法：python research/paper_opt_f18.py           每日跑（只處理還沒寫過的交易日）
      python research/paper_opt_f18.py --probe   只印「假設今天是換股日」的名單，不寫帳
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
OUT = Path(os.environ.get("PAPER_OPT_OUT") or HERE / "data" / "paper_opt")
LOOKBACK = HERE / "data" / "paper_9_lookback"
ODD = HERE / "data" / "raw_twse_odd_lot"
LEDGER = OUT / "ledger_F18.jsonl"
STATE = OUT / "state_F18.json"
BARS = OUT / "f18_bars.json"
UNIV = OUT / "f18_universe.json"

sys.path.insert(0, str(HERE))
import paper_opt_exright_fix as XF  # noqa: E402  （先.一五八-3）
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from validation import costs as costmod  # noqa: E402  （只呼叫、不改）

START = "2026-11-10"
TOP_N, REBAL, POS_STOP = 30, 21, 0.15
LIQ_WIN, LIQ_PCT = 20, 10  # 同 portfolio_backtest_v2._liquidity_proxy_series／LIQUIDITY_FLOOR_PERCENTILE
SLIP_BPS = 5.0
BUY_RATE = costmod.COMMISSION_RATE + SLIP_BPS / 10_000
L, ACC_STOP, COOLDOWN = 2.85, 0.10, 21
MARGIN_RATE = 0.065 / 252.0
INIT = 1_000_000.0
MIN_TRADED = 1000


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


# ------------------------------------------------------------------ 宇宙／產業
def universe() -> list[str]:
    u = _rj(UNIV, None)
    if u:
        return u["ids"]
    import socket  # 封網重建（factor_ic 讀本機 FinMind 快取；萬一要連網就直接失敗，不送請求）

    def _no(*a, **k):
        raise RuntimeError("paper_opt_f18：重建宇宙時禁止外部連線")
    socket.socket.connect = _no
    socket.create_connection = _no
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids  # noqa: PLC0415
    from score import load_industry_map  # noqa: PLC0415
    ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    im = load_industry_map()
    _wj(UNIV, {"source": f"factor_ic.sample_universe_ids({SAMPLE_SIZE}, {SAMPLE_SEED})（同 F18 回測），封網重建",
               "ids": ids, "industry": {i: im.get(i, "UNKNOWN") for i in ids}})
    return ids


def industry() -> dict:
    return (_rj(UNIV, {}) or {}).get("industry") or {}


# ------------------------------------------------------------------ 價格（含成交金額）
def build_bars(ids: list[str]) -> tuple[dict, list[str]]:
    """回傳 ({代號: {日期: [o,h,l,c,ret,成交金額]}}, 交易日曆)。"""
    want = set(ids)
    cache = _rj(BARS, {"bars": {}, "calendar": []})
    bars: dict = cache["bars"]
    cal = set(cache["calendar"])
    if not cache["calendar"]:
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
                    o, h, lo, c, _v, t, chg = rows[sid]
                    if not c or c <= 0:
                        continue
                    ref = c - chg if chg is not None else None
                    ret = (c / ref - 1.0) if ref and ref > 0 else None
                    bars.setdefault(sid, {})[dt] = [o, h, lo, c, ret, t]
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
                bars.setdefault(sid, {})[r["date"]] = [r["open"], r["high"], r["low"], r["close"], ret, r.get("turnover")]
            if ok:
                prev = r
    cal |= set(new_days)
    calendar = sorted(cal)
    XF.apply_once(cache, XF.lookback_last())  # 先.一五八-3 除權息日 0 報酬補正（冪等，只補一次）
    _wj(BARS, {"note": "F18 紙上：原始 OHLC＋還原日報酬＋成交金額（見 paper_opt_f18.py 檔頭）", "calendar": calendar, "bars": bars, "exright_fix": cache.get("exright_fix")})
    return bars, calendar


def adj_and_liq(bars: dict) -> dict:
    """{代號: {日期: (還原價位, 20 日均成交金額或 None)}}。"""
    out = {}
    for sid, b in bars.items():
        ds = sorted(b)
        lv, res, tv = None, {}, []
        for d in ds:
            o, h, lo, c, ret, t = (b[d] + [None])[:6]
            lv = c if lv is None else lv * (1.0 + (ret if ret is not None else 0.0))
            tv.append(float(t) if t is not None else np.nan)
            w = tv[-LIQ_WIN:]
            liq = float(np.mean(w)) if len(w) == LIQ_WIN and not np.isnan(w).any() else None
            res[d] = (lv, liq)
        out[sid] = res
    return out


# ------------------------------------------------------------------ 訊號
def odd_lot_file(day: str) -> Path:
    return ODD / f"TWTC7U_{day.replace('-', '')}.parquet"


def signal(day: str, ids: list[str], ind: dict, imap: dict) -> list[str] | None:
    """回傳當日高失衡前 30 檔；當日沒有 TWTC7U 檔回 None（換股順延）。"""
    f = odd_lot_file(day)
    if not f.exists():
        return None
    from score import _zscore_within_group  # noqa: PLC0415  （只呼叫）
    import portfolio_backtest_v2 as pbv2  # noqa: PLC0415
    assert pbv2.LIQUIDITY_FLOOR_PERCENTILE == LIQ_PCT
    od = pd.read_parquet(f)
    od["code"] = od["code"].astype(str).str.strip()
    denom = od["last_bid_qty"] + od["last_ask_qty"]
    od["imbalance"] = np.where(denom > 0, (od["last_bid_qty"] - od["last_ask_qty"]) / denom, np.nan)
    imb = dict(zip(od["code"], od["imbalance"]))
    rows = []
    for sid in ids:
        v = ind.get(sid, {}).get(day)
        if v is None:  # 回測 compute_composite_at_date：當天沒價格列就不進橫斷面
            continue
        x = imb.get(sid)
        rows.append({"stock_id": sid, "industry": imap.get(sid, "UNKNOWN"), "liq": v[1],
                     "raw": float(x) if x is not None and pd.notna(x) else np.nan})
    if not rows:
        return []
    cs = pd.DataFrame(rows).set_index("stock_id")
    cs["composite"] = _zscore_within_group(cs["raw"], cs["industry"])
    pool = cs[cs["composite"].notna()].copy()  # n_components>=1
    liq = pool["liq"].dropna()
    if len(liq) >= 10:
        floor = np.percentile(liq, LIQ_PCT)
        pool = pool[pool["liq"].isna() | (pool["liq"] >= floor)]
    # 回測：先升冪排序、再整個反轉（高失衡）→ 同分時順序也照反轉
    pool = pool.reset_index().sort_values("composite", ascending=True).iloc[::-1]
    return pool["stock_id"].head(TOP_N).tolist()


def rf_daily() -> float:
    m = _rj(DATA / "rf_monthly.json", {}).get("monthly") or []
    return float(m[-1]["rf_rate_pct"]) / 100.0 / 252.0 if m else 0.0


def _locked(row, prev_close):
    if row is None or not prev_close:
        return costmod.LimitStatus(False, False)
    o, h, lo, c = row[:4]
    return costmod.limit_status(o, h, lo, c, prev_close)


# ------------------------------------------------------------------ 一日
def step(day: str, s: dict, bars: dict, ind: dict, ids: list[str], imap: dict, rf: float) -> dict:
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
            sh = int((e["last_equity"] / TOP_N) // (adj * (1 + BUY_RATE)))
            if sh <= 0 or sid in e["pos"]:
                continue
            notional = sh * adj
            cost = notional * BUY_RATE
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

    # ② 個股停損 15%（引擎 tier3）
    for sid in list(e["pos"]):
        v = ind.get(sid, {}).get(day)
        if not row(sid) or not v or v[0] is None or v[0] <= 0:
            continue
        e["last_valid"][sid] = v[0]
        if v[0] <= e["pos"][sid]["entry_price"] * (1 - POS_STOP):
            schedule(sid, "sell", "tier3_hard_stop")

    # ③ 換股日（沒有當日 TWTC7U → 順延）
    if e["day_i"] >= e["next_rebal_i"]:
        top = signal(day, ids, ind, imap)
        if top is None:
            log["rebalance"] = {"postponed": "no_TWTC7U_file"}
        else:
            keep = set(top)
            for sid in list(e["pos"]):
                if sid not in keep:
                    schedule(sid, "sell", "rebalance_dropped")
            slots = TOP_N - len(e["pos"]) - sum(1 for p in e["pending"] if p["side"] == "buy")
            for sid in top:
                if slots <= 0:
                    break
                if sid in e["pos"] or any(p["sid"] == sid and p["side"] == "buy" for p in e["pending"]):
                    continue
                schedule(sid, "buy", "rebalance_entry")
                slots -= 1
            e["next_rebal_i"] = e["day_i"] + REBAL
            log["rebalance"] = {"top": top}

    # ④ mark to market
    mtm = e["cash"]
    for sid, pos in e["pos"].items():
        v = ind.get(sid, {}).get(day)
        px = v[0] if v and v[0] and row(sid) else e["last_valid"].get(sid, pos["entry_price"])
        mtm += pos["shares"] * px
    r1 = mtm / e["last_equity"] - 1.0
    e["last_equity"] = mtm
    e["day_i"] += 1

    # 帳戶層（drawdown_fix.overlay() 同式，不加崩盤條件）
    a = s["account"]
    v0, held = a["v"], a["in_pos"]
    if a["in_pos"]:
        a["v"] *= 1.0 + L * r1 - max(L - 1.0, 0.0) * MARGIN_RATE
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
    return {"date": day, "ret": round(a["v"] / v0 - 1.0, 8), "ret_1x": round(r1, 8), "equity_1x": round(mtm, 2),
            "account": round(a["v"], 8), "exposure": L if held else 0.0, "in_pos_next": a["in_pos"],
            "account_event": stop_evt, "n_holdings": len(e["pos"]),
            "cash_frac": round(e["cash"] / mtm, 4) if mtm else None, **log}


def new_state(ids: list[str]) -> dict:
    return {"start": START, "engine": {"cash": INIT, "pos": {}, "pending": [], "day_i": 0, "next_rebal_i": 0,
                                        "last_equity": INIT, "last_valid": {}},
            "account": {"v": 1.0, "peak": 1.0, "cool": 0, "in_pos": True}, "last_date": None, "universe_n": len(ids)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    ids = universe()
    imap = industry()
    bars, calendar = build_bars(ids)
    ind = adj_and_liq(bars)
    rf = rf_daily()
    if a.probe:
        day = calendar[-1]
        top = signal(day, ids, ind, imap)
        n_liq = sum(1 for sid in ids if (ind.get(sid, {}).get(day) or (None, None))[1] is not None)
        print(f"最新交易日 {day}；宇宙 {len(ids)} 檔、當天有價 {sum(1 for s_ in ids if day in bars.get(s_, {}))} 檔、有 20 日均量 {n_liq} 檔")
        print("TWTC7U 檔：", odd_lot_file(day).name, odd_lot_file(day).exists())
        print("假設今天換股，高失衡前 30：", top)
        return 0
    s = _rj(STATE, None) or new_state(ids)
    if a.start != START:
        s["start"] = a.start
    done = 0
    for day in calendar:
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        rec = step(day, s, bars, ind, ids, imap, rf)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 1× {rec['ret_1x']:+.2%}　帳戶 {rec['ret']:+.2%}　持股 {rec['n_holdings']}　換股 {rec.get('rebalance', {}).get('postponed', bool(rec.get('rebalance')))}")
    _wj(STATE, s)
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0，不拖垮排程
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f18 失敗：{e}")
        sys.exit(0)
