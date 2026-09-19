# -*- coding: utf-8 -*-
"""工廠穩定性儀表板（2026-09-16 總司令交辦【工廠四】）。

**目的**：把「工廠有沒有變好」從感覺變成可以查的數字。總司令給的起點是這兩週
（約 2026-09-01～09-15，健康帳與自走阻塞機制建立之前）的真實慘況：
4 天額度停擺、3 次重開機全停、IBKR 死 6 天、alpha.db 空轉 20 天——
「現在難看是應該的，正因為難看才該量」。

**兩個數字**：
1. **MTBF**（各管線平均無故障時間）——讀 `data/seed/pipeline_registry.json`
   每個節點的 `fault_history.event_log`（`scripts/pipeline_fault_ledger.py`
   2026-09-16 新增的故障事件時間戳陣列）。**誠實限制**：這個陣列從
   2026-09-15 才開始累積，此刻幾乎每個節點都是 0～1 筆事件，算不出真正的
   「間隔平均」（MTBF 的定義就是間隔，1 個時間點沒有間隔可言）。少於 2 筆
   一律回報「資料不足」，不得用單一次事件硬湊一個看似精確的數字。
2. **每週人工介入次數**——這裡精確定義成「`scripts/dev_queue_runner.py`
   判定需要總司令介入而在 `PENDING_QUEUE.md` 標記『⛔ 自走中止』的次數，
   依 ISO 週分組」。**這不等於「總司令實際動手介入的次數」**，只是目前
   唯一一個有精確時間戳、可稽核的系統性訊號；馬拉松／假設佇列兩條自走
   軌道目前沒有等價的阻塞標記機制，不在這個數字裡，如實揭露不是刻意
   窄化定義來讓數字好看。

**「每週記錄」怎麼做**：`data/factory_stability.json` 是每次執行都覆蓋的
最新快照（給人/儀表板看現況）；`data/factory_stability_history.jsonl`
是 append-only 的週紀錄，同一個 ISO 週只會有一筆（用「上一筆記的週別
是否等於本週」判斷要不要新增，不是每次呼叫都追加，避免同一週被 5 分鐘
一次的連通性檢查洗成幾百筆重複資料）。

用法：
    python scripts/factory_stability.py           # 印出摘要，並更新兩份輸出檔
    python scripts/factory_stability.py --json    # 只印最新快照的 JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有
# 🚫/✓(U+26D4/2713)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明——這支是排程常跑的腳本，優先修。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "seed" / "pipeline_registry.json"
QUEUE = ROOT / "PENDING_QUEUE.md"
SNAPSHOT = ROOT / "data" / "factory_stability.json"
HISTORY = ROOT / "data" / "factory_stability_history.jsonl"
TZ = timezone(timedelta(hours=8))

# 故障事件時間戳（event_log）從這一天才開始累積，見 pipeline_fault_ledger.py
# 2026-09-16 新增的說明；在這之前發生的故障只有文字記錄在 PROGRESS.md/CLAUDE.md，
# 沒有精確時間戳可回填。
FAULT_LEDGER_EPOCH = datetime(2026, 9, 15, 0, 0, 0, tzinfo=TZ)

BLOCK_PATTERN = re.compile(r"⛔\s*自走中止（(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})）")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

# 總司令 2026-09-15 交辦【工廠四】原文給的起點數字，發生在健康帳/自走阻塞
# 機制建立之前，只能人工回溯登記、無法用本系統自動量測——跟下面兩個自動
# 算出來的數字分開陳列，不混在同一個計算裡冒充同一種量測方法。
BASELINE_INCIDENTS_PRE_LEDGER = {
    "period_note": "約 2026-09-01～09-15，健康帳（工廠一）與 DevQueue 自走阻塞"
                   "標記機制建立之前，屬總司令人工回溯記錄，非本系統自動量測",
    "recorded_at": "2026-09-15",
    "source": "PENDING_QUEUE.md【工廠四】條目總司令原話",
    "items": [
        {"label": "額度停擺", "value": "4 天"},
        {"label": "重開機全停", "value": "3 次"},
        {"label": "IBKR 死線", "value": "6 天"},
        {"label": "alpha.db 空轉", "value": "20 天"},
    ],
}


def _load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def compute_pipeline_mtbf(now: datetime) -> list[dict]:
    """算每個節點的 MTBF。少於 2 筆事件一律誠實回報資料不足，不硬算。"""
    reg = _load_registry()
    out = []
    window_hours = max((now - FAULT_LEDGER_EPOCH).total_seconds() / 3600.0, 0.0)
    for p in reg.get("pipelines", []):
        fh = p.get("fault_history") or {}
        count = int(fh.get("count", 0) or 0)
        log_raw = fh.get("event_log") or []
        events = []
        for ts in log_raw:
            try:
                events.append(datetime.fromisoformat(ts))
            except ValueError:
                continue  # 壞掉的時間戳字串跳過，不讓一筆髒資料炸掉整支
        events.sort()

        row = {
            "task": p.get("task"),
            "artifact": p.get("artifact"),
            "fault_count_since_epoch": count,
        }
        if len(events) >= 2:
            gaps_hours = [
                (b - a).total_seconds() / 3600.0
                for a, b in zip(events[:-1], events[1:])
            ]
            row["mtbf_hours"] = round(sum(gaps_hours) / len(gaps_hours), 1)
            row["mtbf_basis"] = f"近 {len(events)} 筆故障事件時間間隔平均（{len(gaps_hours)} 個間隔）"
        elif count >= 1:
            row["mtbf_hours"] = None
            row["mtbf_basis"] = (
                f"僅 {count} 筆故障事件（自 {FAULT_LEDGER_EPOCH.date().isoformat()} 健康帳"
                f"建立起累積 {window_hours:.0f} 小時），MTBF 定義為間隔平均，1 筆事件沒有"
                f"間隔可算，不強算——資料不足"
            )
        else:
            row["mtbf_hours"] = None
            row["mtbf_basis"] = "資料不足：尚無故障事件"
        out.append(row)
    return out


def compute_weekly_devqueue_blocks() -> list[dict]:
    """從 PENDING_QUEUE.md 掃『⛔ 自走中止（日期 時間）』，依 ISO 週分組計數。

    見本檔開頭說明：這是「系統判定需要總司令介入」的次數，不是「總司令實際
    介入」的次數；目前只有 DevQueue 有這個標記機制。
    """
    text = QUEUE.read_text(encoding="utf-8")
    weeks: dict[tuple[int, int], list[datetime]] = {}
    for m in BLOCK_PATTERN.finditer(text):
        dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
        iso_year, iso_week, _ = dt.isocalendar()
        weeks.setdefault((iso_year, iso_week), []).append(dt)

    out = []
    for (iso_year, iso_week), stamps in sorted(weeks.items()):
        week_start = datetime.fromisocalendar(iso_year, iso_week, 1)
        week_end = week_start + timedelta(days=6)
        out.append({
            "iso_week": f"{iso_year}-W{iso_week:02d}",
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "devqueue_block_count": len(stamps),
        })
    return out


def build_snapshot(now: datetime) -> dict:
    return {
        "generated_at": now.isoformat(),
        "methodology_note": (
            "MTBF：以 data/seed/pipeline_registry.json 各節點 fault_history.event_log"
            "（2026-09-16 新增，2026-09-15 起累積）算故障事件間隔平均，需要至少 2 筆"
            "事件才回報數字，否則誠實標「資料不足」。每週人工介入次數：以"
            "PENDING_QUEUE.md 內『⛔ 自走中止』標記（scripts/dev_queue_runner.py "
            "block 產生）的時間戳依 ISO 週分組計數，只涵蓋 DevQueue 一條自走軌道。"
        ),
        "limits_note": (
            "1) 故障事件時間戳只從 2026-09-15 起累積，累積週期不夠長之前 MTBF 大多"
            "是「資料不足」，這是誠實現況不是程式錯誤。"
            "2) 每週人工介入次數只計 DevQueue 的阻塞標記，馬拉松／假設佇列兩條自走"
            "軌道目前沒有等價機制，未計入，會低估真正的介入頻率。"
            "3) baseline_incidents_pre_ledger 是總司令人工回溯登記的兩週前起點數字，"
            "跟上面兩個自動計算的數字不是同一種量測方法，不可直接相減比較「進步多少」。"
        ),
        "baseline_incidents_pre_ledger": BASELINE_INCIDENTS_PRE_LEDGER,
        "pipeline_mtbf": compute_pipeline_mtbf(now),
        "weekly_devqueue_blocks": compute_weekly_devqueue_blocks(),
    }


def _current_iso_week(now: datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def maybe_append_weekly_history(now: datetime, snapshot: dict) -> bool:
    """同一個 ISO 週只留一筆，之後每次呼叫覆蓋『本週那一筆』直到週別換了才新增。

    這樣本週的數字每次執行都會是最新的（例如週中新增一次阻塞），但歷史檔
    不會被 5 分鐘一次的連通性檢查洗成上百筆重複列。
    """
    rows = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 壞掉的舊行跳過，不讓歷史檔卡死

    this_week = _current_iso_week(now)
    entry = {
        "iso_week": this_week,
        "recorded_at": now.isoformat(),
        "pipeline_mtbf": snapshot["pipeline_mtbf"],
        "weekly_devqueue_blocks_to_date": snapshot["weekly_devqueue_blocks"],
    }
    if rows and rows[-1].get("iso_week") == this_week:
        rows[-1] = entry
        changed_kind = "更新本週既有列"
    else:
        rows.append(entry)
        changed_kind = "新增一筆新週別"

    HISTORY.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    return changed_kind == "新增一筆新週別"


def run(now: datetime) -> dict:
    """給 check_external_connectivity.py 呼叫的入口：更新兩份輸出檔。"""
    snapshot = build_snapshot(now)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    maybe_append_weekly_history(now, snapshot)
    return snapshot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    now = datetime.now(TZ)
    snapshot = run(now)

    if a.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=1))
        return 0

    print("=" * 78)
    print(f"  工廠穩定性儀表板　{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)
    print("  [MTBF] 各管線節點：")
    for row in snapshot["pipeline_mtbf"]:
        if row["mtbf_hours"] is not None:
            print(f"    ✓ {row['task']:<20}{row['artifact']:<44}"
                  f"MTBF={row['mtbf_hours']} 小時（{row['mtbf_basis']}）")
        else:
            print(f"    － {row['task']:<20}{row['artifact']:<44}{row['mtbf_basis']}")
    print()
    print("  [每週 DevQueue 自走阻塞次數]（只計 DevQueue，見 limits_note）：")
    if snapshot["weekly_devqueue_blocks"]:
        for w in snapshot["weekly_devqueue_blocks"]:
            print(f"    {w['iso_week']}（{w['week_start']}~{w['week_end']}）：{w['devqueue_block_count']} 次")
    else:
        print("    （目前沒有任何 ⛔ 自走中止 紀錄）")
    print()
    print(f"  快照：{SNAPSHOT.relative_to(ROOT)}")
    print(f"  週歷史：{HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
