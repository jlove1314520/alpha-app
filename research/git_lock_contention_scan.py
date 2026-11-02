"""先.一三五-1iq：本機排程「拿不到 git_op_lock／push 失敗」頻率普查（唯讀、零外部請求）。

掃 research/ 與 research/data/ 下有收尾提交紀錄的排程 log，近 14 天（以執行當下台北時間往回算），
依啟動器×台北小時列出：班次數、拿不到鎖次數、push 失敗次數；另讀 research/git_op_lock.log
（2026-11-02 先.一三五-1hu 起才會記 LOCK_HELD 的持有者）。
輸出 research/data/git_lock_contention_YYYYMMDD.json，只放計數與時間，不放 log 內容。

用法：python research/git_lock_contention_scan.py [--days 14]
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — 主控台編碼設定失敗只影響印字
    pass

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data"


def _read(p: Path) -> list[str]:
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        print(f"[warn] 讀不到 {p}：{e}")
        return []


def _sectioned(path: Path, header_re: str, lock_re: str, fail_re: str, trailing: bool = False):
    """以「===== … YYYY-MM-DD HH:MM:SS」為班次開頭的 log。

    trailing=True：事件行可能寫在下一個班次開頭之前（DevQueue 收尾在 cycle end 之後才印），
    仍歸給前一個班次。"""
    hdr = re.compile(header_re)
    runs = []  # (start_dt, lock, fail)
    cur = None
    for line in _read(path):
        m = hdr.search(line)
        if m:
            if cur:
                runs.append(cur)
            cur = [datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), 0, 0]
            continue
        if cur is None:
            continue
        if re.search(lock_re, line):
            cur[1] += 1
        elif re.search(fail_re, line):
            cur[2] += 1
    if cur:
        runs.append(cur)
    return runs


def _news(path: Path, year: int):
    runs = []
    pat = re.compile(r"^\[(\d{2})-(\d{2}) (\d{2}):(\d{2})\]\s+提交：(.*)$")
    for line in _read(path):
        m = pat.match(line)
        if not m:
            continue
        mo, d, h, mi, rest = m.groups()
        dt = datetime(year, int(mo), int(d), int(h), int(mi))
        if dt > datetime.now() + timedelta(days=1):  # 跨年：12 月的紀錄
            dt = dt.replace(year=year - 1)
        runs.append([dt, int("鎖被其他排程持有" in rest), int("push 失敗" in rest)])
    return runs


def main() -> int:
    days = 14
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    now = datetime.now()
    since = now - timedelta(days=days)
    sources = {
        "warrant_snapshot": _sectioned(
            ROOT / "data" / "warrant_snapshot_cycle.log",
            r"^===== warrant_snapshot launcher: (\S+ \S+)",
            r"拿不到 git_op_lock", r"push 失敗"),
        "disposal_flags": _sectioned(
            ROOT / "data" / "disposal_flags_cycle.log",
            r"^===== disposal_flags launcher: (\S+ \S+)",
            r"git_op_lock|LOCK_HELD|拿不到", r"push failed"),
        "dev_queue": _sectioned(
            ROOT / "dev_queue_cycle.log",
            r"^===== DevQueue cycle start: (\S+ \S+)",
            r"git_op_lock 被其他 wrapper 持有", r"push 失敗|push失敗", trailing=True),
        "marathon": _sectioned(
            ROOT / "marathon_cycle.log",
            r"^===== Marathon cycle start: (\S+ \S+)",
            r"git_op_lock 被其他 wrapper 持有", r"push 失敗|push失敗"),
        "hypothesis_queue": _sectioned(
            ROOT / "hypothesis_queue_cycle.log",
            r"^===== Hypothesis-queue cycle start: (\S+ \S+)",
            r"git_op_lock 被其他 wrapper 持有", r"push 失敗|push失敗"),
        "news_local_fallback（只算有走到提交的班次）": _news(ROOT / "news_local_fallback.log", now.year),
    }
    out = {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"), "window_days": days,
           "since": since.strftime("%Y-%m-%d %H:%M"), "launchers": {}}
    for name, runs in sources.items():
        runs = [r for r in runs if r[0] >= since]
        by_hour = defaultdict(lambda: {"runs": 0, "lock_miss": 0, "push_fail": 0})
        events = []
        for dt, lk, pf in runs:
            b = by_hour[f"{dt.hour:02d}"]
            b["runs"] += 1
            b["lock_miss"] += 1 if lk else 0
            b["push_fail"] += 1 if pf else 0
            if lk or pf:
                events.append({"start": dt.strftime("%Y-%m-%d %H:%M"),
                               "kind": "lock_miss" if lk else "push_fail"})
        n = len(runs)
        lk_n = sum(1 for r in runs if r[1])
        pf_n = sum(1 for r in runs if r[2])
        out["launchers"][name] = {
            "runs": n, "lock_miss": lk_n, "push_fail": pf_n,
            "miss_rate_pct": round(100 * (lk_n + pf_n) / n, 1) if n else None,
            "by_taipei_hour": dict(sorted(by_hour.items())), "events": events,
        }
    held = []
    for line in _read(ROOT / "git_op_lock.log"):
        if "LOCK_HELD" in line or "held" in line.lower():
            held.append(line[:19])
    out["lock_holder_log"] = {
        "path": "research/git_op_lock.log",
        "lock_held_entries": len(held), "lock_held_times": held,
        "note": "2026-11-02 先.一三五-1hu 起才記 LOCK_HELD 持有者；更早的事件無法得知持鎖者",
    }
    p = OUT_DIR / f"git_lock_contention_{now:%Y%m%d}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, v in out["launchers"].items():
        print(f"{name}: 班次 {v['runs']}、拿不到鎖 {v['lock_miss']}、push 失敗 {v['push_fail']}、落空率 {v['miss_rate_pct']}%")
    print(f"git_op_lock.log LOCK_HELD 紀錄：{len(held)} 筆")
    print(f"寫入 {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
