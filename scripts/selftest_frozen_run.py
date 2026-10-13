# -*- coding: utf-8 -*-
"""先.八十一-3 自測：策略資金凍結（STOP＋strategy_frozen）時 --run 安靜化。全程暫存目錄、假券商（一連線就算失敗）、假推播。
①凍結中 --run：回 0、只寫 FROZEN 心跳；不連券商、不寫帳本（無 REJECT）、不推播
②看門狗：今天 run 的心跳是 FROZEN → 回 FROZEN（不是 MISSED、不報錯）
③單純 STOP（沒有 strategy_frozen）→ 不走凍結路徑，照原流程判斷觸發
④SIMULATION 演練（--mode-override）→ 不受凍結影響
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime
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


class NoBroker:
    def __init__(self, *a, **k):
        raise AssertionError("凍結路徑不得建立券商連線")


tmp = Path(tempfile.mkdtemp())
saved = {k: getattr(A, k) for k in ("DEFAULT_DIR", "HEARTBEAT", "ShioajiBroker", "push_send", "should_run", "load_calendar", "run_month_end")}
pushes, calls = [], []
try:
    A.DEFAULT_DIR, A.HEARTBEAT = tmp, tmp / "hb.jsonl"
    A.ShioajiBroker = NoBroker
    A.push_send = lambda paths, t, b, k: (pushes.append(t), {"ok": 1})[1]
    A.load_calendar = lambda y, base=None, fetch=None: {"year": y, "closed": []}
    A.should_run = lambda *a, **k: (calls.append("should_run"), None)[1]
    A.run_month_end = lambda *a, **k: (calls.append("run_month_end"), {"state": "OK"})[1]
    (tmp / "LIVE").mkdir()
    (tmp / "config.local.json").write_text(json.dumps({"mode": "LIVE_WITH_VETO"}), encoding="utf-8")
    (tmp / "STOP.flag").write_text("x", encoding="utf-8")
    (tmp / "LIVE" / "status.json").write_text(json.dumps({"strategy_frozen": {"since": "2026-10-12T14:00:01+08:00", "reason": "等紙上策略打贏 0050"}}), encoding="utf-8")

    def run(argv):
        old = sys.argv
        sys.argv = ["auto_rebalance_bb90.py", *argv]
        try:
            return A.main()
        finally:
            sys.argv = old

    rc = run(["--run"])
    hb = [json.loads(x) for x in (tmp / "schedule_heartbeat.jsonl").read_text(encoding="utf-8").splitlines()]
    check("①凍結中 --run 回 0、寫 FROZEN 心跳", rc == 0 and hb and hb[-1]["task"] == "run" and hb[-1]["outcome"] == "FROZEN")
    check("①不判斷觸發、不建單、不推播、不寫帳本", not calls and not pushes and not (tmp / "LIVE" / "orders.jsonl").exists())
    now = datetime.now(A.TW).replace(hour=10, minute=0)
    hb_line = {"ts": now.replace(hour=9, minute=40).isoformat(timespec="seconds"), "task": "run", "outcome": "FROZEN"}
    (tmp / "schedule_heartbeat.jsonl").write_text(json.dumps(hb_line) + "\n", encoding="utf-8")
    w = A.watchdog(A.Paths(tmp, heartbeat=tmp / "hb.jsonl"), now, "run", cal={"year": now.year, "closed": []})
    check(f"②看門狗看到 FROZEN 心跳 → 回 FROZEN（實得 {w}），不報漏跑", w in ("FROZEN", "NOT_TRADING_DAY") and not pushes)
    # ③ 單純 STOP：拿掉 strategy_frozen
    (tmp / "LIVE" / "status.json").write_text(json.dumps({}), encoding="utf-8")
    calls.clear()
    rc = run(["--run"])
    hb = [json.loads(x) for x in (tmp / "schedule_heartbeat.jsonl").read_text(encoding="utf-8").splitlines()]
    check("③單純 STOP → 走原流程（判斷觸發，記 NOT_TRIGGERED）", calls == ["should_run"] and hb[-1]["outcome"] == "NOT_TRIGGERED")
    # ④ SIMULATION 演練不受凍結影響
    (tmp / "LIVE" / "status.json").write_text(json.dumps({"strategy_frozen": {"since": "2026-10-12T14:00:01+08:00"}}), encoding="utf-8")
    calls.clear()
    A.ShioajiBroker = lambda *a, **k: type("B", (), {"close": lambda self: None})()
    run(["--run", "--mode-override", "SIMULATION"])
    check("④SIMULATION 演練照常執行（進到 run_month_end）", calls == ["run_month_end"])
finally:
    for k, v in saved.items():
        setattr(A, k, v)
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
