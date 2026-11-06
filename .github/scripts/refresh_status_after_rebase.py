# -*- coding: utf-8 -*-
"""market.yml rebase 衝突把 data/STATUS.json 取 main 版本後，重算檔案新鮮度（先.一三五-1lu，純 bug 修復）。

背景：先.一三五-1kd-a 甲讓 rebase 衝突時共用追蹤檔（含 STATUS.json）取 main 的版本。main 上那份常是
local_schedule_watchdog.yml 一分鐘前寫的——它重算 data_files 時，本班剛抓好的資料還沒進 main，
所以會把本班剛更新的檔標 stale（2026-11-06 01:52Z 實例：insider_transfer_tw_history／us_index_close_history
實際 01:51Z 已更新，STATUS 卻標 stale，any_overdue=true，直到下一次 watchdog 或 market 提交才消失）。

做法：rebase 完成後（工作目錄＝main＋本班資料），只重算「只讀 repo 內資料檔、不連網」的欄位：
data_files／data_files_checked_at／schedule_health／any_overdue，並重產 status_lite.json。
不重跑整支 generate_status_json.py（那會再打 GitHub API，未帶 token 時每小時 60 次的額度會被吃兩倍）。

守門員規則（CLAUDE.md 十二節）：任何失敗只印 ::warning:: 並 exit 0，不擋 push 迴圈。
自測：scripts/selftest_refresh_status_after_rebase.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "data" / "STATUS.json"
TW = timezone(timedelta(hours=8))


def refresh(status_path: Path = STATUS, g=None, now: datetime | None = None, lite=None) -> bool:
    """回傳 True＝有寫檔。g／lite 可注入（自測用），預設 import generate_status_json／build_status_lite.write_status_lite。"""
    try:
        doc = json.loads(status_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("STATUS.json 不是物件")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::refresh_status_after_rebase 讀不到 STATUS.json，略過：{type(e).__name__}: {e}")
        return False
    if g is None:
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            import generate_status_json as g  # noqa: PLW0127
        except Exception as e:  # noqa: BLE001
            print(f"::warning::refresh_status_after_rebase import generate_status_json 失敗，略過：{type(e).__name__}: {e}")
            return False
    now = now or datetime.now(timezone.utc)
    changed = False
    try:
        doc["data_files"] = g.build_data_files()
        doc["data_files_checked_at"] = now.astimezone(TW).isoformat()
        changed = True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::data_files 重算失敗，保留 main 版本：{type(e).__name__}: {e}")
    try:
        sh = g.build_schedule_health()
        doc["schedule_health"] = sh
        doc["any_overdue"] = bool(sh.get("any_overdue"))
        changed = True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::schedule_health 重算失敗，保留 main 版本：{type(e).__name__}: {e}")
    if not changed:
        return False
    try:
        tmp = status_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        tmp.replace(status_path)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::refresh_status_after_rebase 寫檔失敗：{type(e).__name__}: {e}")
        return False
    try:
        if lite is None:
            if str(ROOT / "scripts") not in sys.path:
                sys.path.insert(0, str(ROOT / "scripts"))
            from build_status_lite import write_status_lite as lite  # 同 generate_status_json 的用法
        lite(status_path)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::status_lite 重產失敗（STATUS.json 已更新）：{type(e).__name__}: {e}")
    stale = [x.get("path") for x in doc.get("data_files", []) if isinstance(x, dict) and x.get("status") == "stale"]
    print(f"refresh_status_after_rebase：已重算 data_files（stale {len(stale)} 檔）、any_overdue={doc.get('any_overdue')}")
    return True


if __name__ == "__main__":
    try:
        refresh()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::refresh_status_after_rebase 未預期錯誤：{type(e).__name__}: {e}")
    sys.exit(0)
