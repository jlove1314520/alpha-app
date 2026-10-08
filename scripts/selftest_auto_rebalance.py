"""先.二十九-三.4：自動再平衡自測（FakeBroker，不碰任何券商）。"""
import json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
import auto_rebalance_bb90 as A

PUSH_CALLS = []
PUSH_RESULT = {"ok": 1, "failed": 0, "errors": []}


def _push_stub(paths, title, body, kind):
    PUSH_CALLS.append({"title": title, "body": body, "kind": kind})
    return dict(PUSH_RESULT)


A.push_send = _push_stub

TW = A.TW
NOW = datetime(2026, 10, 30, 13, 0, tzinfo=TW)
PC = {"0050": (100.0, "2026-10-29"), "00646": (50.0, "2026-10-29"), "00697B": (36.0, "2026-10-29")}
fails = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

class Fake:
    def __init__(self, pos=None, fill=True, fail_place=False, cash=10**9, cash_err=False, partial=None,
                 refs=None, payable=0.0, payable_err=False):
        self.refs = refs; self.payable = payable; self.payable_err = payable_err
        self.pos = dict(pos or {}); self.fill = fill; self.fail_place = fail_place; self.placed = []; self.orders = {}
        self.cash_val = cash; self.cash_err = cash_err; self.partial = partial; self.late = {}  # oid -> 遲到成交量
    def cash(self):
        if self.cash_err: raise RuntimeError("balance timeout")
        return self.cash_val
    def reference_prices(self, codes, today=None):
        if self.refs is not None: return self.refs
        return {c: (PC[c][0], today.isoformat()) for c in codes}
    def unsettled_payable(self):
        if self.payable_err: raise RuntimeError('settlements timeout')
        return self.payable
    def late_fill(self, frac=1.0):
        for oid, o in self.orders.items():
            q = int(o["qty"] * frac) // (1000 if o["lot"] == "Common" else 1) * (1000 if o["lot"] == "Common" else 1)
            self.late[oid] = q; self.pos[o["symbol"]] = self.pos.get(o["symbol"], 0) + q
    def positions(self): return dict(self.pos)
    def place(self, o):
        if self.fail_place: raise RuntimeError("boom")
        oid = f"O{len(self.placed)+1}"; self.placed.append(o); self.orders[oid] = o
        if self.fill: self.pos[o["symbol"]] = self.pos.get(o["symbol"], 0) + o["qty"]
        return {"order_id": oid}
    def status(self, oid):
        o = self.orders[oid]; q = o["qty"] if self.fill else self.late.get(oid, 0)
        return {"status": "Filled" if q else "Submitted", "filled_qty": q, "avg_price": o["limit_price"]}

def S(p):  # 測試用：SIMULATION 族的分檔路徑
    return p.scoped("SIMULATION")

def setup(cfg=None):
    d = Path(tempfile.mkdtemp())
    base = {"mode": "SIMULATION", "tranche": 1, "tranche_total": 4, "total_capital_twd": 4_000_000,
            "per_order_cap_twd": 1_000_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4, "sim_cash_twd": 100_000_000}
    base.update(cfg or {})
    (d / "config.local.json").write_text(json.dumps(base), encoding="utf-8")
    return A.Paths(d)

def ledger(p, mode="SIMULATION"):
    q = p.scoped(mode)
    return [json.loads(l) for l in q.ledger.read_text(encoding="utf-8").splitlines()] if q.ledger.exists() else []

def run(p, b, now=NOW, pc=PC):
    return A.run_month_end(p, b, now, prev_close=pc, poll_sec=0, polls=1)

# 規劃：新資金補低配、不賣
o = A.plan_orders({"0050": 100, "00646": 50, "00697B": 36}, {"0050": 10000}, 1_000_000, True)
check("規劃只買不賣且 0050 超配不買", all(x["action"] == "Buy" for x in o) and not any(x["symbol"] == "0050" for x in o))
o = A.plan_orders({"0050": 100, "00646": 50, "00697B": 36}, {}, 1_000_000, False)
check("整股模式數量為 1000 倍數", all(x["qty"] % 1000 == 0 for x in o))
check("tick：<50 為 0.01、>=50 為 0.05", A.tick_size(36) == 0.01 and A.tick_size(102.5) == 0.05 and A.round_down_tick(100.52) == 100.5)

# 正常流程
p = setup(); b = Fake()
r = run(p, b)
check("正常：模擬端送單且成交", r["state"] == "OK" and len(r["submitted"]) >= 1 and any(x["event"] == "FILLED" for x in ledger(p)))
n = len(b.placed)
r2 = run(p, b)
check("重複執行不重複下單", len(b.placed) == n and len(r2["skipped"]) == n)

# 逐條硬限制（直接測 gate，各一）
cfg = {"per_order_cap_twd": 1_000_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4}
ctx = lambda **k: {"cfg": cfg, "prev_close": PC, "today": NOW.date(), "stopped": False, "reconciled": True, **k}
good = {"symbol": "0050", "action": "Buy", "qty": 1000, "limit_price": 100.5, "lot": "Common", "cond": "Cash"}
check("gate 合格單通過", A.gate_order(good, ctx()) == [])
check("拒單：非白名單", any(w.startswith("WHITELIST") for w in A.gate_order({**good, "symbol": "2330"}, ctx())))
check("拒單：非現股(融資)", any(w.startswith("CASH_ONLY") for w in A.gate_order({**good, "cond": "MarginTrading"}, ctx())))
check("拒單：賣出", any(w.startswith("ACTION") for w in A.gate_order({**good, "action": "Sell"}, ctx())))
check("拒單：超過單次金額上限", any(w.startswith("CAP") for w in A.gate_order({**good, "qty": 20000}, ctx())))
check("拒單：未設上限", any(w.startswith("CAP") for w in A.gate_order(good, ctx(cfg={**cfg, "per_order_cap_twd": 0}))))
check("拒單：限價偏離前收>1%", any(w.startswith("LIMIT_DEV") for w in A.gate_order({**good, "limit_price": 102.0}, ctx())))
check("拒單：價格缺失", any(w.startswith("PRICE_MISSING") for w in A.gate_order(good, ctx(prev_close={}))))
check("拒單：資料過期", any(w.startswith("STALE") for w in A.gate_order(good, ctx(prev_close={"0050": (100.0, "2026-10-01")}))))
check("拒單：持股對帳未過", any(w.startswith("RECONCILE") for w in A.gate_order(good, ctx(reconciled=False))))
check("拒單：停止旗標", any(w.startswith("STOP_FLAG") for w in A.gate_order(good, ctx(stopped=True))))

# 端到端情境
p = setup(); b = Fake(); run(p, b)
p.stop_flag.write_text("x"); p2 = p
S(p2).ledger.unlink()
b2 = Fake(); p3 = setup(); p3.stop_flag.write_text("x")
r = run(p3, b2)
check("停止旗標：一張單都不送", len(b2.placed) == 0 and any(x["event"] == "REJECT" for x in ledger(p3)))

p = setup(); b = Fake()
r = run(p, b, pc={k: v for k, v in PC.items() if k != "00646"})
check("價格缺失：整批拒單＋ERROR 心跳＋紅色橫幅", len(b.placed) == 0 and r["state"] == "ERROR"
      and json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red"
      and "ERROR" in p.heartbeat.read_text(encoding="utf-8"))

p = setup(); b = Fake()
r = run(p, b, pc={k: (v[0], "2026-09-01") for k, v in PC.items()})
check("資料過期：全數拒單", len(b.placed) == 0 and all(x["event"] == "REJECT" for x in ledger(p)))

p = setup(); run(p, Fake())  # 建基準（首次不送單？先清）
p = setup(); b = Fake({"0050": 5})
run(p, b)  # 首次：基準＝{0050:5}，送單成交後快照更新
b.pos["0050"] += 777  # 券商持股被外部改動
S(p).ledger.unlink(); S(p).pending.unlink(missing_ok=True)
b.placed.clear()
r = run(p, b, now=NOW + timedelta(days=31), pc={k: (v[0], "2026-11-29") for k, v in PC.items()})
check("持股對不上：不送單、ERROR、紅色橫幅", len(b.placed) == 0 and r["state"] == "ERROR"
      and json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red")

p = setup(); b = Fake(fill=False)
r = run(p, b)
ev = [x["event"] for x in ledger(p)]
check("未成交：記 OPEN 且成交後對帳以實際成交量為準", "OPEN" in ev and r["state"] == "OK")

p = setup(); b = Fake(fail_place=True)
r = run(p, b)
check("送單例外：記 ERROR、不中斷流程", r["state"] == "ERROR" and any(x["event"] == "ERROR" for x in ledger(p)))

p = setup({"mode": "bogus"})
check("設定檔模式無效→SIMULATION", A.load_config(p)["mode"] == "SIMULATION")
check("設定檔缺失→SIMULATION", A.load_config(A.Paths(Path(tempfile.mkdtemp())))["mode"] == "SIMULATION")
try:
    run_ = A.run_month_end(setup(), Fake(), NOW, prev_close=PC, mode_override="LIVE"); check("override 不得升級", False)
except A.AutoTradingError:
    check("--mode-override 不得升級成 LIVE", True)

# 否決窗
p = setup({"mode": "LIVE_WITH_VETO"}); b = Fake()
r = run(p, b)
L = p.scoped("LIVE_WITH_VETO")
check("否決窗：先寫待執行訂單、不送單", r["state"] == "WAITING_VETO" and len(b.placed) == 0 and L.pending.exists())
r = run(p, b, now=NOW + timedelta(minutes=10))
check("否決窗內再跑仍等待", r["state"] == "WAITING_VETO" and len(b.placed) == 0)
p.stop_flag.write_text("x")
r = run(p, b, now=NOW + timedelta(minutes=31))
check("否決窗：全部取消(停止旗標)後逾時也不送", len(b.placed) == 0)
p.stop_flag.unlink()
L.pending.write_text(json.dumps({**json.loads(L.pending.read_text(encoding="utf-8")), "cancelled": False}), encoding="utf-8")
r = run(p, b, now=NOW + timedelta(minutes=31))
check("否決窗：逾時且未取消才送單", len(b.placed) >= 1)

# 先.三十-一-1：模擬與 LIVE 狀態分離、冪等鍵含模式
p = setup(); bs = Fake()
r = run(p, bs)
check("分離：模擬先成交", r["state"] == "OK" and len(bs.placed) >= 1)
cfgj = json.loads(p.config.read_text(encoding="utf-8")); cfgj["mode"] = "LIVE"
p.config.write_text(json.dumps(cfgj), encoding="utf-8")
bl = Fake()  # 真錢帳戶：持股與模擬無關
r = run(p, bl)
check("分離：同月切 LIVE 真錢照常送單", len(bl.placed) >= 1 and r["state"] == "OK" and not r["skipped"])
check("分離：切 LIVE 對帳不報錯", json.loads(p.status.read_text(encoding="utf-8")).get("banner") != "red")
check("分離：冪等鍵含模式", all(o.get("key", "").startswith("LIVE-") for o in bl.placed)
      and all(o.get("key", "").startswith("SIMULATION-") for o in bs.placed))
n = len(bl.placed); run(p, bl)
check("分離：LIVE 重跑不重複下單", len(bl.placed) == n)

# ---- 先.三十-一-3：拆單 ----
check("拆單：1449 → 整股1000＋零股449", A.split_qty(1449, True) == [("Common", 1000), ("IntradayOdd", 449)])
check("拆單：整張只一單、<1000 只零股、模擬不支援零股只留整張",
      A.split_qty(2000, True) == [("Common", 2000)] and A.split_qty(449, True) == [("IntradayOdd", 449)]
      and A.split_qty(1449, False) == [("Common", 1000)])
LIVEC = {"mode": "LIVE", "total_capital_twd": 4 * 323_611, "per_order_cap_twd": 1_000_000}
p = setup(LIVEC); b = Fake()
r = run(p, b)
o50 = [o for o in b.placed if o["symbol"] == "0050"]
check("拆單：0050 實際送出整股1000＋零股449、冪等鍵各自獨立",
      sorted((o["lot"], o["qty"]) for o in o50) == [("Common", 1000), ("IntradayOdd", 449)]
      and len({o["key"] for o in o50}) == 2 and all(o["key"].startswith("LIVE-") for o in b.placed))
check("拆單：LIVE 全成交後對帳通過、批次完成、下一期=2", r["state"] == "OK"
      and json.loads(p.scoped("LIVE").state.read_text(encoding="utf-8")).get("next_tranche") == 2)

# ---- 先.三十-一-2：遲到成交與盤後結算 ----
AFTER = NOW.replace(hour=13, minute=40)
PC2 = {k: (v[0], "2026-10-30") for k, v in PC.items()}
PC3 = {k: (v[0], "2026-11-29") for k, v in PC.items()}
p = setup(); b = Fake(fill=False)
r = run(p, b)
check("結算：輪詢時未成交→OPEN、尚未入帳", any(x["event"] == "OPEN" for x in ledger(p))
      and json.loads(S(p).state.read_text(encoding="utf-8")).get("applied") == [])
check("結算：13:35 前不結算(TOO_EARLY)", A.settle(p, b, NOW, prev_close=PC)["state"] == "TOO_EARLY")
r = run(p, b)
check("結算：同日重跑不重複下單", len(b.placed) == 3 and len(r["skipped"]) == 3)
b.late_fill()
r = A.settle(p, b, AFTER, prev_close=PC)
check("結算：遲到成交記 FILLED(settled)", r["state"] == "OK"
      and sum(1 for x in ledger(p) if x["event"] == "FILLED" and x.get("settled")) == 3)
b.fill = True
n = len(b.placed)
r = run(p, b, now=NOW + timedelta(days=31), pc=PC3)
check("結算：遲到成交當日結清→下月對帳通過並照常送單(T2)", r["state"] == "OK" and len(b.placed) > n
      and r["submitted"] and all("-T2-" in k for k in r["submitted"]))

p = setup(); b = Fake(fill=False)
run(p, b)
r = A.settle(p, b, AFTER, prev_close=PC)
ev = [x["event"] for x in ledger(p)]
check("到期：整日未成交→EXPIRED、不報錯、批次保留待重排", r["state"] == "OK" and ev.count("EXPIRED") == 3
      and json.loads(S(p).state.read_text(encoding="utf-8")).get("batch") is not None)
r = run(p, b, now=AFTER)
check("到期：當日不重排（等下個交易日）", len(b.placed) == 3)
b.fill = True
r = run(p, b, now=NOW + timedelta(days=3), pc=PC2)
check("到期：下一個交易日以新冪等鍵後綴(R2)重排", r["state"] == "OK" and r["submitted"]
      and all("-R2-" in k for k in r["submitted"]))
check("到期：R2 成交後批次完成、期數+1",
      json.loads(S(p).state.read_text(encoding="utf-8")).get("next_tranche") == 2)

p = setup(); b = Fake(fill=False)
run(p, b); b.late_fill(0.5)
r = A.settle(p, b, AFTER, prev_close=PC)
evs = ledger(p)
check("部分成交：記 PARTIAL＋EXPIRED(remaining)、持股對帳通過", r["state"] == "OK"
      and any(x["event"] == "PARTIAL" for x in evs)
      and any(x["event"] == "EXPIRED" and x.get("remaining") for x in evs))

p = setup(); b = Fake(fill=False)
run(p, b)
b.orders.clear()
r = A.settle(p, b, AFTER, prev_close=PC)
check("結算：查不到委託→ERROR＋紅色橫幅", r["state"] == "ERROR"
      and json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red")
r = run(p, b, now=NOW + timedelta(days=1), pc=PC2)
check("前日未結算：隔日不送新單、ERROR", r["state"] == "ERROR" and len(b.placed) == 3)

# ---- 先.三十-一-4：INSUFFICIENT_CASH ----
need = sum(o["qty"] * o["limit_price"]
           for o in A.plan_orders({c: v[0] for c, v in PC.items()}, {}, 323_611 * 1.0, True)) * 1.003
p = setup(LIVEC); b = Fake(cash=need - 1)
r = run(p, b)
check("現金不足(差1元)：整批拒單、不送任何一張", r["state"] == "ERROR" and len(b.placed) == 0
      and any("INSUFFICIENT_CASH" in str(x.get("reasons")) for x in ledger(p, "LIVE")))
check("現金不足：紅色橫幅＋心跳 ERROR", json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red"
      and "ERROR" in p.heartbeat.read_text(encoding="utf-8"))
p = setup(LIVEC); b = Fake(cash=need + 1)
check("現金剛好足夠(含0.3%緩衝)：照送", run(p, b)["state"] == "OK" and len(b.placed) >= 3)
p = setup(LIVEC); b = Fake(cash_err=True)
r = run(p, b)
check("餘額查詢失敗：fail closed 不送單", r["state"] == "ERROR" and len(b.placed) == 0)
p = setup({"sim_cash_twd": None}); b = Fake()
r = run(p, b)
check("模擬未設 sim_cash_twd：fail closed 不送單", r["state"] == "ERROR" and len(b.placed) == 0)
p = setup({"sim_cash_twd": 1000}); b = Fake()
check("模擬現金不足：整批拒單", run(p, b)["state"] == "ERROR" and len(b.placed) == 0)

# ---- 先.三十-一-5：期數遞增、常態期、偏離告警 ----
p = setup({"tranche_total": 2, "monthly_contribution_twd": 300_000}); b = Fake()
r1 = run(p, b)
r2 = run(p, b, now=NOW + timedelta(days=31), pc=PC3)
r3 = run(p, b, now=NOW + timedelta(days=62), pc={k: (v[0], "2026-12-30") for k, v in PC.items()})
check("期數：T1→T2→常態期M", r1["submitted"] and all("-T1-" in k for k in r1["submitted"])
      and r2["submitted"] and all("-T2-" in k for k in r2["submitted"])
      and r3["submitted"] and all("-M-" in k for k in r3["submitted"]))
check("常態期：每月投入金額不超過 monthly_contribution_twd",
      sum(o["amount"] for o in b.placed if "-M-" in o["key"]) <= 300_000)
p = setup({"tranche_total": 1, "total_capital_twd": 600_000, "monthly_contribution_twd": 300_000})
b = Fake({"0050": 20000})
run(p, b)
st = json.loads(p.status.read_text(encoding="utf-8"))
check("偏離>5pp：寫入 status 供 App 顯示、永不賣出",
      "0050" in st.get("drift_alert", []) and b.placed and all(o["action"] == "Buy" for o in b.placed))

# ---- 官方交易日曆與觸發條件 ----
ROWS = [["2026-10-09", "國慶日", ""], ["2026-10-26", "調整放假", ""], ["2026-09-28", "教師節", ""],
        ["2026-10-12", "市場無交易，僅辦理結算交割作業", ""], ["2026-10-02", "某某開始交易日", ""],
        ["2026-10-30", "最後交易日", ""]]
cd = Path(tempfile.mkdtemp())
cal = A.load_calendar(2026, cd, fetch=lambda y: ROWS)
D = lambda s: datetime.fromisoformat(s).date()
check("日曆：休市日／結算交割日／週末非交易日，開始／最後交易日為交易日",
      not A.is_trading_day(D("2026-10-09"), cal) and not A.is_trading_day(D("2026-10-12"), cal)
      and not A.is_trading_day(D("2026-10-10"), cal) and A.is_trading_day(D("2026-10-02"), cal)
      and A.is_trading_day(D("2026-10-08"), cal))
check("日曆：月底最後交易日", A.is_last_trading_day_of_month(D("2026-10-30"), cal)
      and not A.is_last_trading_day_of_month(D("2026-10-29"), cal))
def _boom(y): raise RuntimeError("net")
cal2 = A.load_calendar(2026, cd, fetch=_boom)
check("日曆：抓取失敗退回本機快取", cal2 is not None and cal2["closed"] == cal["closed"])
check("日曆：抓取與快取皆失敗→回傳 None", A.load_calendar(2026, Path(tempfile.mkdtemp()), fetch=_boom) is None)
try:
    A.is_trading_day(D("2026-10-08"), None); check("日曆缺失→拋錯(fail closed)", False)
except A.AutoTradingError:
    check("日曆缺失→拋錯(fail closed)", True)
mk = lambda s, h=9, m=5: datetime.fromisoformat(s + f"T{h:02d}:{m:02d}:00+08:00")
p = setup(); cfgx = A.load_config(p)
check("觸發：模擬模式非月底不觸發", A.should_run(p, mk("2026-10-08"), cfgx, cal) is None)
check("觸發：月底最後交易日觸發", A.should_run(p, mk("2026-10-30"), cfgx, cal) == "month_end")
check("觸發：休市日不觸發", A.should_run(p, mk("2026-10-09"), cfgx, cal) is None)
p = setup({"mode": "LIVE_WITH_VETO"}); cfgl = A.load_config(p)
check("觸發：LIVE 類且第1期未執行→切換後第一個交易日觸發",
      A.should_run(p, mk("2026-10-08"), cfgl, cal) == "first_tranche")
sp = p.scoped("LIVE_WITH_VETO")
sp.state.parent.mkdir(parents=True, exist_ok=True)
sp.state.write_text(json.dumps({"last_done": "202610", "next_tranche": 2}), encoding="utf-8")
check("觸發：本月已完成不再觸發", A.should_run(p, mk("2026-10-30"), cfgl, cal) is None)
sp.state.write_text(json.dumps({"batch": {"label": "T1"}, "next_tranche": 1}), encoding="utf-8")
check("觸發：有未完成批次→觸發(補單)", A.should_run(p, mk("2026-10-13"), cfgl, cal) == "open_batch")

# ---- 看門狗與排程心跳 ----
p = setup()
wd = A.watchdog(p, mk("2026-10-08", 9, 55), "run", cal)
check("看門狗：交易日 run 沒心跳→MISSED＋紅色橫幅", wd == "MISSED"
      and json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red")
p = setup()
A._append(p.base / "schedule_heartbeat.jsonl", {"ts": "2026-10-08T09:41:00+08:00", "task": "run", "outcome": "NOT_TRIGGERED"})
check("看門狗：有心跳→OK", A.watchdog(p, mk("2026-10-08", 9, 55), "run", cal) == "OK")
check("看門狗：settle 任務沒心跳→MISSED", A.watchdog(p, mk("2026-10-08", 14, 0), "settle", cal) == "MISSED")
check("看門狗：非交易日不告警", A.watchdog(setup(), mk("2026-10-10", 9, 55), "run", cal) == "NOT_TRADING_DAY")
check("看門狗：自身失敗 fail open(不告警不拋錯)",
      A.watchdog(setup(), mk("2026-10-08", 9, 55), "run", {"bad": 1}) == "WATCHDOG_FAILED_OPEN")
p = setup(); A.sched_heartbeat(p, "run", "OK")
check("排程心跳：寫入 schedule_heartbeat.jsonl", (p.base / "schedule_heartbeat.jsonl").exists())

# ---- 先.三十一-六：App／expected_shift_calendar 的 2026 休市表與官方日曆快取一致 ----
import re as _re
_root = Path(__file__).resolve().parent.parent
_off = A.load_calendar(2026)
SKIPS = []
if _off is None:
    # 先.三十二-三：無網路且無本機快取時只 SKIP＋警告（交易流程本身仍是抓不到日曆一律不動作，不在此放寬）
    SKIPS.append("休市表比對：取得官方日曆（網路或本機快取）")
    print("SKIP 休市表比對：取得官方日曆（網路與本機快取皆無）——[警告] 本項未驗證，有網路或快取時須重跑", flush=True)
else:
    _offw = {d for d in _off["closed"] if datetime.fromisoformat(d).weekday() < 5}
    _html = (_root / "index.html").read_text(encoding="utf-8")
    _m = _re.search(r"const TW_HOLIDAYS_2026=new Set\(\[(.*?)\]\)", _html, _re.S)
    _app = set(_re.findall(r"\d{4}-\d{2}-\d{2}", _m.group(1))) if _m else set()
    _appw = {d for d in _app if datetime.fromisoformat(d).weekday() < 5}
    _py = (_root / "scripts" / "expected_shift_calendar.py").read_text(encoding="utf-8")
    _m2 = _re.search(r"TW_HOLIDAYS_2026 = \{(.*?)\}", _py, _re.S)
    _pyset = set(_re.findall(r"\d{4}-\d{2}-\d{2}", _m2.group(1))) if _m2 else set()
    _pyw = {d for d in _pyset if datetime.fromisoformat(d).weekday() < 5}
    check(f"休市表比對：index.html 平日休市日 == 官方（差異 {sorted(_offw ^ _appw)}）", _appw == _offw and bool(_app))
    check(f"休市表比對：expected_shift_calendar.py 平日休市日 == 官方（差異 {sorted(_offw ^ _pyw)}）", _pyw == _offw and bool(_pyset))
    check("休市表比對：兩份清單含 2026-09-28（教師節）", "2026-09-28" in _app and "2026-09-28" in _pyset)

# ---- 先.三十一-三／四：限價基準改平盤參考價＋交叉核對；未交割款扣除 ----
TODAY = NOW.date()
TD = TODAY.isoformat()
_ok, _pr = A.resolve_base_prices({c: (PC[c][0], TD) for c in PC}, PC, TODAY, {})
check("參考價：與昨收一致→通過且基準＝參考價", not _pr and _ok["0050"] == (100.0, TD))
_ok, _pr = A.resolve_base_prices({"0050": (97.5, TD), "00646": (50.0, TD), "00697B": (36.0, TD)}, PC, TODAY, {})
check("參考價：非除息日價差2.5%→問題清單含 REFERENCE_GAP", any(x.startswith("REFERENCE_GAP:0050") for x in _pr))
_ev = {"0050": [{"ex_date": TD, "cash": 2.0}]}
_ok, _pr = A.resolve_base_prices({"0050": (97.5, TD), "00646": (50.0, TD), "00697B": (36.0, TD)}, PC, TODAY, _ev)
check("參考價：除息日（股利2.0）價差2.5%→放行並採參考價", not _pr and _ok["0050"][0] == 97.5)
_ev2 = {"0050": [{"ex_date": TD, "cash": 0.5}]}
_ok, _pr = A.resolve_base_prices({"0050": (95.0, TD), "00646": (50.0, TD), "00697B": (36.0, TD)}, PC, TODAY, _ev2)
check("參考價：除息日但價差5%遠超股利可解釋範圍→仍拒", any(x.startswith("REFERENCE_GAP:0050") for x in _pr))
_ok, _pr = A.resolve_base_prices({"0050": (100.0, TD), "00646": (50.0, TD)}, PC, TODAY, {})
check("參考價：缺 00697B→REFERENCE_MISSING", any(x.startswith("REFERENCE_MISSING:00697B") for x in _pr))
_ok, _pr = A.resolve_base_prices({"0050": (100.0, "2026-10-29"), "00646": (50.0, TD), "00697B": (36.0, TD)}, PC, TODAY, {})
check("參考價：更新日不是今天→REFERENCE_STALE", any(x.startswith("REFERENCE_STALE:0050") for x in _pr))

p = setup(); b = Fake(refs={"0050": (100.5, TD), "00646": (50.0, TD), "00697B": (36.0, TD)})
r = run(p, b)
_o = [x for x in b.placed if x["symbol"] == "0050"]
check("端到端：限價基準採參考價100.5（不是昨收100）", bool(_o) and _o[0]["limit_price"] == A.round_down_tick(100.5 * 1.005))
p = setup(); b = Fake(refs={"0050": (97.0, TD), "00646": (50.0, TD), "00697B": (36.0, TD)})
_saved = A.load_ex_div_events; A.load_ex_div_events = lambda *a, **k: {}
r = run(p, b); A.load_ex_div_events = _saved
check("端到端：價差異常且非除息日→整批拒單、不送單、ERROR",
      r["state"] == "ERROR" and not b.placed and any("REFERENCE_GAP" in str(x) for x in r["rejected"]))
p = setup(); b = Fake(refs={})
r = run(p, b)
check("端到端：查不到參考價→整批拒單", r["state"] == "ERROR" and not b.placed)
p = setup(); b = Fake(payable=99_500_000)
r = run(p, b)
check("交割款：可用餘額扣掉未交割應付款後不足→INSUFFICIENT_CASH 不送單",
      not b.placed and any("INSUFFICIENT_CASH" in str(x) for x in r["rejected"]))
p = setup(); b = Fake(payable=1_000)
r = run(p, b)
check("交割款：未交割款很小→照常送單", bool(b.placed))
p = setup(); b = Fake(payable_err=True)
r = run(p, b)
check("交割款：未交割款查詢失敗→一律拒單（fail closed）", not b.placed and r["state"] == "ERROR")

# ---- 先.三十一-二：去識別化心跳 ----
import importlib.util as _ilu
_sp = _ilu.spec_from_file_location("publish_heartbeat", str(Path(__file__).resolve().parent / "scheduler" / "publish_heartbeat.py"))
_ph = _ilu.module_from_spec(_sp); _sp.loader.exec_module(_ph)
p = setup()
A.sched_heartbeat(p, "run", "WAITING_VETO", reason="mode_override", detail="X123456789")
A.sched_heartbeat(p, "settle", "weird code 1234")
A.sched_heartbeat(p, "watchdog", "OK")
_pub = json.loads(p.public_hb.read_text(encoding="utf-8"))
check("公開心跳：只有 schema/updated_at/events", set(_pub) == {"schema", "updated_at", "events"})
check("公開心跳：每筆只有 ts/task/code", all(set(e) == {"ts", "task", "code"} for e in _pub["events"]))
check("公開心跳：不合規結果碼降為 OTHER、非 run/settle 任務不寫", [e["code"] for e in _pub["events"]] == ["WAITING_VETO", "OTHER"])
check("公開心跳：不含 reason/detail 內容", "X123456789" not in json.dumps(_pub) and "mode_override" not in json.dumps(_pub))
check("隱私檢查：正常檔通過", _ph.privacy_check(_pub) is None)
_bad = json.loads(json.dumps(_pub)); _bad["events"][0]["qty"] = 1000
check("隱私檢查：多出 qty 欄位被擋", _ph.privacy_check(_bad) is not None)
_bad = json.loads(json.dumps(_pub)); _bad["events"][0]["code"] = "OK1000"
check("隱私檢查：結果碼含數字被擋", _ph.privacy_check(_bad) is not None)
_bad = json.loads(json.dumps(_pub)); _bad["events"][0]["task"] = "buy 0050"
check("隱私檢查：任務名不在白名單被擋", _ph.privacy_check(_bad) is not None)
_bad = json.loads(json.dumps(_pub)); _bad["holdings"] = {"0050": 1}
check("隱私檢查：多出頂層欄位被擋", _ph.privacy_check(_bad) is not None)

# ---- 先.三十一-一：Web Push 接線 ----
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
p = setup({"mode": "LIVE_WITH_VETO"}); b = Fake()
r = run(p, b); L = p.scoped("LIVE_WITH_VETO")
vs = [c for c in PUSH_CALLS if c["kind"] == "veto_start"]
check("推播：否決窗開始送出一則 veto_start 並寫入 pending", len(vs) == 1 and L.pending.exists() and r["state"] == "WAITING_VETO")
check("推播：內容含股數／限價／總額／送出時間／取消方式", all(k in vs[0]["body"] for k in ("股", "限價", "總額", "送出", "全部取消")))
check("推播（先.三十九修訂）：寫「無需操作、HH:MM 將自動送出、可按全部取消」，不要求限時操作", "無需操作" in vs[0]["body"] and "將自動送出" in vs[0]["body"] and "請在" not in vs[0]["body"])
check("推播：內容不含帳號與金鑰字樣", not any(k in vs[0]["body"].lower() for k in ("secret", "api_key", "token", "account")))
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 0, "errors": ["NO_SUBSCRIPTION:x"]})
p = setup({"mode": "LIVE_WITH_VETO"}); b = Fake()
r = run(p, b); L = p.scoped("LIVE_WITH_VETO")
check("推播：否決窗推播失敗→不寫 pending、不送單（fail closed）", r["state"] == "ERROR" and not L.pending.exists() and not b.placed)
check("推播：失敗→紅色橫幅與 last_error", json.loads(p.status.read_text(encoding="utf-8")).get("banner") == "red")
check("推播：失敗原因 PUSH_FAILED 進拒單紀錄", any("PUSH_FAILED" in json.dumps(x, ensure_ascii=False) for x in r["rejected"]))
PUSH_RESULT.update({"ok": 1, "errors": []})
r = run(p, b, now=NOW + timedelta(days=1))
check("推播：恢復後下次排程重試即進入否決窗", r["state"] == "WAITING_VETO" and L.pending.exists())
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 0, "errors": ["NO_SUBSCRIPTION:x"]})
p = setup(); b = Fake()
r = run(p, b)
check("推播：模擬模式推播失敗只降級，照常成交", r["state"] == "OK" and len(b.placed) >= 1)
check("推播：批次完成有送 complete 推播（失敗不影響）", any(c["kind"] == "complete" for c in PUSH_CALLS))
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
A.report_error(p, "對帳不符測試")
check("推播：report_error 送 error 推播", any(c["kind"] == "error" for c in PUSH_CALLS))
A.report_error(p, "漏跑測試", rnd="auto_trading_watchdog")
check("推播：看門狗漏跑送 watchdog 推播", any(c["kind"] == "watchdog" for c in PUSH_CALLS))
_orig = A.push_send
A.push_send = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    A.report_error(p, "推播本身爆炸"); ok_boom = True
except Exception:
    ok_boom = False
A.push_send = _orig
check("推播：推播函式自己拋例外時 report_error 不中斷", ok_boom)


# ---- 先.三十二：sim_veto（僅 SIMULATION 有效、預設 false、LIVE 類不受影響）＋演練日觸發＋演練 B ----
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "failed": 0, "errors": []})
check("sim_veto：輔助判斷（LIVE_WITH_VETO 恆真／LIVE 恆假／SIMULATION 須恰為 true）",
      A.sim_veto_on({}, "LIVE_WITH_VETO") and A.sim_veto_on({"sim_veto": False}, "LIVE_WITH_VETO")
      and not A.sim_veto_on({"sim_veto": True}, "LIVE") and not A.sim_veto_on({}, "SIMULATION")
      and not A.sim_veto_on({"sim_veto": "true"}, "SIMULATION") and A.sim_veto_on({"sim_veto": True}, "SIMULATION"))
p = setup(); b = Fake(); r = run(p, b)
check("sim_veto：預設（未設定）模擬照舊立即送單、無否決窗", r["state"] == "OK" and b.placed and "execute_after" not in (A._read_json(S(p).pending) or {}))
p = setup({"sim_veto": True}); b = Fake(); r = run(p, b)
vs = [c for c in PUSH_CALLS if c["kind"] == "veto_start"]
check("sim_veto：true→模擬也進否決窗＋推播、不送單", r["state"] == "WAITING_VETO" and not b.placed and S(p).pending.exists() and len(vs) == 1)
r = run(p, b, now=NOW + timedelta(minutes=10))
check("sim_veto：否決窗內再跑仍等待", r["state"] == "WAITING_VETO" and not b.placed)
r = run(p, b, now=NOW + timedelta(minutes=31))
check("sim_veto：逾時未取消→送單並成交", r["state"] == "OK" and len(b.placed) >= 1 and any(c["kind"] == "complete" for c in PUSH_CALLS))
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 0, "errors": ["NO_SUBSCRIPTION:x"]})
p = setup({"sim_veto": True}); b = Fake(); r = run(p, b)
check("sim_veto：推播送不到→整批不執行（fail closed，同 LIVE_WITH_VETO）",
      r["state"] == "ERROR" and not S(p).pending.exists() and not b.placed
      and any("PUSH_FAILED" in json.dumps(x, ensure_ascii=False) for x in r["rejected"]))
PUSH_RESULT.update({"ok": 1, "errors": []})
p = setup({"mode": "LIVE", "sim_veto": True}); b = Fake(); r = run(p, b)
check("sim_veto：LIVE 不受影響（照舊直接送單、無否決窗）", r["state"] == "OK" and b.placed and "execute_after" not in (A._read_json(p.scoped("LIVE").pending) or {}))
p = setup({"mode": "LIVE_WITH_VETO", "sim_veto": False}); b = Fake(); r = run(p, b)
check("sim_veto：LIVE_WITH_VETO 設 false 仍走否決窗", r["state"] == "WAITING_VETO" and not b.placed)
# 演練日觸發（僅 SIMULATION）
_cal = {"year": 2026, "closed": []}
_d7 = datetime(2026, 10, 7, 9, 5, tzinfo=TW)
p = setup({"sim_drill_date": "2026-10-07"})
check("演練日：SIMULATION 在 sim_drill_date 觸發 sim_drill", A.should_run(p, _d7, A.load_config(p), _cal) == "sim_drill")
check("演練日：其他日期不觸發", A.should_run(p, _d7 + timedelta(days=1), A.load_config(p), _cal) is None)
p = setup({"mode": "LIVE_WITH_VETO", "sim_drill_date": "2026-10-07"}); A._write_json(p.scoped("LIVE_WITH_VETO").state, {"last_done": "202609", "next_tranche": 2})
check("演練日：LIVE 類設了也不觸發", A.should_run(p, _d7, A.load_config(p), _cal) is None)
# 演練 B：獨立批次走否決窗→停止旗標取消→逾時零送單
def drill(p, b, now):
    return A.run_month_end(p, b, now, prev_close=PC, poll_sec=0, polls=1, mode_override="SIMULATION", drill_label="DRILLB")
p = setup({"sim_veto": True}); b = Fake()
r = run(p, b); r = run(p, b, now=NOW + timedelta(minutes=31))  # 演練 A 先完成，本月 last_done
_st_before = json.loads(S(p).state.read_text(encoding="utf-8")); n_before = len(b.placed)
r = drill(p, b, NOW + timedelta(minutes=40))
pend = json.loads(S(p).pending.read_text(encoding="utf-8"))
check("演練 B：A 已完成同月仍可建立獨立批次待執行訂單", r["state"] == "WAITING_VETO" and "DRILLB" in pend["batch_id"] and pend["orders"])
p.stop_flag.write_text("x")  # App「全部取消」＝POST /auto/stop {stop:true} 寫的同一個旗標
r = drill(p, b, NOW + timedelta(minutes=71))
pend = json.loads(S(p).pending.read_text(encoding="utf-8"))
lg = [x for x in ledger(p) if "DRILLB" in (x.get("key") or "")]
check("演練 B：逾時零送單、pending 標 cancelled", len(b.placed) == n_before and pend.get("cancelled") is True)
check("演練 B：帳本逐筆記 REJECT STOP_FLAG", lg and all(x["event"] == "REJECT" for x in lg) and any("STOP_FLAG" in json.dumps(x, ensure_ascii=False) for x in lg))
_st_after = json.loads(S(p).state.read_text(encoding="utf-8"))
check("演練 B：不動 state 批次（last_done／next_tranche／batch／positions 不變）",
      all(_st_after.get(k) == _st_before.get(k) for k in ("last_done", "next_tranche", "batch", "positions", "last_label")))
r = drill(p, b, NOW + timedelta(minutes=80))
check("演練 B：已取消後重跑仍為 CANCELLED、零送單", r["state"] == "CANCELLED" and len(b.placed) == n_before)
p.stop_flag.unlink()
p = setup({"sim_veto": True}); b = Fake()
r = drill(p, b, NOW); r = drill(p, b, NOW + timedelta(minutes=31))
check("演練 B 保險：未取消到期→判失敗且絕不送單", r["state"] == "ERROR" and not b.placed and not (json.loads(S(p).state.read_text(encoding="utf-8")) or {}).get("batch"))
for cfgx in ({}, {"mode": "LIVE_WITH_VETO"}):
    p = setup(cfgx); b = Fake()
    try:
        drill(p, b, NOW); ok = False
    except A.AutoTradingError:
        ok = True
    check(f"演練 B：{cfgx or '未開 sim_veto'} 一律拒絕", ok and not b.placed)

# ---- 先.三十三-一：上線前自檢（假券商，不碰網路） ----
class _Acct: signed = False
class _Bal: errmsg = ""; acc_balance = 123456.0
class _Api:
    def __init__(self, fail=False): self.fail = fail; self.stock_account = _Acct(); self.orders = 0
    def account_balance(self):
        if self.fail: raise RuntimeError("x")
        return _Bal()
    def settlements(self, a): return []
    def list_positions(self, a): return []
    def place_order(self, *a, **k): self.orders += 1; raise AssertionError("自檢不得送單")
_api = _Api()
p = setup({"sim_veto": True})
_env = {k: "x" for k in A.PREFLIGHT_ENV_KEYS}; _env["SINOPAC_CA_PATH"] = str(p.config)
_tasks = {n: "Ready" for n in A.PREFLIGHT_TASKS}
A._write_json(p.base / f"calendar_{NOW.year}.json", {"year": NOW.year, "closed": ["2026-01-01"]})
out = A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env)
R = {i["id"]: i for i in out["items"]}
check("自檢：涵蓋十一項（env／登入／signed／三查詢／推播／排程／日曆／價格／除息／設定）",
      all(k in R for k in ("env", "live_login", "signed", "q_balance", "q_settlements", "q_positions", "push", "tasks", "calendar", "prices", "exdiv", "config")))
check("自檢：未簽署照實 FAIL 並說明缺什麼", R["signed"]["result"] == "FAIL" and "未簽署" in R["signed"]["detail"])
check("自檢：唯讀查詢成功→PASS，且不送任何委託", R["q_balance"]["result"] == "PASS" and _api.orders == 0)
check("自檢：結果不含金額／金鑰值", "123456" not in json.dumps(out, ensure_ascii=False) and '"x"' not in json.dumps(out, ensure_ascii=False))
check("自檢：寫入本機 status.preflight", (json.loads(p.status.read_text(encoding="utf-8")).get("preflight") or {}).get("ran_at") == out["ran_at"])
_env2 = dict(_env); _env2.pop("SINOPAC_CA_PASSWD")
out = A.preflight(p, NOW, broker_factory=lambda: _Api(fail=True), task_states={**_tasks, "AlphaAutoRun0905": None, "AlphaAutoWatchRun": "Disabled"}, env=_env2)
R = {i["id"]: i for i in out["items"]}
check("自檢：缺金鑰只報名稱", R["env"]["result"] == "FAIL" and "SINOPAC_CA_PASSWD" in R["env"]["detail"])
check("自檢：查詢失敗→FAIL", R["q_balance"]["result"] == "FAIL")
check("自檢：排程未註冊／停用→FAIL", R["tasks"]["result"] == "FAIL" and "未註冊" in R["tasks"]["detail"] and "Disabled" in R["tasks"]["detail"])
p = setup({"per_order_cap_twd": 1000, "total_capital_twd": 0})
out = A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env)
R = {i["id"]: i for i in out["items"]}
check("自檢：資金為 0→設定 FAIL", R["config"]["result"] == "FAIL" and "total_capital_twd" in R["config"]["detail"])
check("自檢：缺當年日曆快取→FAIL", R["calendar"]["result"] == "FAIL")
p = setup({"per_order_cap_twd": 1000})
R = {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env)["items"]}
check("自檢：單筆上限小於單批最大一筆→FAIL", R["config"]["result"] == "FAIL" and "per_order_cap_twd" in R["config"]["detail"])

# ---- 先.三十三-二：真錢帳戶卡 ----
p = setup()
check("帳戶卡：無 LIVE 成交→空狀態", A.live_account_summary(p) == {"empty": True})
_pd = {"prices": {"0050": [{"date": "2026-10-01", "close": 100.0}, {"date": "2026-10-05", "close": 110.0}],
                  "00646": [{"date": "2026-10-05", "close": 55.0}], "00697B": [{"date": "2026-10-05", "close": 36.0}]}}
L = p.scoped("LIVE")
for k, sym, q, px in (("LIVE-202610-T1-R1-0050-C", "0050", 1000, 100.0), ("LIVE-202610-T1-R1-00646-C", "00646", 2000, 50.0)):
    A._append(L.ledger, {"ts": "2026-10-01T09:40:00+08:00", "event": "FILLED", "mode": "LIVE_WITH_VETO", "key": k, "symbol": sym,
                         "qty": q, "filled_qty": q, "avg_price": px, "limit_price": px})
A._write_json(L.state, {"positions": {"0050": 1000, "00646": 2000}})
a = A.live_account_summary(p, price_doc=_pd)
h = {x["symbol"]: x for x in a["holdings"]}
check("帳戶卡：累計投入＝成交金額合計", a["invested"] == 200000)
check("帳戶卡：損益＝市值−投入（110×1000＋55×2000−200000＝20000）", a["pnl"] == 20000 and a["market_value"] == 220000)
check("帳戶卡：0050 對照＝同日同金額買 0050（2000 股×110−200000＝20000）", a["bench_0050_pnl"] == 20000)
check("帳戶卡：占比與偏離（0050 50%，偏離 +5pp）", h["0050"]["pct"] == 50.0 and h["0050"]["dev_pp"] == 5.0 and h["00697B"]["shares"] == 0)
check("帳戶卡：模擬帳本不計入真錢卡", A.live_account_summary(setup(), price_doc=_pd)["empty"] is True)

# ---- 先.三十四-二：自檢除息項（新鮮＋來源涵蓋 ETF；白名單無事件判 PASS）；引擎除息拒單不變 ----
p = setup()
_g = (NOW - timedelta(hours=10)).isoformat()
def _ex(doc):
    return {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env, exdiv_doc=doc)["items"]}["exdiv"]
r1 = _ex({"meta": {"generated_at": _g}, "events": {"00713": [{"ex_date": "2026-10-20"}], "2330": [{}]}})
check("自檢除息：新鮮＋有 00 開頭代號、白名單無事件→PASS 附註近期無除息公告", r1["result"] == "PASS" and "近期無除息公告" in r1["detail"])
r2 = _ex({"meta": {"generated_at": (NOW - timedelta(hours=80)).isoformat()}, "events": {"00713": [{}]}})
check("自檢除息：超過 72 小時→FAIL", r2["result"] == "FAIL" and "過期" in r2["detail"])
r3 = _ex({"meta": {"generated_at": _g}, "events": {"2330": [{}]}})
check("自檢除息：來源沒有任何 00 開頭代號→FAIL", r3["result"] == "FAIL" and "ETF" in r3["detail"])
_b, _pr = A.resolve_base_prices({c: (PC[c][0] * (0.95 if c == "0050" else 1), TODAY.isoformat()) for c in PC}, PC, TODAY, {})
check("引擎除息規則不變：無事件可解釋的 >1% 價差仍整批拒單", bool(_pr))

# ---- 先.三十四補充：登入錯誤逐字但遮蔽；權限生效顯示＋只推播一次 ----
class _Rej(Exception): pass
def _rej():
    raise _Rej("StatusCode: 400, Detail: Token doesn't have production permission. id=A123456789 key=" + _env["SINOPAC_API_KEY"] + "zz")
_env3 = dict(_env); _env3["SINOPAC_API_KEY"] = "SECRETKEY123"; _env = _env3
p = setup()
R = {i["id"]: i for i in A.preflight(p, NOW, broker_factory=_rej, task_states=_tasks, env=_env)["items"]}
d = R["live_login"]["detail"]
check("權限：被拒時逐字記錄錯誤訊息", "Token doesn't have production permission" in d)
check("權限：錯誤訊息遮蔽金鑰與身分證字號", "SECRETKEY123" not in d and "A123456789" not in d and "<已遮蔽>" in d)
st = json.loads(p.status.read_text(encoding="utf-8"))
check("權限：未生效寫 live_permission.effective=false", st["live_permission"]["effective"] is False)
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
_ok = _Api(); _ok.stock_account.signed = True
A.preflight(p, NOW, broker_factory=lambda: _ok, task_states=_tasks, env=_env)
st = json.loads(p.status.read_text(encoding="utf-8"))
check("權限：生效→effective=true、自檢顯示「正式環境權限：已生效」",
      st["live_permission"]["effective"] is True and "已生效" in [i for i in st["preflight"]["items"] if i["id"] == "live_login"][0]["detail"])
check("權限：首次生效推播一次", len([c for c in PUSH_CALLS if c["title"] == "正式環境權限已生效"]) == 1)
A.preflight(p, NOW + timedelta(hours=1), broker_factory=lambda: _ok, task_states=_tasks, env=_env)
check("權限：之後再跑不重複推播、since 不變", len([c for c in PUSH_CALLS if c["title"] == "正式環境權限已生效"]) == 1
      and json.loads(p.status.read_text(encoding="utf-8"))["live_permission"]["since"] == st["live_permission"]["since"])
PUSH_RESULT.update({"ok": 0, "errors": ["NO_SUBSCRIPTION:x"]})
p2 = setup(); out = A.preflight(p2, NOW, broker_factory=lambda: _ok, task_states=_tasks, env=_env)
check("權限：推播送不到只警告、自檢照常完成", out["fail"] >= 0 and json.loads(p2.status.read_text(encoding="utf-8"))["live_permission"]["effective"] is True)
PUSH_RESULT.update({"ok": 1, "errors": []})

# ---- 先.三十六：自檢推播依賴項 ----
p = setup()
R = {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env, sched_python=str(p.base / "no_python.exe"))["items"]}
check("自檢推播依賴：找不到排程直譯器→FAIL", R["push_deps"]["result"] == "FAIL")
R = {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env, sched_python=sys.executable)["items"]}
check("自檢推播依賴：可載入→PASS", R["push_deps"]["result"] == "PASS")

# ---- 先.三十七：今晚無券商演練（暫時把正式／演練目錄都指到暫存，確認只動演練目錄） ----
import shutil as _sh, sys as _sys
_off = Path(tempfile.mkdtemp()); _drl = Path(tempfile.mkdtemp()) / "auto_trading_drill"
(_off / "config.local.json").write_text(json.dumps({"mode": "SIMULATION", "tranche": 1, "tranche_total": 4,
    "total_capital_twd": 4_000_000, "per_order_cap_twd": 1_000_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4}), encoding="utf-8")
(_off / "push_subscriptions.json").write_text("[]", encoding="utf-8")
_od, _dd, _lp = A.DEFAULT_DIR, A.DRILL_DIR, A.load_prev_closes
A.DEFAULT_DIR, A.DRILL_DIR = _off, _drl
_t0 = datetime.now(TW).replace(hour=21, minute=0, second=0, microsecond=0)
A.load_prev_closes = lambda *a, **k: {c: (PC[c][0], (_t0.date() - timedelta(days=1)).isoformat()) for c in PC}
_before = {f.name: f.stat().st_mtime for f in _off.iterdir()}
_shio = "shioaji" in _sys.modules
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
try:
    A.night_drill("start", _t0)
    dp = A.Paths(_drl)
    check("夜間演練：start 建立旗標與演練設定（SIMULATION＋sim_veto）", (_drl / A.DRILL_FLAG).exists() and A.load_config(dp)["sim_veto"] is True)
    r = A.night_drill("n1-create", _t0 + timedelta(minutes=1))
    pend = json.loads(dp.scoped("SIMULATION").pending.read_text(encoding="utf-8"))
    check("夜間演練 N1：待執行訂單＋演練否決窗（NIGHT_VETO_MINUTES）", r["state"] == "WAITING_VETO" and "DRILLN1" in pend["batch_id"]
          and datetime.fromisoformat(pend["execute_after"]) - datetime.fromisoformat(pend["created_at"]) == timedelta(minutes=A.NIGHT_VETO_MINUTES))
    dp.stop_flag.write_text("x")
    r = A.night_drill("n1-execute", _t0 + timedelta(minutes=12))
    lg = [x for x in ledger(dp) if "DRILLN1" in (x.get("key") or "")]
    check("夜間演練 N1：取消後零送單、帳本記取消（REJECT STOP_FLAG）", not r.get("submitted") and lg and all(x["event"] == "REJECT" for x in lg))
    r = A.night_drill("n2-create", _t0 + timedelta(minutes=13))
    check("夜間演練 N2：清除停止旗標後建立新批次待執行訂單", r["state"] == "WAITING_VETO" and not dp.stop_flag.exists())
    r = A.night_drill("n2-execute", _t0 + timedelta(minutes=24))
    check("夜間演練 N2：到期送單（假券商，先掛著）", len(r["submitted"]) >= 1 and r["state"] == "OK")
    r = A.night_drill("n2-settle", _t0 + timedelta(minutes=25))
    check("夜間演練 N2：結算成交入帳、對帳通過、批次完成", r["state"] == "OK" and r["last_done"] and all(x["filled"] == x["qty"] for x in r["settled"]))
    check("夜間演練：每步有進度推播且有批次完成推播", sum(c["title"] == "演練（假券商）進度" for c in PUSH_CALLS) >= 5 and any(c["kind"] == "complete" for c in PUSH_CALLS))
    A.night_drill("finish", _t0 + timedelta(minutes=26))
    check("夜間演練：finish 移除旗標與待執行訂單", not (_drl / A.DRILL_FLAG).exists() and not dp.scoped("SIMULATION").pending.exists())
    check("夜間演練：正式目錄完全未被改動", {f.name: f.stat().st_mtime for f in _off.iterdir()} == _before)
    check("夜間演練：沒有載入 shioaji", ("shioaji" in _sys.modules) == _shio)
    _cfg = json.loads((_off / "config.local.json").read_text(encoding="utf-8")); _cfg["mode"] = "LIVE_WITH_VETO"
    (_off / "config.local.json").write_text(json.dumps(_cfg), encoding="utf-8")
    try:
        A.night_drill("start", _t0); _ok = False
    except A.AutoTradingError:
        _ok = True
    check("夜間演練：正式設定為 LIVE 類時拒絕執行", _ok)
finally:
    A.DEFAULT_DIR, A.DRILL_DIR, A.load_prev_closes = _od, _dd, _lp

# ---- 先.三十八-一：緊急停止撤單（只撤本系統帳本內未終結委託） ----
class FakeC(Fake):
    def __init__(self, *a, cancel_err=False, **k):
        super().__init__(*a, **k); self.cancelled = []; self.cancel_err = cancel_err
        self.orders["OTHER-1"] = {"symbol": "2330", "qty": 1000, "limit_price": 900.0, "lot": "Common"}  # 帳戶裡別人的單
    def cancel(self, oid):
        if self.cancel_err: raise RuntimeError("cancel rejected")
        self.cancelled.append(oid); return {"status": "Cancelled", "filled_qty": 0, "avg_price": None}
p = setup(); b = FakeC(fill=False)
r = run(p, b)
open_keys = [x["key"] for x in ledger(p) if x["event"] == "OPEN"]
check("撤單前置：模擬送單後掛著（OPEN）", r["state"] == "OK" and len(open_keys) >= 1)
p.stop_flag.write_text("x")
r = A.settle(p, b, NOW, force=True, prev_close=PC)
lg = A._ledger_latest(S(p))
check("撤單成功：停止旗標生效時 settle 先撤單，帳本記 CANCELLED", all(lg[k]["event"] == "CANCELLED" for k in open_keys) and len(r["cancelled_open"]["cancelled"]) == len(open_keys))
check("撤單：只撤本系統帳本內的委託（不動帳戶其他委託）", "OTHER-1" not in b.cancelled and len(b.cancelled) == len(open_keys))
check("撤單：撤單後對帳通過（CANCELLED 視為終結）", r["state"] == "OK")
p.stop_flag.unlink()
p = setup(); b = FakeC(fill=False)
run(p, b)
b.cancel_err = True
p.stop_flag.write_text("x")
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
r = run(p, b, now=NOW + timedelta(minutes=5))
st = json.loads(p.status.read_text(encoding="utf-8"))
check("撤單失敗：ERROR＋紅橫幅＋推播", r["state"] == "ERROR" and r["cancelled_open"]["failed"] and st.get("banner") == "red"
      and any(c["kind"] == "error" for c in PUSH_CALLS))
check("撤單失敗：帳本記 ERROR、不送新單", any(x["event"] == "ERROR" and "撤單失敗" in (x.get("error") or "") for x in ledger(p)) and not r["submitted"])
p.stop_flag.unlink()
p = setup(); b = FakeC(fill=True); run(p, b)
p.stop_flag.write_text("x")
r = A.settle(p, b, NOW, force=True, prev_close=PC)
check("撤單：沒有未終結委託時不呼叫撤單", b.cancelled == [] and r["cancelled_open"] == {"cancelled": [], "failed": []})
p.stop_flag.unlink()

# ---- 先.三十八-二／三：模擬掛單撤單、真錢測試指令防呆（不連券商） ----
class _CB:
    def __init__(self): self.st = {}
    def place(self, o): self.st["X1"] = "PreSubmitted"; return {"order_id": "X1"}
    def status(self, oid): return {"status": self.st[oid], "filled_qty": 0, "avg_price": None}
    def cancel(self, oid): self.st[oid] = "Cancelled"; return self.status(oid)
_ctl, _ts = A.CANCEL_TEST_LOG, A.time.sleep
A.CANCEL_TEST_LOG = Path(tempfile.mkdtemp()) / "cancel_test.jsonl"; A.time.sleep = lambda *a: None
try:
    rec = A.sim_cancel_test(NOW, broker=_CB())
    check("模擬掛單撤單：PreSubmitted→Cancelled、成交 0 判 PASS，且只寫演練目錄的紀錄檔", rec["result"] == "PASS" and A.CANCEL_TEST_LOG.exists())
    check("模擬掛單撤單：限價＝前收×0.95 依檔位取整", rec["limit_price"] == A.round_down_tick(A.load_prev_closes()["0050"][0] * 0.95))
finally:
    A.CANCEL_TEST_LOG, A.time.sleep = _ctl, _ts
import io as _io
_stdin = sys.stdin
sys.stdin = _io.StringIO(A.LIVE_TEST_CONFIRM + "\n")
try:
    A.live_cancel_test(NOW); _ok = False
except A.AutoTradingError as e:
    _ok = "互動終端機" in str(e)
finally:
    sys.stdin = _stdin
check("真錢撤單測試：非互動終端機（排程／自動化）一律拒絕，且在連券商之前就擋下", _ok)

# ---- 先.三十九：「全部取消（只取消本批）」與「緊急停止」拆開 ----
NOV = datetime(2026, 11, 30, 13, 0, tzinfo=TW)
PCN = {c: (v[0], "2026-11-27") for c, v in PC.items()}
p = setup({"sim_veto": True}); b = Fake()
r = run(p, b)
c = A.cancel_pending(p, NOW + timedelta(minutes=1))
check("取消本批：cancel_pending 標 cancelled、不寫 STOP.flag", c["cancelled"] and not p.stop_flag.exists()
      and json.loads(S(p).pending.read_text(encoding="utf-8"))["cancelled_by"] == "USER_CANCEL_PENDING")
r = run(p, b, now=NOW + timedelta(minutes=31))
lg = A._ledger_latest(S(p))
check("取消本批：到期記 CANCELLED、0 張送出", r["state"] == "CANCELLED" and not b.placed
      and all(lg[o]["event"] == "CANCELLED" for o in lg if "-T1-R1-" in o and not o.endswith("-ALL")))
check("取消本批：沒有待執行訂單時回 cancelled=false", A.cancel_pending(p)["cancelled"] is False)
r = run(p, b, now=NOV, pc=PCN)
check("取消本批不影響下一批：下個月照常進否決窗", r["state"] == "WAITING_VETO" and S(p).pending.exists())
r = run(p, b, now=NOV + timedelta(minutes=31), pc=PCN)
check("取消本批不影響下一批：下個月到期照常送單", len(b.placed) >= 1)
p = setup({"sim_veto": True}); b = Fake()
run(p, b); p.stop_flag.write_text("x")
run(p, b, now=NOW + timedelta(minutes=31))
r1 = run(p, b, now=NOV, pc=PCN); r2 = run(p, b, now=NOV + timedelta(minutes=31), pc=PCN)
check("緊急停止擋所有批：本月與下個月都 0 張", not b.placed)
p.stop_flag.unlink()
p = setup({"sim_veto": True}); b = Fake()
run(p, b); A.cancel_pending(p); p.stop_flag.write_text("x")
run(p, b, now=NOW + timedelta(minutes=31))
r = run(p, b, now=NOV, pc=PCN); run(p, b, now=NOV + timedelta(minutes=31), pc=PCN)
check("兩者同時：以緊急停止為準（本批與之後批次都不送）", not b.placed)
p.stop_flag.unlink()
# 公開心跳 installed_at
p = setup()
(p.base / "installed_at.txt").write_text("2026-10-06T17:13:09+08:00", encoding="utf-8")
A.write_public_heartbeat(p, "run", "OK", NOW)
hb = json.loads(p.public_hb.read_text(encoding="utf-8"))
check("公開心跳：含 installed_at（只有時間）", hb.get("installed_at") == "2026-10-06T17:13:09+08:00")
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("pubhb", str(Path(__file__).resolve().parent / "scheduler" / "publish_heartbeat.py"))
_pub = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_pub)
check("公開心跳：隱私檢查接受 installed_at", _pub.privacy_check(hb) is None)
check("公開心跳：installed_at 格式不符被擋", _pub.privacy_check({**hb, "installed_at": "2026/10/06 金額100"}) is not None)
(p.base / "installed_at.txt").write_text("not-a-time", encoding="utf-8")
A.write_public_heartbeat(p, "run", "OK", NOW)
check("公開心跳：安裝時間檔格式錯就不寫該欄位", "installed_at" not in json.loads(p.public_hb.read_text(encoding="utf-8")))

# ---- 先.四十四：CA 憑證檢查、演練結果項、可切換真錢判定 ----
class _ApiCA(_Api):
    def __init__(self, exp="2027-06-30", ok=True):
        super().__init__(); self.stock_account.signed = True; self._exp = exp; self._ok = ok; self.ca_calls = 0
    def account_balance(self):
        return type("B", (), {"errmsg": "", "acc_balance": 10_000_000.0})()
    def activate_ca(self, ca_path, ca_passwd, person_id=None):
        self.ca_calls += 1; return self._ok
    def get_ca_expiretime(self, person_id): return self._exp
_env_ok = dict(_env); _env_ok["SINOPAC_API_KEY"] = "K1234567"
PUSH_RESULT.update({"ok": 1, "errors": []})
p = setup({"sim_veto": True}); b = Fake()
run(p, b); run(p, b, now=NOW + timedelta(minutes=31))                         # 演練 A：成交、批次完成
A._write_json(p.base / "calendar_2026.json", {"year": 2026, "closed": ["2026-01-01"]})
p.config.write_text(json.dumps({**json.loads(p.config.read_text(encoding="utf-8"))}), encoding="utf-8")
r = A.run_month_end(p, b, NOW + timedelta(minutes=40), prev_close=PC, poll_sec=0, polls=1, mode_override="SIMULATION", drill_label="DRILLB")
A.cancel_pending(p, NOW + timedelta(minutes=41))
A.run_month_end(p, b, NOW + timedelta(minutes=71), prev_close=PC, poll_sec=0, polls=1, mode_override="SIMULATION", drill_label="DRILLB")
api_ok = _ApiCA()
(p.base / "push_subscriptions.json").write_text(json.dumps({"subscriptions": [{"endpoint": "https://push.example/x", "keys": {"p256dh": "a", "auth": "b"}}]}), encoding="utf-8")
NOWP = datetime(2026, 10, 7, 19, 0, tzinfo=TW)
out = A.preflight(p, NOWP, broker_factory=lambda: api_ok, task_states=_tasks, env=_env_ok, exdiv_doc={"meta": {"generated_at": NOWP.isoformat()}, "events": {"00713": [{}]}}, sched_python=sys.executable)
R = {i["id"]: i for i in out["items"]}
check("CA：啟用成功且到期日 >30 天→PASS，顯示到期日", R["ca"]["result"] == "PASS" and "2027-06-30" in R["ca"]["detail"] and api_ok.ca_calls == 1)
check("CA：detail 不含路徑／密碼／身分證", not any(v in R["ca"]["detail"] for v in (_env_ok["SINOPAC_CA_PATH"], _env_ok["SINOPAC_CA_PASSWD"])))
check("演練項：A 完成、B 取消 0 張、無 sim_drill_date→皆 PASS", all(R[k]["result"] == "PASS" for k in ("drill_a", "drill_b", "drill_cfg")))
check("自檢：CA 檢查不送任何委託", api_ok.orders == 0)
check("可切換真錢：全部 PASS→go_live_ready=True", out["fail"] == 0 and out["go_live_ready"] is True and not out["go_live_blockers"])
out = A.preflight(p, NOWP, broker_factory=lambda: _ApiCA(exp="2026-11-05"), task_states=_tasks, env=_env_ok, exdiv_doc={"meta": {"generated_at": NOWP.isoformat()}, "events": {"00713": [{}]}}, sched_python=sys.executable)
R = {i["id"]: i for i in out["items"]}
check("CA：距到期 ≤30 天→FAIL", R["ca"]["result"] == "FAIL")
check("可切換真錢：任一 FAIL→不顯示且列出原因", out["go_live_ready"] is False and any("CA" in x for x in out["go_live_blockers"]))
cfg = json.loads(p.config.read_text(encoding="utf-8")); cfg["sim_drill_date"] = "2026-10-07"; p.config.write_text(json.dumps(cfg), encoding="utf-8")
out = A.preflight(p, NOWP, broker_factory=lambda: _ApiCA(), task_states=_tasks, env=_env_ok, exdiv_doc={"meta": {"generated_at": NOWP.isoformat()}, "events": {"00713": [{}]}}, sched_python=sys.executable)
check("演練設定未清理→FAIL、不可切換", {i["id"]: i for i in out["items"]}["drill_cfg"]["result"] == "FAIL" and out["go_live_ready"] is False)

# ---- 先.五十：TG 群組實戰回饋修補 ----
import subprocess as _sp, re as _re2
from types import SimpleNamespace as _NS
# 1 close()：登出失敗只記警告；_close_broker 對沒有 close 的券商略過
class _ApiLogout:
    def __init__(self, boom=False): self.boom = boom; self.n = 0
    def logout(self):
        self.n += 1
        if self.boom: raise RuntimeError("x")
_b = object.__new__(A.ShioajiBroker); _b.api = _ApiLogout()
A._close_broker(_b)
_b2 = object.__new__(A.ShioajiBroker); _b2.api = _ApiLogout(boom=True)
try:
    A._close_broker(_b2); A._close_broker(Fake()); _cl_ok = True
except Exception:
    _cl_ok = False
check("close()：呼叫 api.logout()；登出失敗只警告；沒有 close 的券商略過", _b.api.n == 1 and _b2.api.n == 1 and _cl_ok)
_src = Path(A.__file__).read_text(encoding="utf-8")
check("close()：run／settle／模擬撤單測試／真錢撤單測試／零股驗證進入點都以 finally 或結尾關閉連線",
      _src.count("_close_broker(broker)") >= 2 and "_close_broker(b)" in _src and "_close_broker(vb)" in _src)
# 2 連線預算
p = setup()
_pf = lambda procs: {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _api, task_states=_tasks, env=_env, proc_lister=lambda: procs)["items"]}["conn_budget"]
check("連線預算：3 個常駐＋本次＝4 條→PASS", _pf(["shioaji_quotes.py", "alpha_x", "y"])["result"] == "PASS")
check("連線預算：4 個常駐＋本次＝5 條→FAIL", _pf(["shioaji_quotes.py", "shioaji_order_server.py", "auto_rebalance_bb90.py", "shioaji_quotes.py"])["result"] == "FAIL")
# 3 禁止以 limit_up／limit_down 計價；00697B 極端漲跌停仍以 reference 出價並對齊級距
_root = Path(A.__file__).resolve().parent.parent
_hits = []
for _f in list((_root / "research").glob("*.py")) + list((_root / "scripts").glob("*.py")):
    if _f.name.startswith("selftest_"):
        continue
    _t = _f.read_text(encoding="utf-8", errors="ignore")
    if ("place_order" in _t or "plan_orders" in _t or "limit_price" in _t) and _re2.search(r"limit_up|limit_down", _t):
        _hits.append(_f.name)
check(f"全 repo 下單路徑不使用 limit_up／limit_down 計價（命中：{_hits or '無'}）", not _hits)
class _Contract:
    def __init__(self, ref, ud): self.reference = ref; self.update_date = ud; self.limit_up = 9999.95; self.limit_down = 0.01
_bb = object.__new__(A.ShioajiBroker)
_bb.api = _NS(Contracts=_NS(Stocks={"0050": _Contract(117.0, TODAY.isoformat()), "00646": _Contract(78.0, TODAY.isoformat()),
                                    "00697B": _Contract(33.95, TODAY.isoformat())}))
_refs = _bb.reference_prices(["0050", "00646", "00697B"], TODAY)
_pc = {"0050": (117.0, TD), "00646": (78.0, TD), "00697B": (33.95, TD)}
_base, _probs = A.resolve_base_prices(_refs, _pc, TODAY, {})
_ords = A.plan_orders({c: _base[c][0] for c in _base}, {}, 1_000_000, True, dev_pct=0.5)
_o97 = [o for o in _ords if o["symbol"] == "00697B"]
check("00697B 參考價情境（limit_up=9999.95、limit_down=0.01）：基準取 reference 33.95、無問題", not _probs and _base["00697B"][0] == 33.95)
check("00697B 限價在 reference ±1% 內且對齊 0.01 級距", _o97 and all(abs(o["limit_price"] / 33.95 - 1) <= 0.01 and round(o["limit_price"] * 100) == o["limit_price"] * 100 for o in _o97))
check("0050 限價在 reference ±1% 內且對齊 0.05 級距", all(abs(o["limit_price"] / 117.0 - 1) <= 0.01 and abs(o["limit_price"] / 0.05 - round(o["limit_price"] / 0.05)) < 1e-9
      for o in _ords if o["symbol"] == "0050"))
# 4 SIM 零股標記
p = setup()
A._log(S(p), NOW, "SIMULATION", "FILLED", {"key": "SIMULATION-202610-T1-R1-0050-O", "symbol": "0050", "qty": 5, "lot": "IntradayOdd"}, filled_qty=5)
A._log(S(p), NOW, "SIMULATION", "FILLED", {"key": "SIMULATION-202610-T1-R1-0050-C", "symbol": "0050", "qty": 1000, "lot": "Common"}, filled_qty=1000)
_lg = {x["key"]: x for x in ledger(p)}
check("SIM 零股紀錄標 SIM_ODD_UNSUPPORTED、整股不標", _lg["SIMULATION-202610-T1-R1-0050-O"].get("validation") == "SIM_ODD_UNSUPPORTED"
      and "validation" not in _lg["SIMULATION-202610-T1-R1-0050-C"])
# 5 零股首次真實驗證
p = setup({"mode": "LIVE_WITH_VETO"}); L = p.scoped("LIVE_WITH_VETO")
_day = NOW.date().isoformat()
A._write_json(L.state, {"positions": {"0050": 0}, "pre_batch_positions": {"0050": 0, "00646": 0, "00697B": 0}, "pre_batch_date": _day})
for k, q, f in (("LIVE-202610-T1-R1-0050-C", 1000, 1000), ("LIVE-202610-T1-R1-0050-O", 449, 449), ("LIVE-202610-T1-R1-00646-O", 30, 20)):
    A._log(L, NOW, "LIVE_WITH_VETO", "FILLED" if q == f else "PARTIAL", {"key": k, "symbol": k.split("-")[4], "qty": q, "limit_price": 100.0,
           "lot": "IntradayOdd" if k.endswith("-O") else "Common"}, filled_qty=f, avg_price=100.0)
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
_vb = Fake(pos={"0050": 1449, "00646": 20})
_rep = A.odd_lot_verification(L, _vb, NOW)
check("零股驗證：逐筆列 2 筆零股委託（委託量、成交量、均價）", _rep and len(_rep["odd_orders"]) == 2 and {r["filled"] for r in _rep["odd_orders"]} == {449, 20})
check("零股驗證：unit=Share 持股前後差與成交量逐檔比對相符", _rep["per_symbol"]["0050"]["match"] and _rep["per_symbol"]["00646"]["match"] and _rep["all_match"])
check("零股驗證：寫本機報告檔並推播", (L.ledger.parent / f"odd_lot_verification_{_day.replace('-', '')}.json").exists() and any(c["title"] == "零股首次真實驗證" for c in PUSH_CALLS))
_rep2 = A.odd_lot_verification(L, Fake(pos={"0050": 1000, "00646": 20}), NOW)
check("零股驗證：持股差不符時標記不符", _rep2["all_match"] is False and _rep2["per_symbol"]["0050"]["match"] is False)
check("零股驗證：模擬族不產生報告", A.odd_lot_verification(S(setup()), Fake(), NOW) is None)
# 6 可用額度交叉核對：只警告、不改擋單
class _FakeTA(Fake):
    def __init__(self, ta, **k): super().__init__(**k); self.ta = ta
    def trading_available(self): return self.ta
p = setup({"mode": "LIVE_WITH_VETO"})
_now_mkt = datetime(2026, 10, 30, 9, 40, tzinfo=TW)
A._cash_crosscheck(p.scoped("LIVE"), _FakeTA(800_000), 1_000_000, _now_mkt)
_cc = json.loads(p.status.read_text(encoding="utf-8")).get("cash_crosscheck") or {}
check("可用額度交叉核對：差 >5% 記警告（status.cash_crosscheck.warn）", _cc.get("warn") is True and _cc.get("gap_pct") == 20.0)
p2 = setup({"mode": "LIVE_WITH_VETO"})
A._cash_crosscheck(p2.scoped("LIVE"), _FakeTA(800_000), 1_000_000, datetime(2026, 10, 30, 16, 0, tzinfo=TW))
check("可用額度交叉核對：08:30–15:00 以外不查", "cash_crosscheck" not in (json.loads(p2.status.read_text(encoding="utf-8")) if p2.status.exists() else {}))
class _FakeTABoom(Fake):
    def trading_available(self): raise RuntimeError("x")
try:
    A._cash_crosscheck(p.scoped("LIVE"), _FakeTABoom(), 1_000_000, _now_mkt); _ccb = True
except Exception:
    _ccb = False
check("可用額度交叉核對：查詢失敗只警告不拋錯", _ccb)
p = setup({"mode": "LIVE"}); b = _FakeTA(1, cash=10**9)
r = run(p, b)
check("可用額度交叉核對：不改變擋單規則（差距極大仍照常送單）", r["state"] == "OK" and len(b.placed) >= 1)

# ---- 先.五十五-B6：現金不足推播節流＋心跳遮蔽金額 ----
p = setup({"mode": "LIVE", "total_capital_twd": 4_000_000})
PUSH_CALLS.clear(); PUSH_RESULT.update({"ok": 1, "errors": []})
b0 = Fake(cash=0)
r1 = run(p, b0, now=NOW)
r2 = run(p, b0, now=NOW + timedelta(minutes=35))
_cash_push = [c for c in PUSH_CALLS if c["kind"] == "error" and "INSUFFICIENT_CASH" in c["body"]]
check("推播節流：同一期同原因同一交易日兩次拒單只推播一次", r1["state"] == r2["state"] == "ERROR" and len(_cash_push) == 1)
_st = json.loads(p.status.read_text(encoding="utf-8"))
check("推播節流：紅條與 last_error 照常更新", _st.get("banner") == "red" and str(_st.get("last_error", "")).startswith("INSUFFICIENT_CASH"))
_orig_now = A.datetime
class _DT(A.datetime):
    @classmethod
    def now(cls, tz=None): return _orig_now(2026, 10, 31, 9, 5, tzinfo=tz)
A.datetime = _DT
try:
    run(p, b0, now=NOW + timedelta(days=1))
finally:
    A.datetime = _orig_now
check("推播節流：隔一個交易日同原因會再推播一次", len([c for c in PUSH_CALLS if c["kind"] == "error" and "INSUFFICIENT_CASH" in c["body"]]) == 2)
_hb = (p.base / "heartbeat.jsonl").read_text(encoding="utf-8")
check("心跳檔（repo 追蹤檔）不含金額：數字一律遮蔽", "INSUFFICIENT_CASH" in _hb and not any(ch.isdigit() for l in _hb.splitlines() for ch in json.loads(l)["item"]))
check("_redact_numbers：股數、金額、小數一律遮蔽", A._redact_numbers("對帳不符：預期{'0050': 3000}≠券商 1,449.5") == "對帳不符：預期{'#': #}≠券商 #")

# ---- 先.五十四-6 更正：現金不足文字、自檢第 19 項 ----
p = setup({"mode": "LIVE", "total_capital_twd": 4_000_000})
r = run(p, Fake(cash=0))
_le = json.loads(p.status.read_text(encoding="utf-8")).get("last_error", "")
check("現金不足文字：永豐交割戶可用餘額 X 元，不足本批所需 Y 元（尚未入金或餘額不足）…不需任何操作",
      _le.startswith("INSUFFICIENT_CASH:永豐交割戶可用餘額 0 元，不足本批所需") and "尚未入金或餘額不足" in _le and "09:05 自動重跑本批，不需任何操作" in _le and "中國信託" not in _le)
class _ApiCash(_ApiCA):
    def __init__(self, bal, pay=0.0):
        super().__init__(); self._bal = bal; self._pay = pay
    def account_balance(self):
        return type("B", (), {"errmsg": "", "acc_balance": self._bal})()
    def settlements(self, a):
        return [type("S", (), {"amount": -self._pay})()] if self._pay else []
_cfg19 = {"mode": "LIVE_WITH_VETO", "total_capital_twd": 4_000_000, "tranche_total": 4}
def _cr(bal, pay=0.0):
    p = setup(_cfg19)
    return {i["id"]: i for i in A.preflight(p, NOW, broker_factory=lambda: _ApiCash(bal, pay), task_states=_tasks, env=_env)["items"]}["cash_ready"]
check("自檢第 19 項：可用（餘額−未交割）≥ 下一批×1.003 → PASS", _cr(1_010_000)["result"] == "PASS")
c = _cr(1_010_000, pay=20_000)
check("自檢第 19 項：扣掉未交割應付後不足 → FAIL「尚未入金或餘額不足」", c["result"] == "FAIL" and c["detail"].startswith("尚未入金或餘額不足"))
c = _cr(0)
check("自檢第 19 項：餘額 0 → FAIL 並附註可能不在 account_balance 支援範圍、不顯示金額",
      c["result"] == "FAIL" and "#83761" in c["detail"] and "1,010,000" not in c["detail"] and "元" not in c["detail"])

if SKIPS:
    print("SKIP：", SKIPS)
print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
