#!/usr/bin/env python3
"""先.一三五-1dy：FinMind 快取暖機（research/finmind_warmup.py，本機排程 AlphaFinMindWarmup）合成自測。

零外部請求、不讀真實快取、不算報酬：
- finmind_client 的快取目錄（DATA_DIR）換暫存目錄，_fetch／calls_last_hour 換假的，requests.get 換成一呼叫就記錯；
- paper_supply_v2 換成假模組（只給 warmup 用到的常數與函式，換股視窗日期可控）；
- 鎖檔／狀態檔／狀態輸出檔／P3 暫停旗標／心跳檔全部指到暫存目錄。
檢查：鎖檔佔用時不跑、過期鎖會清掉、跑完鎖會釋放；gen_tasks 只排缺檔或逾期者；額度／封鎖錯誤立即停（不重試）；
退避時間內不重抓同一鍵；write_status 原子寫入；狀態檔損壞不拋未處理例外；時間／每小時上限到就停。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

# 自身逾時保護：上一輪（20261030-233102）在這一項被外層 60 分鐘砍掉，這支自測最多跑 120 秒
_watchdog = threading.Timer(120, lambda: (print("[FAIL] 自測超過 120 秒，強制結束", flush=True), os._exit(2)))
_watchdog.daemon = True
_watchdog.start()

import finmind_client as fc  # noqa: E402
import finmind_warmup as w  # noqa: E402

fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"：{detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


NET_CALLS: list = []


def _no_net(*a, **k):
    NET_CALLS.append((a, k))
    raise AssertionError("自測不得送外部請求")


fc.requests.get = _no_net

TMP = Path(tempfile.mkdtemp(prefix="selftest_fm_warmup_"))
CACHE = TMP / "cache"
CACHE.mkdir()
fc.DATA_DIR = CACHE
w.DATA = TMP
w.LOCK_PATH = TMP / "finmind_warmup.lock"
w.STATE_PATH = TMP / "finmind_warmup_state.json"
w.STATUS_PATH = TMP / "finmind_warmup_status.json"
w.P3_PAUSE_PATH = TMP / "finmind_warmup_p3_pause.json"
w.V1_PREP_STATUS = TMP / "var1018_v1_prep_status.json"
w.HEARTBEAT = TMP / "heartbeat.jsonl"

CODES = ["1101", "2330"]


class FakeSrc:
    def __init__(self, read_only=True):
        pass

    def universe(self):
        return pd.DataFrame({"code": CODES})

    def calendar(self, now):
        return pd.DataFrame(index=pd.DatetimeIndex(["2026-10-29", "2026-10-30"]))

    def events_ready(self, d):
        return True

    def px_pending(self, c, d):
        return []

    def _cache(self, ds, c):
        return None, None


FAR = {"deadline": pd.Timestamp("2099-01-01")}  # 換股視窗遠在未來 → P0／P1 不啟動


def fake_pv2():
    m = types.SimpleNamespace()
    m.STMT_DS = (("fs", "TaiwanStockFinancialStatements"), ("bs", "TaiwanStockBalanceSheet"),
                 ("cf", "TaiwanStockCashFlowsStatement"))
    m.PRICE_DS = ("TaiwanStockPrice", "TaiwanStockDividend", "TaiwanStockCapitalReductionReferencePrice")
    m.EVENT_DS_ALL = ("TaiwanStockSplitPrice", "TaiwanStockParValueChange")
    m.STMT_START = "2024-01-01"
    m.PRICE_START = "2025-01-01"
    m.FIRST_PERIOD = pd.Period("2026Q3", freq="Q")
    m.WINDOW_BEFORE_DAYS = 30
    # 期限必須逐季遞增（真函式如此）；全部回同一天會讓 target_period() 的 while 永不結束
    m.deadline = lambda p: FAR["deadline"] + pd.Timedelta(days=91 * (p - m.FIRST_PERIOD).n)
    m.periods_until = lambda until: []
    m.LOG_PATH = TMP / "fake_log.jsonl"
    m.load_log = lambda p: ([], None)
    m._settled = lambda src, c, p, D: (True, [])
    m.LiveSource = FakeSrc
    return m


w.pv2 = fake_pv2()
NOW = pd.Timestamp("2026-10-31 02:00", tz=w.TZ).to_pydatetime()
w._now = lambda: NOW

FETCHED: list = []
FETCH_MODE = {"mode": "ok", "fail_codes": set()}
CALLS_HOUR = {"n": 0}


def fake_fetch(ds, code="", start="2000-01-01", end=None, force_refresh=False, **k):
    FETCHED.append((ds, code))
    if FETCH_MODE["mode"] == "blocked":
        raise RuntimeError("finmind 目前處於封鎖冷卻中（還剩約100分鐘，原因：HTTP 402），依「資料源禮儀」規則拒絕發送請求")
    if FETCH_MODE["mode"] == "quota":
        raise RuntimeError("FinMind回應HTTP 402（額度/封鎖類錯誤，已標記finmind封鎖2小時）：dataset=x")
    if FETCH_MODE["mode"] == "fail" or code in FETCH_MODE["fail_codes"]:
        raise RuntimeError("FinMind rejected the request (HTTP 400): bad")
    p = fc._cache_path(ds, code, start, end)
    pd.DataFrame({"date": ["2026-06-30"], "v": [1]}).to_parquet(p)
    return pd.DataFrame()


fc._fetch = fake_fetch
fc.calls_last_hour = lambda *a, **k: CALLS_HOUR["n"]


def reset_cache():
    for p in CACHE.glob("*"):
        p.unlink()
    for p in (w.STATE_PATH, w.STATUS_PATH, w.LOCK_PATH, w.P3_PAUSE_PATH):
        if p.exists():
            p.unlink()
    FETCHED.clear()
    FETCH_MODE.update(mode="ok", fail_codes=set())
    CALLS_HOUR["n"] = 0


def touch(ds, code, start, period_date="2026-06-30", age_h=0.0):
    p = fc._cache_path(ds, code, start, None)
    pd.DataFrame({"date": [period_date], "v": [1]}).to_parquet(p)
    t = time.time() - age_h * 3600
    os.utime(p, (t, t))
    return p


def fill_all(codes, age_h=0.0, period_date="2026-06-30"):
    for c in codes:
        for _, ds in w.pv2.STMT_DS:
            touch(ds, c, w.pv2.STMT_START, period_date, age_h)
        for ds in w.pv2.PRICE_DS:
            touch(ds, c, w.pv2.PRICE_START, period_date, age_h)


def run(*args):
    try:
        return w.main(list(args)), None
    except Exception as e:  # noqa: BLE001
        return None, e


# ── 1. 鎖檔 ──
reset_cache()
w.LOCK_PATH.write_text("999 test", encoding="utf-8")
rc, err = run()
check("鎖檔被佔用：不拋例外、回 0", err is None and rc == 0, f"rc={rc} err={err!r}")
check("鎖檔被佔用：沒有送任何抓取", FETCHED == [], str(FETCHED))
check("鎖檔被佔用：別人的鎖不被刪", w.LOCK_PATH.exists())
old = time.time() - (w.STALE_LOCK_S + 60)
os.utime(w.LOCK_PATH, (old, old))
rc, err = run()
check("過期鎖（>30 分鐘）會被清掉並照跑", err is None and len(FETCHED) > 0, f"fetched={len(FETCHED)} err={err!r}")
check("跑完鎖檔已釋放", not w.LOCK_PATH.exists())

# 主流程中途拋例外也要釋放鎖
reset_cache()
_orig_save = w._save_json


def _boom(p, obj):
    raise OSError("模擬寫檔失敗")


w._save_json = _boom
rc, err = run()
w._save_json = _orig_save
check("主流程中途拋例外：鎖檔仍釋放", not w.LOCK_PATH.exists() and err is not None, f"err={err!r}")

# ── 2. gen_tasks 只排缺檔或逾期者 ──
reset_cache()
fill_all(CODES)
fc_path_missing = fc._cache_path("TaiwanStockBalanceSheet", "2330", w.pv2.STMT_START, None)
fc_path_missing.unlink()
fc._cache_path("TaiwanStockDividend", "1101", w.pv2.PRICE_START, None).unlink()
sc = w.scan(CODES)
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
keys = [(t[0], t[1], t[2]) for t in tasks]
check("缺檔才排：只排 2 個缺檔（財報先、價格後）",
      keys == [("P2-stmt", "TaiwanStockBalanceSheet", "2330"), ("P2-px", "TaiwanStockDividend", "1101")], str(keys))

reset_cache()
fill_all(CODES, age_h=1.0)  # 都新、都含目標季 2026Q2
sc = w.scan(CODES)
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
check("全部齊全且新鮮：零任務", tasks == [], str(tasks))

reset_cache()
fill_all(CODES, age_h=1.0)
touch("TaiwanStockFinancialStatements", "1101", w.pv2.STMT_START, "2026-03-31", age_h=8 * 24)  # 逾期且缺 Q2
touch("TaiwanStockFinancialStatements", "2330", w.pv2.STMT_START, "2026-06-30", age_h=8 * 24)  # 逾期但已含 Q2
sc = w.scan(CODES)
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
keys = [(t[0], t[1], t[2]) for t in tasks]
check("P3 保鮮：只排逾期且缺目標季者", keys == [("P3-stale", "TaiwanStockFinancialStatements", "1101")], str(keys))

w.P3_PAUSE_PATH.write_text(json.dumps({"until": "2099-01-01T00:00:00+08:00"}), encoding="utf-8")
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
check("P3 暫停旗標有效時不排 P3", tasks == [], str(tasks))
w.P3_PAUSE_PATH.write_text("{壞掉的 json", encoding="utf-8")
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
check("P3 暫停旗標損壞：不拋例外、照常排 P3", len(tasks) == 1, str(tasks))
w.P3_PAUSE_PATH.unlink()

# P0 視窗內：0050 新鮮者不重排
reset_cache()
fill_all(CODES, age_h=1.0)
FAR["deadline"] = pd.Timestamp("2026-11-14")
fill_all(["0050"], age_h=1.0)
touch("TaiwanStockSplitPrice", "", w.pv2.PRICE_START, age_h=1.0)
touch("TaiwanStockParValueChange", "", w.pv2.PRICE_START, age_h=30.0)  # 逾 20 小時
sc = w.scan(CODES)
tasks = list(w.gen_tasks(w.pv2.LiveSource(), CODES, NOW, sc, {}))
keys = [(t[0], t[1], t[2]) for t in tasks]
check("P0 視窗內：只重抓逾期的事件表", keys == [("P0-events", "TaiwanStockParValueChange", "")], str(keys))
FAR["deadline"] = pd.Timestamp("2099-01-01")

# ── 3. 封鎖／額度錯誤立即停、不重試 ──
for mode in ("blocked", "quota"):
    reset_cache()
    FETCH_MODE["mode"] = mode
    rc, err = run()
    st = json.loads(w.STATUS_PATH.read_text(encoding="utf-8")) if w.STATUS_PATH.exists() else {}
    check(f"{mode}：只送 1 次就停", len(FETCHED) == 1, f"fetched={len(FETCHED)}")
    check(f"{mode}：停止原因 blocked、狀態檔標 blocked", st.get("last_run_stop") == "blocked" and st.get("blocked") is True,
          str({k: st.get(k) for k in ("last_run_stop", "blocked")}))
    check(f"{mode}：鎖已釋放、無例外", not w.LOCK_PATH.exists() and err is None, f"err={err!r}")
    mem = json.loads(w.STATE_PATH.read_text(encoding="utf-8")).get("fails", {})
    check(f"{mode}：封鎖不算該鍵失敗（不誤觸退避）", mem == {}, str(mem))

# 一般失敗連 5 次就停
reset_cache()
FETCH_MODE["mode"] = "fail"
rc, err = run()
st = json.loads(w.STATUS_PATH.read_text(encoding="utf-8"))
check("一般錯誤連續 5 次即停", len(FETCHED) == 5 and st.get("last_run_stop") == "consecutive_fails",
      f"fetched={len(FETCHED)} stop={st.get('last_run_stop')}")
mem = json.loads(w.STATE_PATH.read_text(encoding="utf-8"))["fails"]
check("一般錯誤：失敗次數記進狀態檔", len(mem) == 5 and all(v["n"] == 1 for v in mem.values()), str(mem)[:200])

# ── 4. 退避 ──
reset_cache()
fill_all(CODES)
fc._cache_path("TaiwanStockBalanceSheet", "2330", w.pv2.STMT_START, None).unlink()
fc._cache_path("TaiwanStockPrice", "1101", w.pv2.PRICE_START, None).unlink()
w._save_json(w.STATE_PATH, {"fails": {
    "TaiwanStockBalanceSheet|2330": {"n": 3, "ts": time.time() - 3600},          # 3 次、1 小時前 → 退避 6 小時內
    "TaiwanStockPrice|1101": {"n": 5, "ts": time.time() - 23 * 3600}}})          # 5 次、23 小時前 → 退避 24 小時內
rc, err = run()
check("退避時間內不重抓同一鍵", FETCHED == [], str(FETCHED))
w._save_json(w.STATE_PATH, {"fails": {
    "TaiwanStockBalanceSheet|2330": {"n": 3, "ts": time.time() - 7 * 3600},
    "TaiwanStockPrice|1101": {"n": 2, "ts": time.time()}}})                       # 未滿 3 次不退避
FETCHED.clear()
rc, err = run()
check("退避期滿／未達門檻者照抓", sorted(FETCHED) == [("TaiwanStockBalanceSheet", "2330"), ("TaiwanStockPrice", "1101")],
      str(FETCHED))
mem = json.loads(w.STATE_PATH.read_text(encoding="utf-8"))["fails"]
check("抓成功後清除該鍵失敗紀錄", mem == {}, str(mem))

# ── 5. 時間預算／每小時上限 ──
reset_cache()
rc, err = run("--max-minutes", "0")
st = json.loads(w.STATUS_PATH.read_text(encoding="utf-8"))
check("時間預算為 0：零請求、停止原因 time_budget", FETCHED == [] and st.get("last_run_stop") == "time_budget",
      f"{FETCHED} {st.get('last_run_stop')}")
reset_cache()
CALLS_HOUR["n"] = w.HOURLY_CAP
rc, err = run()
st = json.loads(w.STATUS_PATH.read_text(encoding="utf-8"))
check("滾動 1 小時達上限：零請求、停止原因 hourly_cap", FETCHED == [] and st.get("last_run_stop") == "hourly_cap",
      f"{FETCHED} {st.get('last_run_stop')}")
reset_cache()
rc, err = run("--dry")
check("--dry 不送請求、不寫狀態檔", FETCHED == [] and not w.STATE_PATH.exists(), f"{FETCHED}")

# ── 6. write_status 原子寫入 ──
reset_cache()
sc = w.scan(CODES)
w.write_status(sc, NOW)
before = w.STATUS_PATH.read_text(encoding="utf-8")
try:
    w.write_status(sc, NOW, {"bad": object()})  # 序列化失敗
    raised = False
except TypeError:
    raised = True
check("write_status 序列化失敗：原檔不被截斷", raised and w.STATUS_PATH.read_text(encoding="utf-8") == before)
check("write_status 不殘留暫存檔", not list(TMP.glob("*.tmp")), str(list(TMP.glob("*.tmp"))))
st = json.loads(before)
check("write_status 欄位正確（2 檔 × 6 缺檔＝待補 12）", st.get("universe_n") == 2 and st.get("remaining_backlog_calls") == 12,
      str({k: st.get(k) for k in ("universe_n", "remaining_backlog_calls")}))

# ── 7. 狀態檔損壞 ──
for label, content in (("不是 JSON", "{壞掉"), ("頂層是陣列", "[1, 2]"), ("fails 不是物件", '{"fails": [1]}'),
                       ("單鍵欄位型別錯", '{"fails": {"TaiwanStockPrice|1101": {"n": "x", "ts": "y"}}}'),
                       ("空檔", "")):
    reset_cache()
    w.STATE_PATH.write_text(content, encoding="utf-8")
    rc, err = run()
    check(f"狀態檔損壞（{label}）：不拋未處理例外、照跑", err is None and rc == 0 and len(FETCHED) > 0,
          f"rc={rc} err={err!r} fetched={len(FETCHED)}")
    check(f"狀態檔損壞（{label}）：鎖已釋放", not w.LOCK_PATH.exists())

check("全程零外部請求", NET_CALLS == [], str(NET_CALLS[:1]))

print(f"\n合計 {total} 項，FAIL {len(fails)} 項")
for f in fails:
    print(f"  FAIL：{f}")
sys.exit(1 if fails else 0)
