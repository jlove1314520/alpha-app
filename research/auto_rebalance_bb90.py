"""Bb-90 自動月底再平衡（永豐 Shioaji；0050 45%／00646 45%／00697B 10%）。

2026-10-06 先.二十九-三.2。規則見 CLAUDE.md 第八節、設定與開通見 docs/AUTO_TRADING_SETUP.md。
模式 SIMULATION／LIVE_WITH_VETO／LIVE 由本機 research/data/auto_trading/config.local.json 決定，
缺失或讀不懂一律 SIMULATION。憑證只從 .env 讀進行程記憶體，不印出、不寫檔。
CLI 的 --mode-override 只允許降級成 SIMULATION（互動視窗／Cowork 驗證用）。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO / "research" / "data" / "auto_trading"
LEDGER = REPO / "research" / "data" / "live_orders.jsonl"
HEARTBEAT = REPO / "research" / "PROGRESS_HEARTBEAT.jsonl"
PRICE_HISTORY = REPO / "data" / "price_history.json"
TW = timezone(timedelta(hours=8))

WEIGHTS = {"0050": 0.45, "00646": 0.45, "00697B": 0.10}
WHITELIST = frozenset(WEIGHTS)
MODES = ("SIMULATION", "LIVE_WITH_VETO", "LIVE")
VETO_MINUTES = 30
LOT = 1000


class AutoTradingError(Exception):
    pass


def tick_size(price: float) -> float:
    return 0.01 if price < 50 else 0.05


def round_down_tick(price: float) -> float:
    t = tick_size(price)
    return round(math.floor(round(price / t, 6)) * t, 2)


class Paths:
    def __init__(self, base: Path | None = None, ledger: Path | None = None, heartbeat: Path | None = None):
        self.base = Path(base) if base else DEFAULT_DIR
        self.config = self.base / "config.local.json"
        self.stop_flag = self.base / "STOP.flag"
        self.pending = self.base / "pending_orders.json"
        self.status = self.base / "status.json"
        self.state = self.base / "state.json"
        self.ledger = Path(ledger) if ledger else (self.base / "live_orders.jsonl" if base else LEDGER)
        self.heartbeat = Path(heartbeat) if heartbeat else (self.base / "heartbeat.jsonl" if base else HEARTBEAT)


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _append(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_config(paths: Paths) -> dict:
    cfg = _read_json(paths.config)
    if not isinstance(cfg, dict):
        cfg = {}
    if cfg.get("mode") not in MODES:
        cfg["mode"] = "SIMULATION"
    return cfg


def is_stopped(paths: Paths) -> bool:
    return paths.stop_flag.exists()


def write_status(paths: Paths, **kw) -> None:
    st = _read_json(paths.status) or {}
    st.update(kw)
    st["updated_at"] = datetime.now(TW).isoformat(timespec="seconds")
    _write_json(paths.status, st)


def report_error(paths: Paths, msg: str, rnd: str = "auto_rebalance") -> None:
    """對帳不符等失敗：last_error＋紅色橫幅旗標＋心跳 ERROR。本身失敗只降級成警告。"""
    try:
        write_status(paths, last_error=msg, banner="red")
    except Exception as e:
        print(f"[warn] 寫 status 失敗：{e}", flush=True)
    try:
        _append(paths.heartbeat, {"ts": datetime.now(TW).isoformat(timespec="seconds"), "track": "auto_trading",
                                  "round": rnd, "item": msg, "status": "ERROR"})
    except Exception as e:
        print(f"[warn] 寫心跳失敗：{e}", flush=True)


# ---------- 資料 ----------
def load_prev_closes(path: Path = PRICE_HISTORY) -> dict:
    """回傳 {code: (last_close, 'YYYY-MM-DD')}；缺資料的標的不出現。"""
    doc = _read_json(path) or {}
    px = doc.get("prices") or {}
    out = {}
    for c in WHITELIST:
        rows = px.get(c)
        if rows:
            r = rows[-1]
            if r.get("close") and r.get("date"):
                out[c] = (float(r["close"]), r["date"])
    return out


# ---------- 規劃 ----------
def plan_orders(prices: dict, holdings: dict, budget: float, odd_ok: bool, dev_pct: float = 0.5) -> list[dict]:
    """只買不賣：新資金優先補低配，剩餘資金按目標權重分。prices={code:prev_close}。"""
    total = budget + sum(holdings.get(c, 0) * prices[c] for c in WEIGHTS)
    deficit = {c: max(0.0, WEIGHTS[c] * total - holdings.get(c, 0) * prices[c]) for c in WEIGHTS}
    dsum = sum(deficit.values())
    if dsum > budget and dsum > 0:
        alloc = {c: budget * deficit[c] / dsum for c in WEIGHTS}
    else:
        rest = budget - dsum
        alloc = {c: deficit[c] + rest * WEIGHTS[c] for c in WEIGHTS}
    orders = []
    for c in WEIGHTS:
        limit = round_down_tick(prices[c] * (1 + dev_pct / 100))
        qty = int(alloc[c] // limit)
        if not odd_ok:
            qty = qty // LOT * LOT
        if qty <= 0:
            continue
        orders.append({"symbol": c, "action": "Buy", "qty": qty, "limit_price": limit,
                       "lot": "IntradayOdd" if (qty % LOT and odd_ok) else "Common",
                       "cond": "Cash", "amount": round(qty * limit, 2)})
    return orders


# ---------- 硬限制 ----------
def gate_order(o: dict, ctx: dict) -> list[str]:
    """回傳拒單原因清單；空清單＝通過。ctx: cfg, prev_close{code:(px,date)}, today(date), stopped, reconciled(bool)。"""
    why = []
    sym = o.get("symbol")
    if sym not in WHITELIST:
        why.append("WHITELIST:標的不在白名單")
    if o.get("action") != "Buy":
        why.append("ACTION:僅允許買進")
    if o.get("cond") != "Cash":
        why.append("CASH_ONLY:僅限現股")
    if o.get("lot") not in ("Common", "IntradayOdd"):
        why.append("LOT:僅允許整股／盤中零股")
    cap = ctx["cfg"].get("per_order_cap_twd") or 0
    amt = (o.get("qty") or 0) * (o.get("limit_price") or 0)
    if cap <= 0:
        why.append("CAP:未設定單次金額上限")
    elif amt > cap:
        why.append(f"CAP:金額{amt:.0f}超過上限{cap:.0f}")
    pc = (ctx.get("prev_close") or {}).get(sym)
    if not pc:
        why.append("PRICE_MISSING:缺前收價")
    else:
        lp = o.get("limit_price")
        if not lp or lp <= 0:
            why.append("LIMIT:缺限價")
        elif abs(lp / pc[0] - 1) > ctx["cfg"].get("max_price_dev_pct", 1.0) / 100 + 1e-9:
            why.append("LIMIT_DEV:限價偏離前收超過上限")
        age = (ctx["today"] - date.fromisoformat(pc[1])).days
        if age > ctx["cfg"].get("max_data_age_days", 4):
            why.append(f"STALE:資料已過期{age}天")
    if not ctx.get("reconciled", False):
        why.append("RECONCILE:下單前券商持股對帳未通過")
    if ctx.get("stopped"):
        why.append("STOP_FLAG:緊急停止旗標")
    return why


# ---------- 券商 ----------
class ShioajiBroker:
    """simulation=True 走模擬環境（整股）；False 為正式帳戶。憑證只讀 .env 進記憶體。"""

    def __init__(self, simulation: bool):
        import shioaji as sj
        self.sj = sj
        self.simulation = simulation
        env = {}
        for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        self.api = sj.Shioaji(simulation=simulation)
        self.api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
        if not simulation:
            ca = env.get("SINOPAC_CA_PATH")
            if not (ca and env.get("SINOPAC_CA_PASSWD")):
                raise AutoTradingError("正式模式需要本機 .env 的 CA 憑證設定")
            self.api.activate_ca(ca_path=ca, ca_passwd=env["SINOPAC_CA_PASSWD"],
                                 person_id=env.get("SINOPAC_PERSON_ID", ""))
        self._trades = {}

    def positions(self) -> dict:
        out = {}
        try:
            rows = self.api.list_positions(self.api.stock_account, unit=self.sj.constant.Unit.Share)
            mult = 1
        except Exception:
            rows = self.api.list_positions(self.api.stock_account)
            mult = LOT
        for r in rows:
            out[r.code] = out.get(r.code, 0) + int(r.quantity) * mult
        return out

    def place(self, o: dict) -> dict:
        c = self.sj.constant
        contract = self.api.Contracts.Stocks[o["symbol"]]
        order = self.api.Order(
            price=o["limit_price"], quantity=(o["qty"] // LOT if o["lot"] == "Common" else o["qty"]),
            action=c.Action.Buy, price_type=c.StockPriceType.LMT, order_type=c.OrderType.ROD,
            order_lot=c.StockOrderLot.Common if o["lot"] == "Common" else c.StockOrderLot.IntradayOdd,
            order_cond=c.StockOrderCond.Cash, account=self.api.stock_account)
        trade = self.api.place_order(contract, order)
        oid = getattr(trade.order, "id", None) or str(id(trade))
        self._trades[oid] = (trade, o)
        return {"order_id": oid}

    def status(self, order_id: str) -> dict:
        trade, o = self._trades[order_id]
        self.api.update_status(self.api.stock_account)
        st = trade.status
        filled = sum(d.quantity for d in (st.deals or []))
        if o["lot"] == "Common":
            filled *= LOT
        avg = (sum(d.price * d.quantity for d in st.deals) / sum(d.quantity for d in st.deals)) if st.deals else None
        return {"status": str(getattr(st.status, "value", st.status)), "filled_qty": int(filled), "avg_price": avg}


# ---------- 主流程 ----------
def _ledger_keys(paths: Paths) -> dict:
    keys = {}
    if paths.ledger.exists():
        for line in paths.ledger.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("key"):
                keys[r["key"]] = r.get("event")
    return keys


def run_month_end(paths: Paths, broker, now: datetime, prev_close: dict | None = None,
                  mode_override: str | None = None, poll_sec: float = 2.0, polls: int = 5) -> dict:
    cfg = load_config(paths)
    mode = cfg["mode"]
    if mode_override:
        if mode_override != "SIMULATION":
            raise AutoTradingError("--mode-override 只允許 SIMULATION")
        mode = "SIMULATION"
    today = now.astimezone(TW).date()
    ym = today.strftime("%Y%m")
    tranche = int(cfg.get("tranche", 1))
    prev_close = prev_close if prev_close is not None else load_prev_closes()
    res = {"mode": mode, "month": ym, "tranche": tranche, "submitted": [], "rejected": [], "skipped": [], "state": "OK"}

    def log(event, o, **kw):
        _append(paths.ledger, {"ts": now.astimezone(TW).isoformat(timespec="seconds"), "event": event, "mode": mode,
                               "key": o.get("key"), "symbol": o.get("symbol"), "qty": o.get("qty"),
                               "limit_price": o.get("limit_price"), **kw})

    stopped = is_stopped(paths)
    pend = _read_json(paths.pending)
    try:
        positions = broker.positions()
    except Exception as e:
        report_error(paths, f"取得券商持股失敗：{e}")
        res["state"] = "ERROR"
        return res

    # 下單前對帳：與上次執行後留存的持股快照比較（首次執行只建基準）
    state = _read_json(paths.state)
    reconciled = True
    if state is not None and {k: v for k, v in state.get("positions", {}).items() if v} != {k: v for k, v in positions.items() if v}:
        reconciled = False
        report_error(paths, f"持股對帳不符：本機記錄{state.get('positions')}≠券商{positions}")
        res["state"] = "ERROR"
    elif state is None:
        _write_json(paths.state, {"positions": positions, "baseline_at": now.isoformat(timespec="seconds")})

    if pend and (pend.get("done") or not pend.get("execute_after")):
        pend = None
    if pend and pend.get("month") == ym and pend.get("tranche") == tranche and pend.get("cancelled"):
        res["state"] = "CANCELLED"
        return res
    if pend and pend.get("month") == ym and pend.get("tranche") == tranche:
        if now < datetime.fromisoformat(pend["execute_after"]):
            res["state"] = "WAITING_VETO"
            return res
        orders = pend["orders"]
    else:
        budget = (cfg.get("total_capital_twd") or 0) / max(1, int(cfg.get("tranche_total", 4)))
        missing = [c for c in WHITELIST if c not in prev_close]
        if missing or budget <= 0:
            orders = []
            ctxmsg = f"缺前收價{missing}" if missing else "未設定資金（total_capital_twd）"
            log("REJECT", {"key": f"{ym}-T{tranche}-ALL", "symbol": "ALL"}, reasons=["PRICE_MISSING:" + ctxmsg if missing else "CAP:" + ctxmsg])
            res["rejected"].append({"symbol": "ALL", "reasons": [ctxmsg]})
            if missing:
                report_error(paths, f"價格缺失，整批拒單：{missing}")
                res["state"] = "ERROR"
            return res
        odd_ok = mode != "SIMULATION"
        orders = plan_orders({c: prev_close[c][0] for c in WEIGHTS}, positions, budget, odd_ok,
                             dev_pct=min(0.5, cfg.get("max_price_dev_pct", 1.0) / 2))
        for o in orders:
            o["key"] = f"{ym}-T{tranche}-{o['symbol']}"

    ctx = {"cfg": cfg, "prev_close": prev_close, "today": today, "stopped": stopped, "reconciled": reconciled}
    done = _ledger_keys(paths)
    ok_orders = []
    for o in orders:
        if done.get(o["key"]) in ("SUBMITTED", "FILLED", "PARTIAL", "OPEN"):
            res["skipped"].append(o["key"])
            continue
        why = gate_order(o, ctx)
        if why:
            log("REJECT", o, reasons=why)
            res["rejected"].append({"symbol": o["symbol"], "reasons": why})
        else:
            ok_orders.append(o)

    if res["rejected"]:
        write_status(paths, last_reject=[r["reasons"] for r in res["rejected"]][:5])
    if stopped or not reconciled:
        if pend:
            _write_json(paths.pending, {**pend, "cancelled": True})
        return res

    if mode == "LIVE_WITH_VETO" and not (pend and pend.get("month") == ym and pend.get("tranche") == tranche):
        if ok_orders:
            _write_json(paths.pending, {"month": ym, "tranche": tranche, "created_at": now.isoformat(timespec="seconds"),
                                        "execute_after": (now + timedelta(minutes=VETO_MINUTES)).isoformat(timespec="seconds"),
                                        "orders": ok_orders})
            write_status(paths, mode=mode, pending=len(ok_orders))
            res["state"] = "WAITING_VETO"
        return res

    placed = []
    for o in ok_orders:
        try:
            r = broker.place(o)
        except Exception as e:
            log("ERROR", o, error=str(e))
            report_error(paths, f"送單失敗 {o['symbol']}：{e}")
            res["state"] = "ERROR"
            continue
        log("SUBMITTED", o, order_id=r["order_id"], amount=o["amount"])
        placed.append((o, r["order_id"]))
        res["submitted"].append(o["key"])
        time.sleep(1.0 if mode == "SIMULATION" and poll_sec else 0)

    filled = {}
    for o, oid in placed:
        st = {}
        for _ in range(polls):
            try:
                st = broker.status(oid)
            except Exception as e:
                st = {"status": "UNKNOWN", "filled_qty": 0, "error": str(e)}
            if st.get("filled_qty", 0) >= o["qty"]:
                break
            time.sleep(poll_sec)
        ev = "FILLED" if st.get("filled_qty", 0) >= o["qty"] else ("PARTIAL" if st.get("filled_qty", 0) else "OPEN")
        log(ev, o, order_id=oid, filled_qty=st.get("filled_qty", 0), avg_price=st.get("avg_price"), broker_status=st.get("status"))
        filled[o["symbol"]] = filled.get(o["symbol"], 0) + st.get("filled_qty", 0)

    if placed:
        after = broker.positions()
        expect = dict(positions)
        for c, q in filled.items():
            expect[c] = expect.get(c, 0) + q
        if {k: v for k, v in after.items() if v} != {k: v for k, v in expect.items() if v}:
            report_error(paths, f"成交後持股對帳不符：預期{expect}≠券商{after}")
            res["state"] = "ERROR"
        else:
            _write_json(paths.state, {"positions": after, "updated_at": now.isoformat(timespec="seconds")})
        _write_json(paths.pending, {"month": ym, "tranche": tranche, "done": True, "orders": []})
    if res["state"] == "OK":
        write_status(paths, mode=mode, last_run=now.isoformat(timespec="seconds"), last_error=None, banner=None, pending=0)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="執行一次月底流程（依本機設定檔模式）")
    ap.add_argument("--mode-override", help="只允許 SIMULATION")
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args()
    paths = Paths()
    if a.stop:
        paths.stop_flag.parent.mkdir(parents=True, exist_ok=True)
        paths.stop_flag.write_text(datetime.now(TW).isoformat(), encoding="utf-8")
        print("已寫入停止旗標")
        return 0
    if not a.run:
        ap.print_help()
        return 0
    try:
        mode = "SIMULATION" if a.mode_override else load_config(paths)["mode"]
        broker = ShioajiBroker(simulation=(mode == "SIMULATION"))
        res = run_month_end(paths, broker, datetime.now(TW), mode_override=a.mode_override)
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res["state"] in ("OK", "WAITING_VETO") else 1
    except Exception as e:
        report_error(paths, f"自動再平衡執行失敗：{type(e).__name__}")
        print(f"[ERROR] {type(e).__name__}（細節不印出，避免洩漏憑證）", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
