# -*- coding: utf-8 -*-
"""本機管線新鮮度判定（2026-09-10 停擺四）。

**為什麼要有這支**：`alpha.db` 從 2026-08-21 起沒有再進過任何一筆資料，
整整 20 天沒人發現。事後檢討，缺的不是某一個修正，是**一張清單**——
我們從來沒有「本機有哪些管線、每一條最後一次真正產出是什麼時候」的完整表。

這支只做一件事：讀 `data/seed/pipeline_registry.json`，逐條算出「最後產出時間」
與「是否停擺」。它是**共用函式庫**，兩個地方都呼叫它：

  * `scripts/pipeline_inventory.py`         —— 印給人看的清點表
  * `scripts/check_external_connectivity.py` —— 每 5 分鐘的自動告警

兩邊讀同一份登錄檔、走同一套判定，才不會出現「表上有、自檢沒監控」的漏洞
（總司令 2026-09-10 指示停擺四.3）。

**mtime 與資料層時間戳的差別是這支的核心**：
mtime 只證明「檔案被寫過」，不證明「內容是新的」。
`alpha.db` 每天都被連線寫入所以 mtime 天天更新，但 `daily_price` 的
`max(date)` 停在 8/21——這正是靜默停擺的典型形狀。
所以凡是檔案內部帶有日期／時間戳的，一律看資料層的值。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "seed" / "pipeline_registry.json"
TZ = timezone(timedelta(hours=8))


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _resolve(rel: str) -> Path:
    """登錄檔裡的路徑可以是 repo 相對路徑，也可以是絕對路徑（alpha.db 在 repo 外）。"""
    p = Path(rel)
    return p if p.is_absolute() else ROOT / rel


def _parse_ts(v) -> datetime | None:
    """把各種寫法的時間戳轉成帶時區的 datetime。

    容忍三種格式：ISO 帶時區、ISO 不帶時區（當成台北時間）、
    以及 `20260821` 這種純日期字串（TAIFEX 那張表用的）。
    無法解析就回 None，讓呼叫端標成 unknown——**不要猜**。
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.isdigit() and len(s) == 8:
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


def _dig(doc, path: str):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _last_output(spec: dict, f: Path) -> tuple[datetime | None, str]:
    """回傳 (最後產出時間, 這個時間是怎麼來的)。"""
    kind = spec.get("freshness", "mtime")
    if kind == "mtime":
        return datetime.fromtimestamp(f.stat().st_mtime, TZ), "檔案修改時間"
    if kind == "json_field":
        doc = json.loads(f.read_text(encoding="utf-8"))
        field = spec["field"]
        return _parse_ts(_dig(doc, field)), f"JSON 欄位 {field}"
    if kind == "jsonl_last_field":
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            return None, "JSONL 為空"
        field = spec["field"]
        return _parse_ts(_dig(json.loads(lines[-1]), field)), f"JSONL 末筆 {field}"
    if kind == "sqlite_max_date":
        # 唯讀開啟：這支是監測器，絕不能碰到被監測的資料庫
        con = sqlite3.connect(f"file:{f.as_posix()}?mode=ro", uri=True)
        try:
            best, detail = None, []
            for t in spec.get("tables", []):
                row = con.execute(
                    f'select max("{t["column"]}") from "{t["table"]}"').fetchone()
                dt = _parse_ts(row[0] if row else None)
                detail.append(f'{t["table"]}={row[0] if row else None}')
                # 取**最新**的那一張表：只要有一張還在進資料，就不算整條管線死了
                if dt and (best is None or dt > best):
                    best = dt
            return best, "各表 max(date)：" + "、".join(detail)
        finally:
            con.close()
    return None, f"未知的 freshness 類型 {kind}"


def evaluate(now: datetime | None = None) -> tuple[list[dict], list[str]]:
    """逐條算出狀態，回傳 (每條的結果, 停擺告警文字)。

    每一條各自 try：這支是監測器，**監測器死掉比被監測的東西死掉更糟**，
    單條出錯只標成 unknown，不影響其他條。
    """
    reg = load_registry()
    now = now or datetime.now(TZ)
    factor = reg.get("stall_factor", 3)
    rows: list[dict] = []
    stalled: list[str] = []

    for spec in reg.get("pipelines", []):
        row = {
            "task": spec["task"],
            "purpose": spec.get("purpose", ""),
            "artifact": spec["artifact"],
            "expected_interval_min": spec["interval_min"],
            "freshness": spec.get("freshness", "mtime"),
        }
        try:
            win = spec.get("window_hours")
            if win and not (win[0] <= now.hour < win[1]):
                row.update(status="skipped",
                           reason=f"觀察窗 {win[0]}:00-{win[1]}:00 之外，沒產出是正常的")
                rows.append(row)
                continue
            f = _resolve(spec["artifact"])
            if not f.exists():
                row.update(status="missing", reason="產出檔不存在")
                stalled.append(f'{spec["task"]}：產出檔 {spec["artifact"]} 不存在')
                rows.append(row)
                continue
            last, how = _last_output(spec, f)
            row["source"] = how
            if last is None:
                row.update(status="unknown", reason=f"讀不到時間戳（{how}）")
                rows.append(row)
                continue
            age = (now - last).total_seconds() / 60.0
            limit = spec["interval_min"] * factor
            row.update(last_output=last.isoformat(), age_min=round(age, 1),
                       stall_limit_min=limit,
                       status="stalled" if age > limit else "ok")
            if age > limit:
                stalled.append(
                    f'{spec["task"]}：{spec["artifact"]} 已 {age:.0f} 分鐘沒有新產出'
                    f'（預期每 {spec["interval_min"]} 分鐘，門檻 {limit} 分鐘；{how}）')
        except Exception as e:  # noqa: BLE001
            row.update(status="unknown", reason=f"{type(e).__name__}: {e}")
        rows.append(row)
    return rows, stalled
