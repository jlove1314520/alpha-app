#!/usr/bin/env python3
"""先.一三五-1es／1et：連通性監測（check_external_connectivity.py，AlphaConnectivity 每 30 分鐘）
呼叫、但先前沒有任何自測引用的兩支模組合成自測。

零外部請求：PENDING_QUEUE、輸出目錄全部換到暫存目錄；PowerShell 呼叫換成假的。
- 1es check_stale_user_visible_blocks.get_alerts：超過 3 個交易日才告警（只排週末）、標【已解除】不算、
  日期打錯只略過那一行不拋例外、跨行不誤配對、檔案不存在回空清單。
- 1et mem_profile_sample.maybe_sample：時段外／量滿 2 個平日／9 分鐘內已取都不取樣、
  時段內寫一列、PowerShell 回壞輸出只回 False 不拋例外不寫檔、--force 只印不寫檔。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))
fails: list[str] = []
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global total
    total += 1
    print(f"  {'OK ' if ok else 'FAIL'} {name}{'' if ok else '　' + detail}")
    if not ok:
        fails.append(name)


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"st_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tmp = Path(tempfile.mkdtemp(prefix="selftest_staleblk_mem_"))

# ---------------- 1es check_stale_user_visible_blocks ----------------
print("[1es] check_stale_user_visible_blocks")
sb = load("check_stale_user_visible_blocks")
sb.PENDING_QUEUE = tmp / "PQ.md"
check("檔案不存在回空清單", sb.get_alerts() == [])

now = datetime(2026, 10, 30, 12, 0, tzinfo=TZ)  # 週五
sb.PENDING_QUEUE.write_text("\n".join([
    "  ⛔（2026-10-24）【使用者可見】A 週六起算到週五＝5 個交易日",   # 告警
    "  ⛔（2026-10-26）【使用者可見】B 週一起算＝4 個交易日",          # 告警
    "  ⛔（2026-10-27）【使用者可見】C 週二起算＝3 個交易日，不超過",  # 不告警
    "  ⛔（2026-09-15）【使用者可見】D 很舊但【已解除 2026-09-15：已修】",  # 不告警
    "  ⛔（2026-13-40）【使用者可見】E 日期打錯",                      # 略過
    "  ⛔（2026-09-01）只有阻塞",
    "【使用者可見】F 標籤在另一行",
]), encoding="utf-8")
try:
    got = sb.get_alerts(now)
    ok_no_raise = True
except Exception as e:  # noqa: BLE001
    got, ok_no_raise = [], False
    print(f"    例外：{type(e).__name__}: {e}")
check("日期打錯不拋例外", ok_no_raise)
heads = {t.split("】")[1][:1]: d for t, d in got}
check("A＝5、B＝4 告警，C（剛好 3）不告警", heads == {"A": 5, "B": 4}, str(heads))
check("標【已解除】不算", "D" not in heads)
check("沒有【使用者可見】或跨行不誤配對", not any(k in heads for k in ("F",)) and len(got) == 2)

# ---------------- 1et mem_profile_sample ----------------
print("[1et] mem_profile_sample")
mp = load("mem_profile_sample")
mp.OUT_DIR = tmp / "mem"
clock = {"now": datetime(2026, 11, 2, 19, 0, tzinfo=TZ)}  # 週一 19:00，時段內


class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D401
        return clock["now"]


mp.datetime = FakeDT
calls = {"n": 0, "stdout": json.dumps({"free_mb": 3000, "total_mb": 16000,
                                       "top": [{"name": "python", "ws_mb": 512.0, "n": 3}]})}


def fake_run(*_a, **_k):
    calls["n"] += 1
    return SimpleNamespace(stdout=calls["stdout"], returncode=0)


mp.subprocess = SimpleNamespace(run=fake_run)

clock["now"] = datetime(2026, 11, 2, 17, 0, tzinfo=TZ)
check("平日時段外不取樣", mp.maybe_sample(caller="t") is False and calls["n"] == 0)
clock["now"] = datetime(2026, 11, 1, 19, 0, tzinfo=TZ)  # 週日
check("週末不取樣", mp.maybe_sample(caller="t") is False and calls["n"] == 0)

clock["now"] = datetime(2026, 11, 2, 19, 0, tzinfo=TZ)
ok = mp.maybe_sample(caller="t")
f = mp.OUT_DIR / "mem_profile_2026-11-02.jsonl"
rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []
check("時段內寫一列（含 free_mb／top）", ok and len(rows) == 1 and rows[0]["free_mb"] == 3000
      and rows[0]["top"][0]["name"] == "python" and rows[0]["caller"] == "t", str(rows))

clock["now"] = datetime(2026, 11, 2, 19, 8, tzinfo=TZ)
check("9 分鐘內不重取", mp.maybe_sample(caller="t") is False and calls["n"] == 1)
clock["now"] = datetime(2026, 11, 2, 19, 10, tzinfo=TZ)
check("超過 9 分鐘再取一列", mp.maybe_sample(caller="t") and len(f.read_text(encoding="utf-8").splitlines()) == 2)

calls["stdout"] = "不是 JSON"
clock["now"] = datetime(2026, 11, 2, 19, 30, tzinfo=TZ)
try:
    r = mp.maybe_sample(caller="t")
    ok_no_raise = True
except Exception:  # noqa: BLE001
    r, ok_no_raise = None, False
check("PowerShell 回壞輸出：回 False、不拋例外、不寫檔", ok_no_raise and r is False
      and len(f.read_text(encoding="utf-8").splitlines()) == 2)

calls["stdout"] = json.dumps({"free_mb": 1, "total_mb": 2, "top": []})
clock["now"] = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)  # 時段外，但 force
check("--force 只印不寫檔", mp.maybe_sample(force=True, caller="m") is True
      and not (mp.OUT_DIR / "mem_profile_2026-11-03.jsonl").exists())

(mp.OUT_DIR / "mem_profile_2026-11-03.jsonl").write_text("", encoding="utf-8")
clock["now"] = datetime(2026, 11, 4, 19, 0, tzinfo=TZ)
n0 = calls["n"]
check("已量滿 2 個平日、今天不在其中 → 自動停", mp.maybe_sample(caller="t") is False and calls["n"] == n0)

print(f"\n合計 {total} 項，FAIL {len(fails)} 項" + (f"：{fails}" if fails else ""))
sys.exit(1 if fails else 0)
