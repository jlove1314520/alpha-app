# -*- coding: utf-8 -*-
"""先.一三二-0a（2026-10-23，收件匣 020）：模擬 I 追蹤程式不得對 2026-11-02 以前的日期算報酬或淨值。

模擬 I（#463，docs/PREREG_STOCK_BREAKOUT_252H_FINAL.md §5-1 採甲）可以讀 2025-10-28～2026-10-30 的官方日檔
（research/data/ 底下的模擬 I 回看資料夾，見 research/validation/holdout.py ALLOWED_HOLDOUT_READERS／RESTRICTED_LOOKBACK_DIRS），但**只當訊號回看輸入**。
本自測也是 DevQueue 寫 research/paper_9_breakout_tracker.py 時必須照著做的介面約定：
  - 常數 START_NOT_BEFORE == "2026-11-02"；LOG（帳本路徑）、OUT（App 摘要路徑）為模組層變數（自測會改指到暫存資料夾）；
  - step(today: str | None = None)：today < START_NOT_BEFORE 一律回 {"state": "NOT_STARTED", ...}，不寫帳本；
  - lookback_features(day: str) -> {代號: {"high_252": float|None, "avgvol_20": float|None}}：回看資料只產生這兩個欄位。
檢查：
1. START_NOT_BEFORE 是 2026-11-02；
2. step("2026-10-30")、step("2026-11-01") 都回 NOT_STARTED，帳本沒有新增任何一行；
3. 既有帳本（若有）每一筆日期都 ≥ 2026-11-02；
4. lookback_features("2026-10-30") 每檔只有 high_252／avgvol_20 兩個欄位（沒有報酬、淨值、損益之類的欄位）。
tracker 還沒寫好時印 PENDING、exit 0（DevQueue 寫完後必須跑到全 PASS 才能掛排程）。
跑法：python scripts/selftest_paper_9_no_pre_start_returns.py
"""
import importlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

START = "2026-11-02"
ALLOWED_KEYS = {"high_252", "avgvol_20"}
TRACKER = ROOT / "research" / "paper_9_breakout_tracker.py"

if not TRACKER.exists():
    print("PENDING：research/paper_9_breakout_tracker.py 尚未建立（先.一三二-0 由 DevQueue 寫；寫完必須跑本自測全 PASS 才能掛 market.yml）")
    sys.exit(0)

T = importlib.import_module("paper_9_breakout_tracker")
res = []
res.append((f"START_NOT_BEFORE == {START}", getattr(T, "START_NOT_BEFORE", None) == START))

real_log = Path(getattr(T, "LOG", ROOT / "research" / "data" / "paper_9_log.jsonl"))
if real_log.exists():
    dates = []
    for ln in real_log.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rec = json.loads(ln)
            dates.append(str(rec.get("date") or rec.get("day") or ""))
    early = [d for d in dates if d and d < START]
    res.append((f"既有帳本 {len(dates)} 筆日期都 ≥ {START}", not early))
else:
    res.append(("既有帳本尚不存在（OK）", True))

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    T.LOG, T.OUT = td / "paper_9_log.jsonl", td / "paper_9.json"
    for day in ("2026-10-30", "2026-11-01"):
        try:
            r = T.step(day)
            ok = isinstance(r, dict) and r.get("state") == "NOT_STARTED" and not (T.LOG.exists() and T.LOG.read_text(encoding="utf-8").strip())
            res.append((f"step({day}) 回 NOT_STARTED 且不寫帳本", ok))
        except Exception as e:  # noqa: BLE001
            res.append((f"step({day}) 回 NOT_STARTED 且不寫帳本（例外 {type(e).__name__}: {e}）", False))

try:
    feats = T.lookback_features("2026-10-30")
    extra = sorted({k for v in (feats or {}).values() for k in (v or {})} - ALLOWED_KEYS)
    res.append((f"lookback_features 只產生 high_252／avgvol_20（{len(feats or {})} 檔）" + (f"；多出 {extra}" if extra else ""), not extra))
except Exception as e:  # noqa: BLE001
    res.append((f"lookback_features 只產生 high_252／avgvol_20（例外 {type(e).__name__}: {e}）", False))

for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
nb = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {nb}")
sys.exit(1 if nb else 0)
