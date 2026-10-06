"""Bb-90 自動月底再平衡（永豐 Shioaji；0050 45%／00646 45%／00697B 10%）。

2026-10-06 先.二十九-三.2。規則見 CLAUDE.md 第八節、設定與開通見 docs/AUTO_TRADING_SETUP.md。
模式 SIMULATION／LIVE_WITH_VETO／LIVE 由本機 research/data/auto_trading/config.local.json 決定，
缺失或讀不懂一律 SIMULATION。憑證只從 .env 讀進行程記憶體，不印出、不寫檔。
CLI 的 --mode-override 只允許降級成 SIMULATION（互動視窗／Cowork 驗證用）。
先.三十-一-1：對帳快照、帳本、待執行訂單按模式族分開存（SIMULATION／LIVE 類各一套，
放在 auto_trading/<族>/），冪等鍵以模式族開頭，模擬成交不會讓真錢單被當成已送出。
先.三十-一：--settle 盤後結算（遲到成交／EXPIRED 隔日重排）、整股＋零股拆單、INSUFFICIENT_CASH、
期數自動遞增與常態期（月度投入補低配、偏離>5pp 只告警不賣）、官方交易日曆與 should_run 觸發條件。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
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
HEARTBEAT = REPO / "research" / "PROGRESS_HEARTBEAT.jsonl"
PRICE_HISTORY = REPO / "data" / "price_history.json"
TW = timezone(timedelta(hours=8))

WEIGHTS = {"0050": 0.45, "00646": 0.45, "00697B": 0.10}
WHITELIST = frozenset(WEIGHTS)
MODES = ("SIMULATION", "LIVE_WITH_VETO", "LIVE")
VETO_MINUTES = 30
LOT = 1000
CASH_BUFFER = 1.003
MAX_ROUNDS = 5
SETTLE_AFTER = (13, 35)
DRIFT_ALERT_PP = 5.0
NONFINAL = ("SUBMITTED", "OPEN", "PARTIAL")
CAL_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear={y}"


class AutoTradingError(Exception):
    pass


def tick_size(price: float) -> float:
    return 0.01 if price < 50 else 0.05


def round_down_tick(price: float) -> float:
    t = tick_size(price)
    return round(math.floor(round(price / t, 6)) * t, 2)


def mode_family(mode: str) -> str:
    """LIVE_WITH_VETO 與 LIVE 共用真錢帳戶，同一族；其餘（含無效值）一律 SIMULATION。"""
    return "LIVE" if mode in ("LIVE_WITH_VETO", "LIVE") else "SIMULATION"


class Paths:
    """共用：設定檔、停止旗標、status（App 讀）、心跳。按模式族分開：pending／state／ledger（見 scoped）。"""

    def __init__(self, base: Path | None = None, heartbeat: Path | None = None, family: str | None = None):
        self.base = Path(base) if base else DEFAULT_DIR
        self.config = self.base / "config.local.json"
        self.stop_flag = self.base / "STOP.flag"
        self.status = self.base / "status.json"
        self.heartbeat = Path(heartbeat) if heartbeat else (self.base / "heartbeat.jsonl" if base else HEARTBEAT)
        self.family = family
        if family:
            d = self.base / family
            self.pending = d / "pending_orders.json"
            self.state = d / "state.json"
            self.ledger = d / "orders.jsonl"

    def scoped(self, mode: str) -> "Paths":
        return Paths(self.base, self.heartbeat, mode_family(mode))


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
def split_qty(qty: int, odd_ok: bool) -> list[tuple[str, int]]:
    """>=1000 且非整張：整股一張單＋盤中零股一張單；<1000 只能零股；不支援零股時只留整張部分。"""
    if qty <= 0:
        return []
    whole = qty // LOT * LOT
    odd = qty - whole
    out = []
    if whole:
        out.append(("Common", whole))
    if odd and odd_ok:
        out.append(("IntradayOdd", odd))
    return out


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
        for lot, q in split_qty(int(alloc[c] // limit), odd_ok):
            orders.append({"symbol": c, "action": "Buy", "qty": q, "limit_price": limit, "lot": lot,
                           "part": "C" if lot == "Common" else "O", "cond": "Cash", "amount": round(q * limit, 2)})
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
    elif o.get("lot") == "Common" and (o.get("qty") or 0) % LOT:
        why.append("LOT:整股數量必須是1000的倍數")
    elif o.get("lot") == "IntradayOdd" and (o.get("qty") or 0) >= LOT:
        why.append("LOT:零股數量必須小於1000")
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

    def _find(self, order_id: str):
        if order_id in self._trades:
            return self._trades[order_id]
        # 新行程（盤後 --settle）：從券商當日委託清單找回
        self.api.update_status(self.api.stock_account)
        for t in self.api.list_trades():
            if getattr(t.order, "id", None) == order_id:
                lot = "Common" if "Common" in str(getattr(t.order, "order_lot", "Common")) else "IntradayOdd"
                self._trades[order_id] = (t, {"lot": lot})
                return self._trades[order_id]
        raise AutoTradingError(f"券商當日委託清單找不到 {order_id}")

    def status(self, order_id: str) -> dict:
        trade, o = self._find(order_id)
        self.api.update_status(self.api.stock_account)
        st = trade.status
        filled = sum(d.quantity for d in (st.deals or []))
        if o["lot"] == "Common":
            filled *= LOT
        avg = (sum(d.price * d.quantity for d in st.deals) / sum(d.quantity for d in st.deals)) if st.deals else None
        return {"status": str(getattr(st.status, "value", st.status)), "filled_qty": int(filled), "avg_price": avg}

    def cash(self, timeout: float = 20.0) -> float:
        """現貨交割帳戶餘額（api.account_balance().acc_balance）。逾時或失敗一律拋錯（送單 fail closed）。
        官方文件：https://sinotrade.github.io/zh/tutor/accounting/account_balance/ 僅支援永豐銀行／分戶帳／LINE Bank。"""
        box = {}

        def _call():
            try:
                box["v"] = self.api.account_balance()
            except Exception as e:
                box["e"] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive() or "v" not in box:
            raise AutoTradingError(f"account_balance 查詢逾時或失敗（{type(box.get('e')).__name__ if box.get('e') else 'timeout'}）")
        bal = getattr(box["v"], "acc_balance", None)
        if bal is None or getattr(box["v"], "errmsg", ""):
            raise AutoTradingError("account_balance 回傳無餘額欄位或帶有錯誤訊息")
        return float(bal)


