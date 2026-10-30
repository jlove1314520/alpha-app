# -*- coding: utf-8 -*-
"""自測：紙上追蹤看守員（research/paper_tracking_watchdog.py，market.yml 每班）（先.一三五-1ei）。

看守員內建 `--selftest` 有 9 個情境，但沒有任何 scripts/selftest_*.py 呼叫它，前向自測回歸總跑（1ao，selftest_paper_*）抓不到。
本檔：①跑內建 9 情境；②補「真實帳本形狀」情境——紙.一b 實際 inception 是 2026-10-08（不是內建情境假設的 11-02），
月底事件名是 month_end（紙.一是 monthly_rebalance），確認 11/02 前後不誤報、也不漏報；③__main__ 壞檔降級 exit 0。
全部用暫存目錄＋合成價格（close=1），不讀真實價格、不印淨值或報酬、不寫正式檔，零外部請求。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_tracking_watchdog as W  # noqa: E402

fails = []


def chk(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=W.TZ)


def mk(td: Path, d0050, d697, log1, log1b):
    (td / "data").mkdir(parents=True)
    (td / "research" / "data").mkdir(parents=True)
    rows = lambda ds: [{"date": d, "close": 1, "adj_close": 1} for d in ds]  # noqa: E731
    (td / "data" / "price_history.json").write_text(json.dumps(
        {"prices": {"0050": rows(d0050), W.SAFE_LEG: rows(d697)}}), encoding="utf-8")
    for name, rs in (("paper_7030_log.jsonl", log1), ("paper_1b_log.jsonl", log1b)):
        (td / "research" / "data" / name).write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")


def ids(r):
    return {i["id"] for i in r["items"]}


# ① 內建 9 情境
r = subprocess.run([sys.executable, str(ROOT / "research" / "paper_tracking_watchdog.py"), "--selftest"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
chk("1 內建 --selftest 9 情境全過（exit 0 且印 ALL PASS）", r.returncode == 0 and "ALL PASS" in r.stdout)

inc1 = {"date": "2026-10-01", "event": "inception"}
me1 = {"date": "2026-10-30", "event": "monthly_rebalance"}
inc1b = {"date": "2026-10-08", "event": "inception"}
me1b = {"date": "2026-10-30", "event": "month_end"}
oct_ = ["2026-10-01", "2026-10-08", "2026-10-29", "2026-10-30"]
nov2 = oct_ + ["2026-11-02"]

# ② 真實帳本形狀
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, oct_, oct_, [inc1], [inc1b, me1b])
    chk("2 現況（10/31，紙.一b 10/08 起跑、10/30 month_end 已記；紙.一 等 11 月資料）-> OK",
        W.evaluate(a, t("2026-10-31T12:00:00"))["status"] == "OK")
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, nov2, nov2, [inc1], [inc1b, me1b])
    chk("3 11/02 資料到、紙.一尚未記 10/30 -> 只報 p1_pending（紙.一b 不誤報）",
        ids(W.evaluate(a, t("2026-11-02T13:00:00"))) == {"p1_pending"})
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, nov2, nov2, [inc1, me1], [inc1b, me1b])
    chk("4 11/02 兩支都記好、過死線 -> OK", W.evaluate(a, t("2026-11-02T21:00:00"))["status"] == "OK")
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, oct_, oct_, [inc1], [inc1b])
    chk("5 紙.一b 10/30 month_end 漏記（月底最後平日當日確認）-> p1b_pending_me",
        ids(W.evaluate(a, t("2026-10-30T21:00:00"))) == {"p1b_pending_me"})
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, oct_, oct_, [inc1], [inc1b, me1b])
    chk("6 紙.一 死線過、資料仍沒來 -> 只報 p1_first_month_end（紙.一b 已起跑不報 inception）",
        ids(W.evaluate(a, t("2026-11-02T20:30:00"))) == {"p1_first_month_end"})

# ③ __main__ 壞檔降級：用暫存 ROOT 不可行（ROOT 寫死），改驗 run() 丟例外時 __main__ 的 try 包得住——以 evaluate 壞 JSON 丟例外為前提
with tempfile.TemporaryDirectory() as a:
    a = Path(a)
    mk(a, oct_, oct_, [inc1], [inc1b, me1b])
    (a / "research" / "data" / "paper_1b_log.jsonl").write_text("{bad\n", encoding="utf-8")
    try:
        W.evaluate(a, t("2026-10-31T12:00:00"))
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    chk("7 帳本壞行丟例外（由 __main__ try 降級為 ::warning::，不寫正式檔）", raised)

print("ALL PASS" if not fails else "FAILED: " + str(fails))
sys.exit(1 if fails else 0)
