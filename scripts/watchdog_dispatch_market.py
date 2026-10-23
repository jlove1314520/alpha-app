# -*- coding: utf-8 -*-
"""先.一〇三-18（2026-10-16 總司令裁示）：雲端 watchdog 在台北 17:45 後發現當天 market_tw 還沒落地，就觸發 market.yml。

為什麼放在 local_schedule_watchdog.yml：GitHub 排程常被跳過（10/15 market.yml 17:13 主班與 18:41 補救班都沒觸發，
靠本機 22:00 才補上）。本機也可能停擺（10/15 重開機未登入），所以雲端要有自己的補救。

觸發條件（全部成立才觸發，任一不成立就只印原因、exit 0）：
1. 台北時間 17:45～23:59。
2. 今天是台股交易日（data/trading_calendar.json；讀不到就照週一～五判斷）。
3. 已 checkout 的 data/market_tw.json 的 data_date 不是今天。
4. market.yml 沒有排隊／執行中的 run，且今天還沒有由本腳本觸發過（看今天 workflow_dispatch 的 run 數；同一天最多觸發 1 次，避免每 30 分鐘重打官方端點）。

權杖：用 workflow 自帶的 GITHUB_TOKEN（GitHub 文件：workflow_dispatch 由 GITHUB_TOKEN 觸發仍會建立新 run），
workflow 需 `permissions: actions: write`。不需要總司令另外建立 token。
market.yml 收到 reason=watchdog_tw_catchup 時跳過「內部人持股轉讓」步驟（先.九十五-3 核准每日 2 次請求，不因補救而加倍）。

十二節：本腳本自身任何例外只印 ::warning:: 並 exit 0，不讓 watchdog 的停擺判定一起失敗。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
START_HM = (17, 45)
REASON = "watchdog_tw_catchup"


def _suspected_today(y: dict, d) -> set:
    """先.一三二-10b：盤中零請求判的「今天疑似臨時休市」（detect_suspected_closure.py）也當休市；
    只認 date＝今天（台北）且收盤確認沒有記成「疑似卻有成交」的。"""
    iso = d.isoformat()
    s, m = y.get("suspected_closed_today"), y.get("suspected_closed_mismatch")
    if isinstance(s, dict) and s.get("date") == iso == datetime.now(TW).date().isoformat()             and not (isinstance(m, dict) and m.get("date") == iso):
        return {iso}
    return set()


def is_trading_day(d) -> bool:
    if d.weekday() >= 5:
        return False
    try:
        cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
        y = (cal.get("tw") or {}).get(str(d.year)) or {}
        closed = set(y.get("closed") or []) | set(y.get("unscheduled_closed") or []) | _suspected_today(y, d)
        return d.isoformat() not in closed
    except Exception as e:  # noqa: BLE001 -- 讀不到日曆照平日判斷（多觸發一次無害，漏補才有害）
        print(f"::warning::trading_calendar 讀取失敗，照平日判斷：{type(e).__name__}: {e}")
        return True


def market_runs() -> list[dict]:
    r = subprocess.run(["gh", "run", "list", "--workflow=market.yml", "-L", "20", "--json", "status,createdAt,event,databaseId"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode:
        raise RuntimeError(f"gh run list 失敗：{r.stderr.strip()[:200]}")
    return json.loads(r.stdout or "[]")


def decide(now: datetime, data_date: str | None, runs: list[dict]) -> tuple[bool, str]:
    today = now.date()
    if (now.hour, now.minute) < START_HM:
        return False, f"未到 {START_HM[0]}:{START_HM[1]:02d}"
    if not is_trading_day(today):
        return False, f"{today} 非交易日"
    if data_date == today.isoformat():
        return False, f"market_tw 已落地（data_date={data_date}）"
    day_start_utc = datetime(today.year, today.month, today.day, tzinfo=TW).astimezone(timezone.utc)
    for run in runs:
        if run.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
            return False, f"market.yml 已有 run {run.get('databaseId')} 狀態 {run.get('status')}"
    dispatched_today = [r for r in runs if r.get("event") == "workflow_dispatch"
                        and datetime.fromisoformat(str(r.get("createdAt")).replace("Z", "+00:00")) >= day_start_utc]
    if dispatched_today:
        return False, f"今天已手動／補救觸發過 {len(dispatched_today)} 次，不重複"
    return True, f"market_tw data_date={data_date}，今天 {today} 未落地"


def main() -> int:
    try:
        now = datetime.now(TW)
        try:
            data_date = json.loads((ROOT / "data" / "market_tw.json").read_text(encoding="utf-8")).get("data_date")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::market_tw.json 讀取失敗：{type(e).__name__}: {e}")
            data_date = None
        ok, why = decide(now, data_date, market_runs() if (now.hour, now.minute) >= START_HM else [])
        print(f"watchdog_dispatch_market：{'觸發' if ok else '不觸發'}（{why}）")
        if ok:
            r = subprocess.run(["gh", "workflow", "run", "market.yml", "-f", f"reason={REASON}"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if r.returncode:
                print(f"::warning::觸發 market.yml 失敗：{r.stderr.strip()[:300]}")
            else:
                print(f"::notice::已觸發 market.yml（reason={REASON}）：{why}")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::watchdog_dispatch_market 自身失敗（不影響停擺判定）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
