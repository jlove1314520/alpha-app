# -*- coding: utf-8 -*-
"""鏈路節點健康帳（2026-09-15 工廠一）。

**目的**：`scripts/pipeline_freshness.py` 只回答「現在健不健康」，每 5 分鐘
問一次、答完就丟掉。這支把答案**累積**下來，寫回
`data/seed/pipeline_registry.json` 的每個節點，讓「哪個節點最脆弱、哪個能拿掉」
變成可以用數據回答的問題，而不是憑印象猜。

**邊緣觸發，不是每輪都加**：一次停擺可能連續好幾小時、被 5 分鐘跑一次的
`check_external_connectivity.py` 看到幾十次。如果每次看到「狀態=stalled」
就 +1，數字會變成「停了多久」而不是「停過幾次」，兩者是完全不同的問題，
後者才是評估「這個節點可不可以拿掉」該看的東西。所以只在**狀態從
非故障（ok/skipped/unknown）變成故障（stalled/missing）的那一刻**算一次
新的故障事件；狀態延續中不重複計數。跨行程的「上一輪狀態」存在
`research/.pipeline_fault_state.json`。

**這支只做累積計數，不做「移除」判斷**：`removable` 欄位是人工判斷欄位，
這支只讀不寫，累積的 count/last_fault_at/fault_types 是給人（或未來的
判斷邏輯）看的數據，不在這支裡面自動下結論。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "seed" / "pipeline_registry.json"
STATE = ROOT / "research" / ".pipeline_fault_state.json"

# 自檢亮燈只把這兩種狀態算進 stalled 清單（見 pipeline_freshness.evaluate）
FAULT_STATUSES = {"stalled", "missing"}


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _key(row: dict) -> str:
    # task 名稱會重複（例如 AlphaShioajiQuotes 兩條），要併上 artifact 才唯一
    return f'{row.get("task", "")}::{row.get("artifact", "")}'


def update_fault_history(rows: list[dict], now: datetime) -> list[str]:
    """比對這一輪狀態與上一輪，把新發生的故障事件寫回登錄檔。

    回傳這一輪新增了哪些節點的故障事件（給呼叫端印 log 用）。
    這支自己絕不能因為寫檔失敗而讓呼叫端（監測器本體）崩潰——
    呼叫端要自己包一層 try/except，這支只負責把邏輯做對。
    """
    prev_state = _load_state()
    new_faults: list[str] = []

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_key = {f'{p.get("task", "")}::{p.get("artifact", "")}': p
              for p in reg.get("pipelines", [])}

    changed = False
    next_state = dict(prev_state)
    for row in rows:
        k = _key(row)
        status = row.get("status", "unknown")
        was_fault = prev_state.get(k) in FAULT_STATUSES
        is_fault = status in FAULT_STATUSES
        next_state[k] = status

        if is_fault and not was_fault:
            spec = by_key.get(k)
            if spec is None:
                # 登錄檔裡找不到對應節點（理論上不該發生，rows 本來就是從
                # 登錄檔算出來的）——不要猜，跳過這筆，不寫壞資料。
                continue
            fh = spec.setdefault("fault_history", {
                "count": 0, "last_fault_at": None, "fault_types": {}, "removable": None,
            })
            fh["count"] = int(fh.get("count", 0)) + 1
            fh["last_fault_at"] = now.isoformat()
            types = fh.setdefault("fault_types", {})
            types[status] = int(types.get(status, 0)) + 1
            changed = True
            new_faults.append(f'{row.get("task")}（{row.get("artifact")}）：{status}')

    if changed:
        REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if next_state != prev_state:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(next_state, ensure_ascii=False), encoding="utf-8")

    return new_faults
