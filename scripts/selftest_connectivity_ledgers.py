#!/usr/bin/env python3
"""先.一三五-1eo／1ep／1eq：連通性監測（check_external_connectivity.py，AlphaConnectivity 每 30 分鐘）
呼叫的三支帳本／告警模組合成自測。

零外部請求、零 gh api：登錄檔、狀態檔、PENDING_QUEUE、輸出檔全部換到暫存目錄。
- 1eo pipeline_fault_ledger：邊緣觸發（故障延續不重複計數、恢復後再故障才 +1）、event_log 上限、
  登錄檔找不到節點時跳過不寫壞、狀態沒變不改寫狀態檔。
- 1ep check_pat_expiry.get_alerts：未追蹤／日期壞掉不誤報、門檻內才告警、已過期也告警（剩餘負數）、
  登錄檔讀不到回空清單不拋例外。
- 1eq factory_stability：少於 2 筆事件不硬算 MTBF、壞時間戳跳過、⛔ 自走中止依 ISO 週計數、
  週歷史同週覆蓋／換週新增、壞行跳過、輸出合法 JSON。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def write_reg(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


tmp = Path(tempfile.mkdtemp(prefix="selftest_connledger_"))

# ---------------- 1eo pipeline_fault_ledger ----------------
print("[1eo] pipeline_fault_ledger")
pfl = load("pipeline_fault_ledger")
pfl.REGISTRY = tmp / "reg_pfl.json"
pfl.STATE = tmp / "state" / ".pipeline_fault_state.json"
write_reg(pfl.REGISTRY, {"pipelines": [
    {"task": "A", "artifact": "a.json"},
    {"task": "A", "artifact": "b.json"},
]})
t0 = datetime(2026, 10, 31, 9, 0, tzinfo=TZ)
row_a = lambda s: {"task": "A", "artifact": "a.json", "status": s}  # noqa: E731
row_b = lambda s: {"task": "A", "artifact": "b.json", "status": s}  # noqa: E731

new = pfl.update_fault_history([row_a("stalled"), row_b("ok")], t0)
reg = json.loads(pfl.REGISTRY.read_text(encoding="utf-8"))
fh = reg["pipelines"][0].get("fault_history", {})
check("首次故障 +1", fh.get("count") == 1 and len(new) == 1, str(fh))
check("同 task 不同 artifact 分開記", "fault_history" not in reg["pipelines"][1])
check("狀態檔建立", pfl.STATE.exists())

new = pfl.update_fault_history([row_a("stalled"), row_b("ok")], t0 + timedelta(minutes=30))
fh = json.loads(pfl.REGISTRY.read_text(encoding="utf-8"))["pipelines"][0]["fault_history"]
check("故障延續不重複計數", fh["count"] == 1 and new == [], str(fh))

mtime_state = pfl.STATE.stat().st_mtime_ns
pfl.update_fault_history([row_a("stalled"), row_b("ok")], t0 + timedelta(minutes=60))
check("狀態沒變不改寫狀態檔", pfl.STATE.stat().st_mtime_ns == mtime_state)

pfl.update_fault_history([row_a("ok"), row_b("ok")], t0 + timedelta(hours=2))
new = pfl.update_fault_history([row_a("missing"), row_b("ok")], t0 + timedelta(hours=3))
fh = json.loads(pfl.REGISTRY.read_text(encoding="utf-8"))["pipelines"][0]["fault_history"]
check("恢復後再故障 +1，fault_types 分 stalled/missing",
      fh["count"] == 2 and fh["fault_types"] == {"stalled": 1, "missing": 1}, str(fh))
check("event_log 兩筆", len(fh["event_log"]) == 2)

reg = json.loads(pfl.REGISTRY.read_text(encoding="utf-8"))
reg["pipelines"][0]["fault_history"]["event_log"] = [f"2026-10-01T00:{i:02d}:00+08:00" for i in range(40)]
write_reg(pfl.REGISTRY, reg)
pfl.update_fault_history([row_a("ok"), row_b("ok")], t0 + timedelta(hours=4))
pfl.update_fault_history([row_a("stalled"), row_b("ok")], t0 + timedelta(hours=5))
fh = json.loads(pfl.REGISTRY.read_text(encoding="utf-8"))["pipelines"][0]["fault_history"]
check("event_log 上限 30 筆、最新一筆在尾端",
      len(fh["event_log"]) == pfl.EVENT_LOG_MAX and fh["event_log"][-1] == (t0 + timedelta(hours=5)).isoformat(),
      str(len(fh["event_log"])))

before = pfl.REGISTRY.read_text(encoding="utf-8")
new = pfl.update_fault_history([{"task": "Z", "artifact": "z.json", "status": "stalled"}], t0 + timedelta(hours=6))
check("登錄檔找不到節點：跳過、不改登錄檔", new == [] and pfl.REGISTRY.read_text(encoding="utf-8") == before)

# ---------------- 1ep check_pat_expiry ----------------
print("[1ep] check_pat_expiry.get_alerts")
cpe = load("check_pat_expiry")
cpe.REGISTRY = tmp / "reg_pat.json"
today = datetime.now(TZ).date()


def pat(expires: str | None, **extra) -> None:
    doc: dict = {"pipelines": []}
    if expires is not None:
        doc["github_pat_expiry"] = {"expires_at": expires, **extra}
    write_reg(cpe.REGISTRY, doc)


check("登錄檔不存在回空清單不拋例外", cpe.get_alerts() == [])
pat(None)
check("還沒追蹤不誤報", cpe.get_alerts() == [])
pat("not-a-date")
check("日期壞掉不誤報", cpe.get_alerts() == [])
pat((today + timedelta(days=30)).isoformat())
check("剩 30 天不告警（門檻 14）", cpe.get_alerts() == [])
pat((today + timedelta(days=14)).isoformat())
a = cpe.get_alerts()
check("剩 14 天告警", len(a) == 1 and a[0][1] == 14, str(a))
pat((today - timedelta(days=2)).isoformat())
a = cpe.get_alerts()
check("已過期也告警（剩 -2 天）", len(a) == 1 and a[0][1] == -2, str(a))
pat((today + timedelta(days=20)).isoformat(), alert_threshold_days=30)
check("登錄檔自訂門檻優先", len(cpe.get_alerts()) == 1)
check("訊息不含 token 字樣以外的值（只有日期）", "ghp_" not in (cpe.get_alerts()[0][0]))

# ---------------- 1eq factory_stability ----------------
print("[1eq] factory_stability")
fs = load("factory_stability")
fs.REGISTRY = tmp / "reg_fs.json"
fs.QUEUE = tmp / "PENDING_QUEUE.md"
fs.SNAPSHOT = tmp / "factory_stability.json"
fs.HISTORY = tmp / "factory_stability_history.jsonl"
write_reg(fs.REGISTRY, {"pipelines": [
    {"task": "A", "artifact": "a.json", "fault_history": {"count": 3, "event_log": [
        "2026-10-01T00:00:00+08:00", "garbage", "2026-10-01T10:00:00+08:00", "2026-10-02T06:00:00+08:00"]}},
    {"task": "B", "artifact": "b.json", "fault_history": {"count": 1, "event_log": ["2026-10-05T00:00:00+08:00"]}},
    {"task": "C", "artifact": "c.json"},
]})
fs.QUEUE.write_text(
    "x ⛔ 自走中止（2026-10-26 08:00） y\n⛔ 自走中止（2026-10-27 09:30）\n⛔ 自走中止（2026-11-02 01:00）\n"
    "⛔ 自走中止（2026-10-2 08:00）（格式不對不算）\n", encoding="utf-8")
now = datetime(2026, 10, 31, 9, 0, tzinfo=TZ)
snap = fs.run(now)
m = {r["task"]: r for r in snap["pipeline_mtbf"]}
check("壞時間戳跳過、3 筆事件 MTBF＝(10+20)/2＝15.0", m["A"]["mtbf_hours"] == 15.0, str(m["A"]))
check("1 筆事件不硬算", m["B"]["mtbf_hours"] is None and "資料不足" in m["B"]["mtbf_basis"])
check("沒有事件標資料不足", m["C"]["mtbf_hours"] is None and m["C"]["fault_count_since_epoch"] == 0)
wk = {w["iso_week"]: w["devqueue_block_count"] for w in snap["weekly_devqueue_blocks"]}
check("⛔ 依 ISO 週分組（W44＝2、W45＝1）", wk == {"2026-W44": 2, "2026-W45": 1}, str(wk))
check("快照是合法 JSON", json.loads(fs.SNAPSHOT.read_text(encoding="utf-8"))["generated_at"] == now.isoformat())

fs.run(now + timedelta(hours=1))
lines = [l for l in fs.HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]
check("同週只留一筆（覆蓋）", len(lines) == 1 and json.loads(lines[0])["recorded_at"] == (now + timedelta(hours=1)).isoformat())
fs.HISTORY.write_text(fs.HISTORY.read_text(encoding="utf-8") + "{壞行\n", encoding="utf-8")
fs.run(now + timedelta(days=3))  # 11/03 週二＝W45
lines = [json.loads(l) for l in fs.HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]
check("換週新增一筆、壞行跳過", [r["iso_week"] for r in lines] == ["2026-W44", "2026-W45"], str([r.get("iso_week") for r in lines]))

print(f"\n合計 {total} 項，FAIL {len(fails)} 項" + (f"：{fails}" if fails else ""))
sys.exit(1 if fails else 0)
