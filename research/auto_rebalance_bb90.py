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
import re
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
        self.public_hb = self.base / "auto_heartbeat.json"
        self.heartbeat = Path(heartbeat) if heartbeat else (self.base / "heartbeat.jsonl" if base else HEARTBEAT)
        self.family = family
        if family:
            d = self.base / family
            self.pending = d / "pending_orders.json"
            self.state = d / "state.json"
            self.ledger = d / "orders.jsonl"

    def scoped(self, mode: str) -> "Paths":
        return Paths(self.base, self.heartbeat, mode_family(mode))


def _num(v) -> float:
    """數值統一轉換：先去千分位逗號再轉 float；None／空字串視為 0（呼叫端原本就是 `or 0`）。
    先.四十：data_audit 的 g_comma_parsing 防線要求，不直接 float() 外部來源的值。"""
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", ""))


def _close_broker(broker) -> None:
    """先.五十-1：各進入點 finally 呼叫；沒有 close() 的測試券商略過。"""
    fn = getattr(broker, "close", None)
    if callable(fn):
        try:
            fn()
        except Exception as e:
            print(f"[warn] 券商連線關閉失敗：{type(e).__name__}（只記警告）", flush=True)


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


def push_send(paths: Paths, title: str, body: str, kind: str) -> dict:
    """先.三十一-一：Web Push（research/web_push.py）。永不拋例外；回傳 {"ok": 送達裝置數, ...}。
    自測以替換本函式代替真的送出。"""
    try:
        import web_push
        return web_push.send(title, body, kind=kind, base=paths.base)
    except Exception as e:
        return {"ok": 0, "failed": 0, "errors": [f"INTERNAL:{type(e).__name__}"]}


def push_notify(paths: Paths, title: str, body: str, kind: str) -> bool:
    """非關鍵推播：失敗只印一行警告（降級），不影響交易流程。"""
    try:
        r = push_send(paths, title, body, kind)
        if not r.get("ok"):
            print(f"[warn] 推播未送達（{kind}）：{'；'.join(r.get('errors', [])[:3]) or '未知'}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"[warn] 推播失敗（{kind}）：{type(e).__name__}", flush=True)
        return False


def report_error(paths: Paths, msg: str, rnd: str = "auto_rebalance") -> None:
    """對帳不符等失敗：last_error＋紅色橫幅旗標＋心跳 ERROR。本身失敗只降級成警告。"""
    push_notify(paths, "自動排程漏跑" if rnd == "auto_trading_watchdog" else "自動交易異常或整批拒單",
                msg[:160], "watchdog" if rnd == "auto_trading_watchdog" else "error")
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
                out[c] = (_num(r["close"]), r["date"])
    return out


def load_ex_div_events(path: Path | None = None) -> dict:
    """{code: [{ex_date, cash}]}；讀不到回 {}（此時任何超過門檻的價差都不會被當成除息日豁免）。"""
    doc = _read_json(path or (REPO / "data" / "ex_dividend_events.json")) or {}
    return doc.get("events") or {}


def resolve_base_prices(refs: dict, prev_close: dict, today: date, events: dict | None = None,
                        gap_pct: float = 1.0, max_age_days: int = 4) -> tuple[dict, list]:
    """先.三十一-三：限價基準＝Shioaji 合約平盤參考價（reference），並與 price_history 昨收交叉核對。
    refs={code:(reference, update_date_iso)}；回傳 ({code:(ref, today_iso)}, 問題清單)，問題非空＝整批拒單。
    規則：缺 reference／update_date 不是今天 → 拒；與昨收差距 >gap_pct% → 除息日（events 內 ex_date==今天）
    才放行，且放行上限是「現金股利／昨收＋gap_pct%」，其餘一律拒。"""
    base, problems = {}, []
    events = events or {}
    for c in WEIGHTS:
        r = refs.get(c)
        if not r or not r[0] or r[0] <= 0:
            problems.append(f"REFERENCE_MISSING:{c} 無平盤參考價")
            continue
        px, ud = _num(r[0]), str(r[1] or "")[:10].replace("/", "-")
        if ud != today.isoformat():
            problems.append(f"REFERENCE_STALE:{c} 參考價更新日{ud or '未知'}不是今天{today.isoformat()}")
            continue
        pc = prev_close.get(c)
        if not pc:
            problems.append(f"PRICE_MISSING:{c} 缺昨收，無法交叉核對")
            continue
        age = (today - date.fromisoformat(pc[1])).days
        if age > max_age_days:
            problems.append(f"STALE:{c} 昨收資料已過期{age}天")
            continue
        gap = abs(px / pc[0] - 1) * 100
        if gap > gap_pct + 1e-9:
            ev = [e for e in events.get(c, []) if e.get("ex_date") == today.isoformat()]
            cash = sum(_num(e.get("cash")) for e in ev)
            allow = gap_pct + (cash / pc[0] * 100 if ev else 0.0)
            if not ev:
                problems.append(f"REFERENCE_GAP:{c} 參考價{px}與昨收{pc[0]}差{gap:.2f}%>{gap_pct}%且非除息日")
                continue
            if gap > allow + 1e-9:
                problems.append(f"REFERENCE_GAP:{c} 除息日但價差{gap:.2f}%超過股利{cash}可解釋的{allow:.2f}%")
                continue
        base[c] = (px, today.isoformat())
    return base, problems


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
        # 先.四十四：Shioaji 預設事件訊息（Session Property 那行）含身分證字號，排程會寫進 scheduler.log → 登入前關掉
        self.api.set_event_callback(lambda *a, **k: None)
        self.api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
        # 先.三十八：Shioaji 預設委託回呼會把整筆委託（含帳號）印到 stdout，排程會寫進 scheduler.log；
        # 改成不印（狀態一律用 update_status／list_trades 主動查，不依賴回呼）
        self.api.set_order_callback(lambda *a, **k: None)
        if not simulation:
            ca = env.get("SINOPAC_CA_PATH")
            if not (ca and env.get("SINOPAC_CA_PASSWD")):
                raise AutoTradingError("正式模式需要本機 .env 的 CA 憑證設定")
            self.api.activate_ca(ca_path=ca, ca_passwd=env["SINOPAC_CA_PASSWD"],
                                 person_id=env.get("SINOPAC_PERSON_ID", ""))
        self._trades = {}

    def close(self) -> None:
        """先.五十-1：登出釋放連線（同一身分證最多 5 條）。失敗只記警告。"""
        try:
            self.api.logout()
        except Exception as e:
            print(f"[warn] Shioaji 登出失敗：{type(e).__name__}（只記警告）", flush=True)

    def trading_available(self, timeout: float = 20.0) -> float:
        """先.五十-6：唯讀參考 api.trading_limits().trading_available（官方僅 08:30–15:00 有效）。失敗拋錯由呼叫端吞掉。"""
        box = {}

        def _call():
            try:
                box["v"] = self.api.trading_limits(self.api.stock_account)
            except Exception as e:
                box["e"] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout)
        v = box.get("v")
        ta = getattr(v, "trading_available", None) if v is not None else None
        if ta is None:
            raise AutoTradingError("trading_limits 查詢失敗或無 trading_available 欄位")
        return float(ta)

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

    def cancel(self, order_id: str) -> dict:
        """先.三十八：撤單（只撤指定委託）。官方 api.cancel_order(trade) 後 update_status 回查狀態。
        https://sinotrade.github.io/zh/tutor/order/Stock/ 。失敗一律拋錯（由呼叫端記 ERROR）。"""
        trade, o = self._find(order_id)
        self.api.cancel_order(trade)
        self.api.update_status(self.api.stock_account)
        return self.status(order_id)

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

    def reference_prices(self, codes, today=None) -> dict:
        """{code:(reference, update_date)}。官方合約欄位 reference（參考價）、update_date（合約更新日），
        https://sinotrade.github.io/zh/tutor/contract/ ；文件未說明 reference 是否含除息調整，故另以昨收交叉核對。"""
        out = {}
        for c in codes:
            k = self.api.Contracts.Stocks[c]
            out[c] = (getattr(k, "reference", None), getattr(k, "update_date", None))
        return out

    def unsettled_payable(self, timeout: float = 20.0) -> float:
        """T+0／T+1／T+2 未交割款合計（api.settlements 各列 amount 取絕對值加總）。
        官方文件 https://sinotrade.github.io/zh/tutor/accounting/settlements/ 只列欄位 date／amount／T，
        未說明 amount 正負號與 T 的涵蓋範圍，所以保守加總所有列的絕對值（寧可多扣）；查詢逾時或失敗一律拋錯。"""
        box = {}

        def _call():
            try:
                box["v"] = self.api.settlements(self.api.stock_account)
            except Exception as e:
                box["e"] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive() or "v" not in box or box["v"] is None:
            raise AutoTradingError(f"settlements 查詢逾時或失敗（{type(box.get('e')).__name__ if box.get('e') else 'timeout'}）")
        return sum((abs(_num(getattr(r, "amount", 0))) for r in box["v"]), 0.0)


# ---------- 官方交易日曆 ----------
def _fetch_calendar_rows(year: int) -> list:
    import requests
    r = requests.get(CAL_URL.format(y=year), timeout=20)
    r.raise_for_status()
    doc = r.json()
    if doc.get("stat") != "ok" or not doc.get("data"):
        raise AutoTradingError("TWSE holidaySchedule 回傳異常")
    return doc["data"]


def load_calendar(year: int, base: Path | None = None, fetch=None) -> dict | None:
    """TWSE 官方「市場開休市日期」。列出且名稱含「開始交易日／最後交易日」者為交易日，其餘列出者一律休市
    （含「市場無交易，僅辦理結算交割作業」）。抓取成功就更新本機快取；失敗退回快取；兩者皆無回傳 None。"""
    base = Path(base) if base else DEFAULT_DIR
    cache = base / f"calendar_{year}.json"
    try:
        rows = (fetch or _fetch_calendar_rows)(year)
        closed = sorted(r[0] for r in rows if not ("開始交易日" in r[1] or "最後交易日" in r[1]))
        doc = {"year": year, "closed": closed, "source": CAL_URL.format(y=year),
               "fetched_at": datetime.now(TW).isoformat(timespec="seconds")}
        _write_json(cache, doc)
        return doc
    except Exception as e:
        print(f"[warn] 取得交易日曆失敗，改用本機快取：{type(e).__name__}", flush=True)
        doc = _read_json(cache)
        return doc if isinstance(doc, dict) and doc.get("closed") is not None else None


def is_trading_day(d: date, cal: dict | None) -> bool:
    if d.weekday() >= 5:
        return False
    if cal is None or cal.get("year") != d.year:
        raise AutoTradingError("無法取得官方交易日曆（網路與本機快取皆失敗），不判斷")
    return d.isoformat() not in set(cal["closed"])


def is_last_trading_day_of_month(d: date, cal: dict) -> bool:
    if not is_trading_day(d, cal):
        return False
    n = d + timedelta(days=1)
    while n.month == d.month:
        if is_trading_day(n, cal):
            return False
        n += timedelta(days=1)
    return True


# ---------- 帳本／狀態輔助 ----------
def sim_veto_on(cfg: dict, mode: str) -> bool:
    """是否走 30 分鐘否決窗＋推播。LIVE_WITH_VETO 一律走（與 sim_veto 無關）；
    先.三十二：SIMULATION 僅在本機設定 sim_veto 恰為 true 時走（預設 false）；LIVE 永不走。"""
    if mode == "LIVE_WITH_VETO":
        return True
    return mode == "SIMULATION" and cfg.get("sim_veto") is True


def _eff_mode(cfg: dict, mode_override: str | None) -> str:
    if mode_override:
        if mode_override != "SIMULATION":
            raise AutoTradingError("--mode-override 只允許 SIMULATION")
        return "SIMULATION"
    return cfg["mode"]


def _log(paths: Paths, now: datetime, mode: str, event: str, o: dict, **kw) -> None:
    # 先.五十-4：模擬環境不支援零股（永豐群組 #83956 #84243 #84559），模擬帳本裡的零股紀錄一律標記、不計入驗證
    if mode_family(mode) == "SIMULATION" and o.get("lot") == "IntradayOdd":
        kw.setdefault("validation", "SIM_ODD_UNSUPPORTED")
    _append(paths.ledger, {"ts": now.astimezone(TW).isoformat(timespec="seconds"), "event": event, "mode": mode,
                           "key": o.get("key"), "symbol": o.get("symbol"), "qty": o.get("qty"),
                           "limit_price": o.get("limit_price"), **kw})


def _ledger_latest(paths: Paths) -> dict:
    """每個冪等鍵最後一筆紀錄（只收本模式族；帳本已分檔，再用 mode 欄位擋一次，防手動併檔）。"""
    out = {}
    if paths.ledger.exists():
        for line in paths.ledger.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("key") and mode_family(r.get("mode", "")) == paths.family:
                out[r["key"]] = r
    return out


def _filled(r: dict) -> int:
    return min(int(r.get("filled_qty") or 0), int(r.get("qty") or 0))


def _filled_amount(r: dict) -> float:
    return _filled(r) * _num(r.get("avg_price") or r.get("limit_price"))


def _rec_date(r: dict) -> date:
    return date.fromisoformat(r["ts"][:10])


def _nz(d: dict) -> dict:
    return {k: v for k, v in d.items() if v}


def _complete_batch(state: dict, latest: dict, fam: str, paths: Paths | None = None) -> None:
    b = state.get("batch")
    pref = f"{fam}-{b['ym']}-{b['label']}-"
    if paths is not None:
        push_notify(paths, "自動交易批次完成", f"{b['ym']} 批次 {b['label']} 已完成（共 {len([k for k in latest if k.startswith(pref)])} 筆委託紀錄）。", "complete")
    state["last_keys"] = [k for k in latest if k.startswith(pref)]
    state["last_done"] = b["ym"]
    state["last_label"] = b["label"]
    if b["label"].startswith("T"):
        state["next_tranche"] = int(b["label"][1:]) + 1
    state["batch"] = None


def _update_drift(shared: Paths, positions: dict, prev_close: dict) -> None:
    """常態期偏離檢查：任一資產偏離目標>5 個百分點寫進 status（App 顯示）；只告警，永不賣出。"""
    try:
        if any(c not in prev_close for c in WEIGHTS):
            return
        vals = {c: positions.get(c, 0) * prev_close[c][0] for c in WEIGHTS}
        tot = sum(vals.values())
        if tot <= 0:
            return
        dev = {c: {"target_pct": WEIGHTS[c] * 100, "actual_pct": round(vals[c] / tot * 100, 2),
                   "dev_pp": round(vals[c] / tot * 100 - WEIGHTS[c] * 100, 2)} for c in WEIGHTS}
        alert = [c for c in WEIGHTS if abs(dev[c]["dev_pp"]) > DRIFT_ALERT_PP]
        write_status(shared, deviation=dev, drift_alert=alert)
    except Exception as e:
        print(f"[warn] 偏離計算失敗：{e}", flush=True)


def _finalize(paths: Paths, broker, now: datetime, prev_close: dict) -> str:
    """把已終結（FILLED／EXPIRED）且尚未入帳的成交併進對帳基準，並推進批次。
    回傳 OK／PENDING（仍有未終結委託，不動基準）／ERROR（持股對不上，已通報）。"""
    state = _read_json(paths.state)
    if state is None:
        report_error(paths, "缺對帳基準（state），無法結算")
        return "ERROR"
    latest = _ledger_latest(paths)
    if any(r.get("event") in NONFINAL for r in latest.values()):
        return "PENDING"
    applied = set(state.get("applied", []))
    fresh = {k: r for k, r in latest.items() if r.get("event") in ("FILLED", "EXPIRED", "CANCELLED") and k not in applied}
    try:
        after = broker.positions()
    except Exception as e:
        report_error(paths, f"取得券商持股失敗：{e}")
        return "ERROR"
    expect = dict(state.get("positions", {}))
    for r in fresh.values():
        expect[r["symbol"]] = expect.get(r["symbol"], 0) + _filled(r)
    if _nz(after) != _nz(expect):
        report_error(paths, f"持股對帳不符：預期{_nz(expect)}≠券商{_nz(after)}（基準{_nz(state.get('positions', {}))}）")
        return "ERROR"
    state["positions"] = after
    state["applied"] = sorted(applied | set(fresh))
    state["updated_at"] = now.isoformat(timespec="seconds")
    b = state.get("batch")
    if b:
        pref = f"{paths.family}-{b['ym']}-{b['label']}-R{b['round']}-"
        cur = [r for k, r in latest.items() if k.startswith(pref)]
        if cur and all(r.get("event") == "FILLED" and _filled(r) >= int(r.get("qty") or 0) for r in cur):
            _complete_batch(state, latest, paths.family, paths)
    _write_json(paths.state, state)
    _update_drift(Paths(paths.base, paths.heartbeat), after, prev_close)
    return "OK"


def _cash_crosscheck(paths: Paths, broker, avail: float, now: datetime) -> None:
    """先.五十-6：唯讀參考 trading_limits().trading_available（08:30–15:00），與「餘額−未交割應付」差 >5% 只記警告，
    不改變任何擋單規則。不印金額。"""
    try:
        hm = (now.astimezone(TW).hour, now.astimezone(TW).minute)
        if not ((8, 30) <= hm <= (15, 0)) or not hasattr(broker, "trading_available"):
            return
        ta = float(broker.trading_available())
        gap = abs(ta - avail) / max(abs(avail), 1.0)
        info = {"checked_at": now.isoformat(timespec="seconds"), "gap_pct": round(gap * 100, 2), "warn": gap > 0.05}
        write_status(Paths(paths.base, paths.heartbeat), cash_crosscheck=info)
        if gap > 0.05:
            print(f"[warn] 可用額度交叉核對差距 {gap * 100:.1f}%（>5%，只記警告，不影響擋單）", flush=True)
    except Exception as e:
        print(f"[warn] 可用額度交叉核對失敗：{type(e).__name__}（只記警告）", flush=True)


def _cash_ok(paths: Paths, broker, cfg: dict, mode: str, orders: list, now: datetime, batch_id: str, res: dict) -> bool:
    """INSUFFICIENT_CASH：整批金額×1.003（手續費緩衝）不得超過可用餘額；查不到一律拒（fail closed）。"""
    need = sum(o["qty"] * o["limit_price"] for o in orders) * CASH_BUFFER
    reason = None
    try:
        if mode == "SIMULATION":
            if cfg.get("sim_cash_twd") is None:
                raise AutoTradingError("模擬模式需在本機設定 sim_cash_twd")
            cash = float(cfg["sim_cash_twd"])
        else:
            cash = float(broker.cash())
        payable = float(broker.unsettled_payable())
        cash -= payable
        _cash_crosscheck(paths, broker, cash, now)
        if cash < need:
            reason = (f"INSUFFICIENT_CASH:可用餘額{cash:.0f}（已扣未交割款{payable:.0f}）不足整批所需{need:.0f}"
                      f"（含{(CASH_BUFFER - 1) * 100:.1f}%手續費緩衝）")
    except Exception as e:
        reason = f"INSUFFICIENT_CASH:餘額查詢失敗（{type(e).__name__}），整批不送單"
    if reason:
        _log(paths, now, mode, "REJECT", {"key": f"{batch_id}-ALL", "symbol": "ALL"}, reasons=[reason])
        res["rejected"].append({"symbol": "ALL", "reasons": [reason]})
        report_error(paths, reason)
        res["state"] = "ERROR"
        return False
    return True


def cancel_open(paths: Paths, broker, now: datetime, mode: str) -> dict:
    """先.三十八：撤掉「本系統帳本內」尚未終結（SUBMITTED／OPEN／PARTIAL）的委託——只照帳本的 order_id 撤，
    絕不列舉或撤帳戶裡其他委託。每筆記 CANCELLED（含撤單前已成交量）；任一撤單失敗→ERROR＋紅橫幅＋推播。
    paths 須為已 scoped 的族路徑。"""
    out = {"cancelled": [], "failed": []}
    for key, r in _ledger_latest(paths).items():
        if r.get("event") not in NONFINAL or not r.get("order_id"):
            continue
        o = {"key": key, "symbol": r.get("symbol"), "qty": r.get("qty"), "limit_price": r.get("limit_price")}
        try:
            st = broker.cancel(r["order_id"])
            fq = min(int((st or {}).get("filled_qty") or 0), int(r.get("qty") or 0))
            _log(paths, now, mode, "CANCELLED", o, order_id=r["order_id"], filled_qty=fq,
                 avg_price=(st or {}).get("avg_price"), broker_status=(st or {}).get("status"), reason="STOP_FLAG")
            out["cancelled"].append(key)
        except Exception as e:
            _log(paths, now, mode, "ERROR", o, order_id=r["order_id"], error=f"撤單失敗：{type(e).__name__}")
            out["failed"].append(key)
    if out["failed"]:
        report_error(paths, f"緊急停止撤單失敗 {len(out['failed'])} 筆，請立即人工到券商確認並撤單")
    return out


def cancel_pending(paths: Paths, now: datetime | None = None) -> dict:
    """先.三十九：只把「目前這一批」待執行訂單標成已取消（不寫 STOP.flag，之後的批次照常）。
    paths 為共用（未 scoped）路徑；依設定模式找對應族的 pending。沒有待執行批次時回 cancelled=False。"""
    now = now or datetime.now(TW)
    cfg = load_config(paths)
    sp = paths.scoped(cfg["mode"])
    pend = _read_json(sp.pending)
    if not isinstance(pend, dict) or pend.get("done") or pend.get("cancelled") or not pend.get("execute_after"):
        return {"ok": True, "cancelled": False, "reason": "目前沒有待執行訂單"}
    pend.update(cancelled=True, cancelled_by="USER_CANCEL_PENDING", cancelled_at=now.isoformat(timespec="seconds"))
    _write_json(sp.pending, pend)
    return {"ok": True, "cancelled": True, "batch_id": pend.get("batch_id")}


# ---------- 主流程 ----------
def run_month_end(paths: Paths, broker, now: datetime, prev_close: dict | None = None,
                  mode_override: str | None = None, poll_sec: float = 2.0, polls: int = 5,
                  drill_label: str | None = None, veto_minutes: float | None = None) -> dict:
    cfg = load_config(paths)
    mode = _eff_mode(cfg, mode_override)
    if drill_label and not (mode == "SIMULATION" and cfg["mode"] == "SIMULATION" and sim_veto_on(cfg, mode)):
        raise AutoTradingError("演練批次只允許 SIMULATION 且 sim_veto: true")
    shared, paths = paths, paths.scoped(mode)
    fam = paths.family
    today = now.astimezone(TW).date()
    ym = today.strftime("%Y%m")
    prev_close = prev_close if prev_close is not None else load_prev_closes()
    res = {"mode": mode, "family": fam, "month": ym, "submitted": [], "rejected": [], "skipped": [], "state": "OK"}

    def log(event, o, **kw):
        _log(paths, now, mode, event, o, **kw)

    stopped = is_stopped(shared)
    if stopped:
        co = cancel_open(paths, broker, now, mode)
        res["cancelled_open"] = co
        if co["failed"]:
            res["state"] = "ERROR"
    try:
        positions = broker.positions()
    except Exception as e:
        report_error(paths, f"取得券商持股失敗：{e}")
        res["state"] = "ERROR"
        return res

    # 前一個交易日以前的未結算委託：先嘗試自動結算（補救漏跑的盤後排程），仍未結算就停手
    latest = _ledger_latest(paths)
    if any(r.get("event") in NONFINAL and _rec_date(r) < today for r in latest.values()):
        settle(shared, broker, now, mode_override=mode_override, force=True, prev_close=prev_close)
        latest = _ledger_latest(paths)
        left = [k for k, r in latest.items() if r.get("event") in NONFINAL and _rec_date(r) < today]
        if left:
            report_error(paths, f"前次批次尚未結算（{len(left)}筆），不送新單")
            res["state"] = "ERROR"
            return res
        positions = broker.positions()

    state = _read_json(paths.state)
    if state is None:
        state = {"positions": positions, "applied": [], "next_tranche": int(cfg.get("tranche", 1)),
                 "baseline_at": now.isoformat(timespec="seconds")}
        _write_json(paths.state, state)
    nonfinal = [k for k, r in latest.items() if r.get("event") in NONFINAL]
    if nonfinal:
        res["skipped"] = nonfinal
        return res
    reconciled = True
    if _finalize(paths, broker, now, prev_close) == "ERROR":
        reconciled = False
        res["state"] = "ERROR"
    state = _read_json(paths.state)
    latest = _ledger_latest(paths)

    tranche_total = max(1, int(cfg.get("tranche_total", 4)))
    batch = state.get("batch")
    if drill_label:
        # 先.三十二 演練 B：獨立批次名，不碰 state 的批次／last_done；之後的否決窗／停止流程與正式批次同一條路
        label, bym, rnd = drill_label, ym, 1
        budget = (cfg.get("total_capital_twd") or 0) / tranche_total
        batch = None
    elif batch:
        label, bym, rnd = batch["label"], batch["ym"], int(batch["round"])
        pref = f"{fam}-{bym}-{label}-R{rnd}-"
        if any(k.startswith(pref) for k in latest) and reconciled:
            if today <= date.fromisoformat(batch["round_date"]):
                res["skipped"] = [k for k in latest if k.startswith(pref)]
                return res
            if rnd >= MAX_ROUNDS:
                report_error(paths, f"批次 {label} 補單已達 {MAX_ROUNDS} 輪仍未買足，停止自動補單，需人工處理")
                res["state"] = "ERROR"
                return res
            rnd += 1
        budget = float(batch["budget"])
        if rnd > 1:
            budget = max(0.0, budget - sum(_filled_amount(r) for k, r in latest.items()
                                           if k.startswith(f"{fam}-{bym}-{label}-")))
    else:
        if state.get("last_done") == ym:
            res["skipped"] = list(state.get("last_keys", []))
            return res
        n = int(state.get("next_tranche") or cfg.get("tranche", 1))
        label = f"T{n}" if n <= tranche_total else "M"
        bym, rnd = ym, 1
        budget = ((cfg.get("total_capital_twd") or 0) / tranche_total if label != "M"
                  else _num(cfg.get("monthly_contribution_twd")))
    res.update(tranche=label, round=rnd)
    batch_id = f"{fam}-{bym}-{label}-R{rnd}"
    pend = _read_json(paths.pending)
    if pend and (pend.get("done") or not pend.get("execute_after")):
        pend = None
    same_pend = bool(pend and pend.get("batch_id") == batch_id)

    if same_pend and pend.get("cancelled"):
        # 先.三十九：只取消本批（App「全部取消」→ /auto/cancel_pending）→逐筆記 CANCELLED、不送單；之後批次照常
        for o in pend.get("orders") or []:
            if o.get("key") and latest.get(o["key"], {}).get("event") != "CANCELLED":
                log("CANCELLED", o, filled_qty=0, reason=pend.get("cancelled_by") or "STOP_FLAG")
        res["state"] = "CANCELLED"
        return res
    def base_prices():
        """取平盤參考價並與昨收交叉核對；有任何問題＝整批拒單報錯，回傳 None。"""
        try:
            refs = broker.reference_prices(list(WEIGHTS), today)
            base, problems = resolve_base_prices(refs, prev_close, today, load_ex_div_events(),
                                                 cfg.get("max_price_dev_pct", 1.0), cfg.get("max_data_age_days", 4))
        except Exception as e:
            base, problems = {}, [f"REFERENCE_MISSING:參考價查詢失敗（{type(e).__name__}）"]
        if problems:
            log("REJECT", {"key": f"{batch_id}-ALL", "symbol": "ALL"}, reasons=problems)
            res["rejected"].append({"symbol": "ALL", "reasons": problems})
            report_error(paths, "限價基準檢查未通過，整批拒單：" + "；".join(problems))
            res["state"] = "ERROR"
            return None
        return base

    if same_pend:
        if now < datetime.fromisoformat(pend["execute_after"]):
            res["state"] = "WAITING_VETO"
            return res
        orders = pend["orders"]
        gate_px = base_prices()
        if gate_px is None:
            return res
    else:
        missing = [c for c in WHITELIST if c not in prev_close]
        if missing or budget <= 0:
            if budget <= 0 and not missing and batch:
                _complete_batch(state, latest, fam, paths)
                _write_json(paths.state, state)
                return res
            ctxmsg = (f"缺前收價{missing}" if missing else
                      ("未設定每月投入（monthly_contribution_twd）" if label == "M" else "未設定資金（total_capital_twd）"))
            log("REJECT", {"key": f"{batch_id}-ALL", "symbol": "ALL"},
                reasons=[("PRICE_MISSING:" if missing else "CAP:") + ctxmsg])
            res["rejected"].append({"symbol": "ALL", "reasons": [ctxmsg]})
            if missing:
                report_error(paths, f"價格缺失，整批拒單：{missing}")
                res["state"] = "ERROR"
            return res
        gate_px = base_prices()
        if gate_px is None:
            return res
        odd_ok = mode != "SIMULATION"
        orders = plan_orders({c: gate_px[c][0] for c in WEIGHTS}, positions, budget, odd_ok,
                             dev_pct=min(0.5, cfg.get("max_price_dev_pct", 1.0) / 2))
        for o in orders:
            o["key"] = f"{batch_id}-{o['symbol']}-{o['part']}"
        if not orders and batch and rnd > 1:
            _complete_batch(state, latest, fam, paths)
            _write_json(paths.state, state)
            return res

    ctx = {"cfg": cfg, "prev_close": gate_px, "today": today, "stopped": stopped, "reconciled": reconciled}
    ok_orders = []
    for o in orders:
        if latest.get(o["key"], {}).get("event") in ("SUBMITTED", "OPEN", "PARTIAL", "FILLED", "EXPIRED"):
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

    if sim_veto_on(cfg, mode) and not same_pend:
        if ok_orders and _cash_ok(paths, broker, cfg, mode, ok_orders, now, batch_id, res):
            exec_after = now + timedelta(minutes=VETO_MINUTES if veto_minutes is None else veto_minutes)
            lines = "；".join(f"{o['symbol']} {'賣' if o.get('action') == 'Sell' else '買'}{o['qty']}股 限價{o['limit_price']}" for o in ok_orders)
            total = sum(_num(o.get("amount")) for o in ok_orders)
            hhmm = exec_after.astimezone(TW).strftime('%H:%M')
            # 先.三十九（修訂版）：預設＝無人回應即依計畫送出；取消是可選的，文字不得要求限時操作
            body = (f"無需操作，{hhmm} 將自動送出；如要取消可按全部取消。"
                    f"內容：{lines}；總額約NT${total:,.0f}。")
            r_push = push_send(paths, "自動交易否決窗開始", body, "veto_start")
            if not r_push.get("ok"):
                why_push = "PUSH_FAILED:否決窗開始推播未送達，本批不執行（fail closed）：" + ("；".join(r_push.get("errors", [])[:3]) or "未知")
                log("REJECT", {"key": f"{batch_id}-ALL", "symbol": "ALL"}, reasons=[why_push])
                res["rejected"].append({"symbol": "ALL", "reasons": [why_push]})
                report_error(paths, "否決窗開始推播未送達，本批不執行，下次排程重試")
                res["state"] = "ERROR"
                return res
            _write_json(paths.pending, {"batch_id": batch_id, "month": bym, "tranche": label, "round": rnd,
                                        "created_at": now.isoformat(timespec="seconds"),
                                        "execute_after": exec_after.isoformat(timespec="seconds"),
                                        "orders": ok_orders})
            write_status(paths, mode=mode, family=fam, pending=len(ok_orders))
            res["state"] = "WAITING_VETO"
        return res

    if drill_label:
        # 演練 B 的唯一預期是「已取消」；走到這裡代表否決窗到期仍未取消→判失敗，且絕不送單、不動 state 批次
        log("REJECT", {"key": f"{batch_id}-ALL", "symbol": "ALL"}, reasons=["DRILL_NOT_CANCELLED:演練批次否決窗到期仍未取消，不送單"])
        report_error(paths, f"演練批次 {label} 否決窗到期仍未取消（演練失敗，未送單）")
        res["state"] = "ERROR"
        return res

    if not ok_orders or not _cash_ok(paths, broker, cfg, mode, ok_orders, now, batch_id, res):
        return res

    state["batch"] = {"label": label, "ym": bym, "round": rnd, "budget": float(batch["budget"]) if batch else budget,
                      "round_date": today.isoformat()}
    state["pre_batch_positions"] = dict(positions)   # 先.五十-5：本批送單前券商持股（unit=Share），供零股驗證比對
    state["pre_batch_date"] = today.isoformat()
    _write_json(paths.state, state)
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
        log(ev, o, order_id=oid, filled_qty=st.get("filled_qty", 0), avg_price=st.get("avg_price"),
            broker_status=st.get("status"))

    if placed:
        _write_json(paths.pending, {"batch_id": batch_id, "month": bym, "tranche": label, "done": True, "orders": []})
        if _finalize(paths, broker, now, prev_close) == "ERROR":
            res["state"] = "ERROR"
    if res["state"] == "OK":
        write_status(paths, mode=mode, family=fam, last_run=now.isoformat(timespec="seconds"), last_error=None,
                     banner=None, pending=0, next_tranche=(_read_json(paths.state) or {}).get("next_tranche"))
    return res


def settle(paths: Paths, broker, now: datetime, mode_override: str | None = None, force: bool = False,
           prev_close: dict | None = None) -> dict:
    """盤後結算：依券商成交回報記下每張委託的最終成交量（FILLED／PARTIAL＋EXPIRED），更新持股基準。
    未成交餘額記 EXPIRED，由下一個交易日的 run 以新冪等鍵後綴（R2…）重排，絕不靜默丟棄。"""
    cfg = load_config(paths)
    mode = _eff_mode(cfg, mode_override)
    shared, paths = paths, paths.scoped(mode)
    local = now.astimezone(TW)
    res = {"mode": mode, "family": paths.family, "state": "OK", "settled": [], "unsettled": []}
    if not force and (local.hour, local.minute) < SETTLE_AFTER:
        res["state"] = "TOO_EARLY"
        return res
    prev_close = prev_close if prev_close is not None else load_prev_closes()
    if is_stopped(shared):
        co = cancel_open(paths, broker, now, mode)
        res["cancelled_open"] = co
        if co["failed"]:
            res["state"] = "ERROR"
    for key, r in _ledger_latest(paths).items():
        if r.get("event") not in NONFINAL:
            continue
        try:
            st = broker.status(r["order_id"])
        except Exception as e:
            res["unsettled"].append(key)
            report_error(paths, f"結算查不到委託 {key}：{type(e).__name__}")
            res["state"] = "ERROR"
            continue
        q, fq = int(r["qty"]), min(int(st.get("filled_qty") or 0), int(r["qty"]))
        o = {"key": key, "symbol": r["symbol"], "qty": q, "limit_price": r.get("limit_price")}
        extra = {"order_id": r["order_id"], "filled_qty": fq, "avg_price": st.get("avg_price"),
                 "broker_status": st.get("status"), "settled": True}
        if fq >= q:
            _log(paths, now, mode, "FILLED", o, **extra)
        else:
            if fq:
                _log(paths, now, mode, "PARTIAL", o, **extra)
            _log(paths, now, mode, "EXPIRED", o, remaining=q - fq, **extra)
        res["settled"].append({"key": key, "filled": fq, "qty": q})
    if res["unsettled"]:
        return res
    if _finalize(paths, broker, now, prev_close) == "ERROR":
        res["state"] = "ERROR"
    else:
        write_status(shared, last_settle=now.isoformat(timespec="seconds"), last_error=None, banner=None,
                     next_tranche=(_read_json(paths.state) or {}).get("next_tranche"))
    try:
        rep_ = odd_lot_verification(paths, broker, now)
        if rep_:
            res["odd_lot_verification"] = rep_
    except Exception as e:
        print(f"[warn] 零股驗證報告產生失敗：{type(e).__name__}（只記警告）", flush=True)
    return res


def odd_lot_verification(paths: Paths, broker, now: datetime) -> dict | None:
    """先.五十-5：「零股首次真實驗證」——只針對 LIVE 族當日的盤中零股委託，逐筆列委託量、成交量、均價，
    並以 unit=Share 持股前後差（券商現有持股 − 本批前對帳基準）對照本日整股＋零股成交量合計。只寫本機，不進 repo。"""
    if paths.family != "LIVE":
        return None
    day = now.astimezone(TW).date().isoformat()
    lat = _ledger_latest(paths)
    today = {k: r for k, r in lat.items() if str(r.get("ts", ""))[:10] == day and r.get("symbol") in WEIGHTS}
    odd = {k: r for k, r in today.items() if k.endswith("-O")}
    if not odd:
        return None
    st = _read_json(paths.state) or {}
    if st.get("pre_batch_date") != day:
        print("[warn] 零股驗證：找不到本日送單前的持股基準（pre_batch_positions），不比對持股差", flush=True)
    base_pos = dict(st.get("pre_batch_positions") or {}) if st.get("pre_batch_date") == day else None
    after = broker.positions()
    rows = [{"key": k, "symbol": r["symbol"], "qty": r.get("qty"), "filled": _filled(r), "avg_price": r.get("avg_price"),
             "event": r.get("event"), "broker_status": r.get("broker_status")} for k, r in sorted(odd.items())]
    per = {}
    for c in WEIGHTS:
        filled_all = sum(_filled(r) for r in today.values() if r["symbol"] == c)
        diff = None if base_pos is None else int(after.get(c, 0)) - int(base_pos.get(c, 0))
        per[c] = {"filled_common_plus_odd": filled_all, "position_diff_shares": diff, "match": diff is not None and filled_all == diff}
    out = {"date": day, "unit": "Share", "odd_orders": rows, "per_symbol": per,
           "all_match": all(v["match"] for v in per.values())}
    _write_json(paths.ledger.parent / f"odd_lot_verification_{day.replace('-', '')}.json", out)
    msg = "；".join(f"{c} 成交 {v['filled_common_plus_odd']} 股／持股增 {v['position_diff_shares']} 股{'' if v['match'] else '（不符）'}"
                   for c, v in per.items())
    push_notify(Paths(paths.base, paths.heartbeat), "零股首次真實驗證", ("全部相符。" if out["all_match"] else "有不符，請查看。") + msg, "info")
    print("零股首次真實驗證：" + msg, flush=True)
    return out


# ---------- 觸發條件與排程入口 ----------
def should_run(paths: Paths, now: datetime, cfg: dict, cal: dict | None) -> str | None:
    """排程每個交易日 09:05／09:40 都會呼叫 --run，這裡決定當天要不要真的動作。
    回傳觸發原因（open_batch／month_end／first_tranche）或 None。"""
    d = now.astimezone(TW).date()
    if not is_trading_day(d, cal):
        return None
    mode = cfg["mode"]
    sp = paths.scoped(mode)
    state = _read_json(sp.state) or {}
    if state.get("batch"):
        return "open_batch"
    ym = d.strftime("%Y%m")
    if state.get("last_done") == ym:
        return None
    pend = _read_json(sp.pending)
    if pend and pend.get("month") == ym and pend.get("cancelled"):
        return None
    if is_last_trading_day_of_month(d, cal):
        return "month_end"
    # 先.三十二：模擬演練日（本機設定 sim_drill_date，僅 SIMULATION 有效）讓排程在非月底也觸發一次
    if mode == "SIMULATION" and cfg.get("sim_drill_date") == d.isoformat():
        return "sim_drill"
    n = int(state.get("next_tranche") or cfg.get("tranche", 1))
    if mode_family(mode) == "LIVE" and n == 1 and not state.get("last_done"):
        return "first_tranche"
    return None


PUBLIC_HB_TASKS = ("run", "settle")
PUBLIC_HB_KEEP = 40


def installed_at(paths: Paths) -> str | None:
    """先.三十九：排程安裝時間（register-auto-trading-tasks.ps1 寫入 installed_at.txt），格式不符回 None。"""
    try:
        t = (paths.base / "installed_at.txt").read_text(encoding="utf-8").strip()
        return t if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", t) else None
    except Exception:
        return None


def write_public_heartbeat(paths: Paths, task: str, outcome: str, now: datetime | None = None) -> None:
    """先.三十一-二：去識別化心跳（只有 ts／任務名／結果代碼，不含金額、持股、委託、reason/detail）。
    寫在 git 忽略的本機路徑，由 scripts/scheduler/publish_heartbeat.py 驗證後以單檔 commit 推上公開 repo。"""
    try:
        code = outcome if isinstance(outcome, str) and re.fullmatch(r"[A-Z_]{2,32}", outcome) else "OTHER"
        if task not in PUBLIC_HB_TASKS:
            return
        now = now or datetime.now(TW)
        doc = _read_json(paths.public_hb) or {}
        events = [e for e in (doc.get("events") or []) if isinstance(e, dict)]
        events.append({"ts": now.isoformat(timespec="seconds"), "task": task, "code": code})
        out = {"schema": 1, "updated_at": now.isoformat(timespec="seconds"), "events": events[-PUBLIC_HB_KEEP:]}
        inst = installed_at(paths)
        if inst:
            out["installed_at"] = inst  # 先.三十九：排程首次安裝時間（只有時間），App 用來避免安裝當天的誤報
        paths.public_hb.parent.mkdir(parents=True, exist_ok=True)
        tmp = paths.public_hb.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(paths.public_hb)
    except Exception as e:
        print(f"[warn] 寫公開心跳失敗：{type(e).__name__}", flush=True)


def sched_heartbeat(paths: Paths, task: str, outcome: str, **kw) -> None:
    try:
        _append(paths.base / "schedule_heartbeat.jsonl",
                {"ts": datetime.now(TW).isoformat(timespec="seconds"), "task": task, "outcome": outcome, **kw})
    except Exception as e:
        print(f"[warn] 寫排程心跳失敗：{e}", flush=True)
    write_public_heartbeat(paths, task, outcome)


def watchdog(paths: Paths, now: datetime, which: str, cal: dict | None = None) -> str:
    """看門狗：交易日該跑的排程任務沒有心跳→紅色橫幅＋心跳 ERROR。自身失敗一律 fail open（不阻擋任何事）。"""
    try:
        d = now.astimezone(TW).date()
        cal = cal if cal is not None else load_calendar(d.year, paths.base)
        if not is_trading_day(d, cal):
            return "NOT_TRADING_DAY"
        since = now.astimezone(TW).replace(hour=9, minute=30, second=0, microsecond=0) if which == "run" \
            else now.astimezone(TW).replace(hour=13, minute=35, second=0, microsecond=0)
        hb = paths.base / "schedule_heartbeat.jsonl"
        seen = []
        if hb.exists():
            for line in hb.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("task") == which and datetime.fromisoformat(r["ts"]) >= since:
                    seen.append(r)
        if not seen:
            report_error(paths, f"排程漏跑：交易日 {d} 的 {which} 任務沒有心跳（工作排程器未觸發或本機未開機）", "auto_trading_watchdog")
            return "MISSED"
        return "OK"
    except Exception as e:
        print(f"[warn] 看門狗自身失敗，fail open：{type(e).__name__}", flush=True)
        return "WATCHDOG_FAILED_OPEN"



# ---------- 先.三十七：今晚無券商演練（假券商、獨立目錄，不建立任何 Shioaji 連線） ----------
DRILL_DIR = REPO / "research" / "data" / "auto_trading_drill"
DRILL_FLAG = "DRILL_ACTIVE.flag"   # 存在時 alpha_live_server 的 /auto/status、/auto/stop 改讀演練目錄
NIGHT_VETO_MINUTES = 10  # 先.三十九：3 分鐘來不及開 App，改 10 分鐘（僅演練）
NIGHT_PHASES = ("start", "n1-create", "n1-execute", "n1b-create", "n1b-execute", "n2-create", "n2-execute",
                "n2-settle", "finish")


class DrillBroker:
    """假券商：狀態存在演練目錄 fake_broker.json（跨行程延續）。送單後先掛著，n2-settle 時才全數成交，
    以走到「盤後結算→對帳→批次完成」那一段。沒有任何網路連線。"""

    def __init__(self, base: Path, fill_now: bool = False):
        self.f = Path(base) / "fake_broker.json"
        self.d = _read_json(self.f) or {"positions": {}, "orders": {}}
        self.fill_now = fill_now

    def _save(self):
        _write_json(self.f, self.d)

    def positions(self):
        return dict(self.d["positions"])

    def reference_prices(self, codes, today=None):
        pc = load_prev_closes()
        return {c: (pc[c][0], today.isoformat()) for c in codes if c in pc}

    def cash(self):
        raise AutoTradingError("演練不查真實餘額")

    def unsettled_payable(self):
        return 0.0

    def place(self, o):
        oid = f"DRILL-{len(self.d['orders']) + 1}"
        self.d["orders"][oid] = {"symbol": o["symbol"], "qty": int(o["qty"]), "price": o["limit_price"], "filled": 0}
        self._save()
        return {"order_id": oid}

    def fill_all(self):
        for oid, o in self.d["orders"].items():
            if o["filled"] < o["qty"]:
                self.d["positions"][o["symbol"]] = self.d["positions"].get(o["symbol"], 0) + (o["qty"] - o["filled"])
                o["filled"] = o["qty"]
        self._save()

    def status(self, oid):
        o = self.d["orders"][oid]
        return {"status": "Filled" if o["filled"] >= o["qty"] else "Submitted", "filled_qty": o["filled"],
                "avg_price": o["price"] if o["filled"] else None}


def _drill_paths() -> Paths:
    return Paths(DRILL_DIR)


def night_drill(phase: str, now: datetime | None = None) -> dict:
    """先.三十七 演練各步驟。只動 DRILL_DIR；正式目錄（DEFAULT_DIR）只讀 config 的資金欄位與推播訂閱（複製一份）。"""
    now = now or datetime.now(TW)
    off_cfg = load_config(Paths())
    if off_cfg["mode"] != "SIMULATION":
        raise AutoTradingError("--night-drill 只允許在 SIMULATION 模式下執行")
    dp = _drill_paths()
    DRILL_DIR.mkdir(parents=True, exist_ok=True)

    def prog(msg):
        push_notify(dp, "演練（假券商）進度", msg, "info")
        print(msg, flush=True)

    if phase == "start":
        cfg = {k: off_cfg[k] for k in ("tranche_total", "total_capital_twd", "per_order_cap_twd",
                                        "max_price_dev_pct", "max_data_age_days") if k in off_cfg}
        cfg.update({"mode": "SIMULATION", "sim_veto": True, "tranche": 1, "sim_cash_twd": 10 ** 12,
                    "note": "先.三十七 今晚無券商演練（假券商）"})
        _write_json(dp.config, cfg)
        subs = DEFAULT_DIR / "push_subscriptions.json"
        if subs.exists():
            (DRILL_DIR / "push_subscriptions.json").write_bytes(subs.read_bytes())
        (DRILL_DIR / DRILL_FLAG).write_text(now.isoformat(timespec="seconds"), encoding="utf-8")
        prog("演練開始：App 自動交易卡現在顯示「演練（假券商）」，不連永豐。")
        return {"phase": phase, "state": "OK"}
    if phase == "finish":
        for f in (DRILL_DIR / DRILL_FLAG, dp.stop_flag, dp.scoped("SIMULATION").pending):
            if f.exists():
                f.unlink()
        prog("演練結束：App 已恢復讀取正式目錄。")
        return {"phase": phase, "state": "OK"}

    broker = DrillBroker(DRILL_DIR)
    pc = load_prev_closes()
    if phase in ("n1b-create", "n1b-execute"):
        if phase == "n1b-create" and dp.stop_flag.exists():
            dp.stop_flag.unlink()
        res = run_month_end(dp, broker, now, prev_close=pc, mode_override="SIMULATION", poll_sec=0, polls=1,
                            drill_label="DRILLN1B", veto_minutes=NIGHT_VETO_MINUTES)
        if phase == "n1b-create" and res["state"] == "WAITING_VETO":
            prog("N1b 已建立待執行訂單（演練：程式稍後會自己呼叫「全部取消」同一個端點，無需操作）。")
        elif phase == "n1b-execute":
            prog(f"N1b 到期：送出 {len(res.get('submitted', []))} 張（預期 0）；狀態 {res['state']}；"
                 f"緊急停止旗標{'有開（不符預期）' if dp.stop_flag.exists() else '未開（符合預期）'}。")
        return {"phase": phase, **res, "stop_flag": dp.stop_flag.exists()}
    if phase in ("n1-create", "n1-execute"):
        res = run_month_end(dp, broker, now, prev_close=pc, mode_override="SIMULATION", poll_sec=0, polls=1,
                            drill_label="DRILLN1", veto_minutes=NIGHT_VETO_MINUTES)
        if phase == "n1-create" and res["state"] == "WAITING_VETO":
            prog(f"N1 已建立待執行訂單（{NIGHT_VETO_MINUTES} 分鐘否決窗）。無需操作。")
        elif phase == "n1-execute":
            sent = [k for k in res.get("submitted", [])]
            prog(f"N1 否決窗到期：送出 {len(sent)} 張（預期 0）；狀態 {res['state']}。")
        return {"phase": phase, **res}
    if phase == "n2-create":
        if dp.stop_flag.exists():
            dp.stop_flag.unlink()
        res = run_month_end(dp, broker, now, prev_close=pc, mode_override="SIMULATION", poll_sec=0, polls=1,
                            veto_minutes=NIGHT_VETO_MINUTES)
        if res["state"] == "WAITING_VETO":
            exe = (_read_json(dp.scoped("SIMULATION").pending) or {}).get("execute_after", "")[11:16]
            prog(f"N2 已建立待執行訂單。無需操作，{exe} 將自動送出；如要取消可按全部取消。")
        return {"phase": phase, **res}
    if phase == "n2-execute":
        res = run_month_end(dp, broker, now, prev_close=pc, mode_override="SIMULATION", poll_sec=0, polls=1,
                            veto_minutes=NIGHT_VETO_MINUTES)
        prog(f"N2 否決窗到期：已送出 {len(res.get('submitted', []))} 張（假券商，尚未成交，等結算）；狀態 {res['state']}。")
        return {"phase": phase, **res}
    if phase == "n2-settle":
        broker.fill_all()
        res = settle(dp, broker, now, mode_override="SIMULATION", force=True, prev_close=pc)
        st = _read_json(dp.scoped("SIMULATION").state) or {}
        prog(f"N2 結算：{len(res.get('settled', []))} 筆成交入帳，對帳{'通過' if res['state'] == 'OK' else '未通過'}"
             f"{'，批次已完成' if st.get('last_done') else ''}。")
        return {"phase": phase, **res, "last_done": st.get("last_done")}
    raise AutoTradingError(f"未知演練步驟 {phase}")


# ---------- 先.三十八：掛單＋砍單串接驗證 ----------
CANCEL_TEST_LOG = REPO / "research" / "data" / "auto_trading_drill" / "cancel_test.jsonl"
LIVE_TEST_CONFIRM = "我確認以真錢帳戶掛0050零股1股並立即撤單"


def _probe_price() -> float:
    pc = load_prev_closes()
    if "0050" not in pc:
        raise AutoTradingError("price_history 沒有 0050 前收")
    return round_down_tick(pc["0050"][0] * 0.95)


def _cancel_roundtrip(broker, o: dict, wait_sec: float = 2.0) -> dict:
    """掛單→查詢→撤單→再查詢。回傳各步結果（不含帳號、金鑰）。"""
    steps = {}
    r = broker.place(o)
    oid = r["order_id"]
    steps["placed"] = True
    time.sleep(wait_sec)
    steps["after_place"] = broker.status(oid)
    steps["after_cancel"] = broker.cancel(oid)
    time.sleep(wait_sec)
    steps["final"] = broker.status(oid)
    steps["cancelled"] = "cancel" in str(steps["final"].get("status", "")).lower()
    steps["filled_qty"] = int(steps["final"].get("filled_qty") or 0)
    return {"order_id": oid, **steps}


def sim_cancel_test(now: datetime | None = None, broker=None) -> dict:
    """先.三十八-二：模擬環境 0050 限價買 1 張（前收×0.95，依檔位取整）→查詢→撤單→確認 Cancelled。
    只寫 research/data/auto_trading_drill/cancel_test.jsonl，不動正式 state／ledger／pending。"""
    now = now or datetime.now(TW)
    rec = {"ts": now.isoformat(timespec="seconds"), "env": "SIMULATION", "symbol": "0050", "qty_lots": 1}
    env = _read_env_file()
    try:
        rec["limit_price"] = _probe_price()
        b = broker or ShioajiBroker(simulation=True)
        o = {"symbol": "0050", "action": "Buy", "qty": LOT, "limit_price": rec["limit_price"], "lot": "Common",
             "part": "C", "cond": "Cash", "key": "SIMTEST"}
        try:
            rec.update(_cancel_roundtrip(b, o))
        finally:
            if broker is None:
                _close_broker(b)
        rec["result"] = "PASS" if rec["cancelled"] and rec["filled_qty"] == 0 else "FAIL"
    except Exception as e:
        rec["result"] = "ERROR"
        rec["error"] = f"{type(e).__name__}：{_mask_secrets(str(e), env)[:300]}"
    _append(CANCEL_TEST_LOG, rec)
    return rec


def live_cancel_test(now: datetime | None = None) -> dict:
    """先.三十八-三：真錢掛單＋撤單測試。**只能由總司令本人在終端機手動執行**；CC／Cowork 不得執行、不得排程。
    0050 盤中零股買 1 股，限價＝前收×0.95（不會成交），掛單後 5 秒內撤單、查詢確認 Cancelled；
    結果寫 LIVE 帳本（事件 SUBMITTED→CANCELLED）、status 並推播。不受 config 模式影響。"""
    now = now or datetime.now(TW)
    if not sys.stdin or not sys.stdin.isatty():
        raise AutoTradingError("--live-cancel-test 只能在互動終端機由本人手動執行（偵測到非互動執行，拒絕）")
    if os.environ.get("ALPHA_SCHEDULED_TASK"):
        raise AutoTradingError("--live-cancel-test 不得由排程呼叫")
    perm = (_read_json(Paths().status) or {}).get("live_permission") or {}
    if not perm.get("effective"):
        raise AutoTradingError("正式環境權限尚未生效（先跑 --preflight 確認「正式環境權限：已生效」）")
    px = _probe_price()
    print(f"即將以【真錢帳戶】送出：0050 盤中零股 買 1 股，限價 {px}（前收×0.95，預期不會成交），掛單後 5 秒內撤單。")
    typed = input(f"請完整輸入確認字串「{LIVE_TEST_CONFIRM}」：").strip()
    if typed != LIVE_TEST_CONFIRM:
        raise AutoTradingError("確認字串不符，已取消，未送出任何委託")
    paths = Paths().scoped("LIVE")
    o = {"symbol": "0050", "action": "Buy", "qty": 1, "limit_price": px, "lot": "IntradayOdd", "part": "O",
         "cond": "Cash", "key": f"LIVETEST-{now.strftime('%Y%m%d%H%M%S')}-0050-O", "amount": px}
    b = ShioajiBroker(simulation=False)
    rec = {"ts": now.isoformat(timespec="seconds"), "env": "LIVE", "symbol": "0050", "qty_shares": 1, "limit_price": px}
    try:
        r = b.place(o)
        _log(paths, now, "LIVE", "SUBMITTED", o, order_id=r["order_id"], reason="LIVE_CANCEL_TEST")
        time.sleep(1.0)
        st = b.cancel(r["order_id"])
        time.sleep(2.0)
        st = b.status(r["order_id"])
        fq = int(st.get("filled_qty") or 0)
        _log(paths, datetime.now(TW), "LIVE", "CANCELLED", o, order_id=r["order_id"], filled_qty=fq,
             avg_price=st.get("avg_price"), broker_status=st.get("status"), reason="LIVE_CANCEL_TEST")
        ok = "cancel" in str(st.get("status", "")).lower() and fq == 0
        rec.update(order_id=r["order_id"], final_status=st.get("status"), filled_qty=fq, result="PASS" if ok else "FAIL")
    except Exception as e:
        rec.update(result="ERROR", error=f"{type(e).__name__}：{_mask_secrets(str(e), _read_env_file())[:300]}")
        report_error(paths, f"真錢掛單＋撤單測試失敗：{type(e).__name__}，請到券商 App 確認是否有殘留委託")
    _close_broker(b)
    _append(CANCEL_TEST_LOG, rec)
    write_status(Paths(), live_cancel_test={k: rec.get(k) for k in ("ts", "result", "final_status", "filled_qty")})
    push_notify(Paths(), "真錢掛單＋撤單測試", f"結果：{rec['result']}（0050 零股 1 股，限價 {px}）", "info")
    return rec

# ---------- 先.三十三-二：真錢帳戶卡（只在本機回給 App，不寫進 repo／公開心跳） ----------
def live_account_summary(paths: Paths | None = None, price_doc: dict | None = None) -> dict:
    """讀 LIVE 族帳本與對帳基準：各標的股數／市值占比／與目標偏離、累計投入、
    與「同金額同日買 0050」對照損益。沒有任何 LIVE 成交時回 {"empty": True}（App 顯示空狀態，不放假資料）。
    未計手續費與稅；市值用 price_history 最新收盤。"""
    paths = (paths or Paths()).scoped("LIVE")
    latest = _ledger_latest(paths)
    fills = [r for r in latest.values() if _filled(r) > 0]
    if not fills:
        return {"empty": True}
    doc = price_doc if price_doc is not None else (_read_json(PRICE_HISTORY) or {})
    px = doc.get("prices") or {}
    last = {c: _num(px[c][-1]["close"]) for c in WEIGHTS if px.get(c)}
    state = _read_json(paths.state) or {}
    pos = {c: int((state.get("positions") or {}).get(c, 0)) for c in WEIGHTS}
    if any(c not in last for c in WEIGHTS):
        return {"empty": False, "error": "price_history 缺白名單標的收盤價，無法計算市值"}
    vals = {c: pos[c] * last[c] for c in WEIGHTS}
    tot = sum(vals.values())
    invested = sum(_filled_amount(r) for r in fills)
    s0050 = sorted(px.get("0050", []), key=lambda r: r["date"])

    def close_on(d: str):
        c = None
        for r in s0050:
            if r["date"] <= d:
                c = r["close"]
            else:
                break
        return c
    bench_sh, miss = 0.0, 0
    for r in fills:
        c = close_on(r["ts"][:10])
        if c:
            bench_sh += _filled_amount(r) / float(c)
        else:
            miss += 1
    bench_val = bench_sh * last["0050"]
    bought = {c: 0 for c in WEIGHTS}
    for r in fills:
        if r.get("symbol") in bought:
            bought[r["symbol"]] += _filled(r)
    sys_val = sum(bought[c] * last[c] for c in WEIGHTS)
    first = min(r["ts"][:10] for r in fills)
    return {"empty": False, "as_of": max(px[c][-1]["date"] for c in WEIGHTS), "since": first,
            "holdings": [{"symbol": c, "shares": pos[c], "value": round(vals[c]),
                          "pct": round(vals[c] / tot * 100, 2) if tot else 0.0, "target_pct": WEIGHTS[c] * 100,
                          "dev_pp": round(vals[c] / tot * 100 - WEIGHTS[c] * 100, 2) if tot else None} for c in WEIGHTS],
            "market_value": round(tot), "invested": round(invested), "pnl": round(sys_val - invested),
            "has_preexisting": any(pos[c] != bought[c] for c in WEIGHTS),
            "bench_0050_value": round(bench_val), "bench_0050_pnl": round(bench_val - invested),
            "bench_missing_fills": miss, "note": "損益只算自動交易買進的股數；未計手續費與稅；市值以最新收盤估算"}


# ---------- 先.三十三-一：上線前自檢（只查詢，絕不送單） ----------
PREFLIGHT_ENV_KEYS = ("SINOPAC_API_KEY", "SINOPAC_SECRET_KEY", "SINOPAC_PERSON_ID", "SINOPAC_CA_PATH",
                      "SINOPAC_CA_PASSWD", "ALPHA_VAPID_PRIVATE_KEY", "ALPHA_VAPID_PUBLIC_KEY", "ALPHA_VAPID_SUBJECT")
SCHED_PYTHON = r"C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"  # 與 run-auto-trading-cycle.ps1 相同
EXDIV_FRESH_HOURS = 72  # 同 generate_status_json.py 對 data/ex_dividend_events.json 的門檻
PREFLIGHT_TASKS = ("AlphaAutoRun0905", "AlphaAutoRun0940", "AlphaAutoSettle1340", "AlphaAutoWatchRun", "AlphaAutoWatchSettle")


def _read_env_file() -> dict:
    env = {}
    p = REPO / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _timed(fn, timeout: float = 25.0):
    box = {}

    def _call():
        try:
            box["v"] = fn()
        except Exception as e:
            box["e"] = e

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("逾時")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def _task_states(names) -> dict:
    """{任務名: State 字串或 None(未註冊)}；用 PowerShell Get-ScheduledTask，只讀。"""
    import subprocess
    cmd = ("$n=@(" + ",".join(f"'{n}'" for n in names) + "); foreach($x in $n){ $t=Get-ScheduledTask -TaskName $x "
           "-ErrorAction SilentlyContinue; if($t){ \"$x=$($t.State)\" } else { \"$x=MISSING\" } }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60).stdout
    res = {n: None for n in names}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.strip().split("=", 1)
            if k in res:
                res[k] = None if v == "MISSING" else v
    return res


SHIOAJI_LOGIN_SCRIPTS = ("shioaji_quotes.py", "shioaji_order_server.py", "auto_rebalance_bb90.py")


def _shioaji_procs() -> list[str]:
    """本機正在執行、會登入 Shioaji 的 python 程式（依命令列判斷，排除本行程）。回傳腳本名清單。"""
    import subprocess
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                        "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    me = os.getpid()
    out = []
    for line in r.stdout.splitlines():
        pid, _, cmd = line.partition("	")
        if not pid.strip().isdigit() or int(pid) == me:
            continue
        hit = next((n for n in SHIOAJI_LOGIN_SCRIPTS if n in cmd), None)
        if hit and "--preflight" not in cmd:
            out.append(hit)
    return out


def preflight(paths: Paths, now: datetime, broker_factory=None, task_states=None, env=None,
              exdiv_doc: dict | None = None, sched_python: str | None = None, proc_lister=None) -> dict:
    """逐項 PASS／FAIL／WARN＋缺什麼。detail 只寫有無／成功與否／日期，不含任何金額、持股數、帳號、金鑰值。
    正式環境只做 login（不 activate_ca——沒有 CA 就不可能送出委託）＋唯讀查詢，結束即 logout。"""
    items = []

    def add(iid, name, result, detail):
        items.append({"id": iid, "name": name, "result": result, "detail": detail})

    cfg = load_config(paths)
    today = now.astimezone(TW).date()
    # 1 .env 金鑰（只報有無）
    try:
        env = env if env is not None else _read_env_file()
        miss = [k for k in PREFLIGHT_ENV_KEYS if not env.get(k)]
        ca_ok = bool(env.get("SINOPAC_CA_PATH")) and Path(env["SINOPAC_CA_PATH"]).exists()
        if not ca_ok and "SINOPAC_CA_PATH" not in miss:
            miss.append("SINOPAC_CA_PATH（檔案不存在）")
        add("env", "本機 .env 金鑰齊全（只檢查有無）", "PASS" if not miss else "FAIL",
            "全部存在" if not miss else "缺：" + "、".join(miss))
    except Exception as e:
        env = {}
        add("env", "本機 .env 金鑰齊全（只檢查有無）", "FAIL", f"讀取失敗（{type(e).__name__}）")
    # 2–3 永豐正式環境唯讀
    api = None
    try:
        if broker_factory:
            api = broker_factory()
        else:
            import shioaji as sj
            api = sj.Shioaji(simulation=False)
            api.set_event_callback(lambda *a, **k: None)  # 事件訊息含身分證字號，不輸出（先.四十四）
            _timed(lambda: api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"]), 60)
        acct = getattr(api, "stock_account", None)
        if acct is None:
            add("live_login", "永豐正式環境唯讀登入", "FAIL", "登入成功但無證券帳戶")
        else:
            add("live_login", "永豐正式環境唯讀登入", "PASS", "正式環境權限：已生效；登入成功（自檢不送任何委託）")
            signed = bool(getattr(acct, "signed", False))
            add("signed", "證券帳戶 API 簽署（signed）", "PASS" if signed else "FAIL",
                "已簽署" if signed else "未簽署：需完成永豐 API 簽署與測試報告（docs/AUTO_TRADING_SETUP.md 第二節）")
            # 先.四十四-一：CA 憑證可啟用（只驗證、不下單；不印路徑、密碼、身分證字號或憑證內容）
            try:
                if broker_factory and not hasattr(api, "activate_ca"):
                    raise AutoTradingError("測試券商不支援 CA")
                ok_ca = _timed(lambda: api.activate_ca(ca_path=env["SINOPAC_CA_PATH"], ca_passwd=env["SINOPAC_CA_PASSWD"],
                                                       person_id=env.get("SINOPAC_PERSON_ID", "")), 60)
                exp = _timed(lambda: api.get_ca_expiretime(env.get("SINOPAC_PERSON_ID", "")), 30)
                exp_s = str(exp)[:10] if exp else "未知"
                days = None
                try:
                    days = (date.fromisoformat(exp_s) - today).days
                except Exception:
                    days = None
                good = bool(ok_ca) and days is not None and days > 30
                add("ca", "CA 憑證可啟用（只驗證、不下單）", "PASS" if good else "FAIL",
                    (f"啟用成功，到期日 {exp_s}（剩 {days} 天）" if ok_ca and days is not None else
                     f"啟用結果 {bool(ok_ca)}，到期日 {exp_s}") + ("" if good else "——需啟用成功且距到期 >30 天"))
            except Exception as e:
                add("ca", "CA 憑證可啟用（只驗證、不下單）", "FAIL",
                    f"啟用失敗（{type(e).__name__}）：{_mask_secrets(str(e), env)[:200]}")
            for iid, name, fn in (
                    ("q_balance", "唯讀查詢：交割戶餘額", lambda: api.account_balance()),
                    ("q_settlements", "唯讀查詢：未交割款", lambda: api.settlements(acct)),
                    ("q_positions", "唯讀查詢：持股", lambda: api.list_positions(acct))):
                try:
                    v = _timed(fn)
                    bad = v is None or bool(getattr(v, "errmsg", ""))
                    add(iid, name, "FAIL" if bad else "PASS", "查詢失敗（回傳空或帶錯誤訊息）" if bad else "查詢成功（金額不顯示）")
                except Exception as e:
                    add(iid, name, "FAIL", f"查詢失敗（{type(e).__name__}）")
    except Exception as e:
        api = None if not broker_factory else api  # 登入失敗不呼叫 logout（會再拋 AuthError）
        # 先.三十四補充：逐字記錄券商錯誤訊息，但先遮掉所有 .env 值（金鑰、身分證字號、憑證路徑等）並限長
        raw = _mask_secrets(str(e), env)[:300]
        why = f"登入失敗（{type(e).__name__}）：{raw}"
        if "production permission" in str(e):
            why += "——目前 API 金鑰尚無正式環境權限，待永豐開通（docs/AUTO_TRADING_SETUP.md 第二節）"
        add("live_login", "永豐正式環境唯讀登入", "FAIL", why)
        for iid, name in (("signed", "證券帳戶 API 簽署（signed）"), ("ca", "CA 憑證可啟用（只驗證、不下單）"),
                          ("q_balance", "唯讀查詢：交割戶餘額"),
                          ("q_settlements", "唯讀查詢：未交割款"), ("q_positions", "唯讀查詢：持股")):
            add(iid, name, "FAIL", "未登入，無法檢查")
    finally:
        if api is not None and not broker_factory:
            try:
                api.logout()
            except Exception as e:
                print(f"[warn] 自檢登出失敗：{type(e).__name__}", flush=True)
    # 4 推播訂閱
    try:
        import web_push
        n = len(web_push.load_subs(paths.base))
        add("push", "推播訂閱 ≥1 支裝置", "PASS" if n >= 1 else "FAIL",
            f"{n} 支" + ("" if n >= 1 else "：請在 iPhone 依文件第八節開啟推播"))
    except Exception as e:
        add("push", "推播訂閱 ≥1 支裝置", "FAIL", f"無法讀取（{type(e).__name__}）")
    # 4b 推播發送依賴（先.三十六）：用排程同一個直譯器實際 import，不送任何推播
    try:
        import subprocess
        sp = sched_python or SCHED_PYTHON
        if not Path(sp).exists():
            add("push_deps", "推播發送依賴可載入（排程直譯器）", "FAIL", "找不到排程用的 python.exe")
        else:
            r = subprocess.run([sp, "-c", "import pywebpush, cryptography, http_ece, py_vapid"],
                               capture_output=True, text=True, timeout=120)
            ok = r.returncode == 0
            last = (r.stderr.strip().splitlines() or ["?"])[-1][:160]
            add("push_deps", "推播發送依賴可載入（排程直譯器）", "PASS" if ok else "FAIL",
                "pywebpush／cryptography／http_ece／py_vapid 皆可載入" if ok
                else f"電腦缺推播套件：{last}（用排程的 python.exe -m pip install -r research/requirements-live.txt）")
    except Exception as e:
        add("push_deps", "推播發送依賴可載入（排程直譯器）", "FAIL", f"檢查失敗（{type(e).__name__}）")
    # 先.五十-2：連線預算（同一身分證最多 5 條 Shioaji 連線，模擬＋正式合計；永豐群組 #81524 #84357）
    try:
        procs = proc_lister() if proc_lister else _shioaji_procs()
        n = len(procs) + 1                      # ＋本次自檢
        names = "、".join(sorted(set(procs))) or "無"
        add("conn_budget", "Shioaji 連線預算（含本次，<5 條）", "PASS" if n < 5 else "FAIL",
            f"本機登入中的程式 {len(procs)} 個（{names}）＋本次自檢＝{n} 條" + ("" if n < 5 else "——達上限，新登入會被拒"))
    except Exception as e:
        add("conn_budget", "Shioaji 連線預算（含本次，<5 條）", "FAIL", f"查詢程序失敗（{type(e).__name__}）")
    # 5 工作排程
    try:
        st = task_states if task_states is not None else _task_states(PREFLIGHT_TASKS)
        bad = [f"{k}（{'未註冊' if v is None else v}）" for k, v in st.items() if v is None or v == "Disabled"]
        add("tasks", "5 個工作排程已註冊且啟用", "PASS" if not bad else "FAIL", "全部 Ready" if not bad else "；".join(bad))
    except Exception as e:
        add("tasks", "5 個工作排程已註冊且啟用", "FAIL", f"查詢失敗（{type(e).__name__}）")
    # 6 日曆快取
    cal = _read_json(paths.base / f"calendar_{today.year}.json")
    ok = isinstance(cal, dict) and cal.get("year") == today.year and bool(cal.get("closed"))
    add("calendar", "官方日曆快取年份正確", "PASS" if ok else "FAIL",
        f"{today.year} 年，抓取於 {str(cal.get('fetched_at', ''))[:10]}" if ok else f"缺 {today.year} 年快取或內容不符")
    # 7 價格與除息資料新鮮度
    pc = load_prev_closes()
    max_age = int(cfg.get("max_data_age_days", 4))
    stale = [f"{c}（{pc[c][1] if c in pc else '無'}）" for c in WEIGHTS
             if c not in pc or (today - date.fromisoformat(pc[c][1])).days > max_age]
    add("prices", f"price_history 新鮮（{max_age} 日內）", "PASS" if not stale else "FAIL",
        "三檔最新 " + "／".join(sorted({pc[c][1] for c in pc})) if not stale else "過期或缺：" + "、".join(stale))
    try:
        # 先.三十四-二：新鮮度依 generate_status_json.py 對本檔的 72 小時門檻；來源涵蓋 ETF＝檔內已有 00 開頭代號。
        # 白名單三檔無事件屬正常（TWT48U 只預告約 5 週內的除權息），判 PASS 附註。引擎的除息拒單規則不在此處、不受影響。
        doc = exdiv_doc if exdiv_doc is not None else (_read_json(REPO / "data" / "ex_dividend_events.json") or {})
        gen_raw = str((doc.get("meta") or {}).get("generated_at") or "")
        gen = datetime.fromisoformat(gen_raw) if gen_raw else None
        if gen is not None and gen.tzinfo is None:
            gen = gen.replace(tzinfo=TW)
        age_h = (now - gen).total_seconds() / 3600 if gen else None
        fresh = age_h is not None and age_h <= EXDIV_FRESH_HOURS
        ev = doc.get("events") or {}
        etf = any(str(k).startswith("00") for k in ev)
        hit = [c for c in WEIGHTS if ev.get(c)]
        probs = ([] if fresh else [f"資料過期或缺產生時間（{gen_raw[:16] or '未知'}，門檻 {EXDIV_FRESH_HOURS} 小時）"]) +                 ([] if etf else ["抓取來源未涵蓋 ETF（檔內沒有 00 開頭代號）"])
        det = (f"產生於 {gen_raw[:16]}，來源涵蓋 ETF；" + (f"白名單有除息公告：{'、'.join(hit)}" if hit else "白名單三檔近期無除息公告")
               if not probs else "；".join(probs))
        add("exdiv", "除息資料新鮮且來源涵蓋 ETF", "PASS" if not probs else "FAIL", det)
    except Exception as e:
        add("exdiv", "除息資料新鮮且來源涵蓋 ETF", "FAIL", f"讀取失敗（{type(e).__name__}）")
    # 8 設定合理
    tot, cap = _num(cfg.get("total_capital_twd")), _num(cfg.get("per_order_cap_twd"))
    tt, tr = int(cfg.get("tranche_total") or 0), int(cfg.get("tranche") or 0)
    probs = []
    if tot <= 0:
        probs.append("total_capital_twd 為 0 或未設定")
    if cap <= 0:
        probs.append("per_order_cap_twd 為 0 或未設定")
    if not (tt >= 1 and 1 <= tr <= tt):
        probs.append("tranche／tranche_total 不在合理範圍")
    if tot > 0 and cap > 0 and tt >= 1 and all(c in pc for c in WEIGHTS):
        biggest = max((o["amount"] for odd in (True, False)
                       for o in plan_orders({c: pc[c][0] for c in WEIGHTS}, {}, tot / tt, odd)), default=0)
        if biggest > cap:
            probs.append("per_order_cap_twd 小於單批最大一筆委託（該筆會被拒單）")
    add("config", "config.local.json 資金／上限／期數合理", "PASS" if not probs else "FAIL",
        "合理（數字不顯示）" if not probs else "；".join(probs))
    # 先.四十四：模擬演練結果與演練設定清理（讀 SIMULATION 族帳本／狀態，不連券商）
    try:
        sp = paths.scoped("SIMULATION")
        sst = _read_json(sp.state) or {}
        lat = _ledger_latest(sp)
        filled = [r for k, r in lat.items() if "-DRILL" not in k and r.get("event") == "FILLED"
                  and r.get("validation") != "SIM_ODD_UNSUPPORTED"]
        okA = bool(sst.get("last_done")) and not sst.get("batch") and bool(filled)
        add("drill_a", "模擬演練 A（建單→送單→成交→結算對帳→批次完成）", "PASS" if okA else "FAIL",
            f"批次完成（{sst.get('last_done')}），成交 {len(filled)} 筆" if okA else "模擬帳本沒有完成的批次")
        dB = {k: r for k, r in lat.items() if "-DRILLB-" in k}
        subB = [k for k, r in dB.items() if r.get("event") in ("SUBMITTED", "OPEN", "PARTIAL", "FILLED")]
        canB = [k for k, r in dB.items() if r.get("event") == "CANCELLED"]
        okB = bool(canB) and not subB and not paths.stop_flag.exists()
        add("drill_b", "模擬演練 B（只取消本批→0 張送出、停止旗標未開）", "PASS" if okB else "FAIL",
            f"取消 {len(canB)} 筆、送出 0 張" if okB else
            (f"有 {len(subB)} 筆被送出" if subB else ("停止旗標是開的" if paths.stop_flag.exists() else "尚未完成（無取消紀錄）")))
        okC = "sim_drill_date" not in cfg
        add("drill_cfg", "演練設定已清理（無 sim_drill_date）", "PASS" if okC else "FAIL",
            "已移除" if okC else f"仍有 sim_drill_date={cfg.get('sim_drill_date')}")
    except Exception as e:
        add("drill_a", "模擬演練結果", "FAIL", f"讀取失敗（{type(e).__name__}）")
    add("mode", "目前模式", "INFO", f"{cfg['mode']}" + ("（sim_veto 開）" if cfg.get("sim_veto") is True else ""))
    out = {"ran_at": now.isoformat(timespec="seconds"),
           "pass": sum(i["result"] == "PASS" for i in items), "fail": sum(i["result"] == "FAIL" for i in items),
           "items": items}
    # 先.四十四-五：全部 PASS 才標示可切換真錢模式（切換仍由總司令本人改設定檔）
    out["go_live_ready"] = out["fail"] == 0 and any(i["id"] == "ca" and i["result"] == "PASS" for i in items)
    out["go_live_blockers"] = [f"{i['name']}：{i['detail']}" for i in items if i["result"] == "FAIL"]
    # 先.三十四補充：正式環境權限首次生效時，App 顯示並推播一次（推播失敗只記警告，不影響自檢）
    prev = (_read_json(paths.status) or {}).get("live_permission") or {}
    ok_live = any(i["id"] == "live_login" and i["result"] == "PASS" for i in items)
    perm = {"effective": ok_live, "checked_at": out["ran_at"],
            "since": (prev.get("since") if prev.get("effective") else out["ran_at"]) if ok_live else None}
    write_status(paths, preflight=out, live_permission=perm)
    if ok_live and not prev.get("effective"):
        try:
            if not push_notify(paths, "正式環境權限已生效", "永豐正式環境唯讀登入成功（自檢只查詢、未啟用 CA，未送任何委託）。", "info"):
                print("[warn] 權限生效推播未送達（只記警告）", flush=True)
        except Exception as e:
            print(f"[warn] 權限生效推播失敗：{type(e).__name__}（只記警告）", flush=True)
    return out


def _mask_secrets(text: str, env: dict | None) -> str:
    for v in sorted((env or {}).values(), key=len, reverse=True):
        if v and len(v) >= 4:
            text = text.replace(v, "<已遮蔽>")
    return re.sub(r"\b[A-Z][12]\d{8}\b", "<已遮蔽>", text)  # 台灣身分證字號樣式


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="排程入口：交易日且符合觸發條件才執行月底流程")
    ap.add_argument("--settle", action="store_true", help="盤後結算（排程 13:40）")
    ap.add_argument("--watchdog", choices=("run", "settle"), help="看門狗：檢查當日該任務是否有心跳")
    ap.add_argument("--mode-override", help="只允許 SIMULATION；--run 時略過觸發條件（互動驗證用）")
    ap.add_argument("--force", action="store_true", help="--settle 略過 13:35 時間限制")
    ap.add_argument("--drill-label", help="先.三十二 演練 B：以獨立批次名走否決窗（僅 SIMULATION＋sim_veto，心跳記 drill 不發布）")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--night-drill", choices=NIGHT_PHASES, help="先.三十七 今晚無券商演練（假券商、獨立目錄、僅 SIMULATION）")
    ap.add_argument("--sim-cancel-test", action="store_true", help="先.三十八 模擬環境掛單＋撤單驗證（不動正式帳本）")
    ap.add_argument("--live-cancel-test", action="store_true",
                    help="先.三十八 真錢掛單＋撤單測試：僅限總司令本人手動執行（CC／Cowork 不得執行、不得排程）")
    ap.add_argument("--preflight", action="store_true", help="先.三十三 上線前自檢：只查詢、絕不送單，結果寫本機 status")
    a = ap.parse_args()
    paths = Paths()
    now = datetime.now(TW)
    if a.stop:
        paths.stop_flag.parent.mkdir(parents=True, exist_ok=True)
        paths.stop_flag.write_text(now.isoformat(), encoding="utf-8")
        print("已寫入停止旗標")
        return 0
    if a.sim_cancel_test:
        out = sim_cancel_test()
        print(json.dumps(out, ensure_ascii=False, default=str))
        return 0 if out.get("result") == "PASS" else 1
    if a.live_cancel_test:
        try:
            out = live_cancel_test()
        except AutoTradingError as e:
            print(f"[拒絕] {e}")
            return 2
        print(json.dumps(out, ensure_ascii=False, default=str))
        return 0 if out.get("result") == "PASS" else 1
    if a.night_drill:
        out = night_drill(a.night_drill)
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get("state") in ("OK", "WAITING_VETO", "CANCELLED") else 1
    if a.preflight:
        out = preflight(paths, now)
        for i in out["items"]:
            print(f"{i['result']:4} {i['name']}：{i['detail']}")
        print(f"合計 PASS {out['pass']}／FAIL {out['fail']}（結果已寫入本機 status.json）")
        return 0
    if a.watchdog:
        out = watchdog(paths, now, a.watchdog)
        print(out)
        return 0
    if not (a.run or a.settle):
        ap.print_help()
        return 0
    task = "settle" if a.settle else "run"
    try:
        cfg = load_config(paths)
        if a.drill_label:
            if not a.run or not re.fullmatch(r"DRILL[A-Z0-9]{1,8}", a.drill_label):
                print("--drill-label 需搭配 --run，且格式為 DRILL 開頭大寫英數")
                return 2
            a.mode_override = "SIMULATION"
            task = "drill"  # 不是 run／settle：不寫進公開心跳、不滿足看門狗，避免混淆排程實證
        mode = _eff_mode(cfg, a.mode_override)
        if a.run:
            reason = "mode_override"
            if not a.mode_override:
                try:
                    reason = should_run(paths, now, cfg, load_calendar(now.year, paths.base))
                except AutoTradingError as e:
                    report_error(paths, f"排程無法判斷交易日：{e}", "auto_trading_schedule")
                    sched_heartbeat(paths, task, "ERROR", detail="calendar")
                    print(f"[ERROR] {e}")
                    return 1
            if reason is None:
                sched_heartbeat(paths, task, "NOT_TRIGGERED")
                print("今日不需動作（非交易日或不符觸發條件）")
                return 0
            broker = ShioajiBroker(simulation=(mode == "SIMULATION"))
            try:
                res = run_month_end(paths, broker, now, mode_override=a.mode_override, drill_label=a.drill_label)
            finally:
                _close_broker(broker)
        else:
            latest = _ledger_latest(paths.scoped(mode))
            if not any(r.get("event") in NONFINAL for r in latest.values()):
                # 先.五十-5：盤中已全數成交也要做零股首次真實驗證（只查詢持股，不送單）
                sp = paths.scoped(mode)
                day = now.date().isoformat()
                if (sp.family == "LIVE" and any(k.endswith("-O") and str(r.get("ts", ""))[:10] == day for k, r in latest.items())
                        and not (sp.ledger.parent / f"odd_lot_verification_{day.replace('-', '')}.json").exists()):
                    vb = ShioajiBroker(simulation=False)
                    try:
                        odd_lot_verification(sp, vb, now)
                    except Exception as e:
                        print(f"[warn] 零股驗證報告產生失敗：{type(e).__name__}（只記警告）", flush=True)
                    finally:
                        _close_broker(vb)
                sched_heartbeat(paths, task, "NOTHING_TO_SETTLE")
                print("沒有待結算的委託")
                return 0
            broker = ShioajiBroker(simulation=(mode == "SIMULATION"))
            try:
                res = settle(paths, broker, now, mode_override=a.mode_override, force=a.force)
            finally:
                _close_broker(broker)
        sched_heartbeat(paths, task, res["state"], reason=(reason if a.run else None))
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res["state"] in ("OK", "WAITING_VETO") else 1
    except Exception as e:
        report_error(paths, f"自動再平衡{task}執行失敗：{type(e).__name__}")
        sched_heartbeat(paths, task, "ERROR", detail=type(e).__name__)
        print(f"[ERROR] {type(e).__name__}（細節不印出，避免洩漏憑證）", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
