# -*- coding: utf-8 -*-
"""個股前向紙上追蹤共用框架（先.一三二-5，2026-10-23；模擬 J／K／L 共用）。

三個模擬只各寫「訊號函式」，下列共用部分全部在這裡（規則照各自 PREREG FINAL，參數不在這裡調）：
- 宇宙：當天在市（data/listed_universe.json active）的上市＋上櫃普通股（4 碼、非 0 開頭、排除 91 開頭），當天有收盤價；
  流動性門檻由各模擬傳入（K／L 近 20 日均成交值 ≥3,000 萬；J 在訊號函式裡算處置前 20 日 ≥1,000 萬）。
- 兩種組合模式：
  monthly＝每月第一個交易日依排名再平衡（前 M 進、跌出前 R 出、空位補滿 M、全部回到等權；解等權同模擬 G）；
  event＝事件進場、固定持有 H 個交易日出場、同時最多 M 檔、每筆＝進場日淨值 ÷ M。
- 成本：research/backtest/engine.py `buy_leg_rate`／`sell_leg_rate`（costs.py 1×）；判定時的 2×／3× 由已平倉交易表重算。
- 帳本（append-only JSONL）：每個已處理的交易日一列（inception／rebalance／trade／mark／skip），帶 nav、cash、positions
  （每檔 units、entry_date、entry_px）＋當日出場的已平倉交易（stock_id／entry_date／exit_date／entry_px／exit_px，
  可直接餵 run_random_timing_control）。每日一列＝判定時天條一回撤用的日淨值序列。
- step() 冪等：同一個交易日不會處理兩次（帳本最後日期之後的交易日才處理，漏跑的日子依序補，最多到 price_history 最新日）；
  起跑日前一律 NOT_STARTED（不建倉、不寫帳本，只寫摘要）。
- 價格只讀 data/price_history（repo 既有、還原收盤），零額外外部請求。自身失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import price_history_store as PHS  # noqa: E402
from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate  # noqa: E402

TW = timezone(timedelta(hours=8))
INITIAL = 1_000_000.0
LIQ_DAYS = 20
_CFG = BacktestConfig(start_date="2026-12-01", end_date="2026-12-01", initial_capital=INITIAL,
                      instrument_type="normal", book_name="paper_forward_common")
BUY, SELL = buy_leg_rate(_CFG), sell_leg_rate(_CFG)


def load_json(p: Path, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def is_common(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and code[0] != "0" and not code.startswith("91")


class Px:
    """price_history 的查詢索引（每檔 date→row），只存參照、不複製資料。"""

    def __init__(self, prices: dict):
        self.rows = prices
        self.idx = {c: {r["date"]: i for i, r in enumerate(rs)} for c, rs in prices.items() if rs}
        self.calendar = sorted({r["date"] for rs in prices.values() for r in rs})

    @staticmethod
    def _v(r):
        v = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
        return float(v) if v is not None else None

    def close_on(self, code: str, d: str):
        i = (self.idx.get(code) or {}).get(d)
        return None if i is None else self._v(self.rows[code][i])

    def raw_close_on(self, code: str, d: str):
        i = (self.idx.get(code) or {}).get(d)
        if i is None:
            return None
        v = self.rows[code][i].get("close")
        return float(v) if v is not None else None

    def close_le(self, code: str, d: str):
        best = None
        for r in self.rows.get(code) or []:
            if r["date"] > d:
                break
            v = self._v(r)
            if v is not None:
                best = v
        return best

    def prev_trading_day(self, d: str):
        prev = [x for x in self.calendar if x < d]
        return prev[-1] if prev else None

    def next_trading_day(self, d: str):
        nxt = [x for x in self.calendar if x > d]
        return nxt[0] if nxt else None

    def avg_turnover(self, code: str, d: str, inclusive: bool = True):
        rs = [r for r in (self.rows.get(code) or []) if (r["date"] <= d if inclusive else r["date"] < d)]
        vals = [float(r["turnover"]) for r in rs if r.get("turnover") is not None][-LIQ_DAYS:]
        return sum(vals) / len(vals) if len(vals) == LIQ_DAYS else None

    def latest_date(self):
        return self.calendar[-1] if self.calendar else None


@dataclass
class Spec:
    key: str                      # 例 "paper_10"
    label: str
    note: str
    prereg: str
    trial_no: int | None
    start_not_before: str         # 起跑日（含），之前 NOT_STARTED
    judge_after: str              # 判定日
    mode: str                     # "monthly" | "event"
    top_n: int                    # M
    exit_rank: int | None = None  # R（monthly）
    hold_days: int | None = None  # H（event）
    min_turnover: float | None = None   # 宇宙流動性門檻（monthly 用；event 由訊號函式自己判）
    delist_value: str = "last"    # 下市且當天無價：last＝最後可得價出場；zero＝以 −100% 計
    # monthly：signal(ctx, day, universe) → 已排序的 [{code, ...}]，或 None＝資料不足、本月不調倉（skip_reason 放 ctx["skip_reason"]）
    # event：signal(ctx, day, universe) → 已依優先順序排好的進場候選 [{code, ...}]
    signal: Callable | None = None
    log_path: Path | None = None
    out_path: Path | None = None
    judge_text: str = ""
    known_limit: str = ""
    extra_summary: dict = field(default_factory=dict)


def read_log(spec: Spec) -> list:
    try:
        return [json.loads(l) for l in spec.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def _append(spec: Spec, rec: dict) -> None:
    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    with spec.log_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"logged_at": datetime.now(TW).isoformat(timespec="seconds"), **rec}, ensure_ascii=False) + "\n")


def universe(px: Px, day: str, active: set, min_turnover: float | None) -> dict:
    """回傳 {code: 近 20 日均成交值}（無門檻時值可能為 None）。"""
    out = {}
    for code in active:
        if not is_common(code) or px.close_on(code, day) is None:
            continue
        liq = px.avg_turnover(code, day)
        if min_turnover is not None and (liq is None or liq < min_turnover):
            continue
        out[code] = liq
    return out


def _mark(px: Px, positions: dict, day: str, active: set, delist_value: str) -> dict:
    vals = {}
    for c, p in positions.items():
        v = px.close_on(c, day)
        if v is None:
            if c not in active and delist_value == "zero" and px.close_le(c, day) is not None \
                    and not any(r["date"] > day for r in px.rows.get(c) or []):
                v = 0.0
            else:
                v = px.close_le(c, day) or p["entry_px"]
        vals[c] = p["units"] * v
    return vals


def _closed(c: str, p: dict, day: str, exit_px: float, reason: str) -> dict:
    return {"stock_id": c, "entry_date": p["entry_date"], "exit_date": day, "entry_px": p["entry_px"],
            "exit_px": round(exit_px, 6), "ret_gross": round(exit_px / p["entry_px"] - 1, 6) if p["entry_px"] else None,
            "exit_reason": reason}


def _day_monthly(spec: Spec, px: Px, day: str, state: dict, ctx: dict, active: set) -> dict:
    positions, cash = state["positions"], state["cash"]
    vals = _mark(px, positions, day, active, spec.delist_value)
    nav_pre = sum(vals.values()) + cash
    month_done = state.get("last_rebalance_month") == day[:7]
    if month_done:
        return {"date": day, "event": "mark", "nav": round(nav_pre, 2), "cash": round(cash, 2), "positions": positions}
    uni = universe(px, day, active, spec.min_turnover)
    ctx.pop("skip_reason", None)
    rk = spec.signal(ctx, day, uni)
    if rk is None:
        return {"date": day, "event": "skip", "skip_reason": ctx.get("skip_reason", "訊號資料不足"), "rebalance_month": day[:7],
                "nav": round(nav_pre, 2), "cash": round(cash, 2), "positions": positions}
    rank = {r["code"]: i for i, r in enumerate(rk, 1)}
    keep = [c for c in positions if rank.get(c, 10 ** 9) <= spec.exit_rank and px.close_on(c, day) is not None]
    new = keep[:]
    for r in rk:
        if len(new) >= spec.top_n:
            break
        if r["code"] not in new:
            new.append(r["code"])
    closed = []
    # 先賣（出場＋減碼）再買；等權目標以扣完賣出成本後的淨值計（解法同模擬 G）
    target_hint = nav_pre / len(new) if new else 0.0
    sells = {c: max(0.0, vals[c] - (0.0 if c not in new else target_hint)) for c in positions}
    cash2 = cash + sum(v * (1 - SELL) for v in sells.values())
    remain = {c: vals.get(c, 0.0) - sells.get(c, 0.0) for c in new}
    t = 0.0
    if new:
        lo, hi = 0.0, (sum(remain.values()) + cash2) / len(new)
        for _ in range(60):
            m = (lo + hi) / 2
            need = sum(max(0.0, m - remain[c]) * (1 + BUY) for c in new) - sum(max(0.0, remain[c] - m) for c in new)
            lo, hi = (m, hi) if need <= cash2 else (lo, m)
        t = lo
    buys = {c: max(0.0, t - remain[c]) for c in new}
    extra_sells = {c: max(0.0, remain[c] - t) for c in new}
    cash3 = cash2 - sum(b * (1 + BUY) for b in buys.values()) + sum(s for s in extra_sells.values())
    new_pos = {}
    for c in new:
        p_now = px.close_on(c, day)
        if c in positions:
            new_pos[c] = {**positions[c], "units": t / p_now}
        else:
            new_pos[c] = {"units": t / p_now, "entry_date": day, "entry_px": p_now}
    for c in positions:
        if c not in new:
            p_now = px.close_on(c, day) or px.close_le(c, day) or positions[c]["entry_px"]
            closed.append(_closed(c, positions[c], day, p_now, "rank_or_eligibility"))
    traded = sum(sells.values()) + sum(buys.values()) + sum(extra_sells.values())
    cost = sum(sells.values()) * SELL + sum(buys.values()) * BUY
    return {"date": day, "event": "inception" if not state.get("started") else "rebalance", "rebalance_month": day[:7],
            "nav_pre": round(nav_pre, 2), "nav": round(t * len(new) + cash3, 2), "cash": round(cash3, 2),
            "rebalance_cost": round(cost, 2), "turnover_pct": round(traded / nav_pre * 100, 2) if nav_pre else None,
            "entered": [c for c in new if c not in positions], "exited": [c for c in positions if c not in new],
            "picks": [dict(r, rank=rank[r["code"]]) for r in rk if r["code"] in new], "universe_n": len(uni),
            "closed_trades": closed, "positions": new_pos}


def _day_event(spec: Spec, px: Px, day: str, state: dict, ctx: dict, active: set) -> dict:
    positions, cash = dict(state["positions"]), state["cash"]
    cal = px.calendar
    closed, exited = [], []
    for c, p in list(positions.items()):
        held = sum(1 for d in cal if p["entry_date"] < d <= day)
        v = px.close_on(c, day)
        delisted = c not in active and not any(r["date"] >= day for r in px.rows.get(c) or [])
        if delisted and v is None:
            exit_px = 0.0 if spec.delist_value == "zero" else (px.close_le(c, day) or 0.0)
            closed.append(_closed(c, p, day, exit_px, "delisted"))
        elif held >= spec.hold_days and v is not None:
            closed.append(_closed(c, p, day, v, "hold_days"))
        else:
            continue
        cash += p["units"] * closed[-1]["exit_px"] * (1 - SELL)
        exited.append(c)
        positions.pop(c)
    vals = _mark(px, positions, day, active, spec.delist_value)
    nav = sum(vals.values()) + cash
    uni = universe(px, day, active, None)
    cands = spec.signal(ctx, day, uni) or []
    entered, picks = [], []
    for r in cands:
        if len(positions) >= spec.top_n or cash <= 1.0:
            break
        c = r["code"]
        if c in positions or c not in uni:
            continue
        p_now = px.close_on(c, day)
        invest = min(nav / spec.top_n, cash)
        units = invest / (1 + BUY) / p_now
        cash -= invest
        positions[c] = {"units": units, "entry_date": day, "entry_px": p_now}
        entered.append(c)
        picks.append(r)
    vals = _mark(px, positions, day, active, spec.delist_value)
    event = "trade" if (entered or exited) else "mark"
    if not state.get("started") and entered:
        event = "inception"
    return {"date": day, "event": event, "nav": round(sum(vals.values()) + cash, 2), "cash": round(cash, 2),
            "entered": entered, "exited": exited, "picks": picks, "closed_trades": closed,
            "candidates_n": len(cands), "positions": positions}


def write_summary(spec: Spec, px: Px | None, log: list, extra: dict | None = None) -> None:
    names = {}
    for row in (load_json(ROOT / "data" / "stock_names.json", {}) or {}).get("tw") or []:
        if row:
            names[row[0]] = row[1]
    doc = {"label": spec.label, "note": spec.note, "prereg": spec.prereg, "trial_no": spec.trial_no,
           "start_not_before": spec.start_not_before, "judge_after": spec.judge_after, "started": bool(log),
           "generated_at": datetime.now(TW).isoformat(timespec="seconds"), "judge": spec.judge_text,
           "known_limit": spec.known_limit, "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。",
           **spec.extra_summary, **(extra or {})}
    if log:
        ev = log[-1]
        navs = [e["nav"] for e in log if e.get("nav") is not None]
        peak, mdd = 0.0, 0.0
        for v in navs:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1) if peak else mdd
        n_closed = sum(len(e.get("closed_trades") or []) for e in log)
        entry_since = {c: p.get("entry_date") for c, p in (ev.get("positions") or {}).items()}
        nav = ev["nav"]
        hold = []
        for c, p in (ev.get("positions") or {}).items():
            v = (px.close_on(c, ev["date"]) if px else None) or p["entry_px"]
            hold.append({"code": c, "name": names.get(c, ""), "since": entry_since.get(c),
                         "weight_pct": round(p["units"] * v / nav * 100, 2) if nav else None})
        doc.update({"as_of_date": ev["date"], "nav": nav, "initial_virtual_capital": INITIAL,
                    "total_return_pct": round((nav / INITIAL - 1) * 100, 2), "max_drawdown_pct": round(mdd * 100, 2),
                    "n_closed_trades": n_closed, "cash": ev.get("cash"), "holdings": sorted(hold, key=lambda h: h["code"]),
                    "last_event": ev.get("event")})
    spec.out_path.parent.mkdir(parents=True, exist_ok=True)
    spec.out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def load_px() -> Px:
    return Px(PHS.load(ROOT / "data" / "price_history.json").get("prices") or {})


def step(spec: Spec, ctx: dict | None = None, px: Px | None = None, active: set | None = None,
         start_override: str | None = None) -> dict:
    """處理帳本最後日期之後、起跑日以後的每一個交易日（冪等）。start_override＝起跑日順延（模擬 L 用）。"""
    ctx = ctx if ctx is not None else {}
    log = read_log(spec)
    px = px or load_px()
    day = px.latest_date()
    if not day:
        raise RuntimeError("price_history 讀不到任何收盤資料")
    start = max(spec.start_not_before, start_override or spec.start_not_before)
    if day < start:
        write_summary(spec, px, log, {"why_not_started": f"{start} 起跑（PREREG 寫死，不倒填）", **(ctx.get("summary_extra") or {})})
        return {"state": "NOT_STARTED", "day": day, "start": start}
    if active is None:
        active = set((load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    last = log[-1] if log else None
    state = {"positions": (last or {}).get("positions") or {}, "cash": (last or {}).get("cash", INITIAL) if last else INITIAL,
             "started": bool(last), "last_rebalance_month": None}
    for e in log:
        if e.get("rebalance_month"):
            state["last_rebalance_month"] = e["rebalance_month"]
    todo = [d for d in px.calendar if d >= start and (not last or d > last["date"])]
    done = []
    for d in todo:
        rec = (_day_monthly if spec.mode == "monthly" else _day_event)(spec, px, d, state, ctx, active)
        _append(spec, rec)
        state = {"positions": rec["positions"], "cash": rec["cash"], "started": True,
                 "last_rebalance_month": rec.get("rebalance_month") or state["last_rebalance_month"]}
        done.append((d, rec["event"]))
    log = read_log(spec)
    write_summary(spec, px, log, ctx.get("summary_extra"))
    return {"state": "HOLD" if not done else "PROCESSED", "day": day, "processed": done}


def run_main(fn: Callable[[], dict], label: str) -> int:
    try:
        print(json.dumps(fn(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] {label} 追蹤失敗：{type(e).__name__}: {e}")
    return 0
