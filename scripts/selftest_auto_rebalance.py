"""先.二十九-三.4：自動再平衡自測（FakeBroker，不碰任何券商）。"""
import json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
import auto_rebalance_bb90 as A

TW = A.TW
NOW = datetime(2026, 10, 30, 13, 0, tzinfo=TW)
PC = {"0050": (100.0, "2026-10-29"), "00646": (50.0, "2026-10-29"), "00697B": (36.0, "2026-10-29")}
fails = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

class Fake:
    def __init__(self, pos=None, fill=True, fail_place=False, cash=10**9, cash_err=False, partial=None):
        self.pos = dict(pos or {}); self.fill = fill; self.fail_place = fail_place; self.placed = []; self.orders = {}
        self.cash_val = cash; self.cash_err = cash_err; self.partial = partial; self.late = {}  # oid -> 遲到成交量
    def cash(self):
        if self.cash_err: raise RuntimeError("balance timeout")
        return self.cash_val
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

print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
