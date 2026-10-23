# -*- coding: utf-8 -*-
"""先.八十一-13（2026-10-13）：台股／美股休市日改讀官方日曆檔 data/trading_calendar.json。

- 台股：TWSE 官方「市場開休市日期」https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear=YYYY
  （與 auto_rebalance_bb90.py／backfill_price_history_gaps.py 同一端點、同一判定：名稱含「開始交易日」「最後交易日」者
  為交易日，其餘列出者休市）。**已知地雷**：查詢尚未公布的年份（例如 2026-10 查 2027）時，官方不報錯、直接回傳
  「當年度」的表（title 為「115 年市場開休市日期」）——所以一定要核對 title 的民國年，不符就當作尚未公布。
- 美股：NYSE 沒有開放 API，依官方頁 https://www.nyse.com/markets/hours-calendars 抄錄（全日休市；2026-10-13 查證，
  頁面列到 2027 年）。提早收盤（半日市）不列入休市。
頻率：每日 3 班 market.yml 各跑一次，但同一年度 7 天內抓過就不再問（每週約 1～2 次請求）；另每日 1 次 FMTQIK
當月確認臨時休市（先.一三二-10b，見 confirm_recent_closure）。官方未公布上限；
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
# 先.八十一-48：事前公布的休市表不含颱風等臨時停市（實例：2026-07-10 全天沒有交易，休市表沒列）。
# 對「已過去的月份」用 FMTQIK（市場成交資訊，每月一次請求）取實際交易日，平日卻沒有交易、又不在休市表的日子，記為 unscheduled_closed。
FMTQIK_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
NYSE_URL = "https://www.nyse.com/markets/hours-calendars"
US_CLOSED = {  # NYSE 官方頁抄錄（2026-10-13 查證）
    "2026": ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
             "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"],
    "2027": ["2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
             "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"],
}
REFRESH_DAYS = 7
# 先.一三二-10b（2026-10-24，收件匣 020 B4 採丙的「收盤後正式確認」半邊）：颱風當天臨時休市原本要等 7 天快取過期才記得到。
# 改成每天另問 1 次 FMTQIK（目標日所在月份），目標日＝台北 17:00 以後是今天、之前是昨天；同一目標日只問一次（每日約 +1 次）。
# 目標日是「今天」時，FMTQIK 可能還沒更新當天，所以另要求官方報價檔 data/quotes_tw.json 的資料日期全部早於今天（零請求），
# 兩邊一致才寫進 unscheduled_closed；不一致只印告警、不寫。
DAILY_CONFIRM_HOUR = 17
QUOTES_TW = REPO_ROOT / "data" / "quotes_tw.json"
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


def _fmtqik_traded(year: int, month: int) -> set | None:
    """FMTQIK 單月實際交易日；stat 非 OK 回 None。402/403/428/429 拋錯不重試。"""
    r = requests.get(FMTQIK_URL, params={"date": f"{year}{month:02d}01", "response": "json"}, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"})
    if r.status_code in (402, 403, 428, 429):
        raise RuntimeError(f"FMTQIK HTTP {r.status_code}（不重試）")
    j = r.json()
    if j.get("stat") != "OK":
        return None
    traded = set()
    for row in j.get("data") or []:
        ry, rm, rd = [int(x) for x in str(row[0]).strip().split("/")]
        traded.add(f"{ry + 1911}-{rm:02d}-{rd:02d}")
    return traded


def _official_quotes_all_before(day) -> bool | None:
    """官方報價檔每檔 date 是否全部早於 day（零請求）；讀不到或沒有資料回 None。"""
    try:
        q = json.loads(QUOTES_TW.read_text(encoding="utf-8")).get("quotes") or {}
        dates = {str(v.get("date") or "") for v in q.values() if isinstance(v, dict)} - {""}
    except (OSError, ValueError, AttributeError):
        return None
    if not dates:
        return None
    return max(dates) < day.strftime("%Y%m%d")


def confirm_recent_closure(tw: dict, now) -> None:
    """每日一次確認目標日所在月份有沒有臨時休市（見 DAILY_CONFIRM_HOUR 註解）。自身失敗只警告、保留既有。"""
    from datetime import date as _d, timedelta as _td
    target = now.date() if now.hour >= DAILY_CONFIRM_HOUR else now.date() - _td(days=1)
    ycur = tw.get(str(target.year))
    if not ycur or not ycur.get("published"):
        return
    if (ycur.get("daily_confirm_through") or "") >= target.isoformat():
        return
    closed = set(ycur.get("closed") or [])
    try:
        traded = _fmtqik_traded(target.year, target.month)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 每日臨時休市確認 FMTQIK 失敗，保留既有：{type(e).__name__}: {e}")
        return
    if traded is None:
        print("[warn] 每日臨時休市確認 FMTQIK 回傳非 OK，保留既有")
        return
    un = set(ycur.get("unscheduled_closed") or [])
    d = _d(target.year, target.month, 1)
    while d <= target:
        iso = d.isoformat()
        if d.weekday() < 5 and iso not in closed and iso not in traded:
            if d == now.date():
                quotes_before = _official_quotes_all_before(d)
                if quotes_before:
                    un.add(iso)
                else:
                    print(f"[warn] {iso} FMTQIK 沒有成交、但官方報價檔不是全部早於今天（{quotes_before}），"
                          f"可能 FMTQIK 尚未更新，不寫入；下一個目標日會再確認")
                    target = d - _td(days=1)  # 今天沒確認完，不把確認進度推到今天
            else:
                un.add(iso)
        d += _td(days=1)
    ycur["unscheduled_closed"] = sorted(un)
    ycur["unscheduled_source"] = ("TWSE FMTQIK 市場成交資訊（已過去月份的實際交易日；"
                                  "當月每日收盤後確認，當天另需官方報價檔資料日期佐證）")
    ycur["daily_confirm_through"] = max(target.isoformat(), ycur.get("daily_confirm_through") or "")
    ycur["daily_confirm_checked_at"] = now.isoformat(timespec="seconds")


def fetch_unscheduled(year: int, closed: set, today) -> list | None:
    """已過去的每個月各一次 FMTQIK，回傳該年「平日、不在休市表、但 FMTQIK 沒有交易」的日期。任一月失敗回 None（保留既有）。"""
    import time as _t
    from datetime import date as _d, timedelta as _td
    out, last = [], 0.0
    for m in range(1, 13):
        if (year, m) > (today.year, today.month):
            break
        w = 3.0 - (_t.time() - last)
        if w > 0:
            _t.sleep(w)
        last = _t.time()
        r = requests.get(FMTQIK_URL, params={"date": f"{year}{m:02d}01", "response": "json"}, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"})
        if r.status_code in (402, 403, 428, 429):
            raise RuntimeError(f"FMTQIK HTTP {r.status_code}（不重試）")
        j = r.json()
        if j.get("stat") != "OK":
            return None
        traded = set()
        for row in j.get("data") or []:
            ry, rm, rd = [int(x) for x in str(row[0]).strip().split("/")]
            traded.add(f"{ry + 1911}-{rm:02d}-{rd:02d}")
        d = _d(year, m, 1)
        while d.month == m and d < today:
            iso = d.isoformat()
            if d.weekday() < 5 and iso not in closed and iso not in traded:
                out.append(iso)
            d += _td(days=1)
    return out


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
            try:
                un = fetch_unscheduled(y, set(closed), now.date()) if y <= now.year else []
                if un is not None:
                    tw[str(y)]["unscheduled_closed"] = un
                    tw[str(y)]["unscheduled_source"] = "TWSE FMTQIK 市場成交資訊（已過去月份的實際交易日）"
            except Exception as e:  # noqa: BLE001
                print(f"[warn] {y} 臨時停市查證失敗，保留既有：{type(e).__name__}: {e}")
                if cur.get("unscheduled_closed") is not None:
                    tw[str(y)]["unscheduled_closed"] = cur["unscheduled_closed"]
    try:
        confirm_recent_closure(tw, now)
    except Exception as e:  # noqa: BLE001 — 守門自身失敗只降級成警告（十二節）
        print(f"[warn] 每日臨時休市確認失敗，保留既有：{type(e).__name__}: {e}")
    out = {"generated_at": now.isoformat(timespec="seconds"),
           "note": "休市日（全日不交易）；週末不列。台股來自 TWSE 官方日曆端點；美股依 NYSE 官方頁抄錄。",
           "tw": tw,
           "us": {y: {"closed": d, "published": True, "source": NYSE_URL, "transcribed_at": "2026-10-13"} for y, d in US_CLOSED.items()}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("trading_calendar：" + "；".join(f"台股{y} {'已公布 ' + str(len(v['closed'])) + ' 日' if v.get('published') else '尚未公布'}" for y, v in sorted(tw.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
