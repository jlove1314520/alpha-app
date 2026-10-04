# -*- coding: utf-8 -*-
"""先.十四-一：彙整單一 launcher 本輪結果到 research/data/claude_launcher_heartbeat.json。

只做檔案讀寫，不判斷「算不算異常」——異常判斷留給雲端的
scripts/check_local_schedule_heartbeat.py（彙整全部 launcher、寫進 data/STATUS.json，
那支才有能力「3小時沒有任何一筆實際執行」這種跨輪次的時間窗判斷）。

research/data/ 整個目錄被 .gitignore 蓋住，所以寫檔後呼叫端的 PS1 wrapper 必須
`git add -f` 這個檔案才會真的進 repo、被雲端的 workflow checkout 讀到——這點
跟 research/data/paper_supply_v2_log.jsonl 的既有做法（同一支 wrapper 已經在
force-add 自己的 append-only log）是同一套模式。

用法：
  python scripts/update_claude_launcher_heartbeat.py <launcher> <cycle_id> <reason> [<detail>]

<reason> 其中一種：OK／ERROR／TIMEOUT／QUEUE_EMPTY／BLOCKED_BY_RULE／
QUEUE_FORMAT_MISMATCH／QUEUE_ORDER_MARKER_AMBIGUOUS／PROMPT_ERROR／LAUNCH_ERROR／
AUTH_EXPIRED／QUOTA_EXCEEDED／UNKNOWN
（AUTH_EXPIRED／QUOTA_EXCEEDED 是 wrapper 呼叫 claude_auth_classifier.py 分類過
 ERROR/TIMEOUT 之後才會傳進來的「升級版」reason，其餘沿用各 wrapper 既有的 $reason 原文。）

「實際執行」的定義（供 3 小時無執行告警用）：reason 不在 NO_ATTEMPT_REASONS 集合
裡就算一次「嘗試執行」，更新 last_attempt_at；reason=="OK" 另外更新 last_ok_at。
QUEUE_EMPTY／BLOCKED_BY_RULE 這類「這一輪本來就不該做事」的狀態不算嘗試，
否則會把「佇列真的空了」誤判成「停擺」（跟 CLAUDE.md 零之一節的節流/交辦分開判斷
是同一個精神：不能把「沒事做」跟「想做卻做不了」混為一談）。

任何寫檔例外都不得往外拋，寫入端（PS1 wrapper）靠這支的 exit code 判斷成功與否，
但即使失敗也只降級、不中斷 wrapper 既有流程（CLAUDE.md 十二節）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

PATH = Path(__file__).resolve().parent.parent / "research" / "data" / "claude_launcher_heartbeat.json"
NO_ATTEMPT_REASONS = {
    "QUEUE_EMPTY", "BLOCKED_BY_RULE", "QUEUE_FORMAT_MISMATCH", "QUEUE_ORDER_MARKER_AMBIGUOUS",
}


def _load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- 壞檔/不存在都視為空白重建，不拋例外
        return {}


def _save(d: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PATH)


def record(launcher: str, cycle_id: str, reason: str, detail: str = "") -> dict:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    d = _load()
    rec = d.get(launcher, {})
    rec["last_cycle_id"] = cycle_id
    rec["last_reason"] = reason
    rec["last_detail"] = detail[:300]
    rec["last_checked_at"] = now
    if reason not in NO_ATTEMPT_REASONS:
        rec["last_attempt_at"] = now
    if reason == "OK":
        rec["last_ok_at"] = now
    d[launcher] = rec
    _save(d)
    return rec


def main() -> int:
    if len(sys.argv) < 4:
        print("用法：python update_claude_launcher_heartbeat.py <launcher> <cycle_id> <reason> [<detail>]",
              file=sys.stderr)
        return 2
    launcher, cycle_id, reason = sys.argv[1], sys.argv[2], sys.argv[3]
    detail = sys.argv[4] if len(sys.argv) > 4 else ""
    try:
        out = record(launcher, cycle_id, reason, detail)
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001 -- 不得讓呼叫端的 launcher 因為心跳記錄失敗而中斷
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
