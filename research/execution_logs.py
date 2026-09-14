# -*- coding: utf-8 -*-
"""真錢執行品質證據紀錄（深讀五，2026-09-15新增，配合`mainnet_gate.py`）。

**目的**：裁示五要求「第一個30天只看執行品質五題（對帳30/30、中位滑價≤回測
假設2倍、成交率≥95%、零非預期停擺、kill演練過一次）」——這支檔案是這五題
各自要讀的**證據來源**，全部是append-only（只用`open(path,"a")`，沒有任何
「讀出全部→改一筆→整份寫回」的路徑），每一行都用雜湊鏈防竄改，比照
`research/shadow_ledger.py`同一套精神但用sequence而非date排序（滑價/成交
紀錄一天可能有多筆，不像影子帳本一天一筆）。

**現況誠實揭露**：目前沒有任何真實下單路徑會呼叫這裡的`log_*()`函式——
`research/shioaji_order_server.py`只有模擬環境，且不記錄這裡定義的格式。
這支檔案是「證據格式先定義好、資料之後才會有」的預備基礎設施，五個
`research/execution_logs/*.jsonl`檔案目前都不存在，這是符合預期的空狀態，
不是bug。

**兩段式滑價記錄（比照Cybex RUNBOOK的`slippage_log`表，符號統一為「正=吃虧」）**：
- `slippage_bp`：相對送單當下參考價（`intended_px`）的滑價。
- `vs_signal_bp`：相對訊號價（`signal_px`）的滑價，含「決策到送單」之間的
  價格漂移——回測是用收盤價成交，所以比較回測假設時要看**這一欄**，不是
  `slippage_bp`（RUNBOOK原文已強調這點，這裡沿用同一個判讀規則）。
- 手續費（`fee_twd`）另計，不併進滑價。
- 台股額外記兩個裁示五指定的欄位：`session`（開盤集合競價／盤中逐筆撮合／
  收盤集合競價）與`is_call_auction`（是否為集合競價撮合，由`session`推導）。

跑法：
    python execution_logs.py verify        # 稽核五本帳本的雜湊鏈
    python execution_logs.py --self-test   # 自我測試，暫存目錄執行
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "execution_logs"
TW_TZ = timezone(timedelta(hours=8))
GENESIS_HASH = "GENESIS"

SLIPPAGE_LOG_PATH = LOG_DIR / "slippage_log.jsonl"
ORDER_ATTEMPTS_LOG_PATH = LOG_DIR / "order_attempts.jsonl"
RECONCILIATION_LOG_PATH = LOG_DIR / "reconciliation_log.jsonl"
OUTAGE_LOG_PATH = LOG_DIR / "outage_log.jsonl"
KILL_DRILL_LOG_PATH = LOG_DIR / "kill_drill_log.jsonl"

ALL_LOG_PATHS = (
    SLIPPAGE_LOG_PATH, ORDER_ATTEMPTS_LOG_PATH, RECONCILIATION_LOG_PATH,
    OUTAGE_LOG_PATH, KILL_DRILL_LOG_PATH,
)

VALID_SESSIONS = ("開盤集合競價", "盤中逐筆撮合", "收盤集合競價")
_CALL_AUCTION_SESSIONS = ("開盤集合競價", "收盤集合競價")
VALID_ORDER_STATUS = ("FILLED", "PARTIAL", "REJECTED", "FAILED", "CANCELLED")
VALID_RECON_STATUS = ("MATCH", "MISMATCH")
VALID_KILL_DRILL_STATES = ("halt_new", "halt")
VALID_KILL_DRILL_RESULTS = ("PASS", "FAIL")


# --- 通用append-only + 雜湊鏈基礎設施 ---

def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _record_hash(prev_hash: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode("utf-8")).hexdigest()


def _append(path: Path, payload: dict) -> dict:
    existing = _read_lines(path)
    prev_hash = existing[-1]["hash"] if existing else GENESIS_HASH
    seq = (existing[-1]["seq"] + 1) if existing else 1
    record = {"seq": seq, "payload": payload, "prev_hash": prev_hash,
              "hash": _record_hash(prev_hash, payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def verify_chain(path: Path) -> tuple[bool, str, int]:
    records = _read_lines(path)
    if not records:
        return True, "尚無資料（空狀態，不算異常）", 0
    prev_hash = GENESIS_HASH
    prev_seq = 0
    for i, rec in enumerate(records):
        if rec.get("prev_hash") != prev_hash:
            return False, f"第{i+1}筆prev_hash對不上前一筆的hash，鏈已斷", i + 1
        expected = _record_hash(prev_hash, rec["payload"])
        if rec.get("hash") != expected:
            return False, f"第{i+1}筆內容雜湊對不上，疑似被竄改", i + 1
        if rec.get("seq") != prev_seq + 1:
            return False, f"第{i+1}筆seq={rec.get('seq')}不連續（預期{prev_seq+1}）", i + 1
        prev_hash = rec["hash"]
        prev_seq = rec["seq"]
    return True, f"雜湊鏈完整，共{len(records)}筆", len(records)


def _payloads(path: Path) -> list[dict]:
    return [r["payload"] for r in _read_lines(path)]


def _within_window(iso_ts: str, window_days: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(TW_TZ)
    ts = datetime.fromisoformat(iso_ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=TW_TZ)
    return ts >= now - timedelta(days=window_days)


# --- 1. 滑價（兩段式） ---

def log_slippage(*, book: str, symbol: str, side: str, signal_px: float, intended_px: float,
                  filled_px: float, qty: float, fee_twd: float, session: str,
                  dry_run: bool = True, at: str | None = None) -> dict:
    if side not in ("BUY", "SELL"):
        raise ValueError("side必須是BUY或SELL")
    if session not in VALID_SESSIONS:
        raise ValueError(f"session必須是{VALID_SESSIONS}其中之一")
    for name, px in (("signal_px", signal_px), ("intended_px", intended_px), ("filled_px", filled_px)):
        if px is None or px <= 0:
            raise ValueError(f"{name}必須是正數")

    sign = 1.0 if side == "BUY" else -1.0  # 買方付更多是吃虧(正)；賣方收更少是吃虧(正)
    slippage_bp = round(((filled_px / intended_px) - 1) * 1e4 * sign, 4)
    vs_signal_bp = round(((filled_px / signal_px) - 1) * 1e4 * sign, 4)

    payload = {
        "at": at or datetime.now(TW_TZ).isoformat(),
        "book": book, "symbol": symbol, "side": side, "qty": qty,
        "signal_px": signal_px, "intended_px": intended_px, "filled_px": filled_px,
        "slippage_bp": slippage_bp, "vs_signal_bp": vs_signal_bp,
        "fee_twd": fee_twd, "session": session,
        "is_call_auction": session in _CALL_AUCTION_SESSIONS,
        "dry_run": bool(dry_run),
    }
    return _append(SLIPPAGE_LOG_PATH, payload)


def median_vs_signal_bp(window_days: int = 30, dry_run: bool | None = None) -> tuple[float | None, int]:
    import statistics
    rows = _payloads(SLIPPAGE_LOG_PATH)
    rows = [r for r in rows if _within_window(r["at"], window_days)]
    if dry_run is not None:
        rows = [r for r in rows if r["dry_run"] == dry_run]
    if not rows:
        return None, 0
    values = [r["vs_signal_bp"] for r in rows]
    return statistics.median(values), len(values)


# --- 2. 下單嘗試（成交率用） ---

def log_order_attempt(*, book: str, symbol: str, side: str, qty: float, status: str,
                       dry_run: bool = True, note: str = "", at: str | None = None) -> dict:
    if status not in VALID_ORDER_STATUS:
        raise ValueError(f"status必須是{VALID_ORDER_STATUS}其中之一")
    payload = {
        "at": at or datetime.now(TW_TZ).isoformat(),
        "book": book, "symbol": symbol, "side": side, "qty": qty,
        "status": status, "dry_run": bool(dry_run), "note": note,
    }
    return _append(ORDER_ATTEMPTS_LOG_PATH, payload)


def fill_rate(window_days: int = 30, dry_run: bool | None = None) -> tuple[float | None, int]:
    rows = _payloads(ORDER_ATTEMPTS_LOG_PATH)
    rows = [r for r in rows if _within_window(r["at"], window_days)]
    if dry_run is not None:
        rows = [r for r in rows if r["dry_run"] == dry_run]
    if not rows:
        return None, 0
    filled = sum(1 for r in rows if r["status"] == "FILLED")
    return filled / len(rows), len(rows)


# --- 3. 每日對帳 ---

def log_reconciliation(*, date: str, book: str, status: str, detail: str = "") -> dict:
    if status not in VALID_RECON_STATUS:
        raise ValueError(f"status必須是{VALID_RECON_STATUS}其中之一")
    payload = {"date": date, "book": book, "status": status, "detail": detail,
               "logged_at": datetime.now(TW_TZ).isoformat()}
    return _append(RECONCILIATION_LOG_PATH, payload)


def reconciliation_streak(window_days: int = 30) -> dict:
    rows = _payloads(RECONCILIATION_LOG_PATH)
    rows = [r for r in rows if _within_window(r["logged_at"], window_days)]
    match = sum(1 for r in rows if r["status"] == "MATCH")
    return {"match": match, "total": len(rows), "mismatches": [r for r in rows if r["status"] == "MISMATCH"]}


# --- 4. 非預期停擺 ---

def log_outage(*, duration_min: float, reason: str, expected: bool, at: str | None = None) -> dict:
    payload = {"at": at or datetime.now(TW_TZ).isoformat(), "duration_min": duration_min,
               "reason": reason, "expected": bool(expected)}
    return _append(OUTAGE_LOG_PATH, payload)


def unexpected_outage_count(window_days: int = 30) -> int:
    rows = _payloads(OUTAGE_LOG_PATH)
    rows = [r for r in rows if _within_window(r["at"], window_days)]
    return sum(1 for r in rows if not r["expected"])


# --- 5. kill switch演練 ---

def log_kill_drill(*, state_tested: str, result: str, note: str = "", at: str | None = None) -> dict:
    if state_tested not in VALID_KILL_DRILL_STATES:
        raise ValueError(f"state_tested必須是{VALID_KILL_DRILL_STATES}其中之一")
    if result not in VALID_KILL_DRILL_RESULTS:
        raise ValueError(f"result必須是{VALID_KILL_DRILL_RESULTS}其中之一")
    payload = {"at": at or datetime.now(TW_TZ).isoformat(), "state_tested": state_tested,
               "result": result, "note": note}
    return _append(KILL_DRILL_LOG_PATH, payload)


def has_passing_drill(window_days: int | None = None) -> bool:
    rows = _payloads(KILL_DRILL_LOG_PATH)
    if window_days is not None:
        rows = [r for r in rows if _within_window(r["at"], window_days)]
    return any(r["result"] == "PASS" for r in rows)


def _cli_verify() -> int:
    all_ok = True
    for path in ALL_LOG_PATHS:
        ok, detail, _n = verify_chain(path)
        print(f"[{'PASS' if ok else 'FAIL'}] {path.name}: {detail}")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


def _self_test() -> int:
    import shutil

    global LOG_DIR, SLIPPAGE_LOG_PATH, ORDER_ATTEMPTS_LOG_PATH, RECONCILIATION_LOG_PATH
    global OUTAGE_LOG_PATH, KILL_DRILL_LOG_PATH, ALL_LOG_PATHS
    orig = (LOG_DIR, SLIPPAGE_LOG_PATH, ORDER_ATTEMPTS_LOG_PATH, RECONCILIATION_LOG_PATH,
            OUTAGE_LOG_PATH, KILL_DRILL_LOG_PATH, ALL_LOG_PATHS)
    tmp = Path(tempfile.mkdtemp(prefix="alpha_execution_logs_selftest_"))
    LOG_DIR = tmp
    SLIPPAGE_LOG_PATH = tmp / "slippage_log.jsonl"
    ORDER_ATTEMPTS_LOG_PATH = tmp / "order_attempts.jsonl"
    RECONCILIATION_LOG_PATH = tmp / "reconciliation_log.jsonl"
    OUTAGE_LOG_PATH = tmp / "outage_log.jsonl"
    KILL_DRILL_LOG_PATH = tmp / "kill_drill_log.jsonl"
    ALL_LOG_PATHS = (SLIPPAGE_LOG_PATH, ORDER_ATTEMPTS_LOG_PATH, RECONCILIATION_LOG_PATH,
                      OUTAGE_LOG_PATH, KILL_DRILL_LOG_PATH)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    try:
        # 空狀態
        for path in ALL_LOG_PATHS:
            ok, _detail, n = verify_chain(path)
            check(f"{path.name}空狀態應PASS", ok is True and n == 0)

        # 滑價：BUY吃虧(正)
        r = log_slippage(book="test", symbol="2330", side="BUY", signal_px=100.0,
                          intended_px=100.5, filled_px=101.0, qty=1000, fee_twd=15.0,
                          session="盤中逐筆撮合")
        check("BUY成交價高於送單價應為正滑價", r["payload"]["slippage_bp"] > 0)
        check("BUY vs_signal應為正", r["payload"]["vs_signal_bp"] > 0)
        check("盤中逐筆撮合不是集合競價", r["payload"]["is_call_auction"] is False)

        # 滑價：SELL吃虧(正) —— 賣方成交價比預期低才是吃虧
        r2 = log_slippage(book="test", symbol="2330", side="SELL", signal_px=100.0,
                           intended_px=100.0, filled_px=99.5, qty=1000, fee_twd=15.0,
                           session="開盤集合競價")
        check("SELL成交價低於送單價應為正滑價", r2["payload"]["slippage_bp"] > 0)
        check("開盤集合競價應標記is_call_auction", r2["payload"]["is_call_auction"] is True)
        check("seq應遞增為2", r2["seq"] == 2)

        med, n = median_vs_signal_bp(window_days=30)
        check("兩筆滑價中位數應可算出", med is not None and n == 2)

        ok, detail, n = verify_chain(SLIPPAGE_LOG_PATH)
        check(f"滑價log雜湊鏈應PASS: {detail}", ok is True and n == 2)

        # 下單嘗試 / 成交率
        log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="FILLED")
        log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="FILLED")
        log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="REJECTED")
        rate, n = fill_rate(window_days=30)
        check("成交率應為2/3", rate is not None and abs(rate - (2 / 3)) < 1e-9 and n == 3)

        # 對帳
        log_reconciliation(date="2026-09-15", book="test", status="MATCH")
        log_reconciliation(date="2026-09-16", book="test", status="MISMATCH", detail="測試用不符")
        streak = reconciliation_streak(window_days=30)
        check("對帳streak應為1/2", streak["match"] == 1 and streak["total"] == 2)
        check("mismatch明細應有1筆", len(streak["mismatches"]) == 1)

        # 停擺
        log_outage(duration_min=5, reason="測試預期維護", expected=True)
        log_outage(duration_min=3, reason="測試非預期斷線", expected=False)
        check("非預期停擺數應為1", unexpected_outage_count(window_days=30) == 1)

        # kill演練
        check("尚未演練前has_passing_drill應為False", has_passing_drill() is False)
        log_kill_drill(state_tested="halt_new", result="PASS", note="自我測試演練")
        check("演練PASS後has_passing_drill應為True", has_passing_drill() is True)

        # 竄改偵測：手動改寫一行payload，雜湊鏈應抓到
        lines = SLIPPAGE_LOG_PATH.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["payload"]["filled_px"] = 999.0
        lines[0] = json.dumps(tampered, ensure_ascii=False)
        SLIPPAGE_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, detail, _n = verify_chain(SLIPPAGE_LOG_PATH)
        check(f"竄改後verify_chain應偵測到FAIL: {detail}", ok is False)

    finally:
        (LOG_DIR, SLIPPAGE_LOG_PATH, ORDER_ATTEMPTS_LOG_PATH, RECONCILIATION_LOG_PATH,
         OUTAGE_LOG_PATH, KILL_DRILL_LOG_PATH, ALL_LOG_PATHS) = orig
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"[FAIL] {len(failures)}項未過：{failures}")
        return 1
    print("[PASS] execution_logs.py 自我測試全部通過（含竄改偵測，暫存目錄執行）")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        sys.exit(_self_test())
    if args and args[0] == "verify":
        sys.exit(_cli_verify())
    print(__doc__)
    sys.exit(1)
