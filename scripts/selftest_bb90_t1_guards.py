# -*- coding: utf-8 -*-
"""先.七十八-5 單元測試：鎖住真錢首批的四個行為＋明日計畫預覽與第 20 項預檢。全程假券商、暫存目錄，不連網、不送單。

①債券 ETF（00697B）限價＝前收×(1+dev_pct) 往下取跳動單位，不是漲停價（limit_up）
②零股：split_qty 把 1500 股拆成整股 1000＋盤中零股 500；gate_order 擋零股 ≥1000、放行 999
③單筆金額超過上限 → gate_order 拒單（CAP）
④可用餘額 < 整批×1.003 → _cash_ok 整批不送（記一筆 REJECT …-ALL）；剛好等於 → 放行
⑤plan_preview 與 run_month_end 同一套（期別、預算、dev_pct、零股、單筆上限、×1.003），可用只回布林
⑥preflight 第 20 項 monthly_ok：每月投入 > 總資金 → WARN（不算 FAIL、不改設定值）
"""
import inspect
import json
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import auto_rebalance_bb90 as A  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


# ① 債券 ETF 不用漲停價
px = {"0050": 114.95, "00646": 78.35, "00697B": 33.94}
orders = A.plan_orders(px, {}, 600000, True, dev_pct=0.5)
bond = [o for o in orders if o["symbol"] == "00697B"]
want = A.round_down_tick(33.94 * 1.005)
check(f"①00697B 限價＝前收×1.005 取跳動單位（{bond[0]['limit_price'] if bond else None} == {want}），不是漲停價",
      bond and all(o["limit_price"] == want for o in bond) and all(o["limit_price"] < 33.94 * 1.09 for o in bond))
check("①plan_orders／gate_order 原始碼沒有使用 limit_up",
      "limit_up" not in inspect.getsource(A.plan_orders) and "limit_up" not in inspect.getsource(A.gate_order))

# ② 零股
check("②split_qty(1500)＝整股 1000＋盤中零股 500", A.split_qty(1500, True) == [("Common", 1000), ("IntradayOdd", 500)])
check("②split_qty(800)＝只有零股 800", A.split_qty(800, True) == [("IntradayOdd", 800)])
cfg = {"per_order_cap_twd": 1_000_000, "max_price_dev_pct": 1.0, "max_data_age_days": 4}
ctx = {"cfg": cfg, "prev_close": {"0050": (114.95, "2026-10-08")}, "today": date(2026, 10, 12), "stopped": False, "reconciled": True}
base = {"symbol": "0050", "action": "Buy", "cond": "Cash", "limit_price": 115.5}
check("②零股 qty=1000 → 拒（零股數量必須小於1000）", any("LOT" in w for w in A.gate_order({**base, "lot": "IntradayOdd", "qty": 1000}, ctx)))
check("②零股 qty=999 → 放行", A.gate_order({**base, "lot": "IntradayOdd", "qty": 999}, ctx) == [])
check("②整股 qty=1500 → 拒（整股必須是 1000 的倍數）", any("LOT" in w for w in A.gate_order({**base, "lot": "Common", "qty": 1500}, ctx)))

# ③ 單筆上限
cap_ctx = {**ctx, "cfg": {**cfg, "per_order_cap_twd": 100_000}}
check("③單筆 1000 股×115.5＝115,500 > 上限 100,000 → CAP 拒單", any(w.startswith("CAP") for w in A.gate_order({**base, "lot": "Common", "qty": 1000}, cap_ctx)))
check("③單筆 800 股×115.5＝92,400 ≤ 上限 → 放行", A.gate_order({**base, "lot": "IntradayOdd", "qty": 800}, cap_ctx) == [])


# ④ 可用餘額 < 整批×1.003 整批不送
class FakeBroker:
    def __init__(self, cash, payable=0.0):
        self._c, self._p = cash, payable

    def cash(self):
        return self._c

    def unsettled_payable(self):
        return self._p


tmp = Path(tempfile.mkdtemp())
try:
    paths = A.Paths(tmp, heartbeat=tmp / "hb.jsonl").scoped("LIVE_WITH_VETO")
    (tmp / "LIVE").mkdir(parents=True, exist_ok=True)
    A._cash_crosscheck = lambda *a, **k: None  # 交叉核對另有測試，這裡只驗整批門檻
    A.report_error = lambda *a, **k: None       # 不推播
    ords = [{"symbol": "0050", "qty": 1000, "limit_price": 100.0}, {"symbol": "00646", "qty": 500, "limit_price": 80.0}]
    need = (100_000 + 40_000) * A.CASH_BUFFER
    now = datetime(2026, 10, 12, 9, 5, tzinfo=A.TW)
    res = {"rejected": [], "state": "OK"}
    ok_short = A._cash_ok(paths, FakeBroker(need - 1), {"mode": "LIVE_WITH_VETO"}, "LIVE_WITH_VETO", ords, now, "LIVE-202610-T1-R1", res)
    led = [json.loads(x) for x in paths.ledger.read_text(encoding="utf-8").splitlines()] if paths.ledger.exists() else []
    check("④可用＝整批×1.003−1 → 整批不送，記 REJECT LIVE-202610-T1-R1-ALL（INSUFFICIENT_CASH）",
          ok_short is False and res["state"] == "ERROR" and led and led[-1]["key"] == "LIVE-202610-T1-R1-ALL"
          and led[-1]["event"] == "REJECT" and led[-1]["reasons"][0].startswith("INSUFFICIENT_CASH"))
    res2 = {"rejected": [], "state": "OK"}
    check("④可用＝整批×1.003 剛好 → 放行", A._cash_ok(paths, FakeBroker(need), {"mode": "LIVE_WITH_VETO"}, "LIVE_WITH_VETO", ords, now, "x", res2) is True)
    res3 = {"rejected": [], "state": "OK"}
    check("④未交割應付要扣掉：餘額夠但扣掉應付後不足 → 不送",
          A._cash_ok(paths, FakeBroker(need, payable=10), {"mode": "LIVE_WITH_VETO"}, "LIVE_WITH_VETO", ords, now, "y", res3) is False)

    # ⑤ plan_preview
    sp = A.Paths(tmp)
    (tmp / "LIVE" / "state.json").write_text(json.dumps({"positions": {}, "applied": [], "next_tranche": 1}), encoding="utf-8")
    pcfg = {"mode": "LIVE_WITH_VETO", "tranche_total": 4, "total_capital_twd": 2_400_000, "per_order_cap_twd": 700_000,
            "max_price_dev_pct": 1.0, "monthly_contribution_twd": 50_000}
    pc = {c: (v, "2026-10-08") for c, v in px.items()}
    pv = A.plan_preview(sp, pcfg, pc, 650_000.0, None, now)
    same = A.plan_orders(px, {}, 600_000, True, dev_pct=0.5)
    check(f"⑤預覽期別 T1、預算＝總資金÷4、委託與 plan_orders(dev 0.5) 一致（{len(pv.get('orders', []))} 筆）",
          pv["label"] == "T1" and [(o["symbol"], o["qty"], o["limit_price"]) for o in pv["orders"]] == [(o["symbol"], o["qty"], o["limit_price"]) for o in same])
    check("⑤合計×1.003＝need_with_buffer；可用只回布林", abs(pv["need_with_buffer"] - pv["total"] * A.CASH_BUFFER) < 0.02
          and pv["available_ok"] in (True, False) and "available" not in json.dumps({k: v for k, v in pv.items() if k != "available_ok"}))
    check("⑤單筆上限檢查：700,000 上限下全部 cap_ok", pv["all_cap_ok"] is True)
    pv_small = A.plan_preview(sp, {**pcfg, "per_order_cap_twd": 100_000}, pc, None, None, now)
    check("⑤上限 100,000 時大筆 cap_ok=False、可用未知回 None", pv_small["all_cap_ok"] is False and pv_small["available_ok"] is None)
    (tmp / "LIVE" / "state.json").write_text(json.dumps({"positions": {}, "applied": ["T1", "T2", "T3", "T4"], "next_tranche": 5}), encoding="utf-8")
    pv_m = A.plan_preview(sp, pcfg, pc, None, None, now)
    check("⑤next_tranche 超過期數 → 月底 M、預算＝每月投入", pv_m["label"] == "M" and abs(sum(o["amount"] for o in pv_m["orders"]) - 50_000) < 50_000 * 0.01 + 200)

    # ⑥ preflight 第 20 項（假券商、假排程、假環境；只看 monthly_ok）
    class FakeApi:
        stock_account = type("Acct", (), {"signed": True})()

        def account_balance(self):
            return type("B", (), {"acc_balance": 1_000_000.0, "errmsg": ""})()

        def settlements(self, a):
            return []

        def list_positions(self, a):
            return []

    def run_pf(cfg_over):
        (tmp / "config.local.json").write_text(json.dumps({**pcfg, **cfg_over}), encoding="utf-8")
        (tmp / "LIVE" / "state.json").write_text(json.dumps({"positions": {}, "applied": [], "next_tranche": 1}), encoding="utf-8")
        return A.preflight(sp, now, broker_factory=FakeApi, task_states={}, env={}, exdiv_doc={}, sched_python=str(tmp / "nope.exe"), proc_lister=lambda: [])

    o1 = run_pf({"monthly_contribution_twd": 3_000_000})
    m1 = next(i for i in o1["items"] if i["id"] == "monthly_ok")
    check("⑥每月投入 > 總資金 → 第 20 項 WARN、文字照裁示", m1["result"] == "WARN" and m1["detail"] == "每月投入大於總資金，第 5 個月起會被擋單，請確認")
    cfg_after = json.loads((tmp / "config.local.json").read_text(encoding="utf-8"))
    check("⑥WARN 不改設定值、不算 FAIL", cfg_after["monthly_contribution_twd"] == 3_000_000 and o1["fail"] == sum(i["result"] == "FAIL" for i in o1["items"]))
    o2 = run_pf({"monthly_contribution_twd": 50_000})
    check("⑥每月投入 ≤ 總資金 → PASS", next(i for i in o2["items"] if i["id"] == "monthly_ok")["result"] == "PASS")
    st = json.loads((tmp / "LIVE" / "status.json").read_text(encoding="utf-8"))
    check("⑥預檢結果寫進 LIVE status，含 t1_plan_preview（App「明天會買」讀這個）", "t1_plan_preview" in st and st["t1_plan_preview"].get("label") == "T1")
    check("⑥預檢明細不含任何金額數字（cash_ready／monthly_ok）",
          all(not any(ch.isdigit() for ch in i["detail"]) for i in o2["items"] if i["id"] in ("cash_ready", "monthly_ok")))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
