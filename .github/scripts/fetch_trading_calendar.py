# -*- coding: utf-8 -*-
"""先.八十一-13（2026-10-13）：台股／美股休市日改讀官方日曆檔 data/trading_calendar.json。

- 台股：TWSE 官方「市場開休市日期」https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear=YYYY
  （與 auto_rebalance_bb90.py／backfill_price_history_gaps.py 同一端點、同一判定：名稱含「開始交易日」「最後交易日」者
  為交易日，其餘列出者休市）。**已知地雷**：查詢尚未公布的年份（例如 2026-10 查 2027）時，官方不報錯、直接回傳
  「當年度」的表（title 為「115 年市場開休市日期」）——所以一定要核對 title 的民國年，不符就當作尚未公布。
- 美股：NYSE 沒有開放 API，依官方頁 https://www.nyse.com/markets/hours-calendars 抄錄（全日休市；2026-10-13 查證，
  頁面列到 2027 年）。提早收盤（半日市）不列入休市。
頻率：每日 3 班 market.yml 各跑一次，但同一年度 7 天內抓過就不再問（每週約 1～2 次請求），官方未公布上限；
402/403/428/429 不重試。抓不到就保留既有內容。用法：python .github/scripts/fetch_trading_calendar.py
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data" / "trading_calendar.json"
TW_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear={y}"
NYSE_URL = "https://www.nyse.com/markets/hours-calendars"
US_CLOSED = {  # NYSE 官方頁抄錄（2026-10-13 查證）
    "2026": ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
             "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"],
    "2027": ["2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
             "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"],
}
REFRESH_DAYS = 7
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fetch_tw(year: int) -> list | None:
    """回傳休市日清單；官方尚未公布該年度（title 民國年不符）回 None。"""
    r = requests.get(TW_URL.format(y=year), timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"})
    if r.status_code in (402, 403, 428, 429):
        raise RuntimeError(f"HTTP {r.status_code}（不重試）")
    r.raise_for_status()
    doc = r.json()
    m = re.search(r"(\d{2,3})\s*年", str(doc.get("title") or ""))
    if doc.get("stat") != "ok" or not doc.get("data") or not m:
        raise RuntimeError("TWSE holidaySchedule 回傳異常")
    if int(m.group(1)) + 1911 != year:
        return None
    return sorted({row[0] for row in doc["data"] if not ("開始交易日" in row[1] or "最後交易日" in row[1])})


def main() -> int:
    now = datetime.now(TW)
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    tw = doc.get("tw") or {}
    for y in (now.year, now.year + 1):
        cur = tw.get(str(y)) or {}
        try:
            fresh = cur.get("checked_at") and now - datetime.fromisoformat(cur["checked_at"]) < timedelta(days=REFRESH_DAYS)
        except ValueError:
            fresh = False
        if fresh:
            continue
        try:
            closed = fetch_tw(y)
        except Exception as e:  # noqa: BLE001 — 失敗保留既有
            print(f"[warn] TWSE {y} 休市日抓取失敗，保留既有：{type(e).__name__}: {e}")
            continue
        if closed is None:
            tw[str(y)] = {"closed": cur.get("closed") or [], "published": False, "checked_at": now.isoformat(timespec="seconds"),
                          "note": f"TWSE 尚未公布 {y} 年市場開休市日期（查詢回傳的是其他年度的表），公布後排程自動補上"}
        else:
            tw[str(y)] = {"closed": closed, "published": True, "checked_at": now.isoformat(timespec="seconds"),
                          "source": TW_URL.format(y=y)}
    out = {"generated_at": now.isoformat(timespec="seconds"),
           "note": "休市日（全日不交易）；週末不列。台股來自 TWSE 官方日曆端點；美股依 NYSE 官方頁抄錄。",
           "tw": tw,
           "us": {y: {"closed": d, "published": True, "source": NYSE_URL, "transcribed_at": "2026-10-13"} for y, d in US_CLOSED.items()}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("trading_calendar：" + "；".join(f"台股{y} {'已公布 ' + str(len(v['closed'])) + ' 日' if v.get('published') else '尚未公布'}" for y, v in sorted(tw.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
