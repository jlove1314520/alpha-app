# -*- coding: utf-8 -*-
"""自測：Shioaji 收盤快照停更判定（2026-11-01 DevQueue 20261101-030102）。

登錄檔原本讀 `checked_at`，收盤快照只寫 `fetched_at` → 永遠 unknown。
改讀 `fetched_at`＋shift_profile=shioaji_close（交易日 14:00 一班、門檻 3）。
零外部請求、不寫任何檔案。用法：python scripts/selftest_shioaji_close_freshness.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from expected_shift_calendar import count_missed_shifts  # noqa: E402

TZ = timezone(timedelta(hours=8))
REG = json.loads((ROOT / "data/seed/pipeline_registry.json").read_text(encoding="utf-8"))
spec = next(p for p in REG["pipelines"] if p["artifact"] == "data/quotes_sinopac.json")
TH = spec["missed_shift_threshold"]

fails = 0


def check(label, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails += 1


def stalled(last, now):
    n, _ = count_missed_shifts("shioaji_close", last, now)
    return n >= TH


def t(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=TZ)


check("登錄檔欄位＝fetched_at", spec["field"] == "fetched_at")
check("登錄檔 shift_profile＝shioaji_close", spec.get("shift_profile") == "shioaji_close")
snap = json.loads((ROOT / "data/quotes_sinopac.json").read_text(encoding="utf-8"))
check("真實快照有 fetched_at", bool(snap.get("fetched_at")))

fri = t(2026, 10, 30, 13, 45, 17)  # 週五收盤快照
check("週五收盤→週一 13:59 不亮燈", not stalled(fri, t(2026, 11, 2, 13, 59)))
check("週五收盤→週一 14:01（週一當天才漏）不亮燈", not stalled(fri, t(2026, 11, 2, 14, 1)))
check("週五收盤→週二 14:01（週一、週二都漏）亮燈", stalled(fri, t(2026, 11, 3, 14, 1)))
# 連假：10/08（四）收盤，10/09 國慶補假＋週末 → 10/12 14:01 只漏 1 天以內
check("10/08 收盤→連假後 10/12 14:01 不亮燈", not stalled(t(2026, 10, 8, 13, 45), t(2026, 10, 12, 14, 1)))
# 颱風臨時休市（10/23 不在靜態假日表）：10/22 收盤→10/26 是假日→10/27 14:01
check("10/22 收盤→颱風休市＋假日後 10/27 13:59（當天收盤寫檔前）不亮燈（多數一班可吸收）",
      not stalled(t(2026, 10, 22, 13, 45), t(2026, 10, 27, 13, 59)))
# 已知限制：颱風日＋下一個交易日真的漏寫 → 10/27 14:00 就亮燈（實際只漏 1 天）。寧可多報。
check("10/22 收盤→10/27 14:01 仍沒寫 亮燈（已知寧可多報）",
      stalled(t(2026, 10, 22, 13, 45), t(2026, 10, 27, 14, 1)))
check("同日 13:46 剛寫完 不亮燈", not stalled(fri, t(2026, 10, 30, 13, 46)))

print(f"\n{'全部通過' if fails == 0 else f'{fails} 項失敗'}")
sys.exit(1 if fails else 0)
