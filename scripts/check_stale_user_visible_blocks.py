# -*- coding: utf-8 -*-
"""掃 PENDING_QUEUE.md，抓「已知阻塞但影響使用者可見資料」超過3個交易日
沒處理的項目（2026-09-15 總司令裁示【防重演】）。

**為什麼要這支**：稽核.六（sparklines.json凍結）的根因，早在「零」條目
2026-08-27~09-05那次完成記錄裡，就已經誠實寫過「⚠ market.yml的新步驟
留在working tree（PAT無workflow scope）」——這件事本身已知，但因為只是
一句話埋在一個已勾選完成的舊條目裡，沒有任何機制會主動提醒任何人回頭看，
一停就是10天，直到總司令自己發現App在顯示過期資料才被抓到。這支腳本
就是把「已知阻塞但影響使用者可見資料」這件事，從「埋在文字裡希望有人
記得」變成「機器主動算天數、超過門檻就亮燈」。

**判定依據**：PENDING_QUEUE.md裡凡是標記`⛔`阻塞且緊跟著`【使用者可見】`
這個明確標籤的行，視為本檢查的監控對象——**這是刻意的opt-in設計**，不是
掃描全部阻塞項（那樣會把大量「阻塞但只影響研究內部、使用者感覺不到」的
項目也算進來，稀釋掉真正該急的訊號）。標記方式：在原有的
`⛔ 自走中止（YYYY-MM-DD HH:MM）` 或總司令自己標的阻塞時間戳之後，
加一段`【使用者可見】`文字，本腳本用正則抓這個組合。

**交易日計算**：跟`index.html::isTradingDay()`同一套台股交易日概念
（週末不算），這裡獨立用Python的`datetime.weekday()`判斷週末，**不含
國定假日**（跟前端TW_HOLIDAYS_2026那份維護在不同語言，這裡先用簡化版
只排週末，理由：3個交易日的門檻本身就有一定緩衝，週末以外的國定假日
一年只有十幾天，漏算一兩天不影響「已經拖了超過3個交易日」這個量級的
判斷；若之後這個簡化造成誤判，再考慮把假日表也搬一份到Python端）。

用法：`python scripts/check_stale_user_visible_blocks.py`
回傳 exit 0（無告警）或 1（有告警，同時印出清單）；
`get_alerts()`給其他腳本（`check_external_connectivity.py`）import 用。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有⚠
# (U+26A0)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明——這支自己也是個守門員，優先修。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
PENDING_QUEUE = ROOT / "PENDING_QUEUE.md"
TZ = timezone(timedelta(hours=8))
STALE_TRADING_DAYS_THRESHOLD = 3

# 抓「⛔ ...（YYYY-MM-DD ...）...【使用者可見】」——時間戳在前、標籤在後，
# 中間允許任意字元（阻塞理由的文字），但限制在同一行內，避免跨行誤配對。
PATTERN = re.compile(r"⛔[^\n]*?（(\d{4}-\d{2}-\d{2})[^）]*）[^\n]*?【使用者可見】")


def _trading_days_since(date_str: str, now: datetime | None = None) -> int:
    """date_str（YYYY-MM-DD）到「今天」之間經過幾個交易日（只排週末，見檔頭說明）。"""
    y, m, d = (int(x) for x in date_str.split("-"))
    start = datetime(y, m, d, tzinfo=TZ)
    end = now or datetime.now(TZ)
    n = 0
    cursor = start + timedelta(days=1)
    while cursor.date() <= end.date():
        if cursor.weekday() < 5:  # 0~4 = 週一~週五
            n += 1
        cursor += timedelta(days=1)
    return n


def get_alerts() -> list[tuple[str, int]]:
    """回傳 [(該行文字前80字, 已拖過幾個交易日), ...]，只含超過門檻的。"""
    if not PENDING_QUEUE.exists():
        return []
    text = PENDING_QUEUE.read_text(encoding="utf-8")
    alerts = []
    for line in text.splitlines():
        m = PATTERN.search(line)
        if not m:
            continue
        days = _trading_days_since(m.group(1))
        if days > STALE_TRADING_DAYS_THRESHOLD:
            alerts.append((line.strip()[:80], days))
    return alerts


def main() -> int:
    alerts = get_alerts()
    if not alerts:
        print("PENDING_QUEUE.md 裡沒有【使用者可見】標記的阻塞項超過"
              f"{STALE_TRADING_DAYS_THRESHOLD}個交易日")
        return 0
    print(f"⚠ {len(alerts)} 項【使用者可見】標記的阻塞已超過"
          f"{STALE_TRADING_DAYS_THRESHOLD}個交易日未處理：")
    for text, days in alerts:
        print(f"  [{days}個交易日] {text}…")
    return 1


if __name__ == "__main__":
    sys.exit(main())
