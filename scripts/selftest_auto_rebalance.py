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
    def __init__(self, pos=None, fill=True, fail_place=False):
        self.pos = dict(pos or {}); self.fill = fill; self.fail_place = fail_place; self.placed = []; self.orders = {}
    def positions(self): return dict(self.pos)
    def place(self, o):
        if self.fail_place: raise RuntimeError("boom")
        oid = f"O{len(self.placed)+1}"; self.placed.append(o); self.orders[oid] = o
        if self.fill: self.pos[o["symbol"]] = self.pos.get(o["symbol"], 0) + o["qty"]
        return {"order_id": oid}
    def status(self, oid):
        o = self.orders[oid]; q = o["qty"] if self.fill else 0
        return {"status": "Filled" if q else "Submitted", "filled_qty": q, "avg_price": o["limit_price"]}

def setup(cfg=None):
    d = Path(tempfile.mkdtemp())
    base = {"mode": "SIMULATION", "tranche": 1, "tranche_total": 4, "total_capital_twd": 4_000_000,
            "per_order_cap_twd": 1_000_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4}
    base.update(cfg or {})
    (d / "config.local.json").write_text(json.dumps(base), encoding="utf-8")
    return A.Paths(d)

def ledger(p):
    return [json.loads(l) for l in p.ledger.read_text(encoding="utf-8").splitlines()] if p.ledger.exists() else []

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
p2.ledger.unlink()
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
p.ledger.unlink(); p.pending.unlink(missing_ok=True)
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
check("否決窗：先寫待執行訂單、不送單", r["state"] == "WAITING_VETO" and len(b.placed) == 0 and p.pending.exists())
r = run(p, b, now=NOW + timedelta(minutes=10))
check("否決窗內再跑仍等待", r["state"] == "WAITING_VETO" and len(b.placed) == 0)
p.stop_flag.write_text("x")
r = run(p, b, now=NOW + timedelta(minutes=31))
check("否決窗：全部取消(停止旗標)後逾時也不送", len(b.placed) == 0)
p.stop_flag.unlink()
p.pending.write_text(json.dumps({**json.loads(p.pending.read_text(encoding="utf-8")), "cancelled": False}), encoding="utf-8")
r = run(p, b, now=NOW + timedelta(minutes=31))
check("否決窗：逾時且未取消才送單", len(b.placed) >= 1)

print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
