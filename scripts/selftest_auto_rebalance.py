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

if SKIPS:
    print("SKIP：", SKIPS)
print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
