# -*- coding: utf-8 -*-
"""先.七十七-2 自測：research/nightly_six_runner.py（常備.開發-6 夜間自動開跑）。全程沙盒、假 preflight／假啟動／假推播。
①記憶體不足：02:00 檢查不算「今晚不足」，05:40 之後最後一次檢查才算 ②連續 3 晚不足才推播一次（同一段連續不重複推）
③某晚中斷（夠了）→ 連續數歸零 ④記憶體夠 → 開跑一次、同晚不重複開 ⑤已在跑（PID 活著）不再開 ⑥結果檔已存在 → 不再開跑
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import nightly_six_runner as N  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


tmp = Path(tempfile.mkdtemp())
saved = {k: getattr(N, k) for k in ("STATE", "LOG", "RESULT")}
try:
    N.STATE, N.LOG, N.RESULT = tmp / "st.json", tmp / "n.log", tmp / "result.json"
    pushes = []
    notify = lambda t, b: pushes.append(t)  # noqa: E731
    short = lambda: (False, 3.0, "可用記憶體 3.00GB 低於開跑門檻 4.5GB，不開跑")  # noqa: E731
    enough = lambda: (True, 5.0, "可用記憶體 5.00GB ≥ 開跑門檻 4.5GB")  # noqa: E731
    launched = []
    launcher = lambda: (launched.append(1), os.getpid())[1]  # noqa: E731
    T = lambda s: datetime.fromisoformat(s + "+08:00")  # noqa: E731

    N.check(T("2026-10-11T18:10:00"), preflight=short, launcher=launcher, notify=notify)
    check("①白天手動執行（18:10）不足 → 不算任何一晚不足", not json.loads(N.STATE.read_text(encoding="utf-8")).get("short_streak"))
    r1 = N.check(T("2026-10-12T02:00:00"), preflight=short, launcher=launcher, notify=notify)
    st = json.loads(N.STATE.read_text(encoding="utf-8"))
    check("①02:00 不足 → SHORT，但不算今晚不足", r1 == "SHORT" and not st.get("short_streak"))
    N.check(T("2026-10-12T05:40:00"), preflight=short, launcher=launcher, notify=notify)
    st = json.loads(N.STATE.read_text(encoding="utf-8"))
    check("①05:40 最後一次仍不足 → 今晚不足，連續第 1 晚", st.get("short_streak") == 1)
    N.check(T("2026-10-12T06:00:00"), preflight=short, launcher=launcher, notify=notify)
    check("①同一晚不重複計算", json.loads(N.STATE.read_text(encoding="utf-8")).get("short_streak") == 1)
    N.check(T("2026-10-13T05:40:00"), preflight=short, launcher=launcher, notify=notify)
    check("②第 2 晚不足還不推播", json.loads(N.STATE.read_text(encoding="utf-8")).get("short_streak") == 2 and not pushes)
    N.check(T("2026-10-14T05:40:00"), preflight=short, launcher=launcher, notify=notify)
    check("②連續第 3 晚不足 → 推播一次", len(pushes) == 1 and "跑不了" in pushes[0])
    N.check(T("2026-10-15T05:40:00"), preflight=short, launcher=launcher, notify=notify)
    check("②第 4 晚仍不足 → 同一段連續不重複推", len(pushes) == 1)
    # ④ 記憶體夠 → 開跑（③連續數歸零）
    r = N.check(T("2026-10-16T02:20:00"), preflight=enough, launcher=launcher, notify=notify)
    st = json.loads(N.STATE.read_text(encoding="utf-8"))
    check("④記憶體夠 → 開跑一次、狀態 running、連續不足歸零", r == "STARTED" and len(launched) == 1 and st["status"] == "running" and st["short_streak"] == 0)
    # ⑤ 已在跑（PID＝本行程，活著）
    r = N.check(T("2026-10-16T02:40:00"), preflight=enough, launcher=launcher, notify=notify)
    check("⑤已在跑 → 不再開", r == "RUNNING" and len(launched) == 1)
    # 同晚 PID 已結束但結果未出（例如被安全閥砍）→ 同晚不重複開
    st["pid"] = 999999
    N.STATE.write_text(json.dumps(st), encoding="utf-8")
    r = N.check(T("2026-10-16T03:00:00"), preflight=enough, launcher=launcher, notify=notify)
    check("④同一晚已開跑過 → 不重複開", r == "ALREADY_STARTED" and len(launched) == 1)
    # ⑥ 結果檔已存在
    N.RESULT.write_text(json.dumps({"boards": {"momentum": {"verdict": "回測未通過"}}}), encoding="utf-8")
    r = N.check(T("2026-10-17T02:00:00"), preflight=enough, launcher=launcher, notify=notify)
    check("⑥結果檔已存在 → DONE、不再開跑", r == "DONE" and len(launched) == 1)
finally:
    for k, v in saved.items():
        setattr(N, k, v)
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
