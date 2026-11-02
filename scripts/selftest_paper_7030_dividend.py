# -*- coding: utf-8 -*-
"""先.一三五-1if 自測：紙.一（paper_7030）股票腿改用含息報酬（adj_close 比值）。

全部用合成資料＋暫存目錄，不碰真實的 paper_7030_log.jsonl／paper_7030.json／PROGRESS_HEARTBEAT.jsonl。
檢查：①期間無除息 → 與舊算法（原始收盤比值）相同 ②期間含一次除息 → 等於「原始收盤比值×除息日前收盤÷(前收−股利)」
（股利再投入），且與「原始收盤比值＋股利÷期初價」差距 <0.1% ③上一筆帳本日期不在視窗 → run() 不推進、
寫 last_error=MISSING_ADJ_CLOSE＋心跳 ERROR、帳本位元組不變 ④adj_close 缺值同③ ⑤真實帳本 10/01→10/30
（期間無除息）用新算法與既有列 stock_value_pre 一致（唯讀，不寫任何檔）。
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_7030_tracker as T  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


PREV = {"date": "2026-10-30", "event": "monthly_rebalance", "price_0050": 100.0,
        "stock_value_post": 700000.0, "bond_value_post": 300000.0, "nav": 1000000.0,
        "stock_weight_post": 0.7, "bond_weight_post": 0.3,
        "rebalance_trade": {"direction": "none", "notional": 0.0, "cost": 0.0}}
RF = None
T._bond_monthly_growth = lambda rf, d: 1.001  # 債券腿與本修正無關，固定值隔離


def row(d, close, adj):
    return {"date": d, "close": close, "adj_close": adj}


# ① 無除息：adj == close
p1 = [row("2026-10-30", 100.0, 100.0), row("2026-11-15", 103.0, 103.0), row("2026-11-30", 105.0, 105.0)]
e1 = T._process_month_end(PREV, p1[-1], RF, p1)
old_stock = PREV["stock_value_post"] * (105.0 / PREV["price_0050"])
old_total = old_stock + PREV["bond_value_post"] * 1.001
check("①無除息：股票成長＝原始收盤比值", abs(e1["stock_growth"] - 1.05) < 1e-12)
check("①無除息：淨值與舊算法相同（舊算法淨值扣同一筆再平衡成本）",
      abs(e1["nav"] + e1["rebalance_trade"]["cost"] - old_total) < 0.05)
check("①price_0050 仍記原始收盤", e1["price_0050"] == 105.0)
check("①growth_source 有寫", "adj_close" in e1.get("growth_source", ""))

# ② 含一次除息：前收 101、股利 2 → 係數 f=(101-2)/101，除息日前 adj 全乘 f
f = (101.0 - 2.0) / 101.0
p2 = [row("2026-10-30", 100.0, 100.0 * f), row("2026-11-17", 101.0, 101.0 * f),
      row("2026-11-18", 99.5, 99.5), row("2026-11-30", 100.0, 100.0)]
e2 = T._process_month_end(PREV, p2[-1], RF, p2)
expect = (100.0 / 100.0) * (101.0 / 99.0)
simple = 100.0 / 100.0 + 2.0 / 100.0
check("②含除息：等於原始收盤比值×股利再投入係數", abs(e2["stock_growth"] - expect) < 1e-8)
check("②含除息：與『原始收盤比值＋股利』差距 <0.1%", abs(e2["stock_growth"] - simple) < 0.001)
check("②含除息：比舊算法（原始收盤）多出股利", e2["stock_growth"] > 100.0 / 100.0 + 0.019)


# ③④ run() 層級：找不到上月底／adj 缺值 → 不推進
def run_case(name, prices):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        T.LOG_PATH = td / "log.jsonl"
        T.APP_SUMMARY_PATH = td / "paper_7030.json"
        T.HEARTBEAT_PATH = td / "hb.jsonl"
        T.LOG_PATH.write_text(json.dumps(PREV, ensure_ascii=False) + "\n", encoding="utf-8")
        before = T.LOG_PATH.read_bytes()
        T._load_0050_price_series = lambda: prices
        T._check_price_freshness = lambda pr, today_iso=None: (True, "")
        T.load_risk_free_rate_series = lambda: None
        out = T.run()
        check(f"{name}：run() 回 aborted、processed=0", out.get("aborted") is True and out.get("processed") == 0)
        check(f"{name}：帳本位元組不變（不推進）", T.LOG_PATH.read_bytes() == before)
        s = json.loads(T.APP_SUMMARY_PATH.read_text(encoding="utf-8"))
        check(f"{name}：last_error=MISSING_ADJ_CLOSE", s.get("last_error", {}).get("status") == "MISSING_ADJ_CLOSE")
        hb = [json.loads(x) for x in T.HEARTBEAT_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
        check(f"{name}：心跳 ERROR", bool(hb) and hb[-1].get("status") == "ERROR")


run_case("③上月底不在視窗", [row("2026-11-03", 100.0, 100.0), row("2026-11-30", 101.0, 101.0),
                            row("2026-12-01", 102.0, 102.0)])
run_case("④adj_close 缺值", [row("2026-10-30", 100.0, None), row("2026-11-30", 101.0, 101.0),
                            row("2026-12-01", 102.0, 102.0)])

# ⑤ 真實帳本唯讀對照
try:
    import importlib
    T2 = importlib.reload(T)
    log = T2._load_log()
    prices = T2._load_0050_price_series()
    if len(log) >= 2 and log[1]["event"] == "monthly_rebalance":
        g = T2._stock_growth(prices, log[0]["date"], next(r for r in prices if r["date"] == log[1]["date"]))
        raw = log[1]["price_0050"] / log[0]["price_0050"]
        check(f"⑤真實 {log[0]['date']}→{log[1]['date']}：含息比值≈原始比值（期間無除息）",
              abs(g - raw) < 1e-6)
    else:
        print("SKIP ⑤真實帳本不足兩列")
except Exception as e:  # noqa: BLE001
    check(f"⑤真實帳本對照（例外 {type(e).__name__}: {e}）", False)

fails = [n for n, ok in results if not ok]
print(f"\n合計 {len(results)} 項，FAIL {len(fails)}")
sys.exit(1 if fails else 0)
