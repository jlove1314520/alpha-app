# -*- coding: utf-8 -*-
"""先.一三五-1kh-e2 自測：pipeline_freshness 的 check=fallback_ratio（雲端停擺被本機備援遮住）。

情境：①jsonl 高補抓比例 → stalled ②低比例 → ok ③檔案不存在 → skipped（不判停擺）
④log 格式高比例 → stalled ⑤樣本不足 → skipped ⑥壞正規式 → evaluate() 只標 unknown、不崩潰（十二節）
零外部請求，只寫暫存目錄。"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_freshness as pf  # noqa: E402

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 5, 12, 30, tzinfo=TZ)
BASE = {"interval_min": 10, "check": "fallback_ratio", "min_samples_per_day": 6,
        "consecutive_days": 2, "ratio_threshold": 0.4, "max_age_days": 5}


def jsonl(path: Path, per_day: dict) -> None:
    rows = []
    for day, (f, s) in per_day.items():
        for i in range(f + s):
            rows.append({"ts": f"{day}T{9 + i // 6:02d}:{(i % 6) * 10:02d}:00+08:00",
                         "decision": "fetched" if i < f else "skip_cloud_fresh"})
        rows.append({"ts": f"{day}T23:00:00+08:00", "decision": "us_skip_outside_window"})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def run(tmp: Path, specs: list[dict]) -> dict:
    reg = {"stall_factor": 3, "pipelines": specs}
    orig_load, orig_resolve = pf.load_registry, pf._resolve
    pf.load_registry = lambda: reg
    pf._resolve = lambda rel: tmp / rel
    try:
        rows, _ = pf.evaluate(NOW)
    finally:
        pf.load_registry, pf._resolve = orig_load, orig_resolve
    return {r["task"]: r for r in rows}


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        jsonl(tmp / "hi.jsonl", {"2026-11-04": (15, 14), "2026-11-05": (11, 8)})
        jsonl(tmp / "lo.jsonl", {"2026-11-04": (1, 28), "2026-11-05": (15, 14)})
        jsonl(tmp / "few.jsonl", {"2026-11-05": (5, 0)})
        (tmp / "n.log").write_text("".join(
            f"[11-0{4 + k // 20} {k % 20:02d}:05] 雲端 news.json 61 分鐘沒更新 → 本機補班\n" if k % 2 == 0
            else f"[11-0{4 + k // 20} {k % 20:02d}:35] 雲端 news.json 30 分鐘前更新，不需補班\n"
            for k in range(40)), encoding="utf-8")
        log_spec = {"format": "log", "fetched_regex": r"沒更新 → 本機補班", "skip_regex": r"前更新，不需補班"}
        rows = run(tmp, [
            {**BASE, "task": "hi", "artifact": "hi.jsonl", "format": "jsonl"},
            {**BASE, "task": "lo", "artifact": "lo.jsonl", "format": "jsonl"},
            {**BASE, "task": "missing", "artifact": "none.jsonl", "format": "jsonl"},
            {**BASE, "task": "log", "artifact": "n.log", **log_spec},
            {**BASE, "task": "few", "artifact": "few.jsonl", "format": "jsonl"},
            {**BASE, "task": "badre", "artifact": "n.log", **log_spec, "fetched_regex": "([壞"},
        ])
    expect = {"hi": "stalled", "lo": "ok", "missing": "skipped", "log": "stalled", "few": "skipped", "badre": "unknown"}
    for k, want in expect.items():
        got = rows.get(k, {}).get("status")
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {k}: 期望 {want}、實得 {got}（{rows.get(k, {}).get('reason')}）")
    print("全部通過" if ok else "有失敗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
