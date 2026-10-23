# -*- coding: utf-8 -*-
"""模擬 I（#463）：個股 252 日新高＋量能突破（事件型）前向紙上追蹤（先.一三二-0，總司令 2026-10-22 13:1x 裁示 §5-1 採甲）。

規則照 docs/PREREG_STOCK_BREAKOUT_252H_FINAL.md（參數寫死，不調參、不倒填）：
- 起算 2026-11-02 起第一個有收盤資料的執行日；之前 step() 一律回 NOT_STARTED、不寫帳本。
- 宇宙：當天在市（data/listed_universe.json active）上市＋上櫃普通股（4 碼、非 0 開頭、排除 91 開頭）、當天有收盤、
  近 20 日平均成交值 ≥ 3,000 萬。
- 訊號（日 t 收盤後）：還原收盤 > 前 251 個交易日（不含 t）還原收盤最高；成交股數 ≥ 1.5 × 前 20 日（不含 t）平均成交股數；未持有。
- t+1 收盤進場；同時最多 20 檔、每筆＝進場日淨值 ÷ 20（現金不足用剩餘現金）；超額依量比高→低、再依代號小→大。
- 出場（收盤判斷、次一交易日收盤賣出）：還原收盤 ≤ (1−10%) × 進場後最高還原收盤；或持有滿 60 個交易日；
  失去宇宙資格（下市／停牌）→ 可交易的第一天收盤賣出。
- 成本：research/backtest/engine.py buy_leg_rate／sell_leg_rate（1×）。虛擬本金 100 萬。
- limit_up_at_entry：進場日收盤相對前一日還原收盤 ≥ +9.5% 標 True（偽影家族⑪敏感度用，不改主判定）。

**holdout 讀取限制（research/validation/holdout.py ALLOWED_HOLDOUT_READERS／RESTRICTED_LOOKBACK_DIRS）**：
research/data/paper_9_lookback/（2025-10-28～2026-10-30 官方日檔，fetch_paper_9_lookback.py 抓）**只用來產生
lookback_features() 的 high_252／avgvol_20 兩個訊號輸入**；本程式不對 2026-11-02 以前任何日期算報酬或淨值
（scripts/selftest_paper_9_no_pre_start_returns.py 檢查）。2026-11-02 之後的收盤取 data/price_history.json（repo 既有、零額外請求）。
回看資料只在本機（research/data/ 不進公開 repo）；讀不到時起跑後回 LOOKBACK_MISSING、**不寫帳本**（之後補到資料再冪等補跑），
不會用殘缺回看靜默產生「沒有訊號」的假交易紀錄。自身失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TW = timezone(timedelta(hours=8))
LOG = ROOT / "research" / "data" / "paper_9_log.jsonl"
OUT = ROOT / "data" / "paper_9.json"
LOOKBACK_DIR = HERE / "data" / "paper_9_lookback"
LOOKBACK_END = "2026-10-30"
START_NOT_BEFORE = "2026-11-02"
JUDGE_AFTER = "2028-11-01"
HIGH_WIN, VOL_WIN = 251, 20      # 「前 251 個交易日」＋當日＝252 日；20 日均量
K_VOL, TRAIL, HOLD_N, MAX_POS = 1.5, 0.10, 60, 20
MIN_TURNOVER = 30_000_000.0
INITIAL = 1_000_000.0
LIMIT_UP = 0.095
LABEL = "模擬 I 個股 252 日新高＋量能突破"
NOTE = ("收盤創 252 日新高且成交量 ≥ 20 日均量 1.5 倍 → 隔日收盤買進；最多 20 檔、每檔淨值 1/20；"
        "從進場後最高點回落 10% 或持有滿 60 個交易日 → 隔日收盤賣出；近 20 日平均成交值 ≥3,000 萬；成本 1×")


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def is_common(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and code[0] != "0" and not code.startswith("91")


# ---------------------------------------------------------------- 價格序列（回看＋前向）
_SERIES_CACHE: dict | None = None


def _lookback_rows() -> dict:
    """{code: {date: (raw_close, shares, factor)}}；factor＝當日參考價÷前一日收盤（除權息日 <1），算不到記 1.0。"""
    out: dict = {}
    for src in ("twse", "tpex"):
        for f in sorted((LOOKBACK_DIR / src).glob("*.json")):
            j = _load(f, {})
            if j.get("status") != "ok":
                continue
            d = j["date"]
            for code, r in (j.get("rows") or {}).items():
                if not is_common(code) or r[3] is None:
                    continue
                out.setdefault(code, {})[d] = [r[3], r[4], r[6]]
    res = {}
    for code, by_d in out.items():
        prev, s = None, {}
        for d in sorted(by_d):
            close, shares, chg = by_d[d]
            fac = 1.0
            if prev and chg is not None:
                ref = close - chg
                if ref > 0 and abs(ref / prev - 1) > 0.002:   # 參考價≠前收＝除權息／減資等調整
                    fac = ref / prev
            s[d] = (close, shares, fac)
            prev = close
        res[code] = s
    return res


def _forward_rows(prices: dict) -> dict:
    """price_history（> LOOKBACK_END 的日子）→ 同格式；factor 由 adj_close／close 比值的跳動推算。"""
    res = {}
    for code, rows in prices.items():
        if not is_common(code):
            continue
        s, prev_ratio = {}, None
        for r in rows:
            c, a = r.get("close"), r.get("adj_close")
            if c is None:
                continue
            ratio = (a / c) if (a and c) else None
            if r["date"] > LOOKBACK_END:
                fac = 1.0
                if ratio and prev_ratio and abs(prev_ratio / ratio - 1) > 0.002:
                    fac = prev_ratio / ratio   # adj 往回縮放：除權息日前的 adj/close 比值較小 → 係數 <1
                s[r["date"]] = (float(c), r.get("volume"), fac)
            if ratio:
                prev_ratio = ratio
        res[code] = s
    return res


def _series(prices: dict | None = None) -> dict:
    """{code: [(date, raw_close, shares, factor), ...]} 依日期排序。"""
    global _SERIES_CACHE
    if _SERIES_CACHE is not None and prices is None:
        return _SERIES_CACHE
    lb = _lookback_rows()
    fw = _forward_rows(prices or {})
    out = {}
    for code in set(lb) | set(fw):
        m = dict(lb.get(code) or {})
        m.update(fw.get(code) or {})
        out[code] = [(d, *m[d]) for d in sorted(m)]
    if prices is None:
        _SERIES_CACHE = out
    return out


def _adj_window(ser: list, day: str, n: int):
    """day（含）以前的序列，回傳 (前 n 日還原收盤 list〔以 day 當日價基準〕, 前 n 日成交股數 list, day 當日列或 None)。"""
    idx = [i for i, row in enumerate(ser) if row[0] <= day]
    if not idx:
        return [], [], None
    last = idx[-1]
    today = ser[last] if ser[last][0] == day else None
    end = last if today else last + 1          # 前 n 日＝不含 day
    prior = ser[max(0, end - n):end]
    cum = today[3] if today else 1.0            # day 當天的係數也要套到之前所有價格
    adj = []
    for i in range(len(prior) - 1, -1, -1):
        d, c, sh, fac = prior[i]
        adj.append(c * cum)
        cum *= fac
    adj.reverse()
    return adj, [p[2] for p in prior], today


def lookback_features(day: str, series: dict | None = None) -> dict:
    """{代號: {"high_252": 前 251 日最高還原收盤（以 day 價格基準）, "avgvol_20": 前 20 日平均成交股數}}——只有這兩欄。"""
    series = series if series is not None else _series()
    out = {}
    for code, ser in series.items():
        adj, _, _ = _adj_window(ser, day, HIGH_WIN)
        _, vols, _ = _adj_window(ser, day, VOL_WIN)
        vols = [v for v in vols if v is not None]
        out[code] = {"high_252": max(adj) if len(adj) == HIGH_WIN else None,
                     "avgvol_20": (sum(vols) / len(vols)) if len(vols) == VOL_WIN else None}
    return out


# ---------------------------------------------------------------- 帳本
def read_log() -> list:
    try:
        return [json.loads(l) for l in Path(LOG).read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def _append(rec: dict) -> None:
    Path(LOG).parent.mkdir(parents=True, exist_ok=True)
    with Path(LOG).open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"logged_at": datetime.now(TW).isoformat(timespec="seconds"), **rec}, ensure_ascii=False) + "\n")


def write_summary(log: list, extra: dict | None = None) -> None:
    doc = {"label": LABEL, "note": NOTE, "prereg": "docs/PREREG_STOCK_BREAKOUT_252H_FINAL.md", "trial_no": 463,
           "start_not_before": START_NOT_BEFORE, "judge_after": JUDGE_AFTER, "started": bool(log),
           "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "judge": "2028-11-01 後判一次：已平倉 ≥100 筆才判；天條一 MDD≤50%、扣 1× 成本年化 > 0050 含息、2×／3× 成本年化 >0、"
                    "隨機時點對照 1,000 次第 95 百分位",
           "known_limit": "收盤鎖漲停進場照記成交（樂觀），limit_up_at_entry 欄照實標；與 #17 52 週高點同家族，不算獨立發現",
           "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。", **(extra or {})}
    if log:
        ev = log[-1]
        navs = [e["nav"] for e in log if e.get("nav") is not None]
        peak, mdd = 0.0, 0.0
        for v in navs:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1) if peak else mdd
        doc.update({"as_of_date": ev["date"], "nav": ev["nav"], "initial_virtual_capital": INITIAL,
                    "total_return_pct": round((ev["nav"] / INITIAL - 1) * 100, 2), "max_drawdown_pct": round(mdd * 100, 2),
                    "n_closed_trades": sum(len(e.get("closed_trades") or []) for e in log), "cash": ev.get("cash"),
                    "holdings": sorted(({"code": c, "since": p.get("entry_date"), "limit_up_at_entry": p.get("limit_up_at_entry")}
                            for c, p in (ev.get("positions") or {}).items()), key=lambda h: h["code"]),
                    "pending_entries": ev.get("pending_entries") or [], "pending_exits": ev.get("pending_exits") or []})
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 每日處理
def _fac_on(series: dict, code: str, day: str) -> float:
    for row in reversed(series.get(code) or []):
        if row[0] == day:
            return row[3] or 1.0
        if row[0] < day:
            break
    return 1.0


def _day(px, series: dict, day: str, state: dict, active: set, BUY: float, SELL: float) -> dict:
    """全部用原始收盤計價；除權息日（係數 f<1）把持股 units ÷ f（股利再投入）、進場後最高點 × f，
    避免 price_history 還原價基準日後重算造成的誤判（存下的價格永遠是當時的原始收盤基準）。"""
    positions = {c: dict(p) for c, p in state["positions"].items()}
    cash = state["cash"]
    pend_in, pend_out = list(state.get("pending_entries") or []), list(state.get("pending_exits") or [])
    closed, exited, entered = [], [], []

    def px_today(c):
        v = px.raw_close_on(c, day)
        return float(v) if v is not None else None

    for c, p in positions.items():
        f = _fac_on(series, c, day)
        if f != 1.0 and f > 0:
            p["units"] /= f
            p["peak_adj"] *= f
            p["adj_mult"] = p.get("adj_mult", 1.0) / f

    # 1) 執行昨日決定的出場（今天收盤賣；今天沒價＝停牌，延到可交易的第一天）
    keep_out = []
    for o in pend_out:
        c = o["code"]
        p = positions.get(c)
        if not p:
            continue
        v = px_today(c)
        if v is None:
            keep_out.append(o)
            continue
        cash += p["units"] * v * (1 - SELL)
        closed.append({"stock_id": c, "entry_date": p["entry_date"], "exit_date": day, "entry_px": p["entry_px"],
                       "exit_px": round(v, 6), "ret_gross": round(v * p.get("adj_mult", 1.0) / p["entry_px"] - 1, 6),
                       "exit_reason": o["reason"], "limit_up_at_entry": p.get("limit_up_at_entry")})
        exited.append(c)
        positions.pop(c)
    pend_out = keep_out
    # 2) 執行昨日訊號的進場（今天收盤買）
    def last_px(c, p):
        v = px_today(c)
        if v is not None:
            return v
        prev = [r for r in px.rows.get(c) or [] if r["date"] < day and r.get("close") is not None]
        return float(prev[-1]["close"]) if prev else p["entry_px"]

    nav = sum(p["units"] * last_px(c, p) for c, p in positions.items()) + cash
    for r in pend_in:
        c = r["code"]
        if len(positions) >= MAX_POS or cash <= 1.0 or c in positions:
            continue
        v = px_today(c)
        if v is None:
            continue
        prev_d = px.prev_trading_day(day)
        prev_v = px.raw_close_on(c, prev_d) if prev_d else None
        prev_v = prev_v * _fac_on(series, c, day) if prev_v else None
        invest = min(nav / MAX_POS, cash)
        cash -= invest
        positions[c] = {"units": invest / (1 + BUY) / v, "entry_date": day, "entry_px": v, "peak_adj": v,
                        "adj_mult": 1.0, "held_days": 0, "signal_date": r["signal_date"],
                        "limit_up_at_entry": bool(prev_v and v / prev_v - 1 >= LIMIT_UP)}
        entered.append(c)
    pend_in = []
    # 3) 收盤判斷出場（明天賣）
    pending_codes = {o["code"] for o in pend_out}
    for c, p in positions.items():
        v = px_today(c)
        if c not in entered and v is not None:
            p["held_days"] = p.get("held_days", 0) + 1
        if v is not None:
            p["peak_adj"] = max(p.get("peak_adj", v), v)
        if c in pending_codes:
            continue
        reason = None
        if c not in active or v is None:
            reason = "lost_universe"
        elif v <= (1 - TRAIL) * p["peak_adj"]:
            reason = "trailing_stop"
        elif p["held_days"] >= HOLD_N:
            reason = "hold_days"
        if reason:
            pend_out.append({"code": c, "reason": reason, "decided": day})
    # 4) 收盤判斷進場訊號（明天買）
    feats_today = lookback_features(day, series)  # 只取 high_252／avgvol_20
    cands = []
    for c in active:
        if not is_common(c) or c in positions:
            continue
        v_raw = px.raw_close_on(c, day)
        liq = px.avg_turnover(c, day)
        if v_raw is None or liq is None or liq < MIN_TURNOVER:
            continue
        f = feats_today.get(c) or {}
        row = next((rw for rw in px.rows.get(c) or [] if rw["date"] == day), None)
        vol = (row or {}).get("volume")
        if f.get("high_252") is None or not f.get("avgvol_20") or vol is None:
            continue
        if v_raw > f["high_252"] and vol >= K_VOL * f["avgvol_20"]:
            cands.append({"code": c, "signal_date": day, "vol_ratio": round(vol / f["avgvol_20"], 4)})
    cands.sort(key=lambda r: (-r["vol_ratio"], r["code"]))
    free = MAX_POS - len(positions) + len(pend_out)
    pend_in = cands[:max(free, 0)]
    vals = {c: p["units"] * last_px(c, p) for c, p in positions.items()}
    event = "trade" if (entered or exited) else "mark"
    if not state.get("started"):
        event = "inception"
    return {"date": day, "event": event, "nav": round(sum(vals.values()) + cash, 2), "cash": round(cash, 2),
            "entered": entered, "exited": exited, "closed_trades": closed, "signals_n": len(cands),
            "pending_entries": pend_in, "pending_exits": pend_out, "positions": positions}


def step(today: str | None = None) -> dict:
    """冪等：處理帳本最後日期之後、起跑日以後的每個交易日。today < START_NOT_BEFORE 一律 NOT_STARTED、不寫帳本。"""
    log = read_log()
    if today is not None and today < START_NOT_BEFORE:
        write_summary(log, {"why_not_started": f"{START_NOT_BEFORE} 起跑（PREREG 寫死，不倒填）"})
        return {"state": "NOT_STARTED", "day": today, "start": START_NOT_BEFORE}
    import price_history_store as PHS  # noqa: E402
    from paper_forward_common import Px  # noqa: E402
    from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate  # noqa: E402
    prices = PHS.load(ROOT / "data" / "price_history.json").get("prices") or {}
    px = Px(prices)
    day = today or px.latest_date()
    if not day or day < START_NOT_BEFORE:
        write_summary(log, {"why_not_started": f"{START_NOT_BEFORE} 起跑（PREREG 寫死，不倒填）"})
        return {"state": "NOT_STARTED", "day": day, "start": START_NOT_BEFORE}
    status = _load(LOOKBACK_DIR / "_status.json", {})
    lb_ok = all((status.get("by_source") or {}).get(s, {}).get("missing", 1) == 0 for s in ("twse", "tpex")) \
        and str((status.get("range") or ["", ""])[1]) == LOOKBACK_END \
        and all((LOOKBACK_DIR / s / f"{LOOKBACK_END.replace('-', '')}.json").exists() for s in ("twse", "tpex"))
    if not lb_ok:
        write_summary(log, {"why_not_started": "252 日回看資料不完整（research/data/paper_9_lookback/，只在本機），不寫帳本、補齊後冪等補跑"})
        return {"state": "LOOKBACK_MISSING", "day": day}
    cfg = BacktestConfig(start_date=START_NOT_BEFORE, end_date=START_NOT_BEFORE, initial_capital=INITIAL,
                         instrument_type="normal", book_name="paper_9_tracker")
    BUY, SELL = buy_leg_rate(cfg), sell_leg_rate(cfg)
    active = set((_load(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    series = _series(prices)
    last = log[-1] if log else None
    state = {"positions": (last or {}).get("positions") or {}, "cash": last["cash"] if last else INITIAL,
             "started": bool(last), "pending_entries": (last or {}).get("pending_entries") or [],
             "pending_exits": (last or {}).get("pending_exits") or []}
    todo = [d for d in px.calendar if START_NOT_BEFORE <= d <= day and (not last or d > last["date"])]
    done = []
    for d in todo:
        rec = _day(px, series, d, state, active, BUY, SELL)
        _append(rec)
        state = {k: rec[k] for k in ("positions", "cash", "pending_entries", "pending_exits")}
        state["started"] = True
        done.append((d, rec["event"]))
    write_summary(read_log())
    return {"state": "PROCESSED" if done else "HOLD", "day": day, "processed": done}


def main() -> int:
    try:
        print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] 模擬 I 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
