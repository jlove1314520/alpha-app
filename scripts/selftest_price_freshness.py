# -*- coding: utf-8 -*-
"""修.八自我測試：(1)0050最新日期＝最近一個交易日（獨立向TWSE MI_INDEX查，不看update_price_history.py
自己的meta）；(2)paper_7030_tracker的價格新鮮度閘門在過期資料下必須中止、不得計算。
用法：python scripts/selftest_price_freshness.py（僅唯讀，網路只打官方MI_INDEX、每次間隔3秒）。
全部通過 exit 0，否則 exit 1。"""
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
TZ = timezone(timedelta(hours=8))
MI = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


def latest_trading_day_via_mi_index(max_back=10):
    today = datetime.now(TZ).date()
    for i in range(max_back):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        r = requests.get(MI, params={"date": d.strftime("%Y%m%d"), "type": "ALLBUT0999", "response": "json"}, timeout=30)
        body = r.json()
        time.sleep(3)
        if body.get("stat") == "OK" and any("每日收盤行情" in (t.get("title") or "") and t.get("data")
                                             for t in body.get("tables") or []):
            return d.isoformat()
    return None


ph = json.load(open(ROOT / "data" / "price_history.json", encoding="utf-8"))
last_0050 = ph["prices"]["0050"][-1]["date"]
truth = latest_trading_day_via_mi_index()
check("0050最新日期＝MI_INDEX最近一個有資料的交易日", truth is not None and last_0050 == truth,
      f"0050={last_0050}, MI_INDEX最近交易日={truth}")

import paper_7030_tracker as T  # noqa: E402

tmp = Path(tempfile.mkdtemp())
fake = {"prices": {"0050": [{"date": "2026-09-24", "close": 112.4}], "6488": [{"date": "2026-09-29", "close": 500.0}]}}
(tmp / "ph.json").write_text(json.dumps(fake), encoding="utf-8")
T.PRICE_HISTORY_PATH = tmp / "ph.json"
T.HEARTBEAT_PATH = tmp / "hb.jsonl"
T.APP_SUMMARY_PATH = tmp / "summary.json"
T.LOG_PATH = tmp / "log.jsonl"
res = T.run()
check("0050落後別檔（09-24 vs 09-29）→中止且不寫淨值紀錄", res.get("aborted") is True and not T.LOG_PATH.exists(), str(res))
check("中止時心跳寫入status=ERROR", "ERROR" in T.HEARTBEAT_PATH.read_text(encoding="utf-8"))
check("中止時App摘要有last_error", "ABORTED_STALE_PRICE" in T.APP_SUMMARY_PATH.read_text(encoding="utf-8"))

fake2 = {"prices": {"0050": [{"date": "2026-09-01", "close": 100.0}], "6488": [{"date": "2026-09-01", "close": 5.0}]}}
(tmp / "ph2.json").write_text(json.dumps(fake2), encoding="utf-8")
T.PRICE_HISTORY_PATH = tmp / "ph2.json"
ok, why = T._check_price_freshness([{"date": "2026-09-01"}], today_iso="2026-09-30")
check("全市場一起停更（落後>5平日）→判過期", ok is False, why)
T.PRICE_HISTORY_PATH = tmp / "ph.json"
ok2, why2 = T._check_price_freshness([{"date": "2026-09-29"}], today_iso="2026-09-30")
check("0050與全市場同日、落後今天1平日→視為新鮮", ok2 is True, why2)

sys.exit(1 if fails else 0)
