#!/usr/bin/env python3
"""先.一三五-1dz：本機 IBKR 報價（research/ibkr_quotes.py）連不上 Gateway／只回部分代號時的行為自測。

零外部連線、不需 Gateway、不碰帳號：IB 連線物件換假的（connect 拋例外／逾時／帳戶空／非 paper／部分合約解析失敗），
三份輸出檔與 Yahoo 備援都換掉（Yahoo 換成回 None，不送請求）。
檢查：連不上 → 三份檔明確標 connected:false＋原因、exit 非 0；內容相同不重寫（fetched_at 停住，App 才判得出逾期）；
帳戶空／非 paper 不抓報價；部分代號解析失敗 → 代號不從檔案消失（全 null 佔位＋原因，不沿用舊價）；寫檔原子、不留暫存檔。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

_watchdog = threading.Timer(90, lambda: (print("[FAIL] 自測超過 90 秒，強制結束", flush=True), os._exit(2)))
_watchdog.daemon = True
_watchdog.start()

import ibkr_quotes as iq  # noqa: E402

fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"：{detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


TMP = Path(tempfile.mkdtemp(prefix="selftest_ibkr_offline_"))
iq.OUT_PATH = TMP / "quotes_ibkr.json"
iq.POSITIONS_OUT_PATH = TMP / "positions_ibkr.json"
iq.BALANCE_OUT_PATH = TMP / "balance_ibkr.json"
iq.TICK_WAIT_SEC = 0
YAHOO = []
iq._fetch_yahoo_index_quote = lambda sym: (YAHOO.append(sym), None)[1]
iq.requests.get = lambda *a, **k: (_ for _ in ()).throw(AssertionError("自測不得送外部請求"))
iq._fetch_positions = lambda ib: ([], None)
iq._fetch_balance = lambda ib, acct: ({"NetLiquidation": 1.0}, None)

BAD_SYMBOLS: set = set()


class FakeTicker:
    def __init__(self, last):
        self.last = last
        self.close = 100.0
        self.bid = -1.0
        self.ask = -1.0
        self.marketDataType = 3


class FakeIB:
    mode = "ok"
    accounts = ["DU1234567"]

    def __init__(self):
        self.disconnected = False
        FakeIB.last = self

    def connect(self, *a, **k):
        if FakeIB.mode == "refused":
            raise ConnectionRefusedError("[WinError 1225] 遠端電腦拒絕網路連線")
        if FakeIB.mode == "timeout":
            raise TimeoutError()

    def managedAccounts(self):
        return list(FakeIB.accounts)

    def reqMarketDataType(self, t):
        pass

    def qualifyContracts(self, c):
        if getattr(c, "symbol", None) in BAD_SYMBOLS:
            return []
        return [c]

    def reqMktData(self, c, *a):
        return FakeTicker(101.0)

    def cancelMktData(self, c):
        pass

    def sleep(self, s):
        pass

    def disconnect(self):
        self.disconnected = True


iq.IB = FakeIB


def run_main():
    try:
        iq.main()
        return 0
    except SystemExit as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return f"例外 {type(e).__name__}: {e}"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def reset():
    for p in TMP.glob("*"):
        p.unlink()
    FakeIB.mode = "ok"
    FakeIB.accounts = ["DU1234567"]
    BAD_SYMBOLS.clear()
    YAHOO.clear()


# ── 1. 連不上（拒絕／逾時）──
for mode in ("refused", "timeout"):
    reset()
    iq._write_json_atomic(iq.OUT_PATH, {"connected": True, "fetched_at": "2026-10-30T10:00:00+08:00",
                                        "quotes": {"AAPL": {"last": 1.0}}})
    FakeIB.mode = mode
    rc = run_main()
    check(f"{mode}：exit 非 0", rc not in (0, None) and not isinstance(rc, str), f"rc={rc}")
    for p in (iq.OUT_PATH, iq.POSITIONS_OUT_PATH, iq.BALANCE_OUT_PATH):
        d = load(p)
        check(f"{mode}：{p.name} 明確標 connected:false 並寫原因", d.get("connected") is False and "連線失敗" in (d.get("error") or ""),
              str(d)[:160])
    check(f"{mode}：不留舊報價冒充現價（文件明載設計）", load(iq.OUT_PATH).get("quotes") == {})
    check(f"{mode}：不殘留暫存檔", not list(TMP.glob("*.tmp")))

# 連續兩輪連不上：內容相同不重寫，fetched_at 停在第一次 → App 判得出逾期
reset()
FakeIB.mode = "refused"
run_main()
t1 = load(iq.OUT_PATH)["fetched_at"]
m1 = iq.OUT_PATH.stat().st_mtime_ns
run_main()
check("連續連不上：內容相同不重寫、fetched_at 停住", load(iq.OUT_PATH)["fetched_at"] == t1 and iq.OUT_PATH.stat().st_mtime_ns == m1)

# 既有檔損壞時連不上：照寫失敗狀態、不拋例外
reset()
iq.OUT_PATH.write_text("{半截", encoding="utf-8")
FakeIB.mode = "timeout"
rc = run_main()
check("既有檔損壞＋連不上：照寫失敗狀態、不拋未處理例外", not isinstance(rc, str) and load(iq.OUT_PATH).get("connected") is False, f"rc={rc}")

# ── 2. 帳戶空／非 paper ──
for label, accts in (("帳戶空", []), ("非 paper 帳戶", ["U7654321"])):
    reset()
    FakeIB.accounts = accts
    rc = run_main()
    d = load(iq.OUT_PATH)
    check(f"{label}：不抓報價、標 connected:false", d.get("connected") is False and d.get("quotes") == {}, str(d)[:160])
    check(f"{label}：連線有關閉", FakeIB.last.disconnected)

# ── 3. 正常與部分代號解析失敗 ──
reset()
rc = run_main()
d = load(iq.OUT_PATH)
want = set(iq.DEFAULT_US_WATCHLIST) | set(iq.US_INDICES)
check("正常：全部代號都有、connected:true", d.get("connected") is True and set(d["quotes"]) == want, str(sorted(d.get("quotes", {}))))
check("正常：bid/ask -1 佔位值轉 null", d["quotes"]["AAPL"]["bid"] is None and d["quotes"]["AAPL"]["last"] == 101.0)
check("正常：不殘留暫存檔、連線有關閉", not list(TMP.glob("*.tmp")) and FakeIB.last.disconnected)

reset()
BAD_SYMBOLS.update({"NVDA", "SOX"})
rc = run_main()
d = load(iq.OUT_PATH)
check("部分解析失敗：代號不從檔案消失", set(d["quotes"]) == want, str(sorted(d.get("quotes", {}))))
nv = d["quotes"].get("NVDA") or {}
check("部分解析失敗：NVDA 全 null 佔位＋原因（不沿用舊價）",
      nv.get("last") is None and nv.get("close") is None and nv.get("data_type") == "UNAVAILABLE" and nv.get("missing_reason"), str(nv))
sx = d["quotes"].get("^SOX") or {}
check("部分解析失敗：費半指數佔位保留中文名稱與原因", sx.get("last") is None and sx.get("label") == "費城半導體指數" and sx.get("missing_reason"), str(sx))
check("部分解析失敗：其他代號照常", d["quotes"]["AAPL"]["last"] == 101.0)

# ── 4. 原子寫入：序列化失敗不截斷既有檔 ──
before = iq.OUT_PATH.read_text(encoding="utf-8")
try:
    iq._write_json_atomic(iq.OUT_PATH, {"bad": object()})
    raised = False
except TypeError:
    raised = True
check("原子寫入：序列化失敗時既有檔不被截斷", raised and iq.OUT_PATH.read_text(encoding="utf-8") == before)

print(f"\n合計 {total} 項，FAIL {len(fails)} 項")
for f in fails:
    print(f"  FAIL：{f}")
sys.exit(1 if fails else 0)
