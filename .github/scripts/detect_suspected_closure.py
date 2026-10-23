# -*- coding: utf-8 -*-
"""先.一三二-10b（2026-10-24，收件匣 020 B4 採丙的「盤中止血」半邊）：零請求判斷「今天疑似臨時休市」。

颱風等臨時休市，事前公布的休市表沒有、FMTQIK 要收盤後才確認（見 fetch_trading_calendar.py confirm_recent_closure）。
盤中先用既有官方報價檔 data/quotes_tw.json 判斷：台北 09:30 以後、報價檔是 30 分鐘內抓的、但每一檔的資料日期都還早於今天
→ 寫 data/trading_calendar.json 的 tw[年].suspected_closed_today（附 source）。

- **不寫 unscheduled_closed**：官方報價源當機也會長這樣，所以只放另一欄，供讀日曆的程式「暫停告警／暫停空跑」用；
  正式休市只由收盤後 FMTQIK 確認寫入。
- 報價檔之後出現今天的日期（真的有開盤）→ 清掉當天的 suspected_closed_today。
- 零外部請求；自身失敗只印警告、永遠 exit 0（十二節：守門員失敗不得中斷被監控的流程）。
用法：python .github/scripts/detect_suspected_closure.py
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAL = REPO_ROOT / "data" / "trading_calendar.json"
QUOTES_TW = REPO_ROOT / "data" / "quotes_tw.json"
TW = timezone(timedelta(hours=8))
START_HHMM = (9, 30)
MAX_QUOTES_AGE_MIN = 30
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def judge(cal: dict, quotes: dict, now: datetime) -> str:
    """回傳 'suspected'／'open'／'skip'，並就地更新 cal。"""
    today = now.date()
    ycur = (cal.get("tw") or {}).get(str(today.year))
    if not ycur or today.weekday() >= 5 or (now.hour, now.minute) < START_HHMM:
        return "skip"
    iso = today.isoformat()
    if iso in set(ycur.get("closed") or []) | set(ycur.get("unscheduled_closed") or []):
        return "skip"  # 已知休市，不用猜
    try:
        fetched = datetime.fromisoformat(str(quotes.get("fetched_at")))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=TW)
    except (TypeError, ValueError):
        return "skip"
    if now - fetched > timedelta(minutes=MAX_QUOTES_AGE_MIN):
        return "skip"  # 報價檔本身舊了，判不出來
    dates = {str(v.get("date") or "") for v in (quotes.get("quotes") or {}).values() if isinstance(v, dict)} - {""}
    if not dates:
        return "skip"
    ymd = today.strftime("%Y%m%d")
    if max(dates) < ymd:
        ycur["suspected_closed_today"] = {
            "date": iso, "detected_at": now.isoformat(timespec="seconds"),
            "source": f"data/quotes_tw.json（{quotes.get('fetched_at')} 抓）{len(quotes.get('quotes') or {})} 檔資料日期全部 ≤ {max(dates)}",
            "note": "疑似臨時休市（零請求推測，非官方確認）；只供暫停告警／空跑，正式休市以收盤後 FMTQIK 寫入 unscheduled_closed 為準",
        }
        return "suspected"
    s = ycur.get("suspected_closed_today")
    if isinstance(s, dict) and s.get("date") == iso:
        ycur.pop("suspected_closed_today", None)
    return "open"


def main() -> int:
    try:
        now = datetime.now(TW)
        cal = json.loads(CAL.read_text(encoding="utf-8"))
        quotes = json.loads(QUOTES_TW.read_text(encoding="utf-8"))
        before = json.dumps(cal, ensure_ascii=False, sort_keys=True)
        verdict = judge(cal, quotes, now)
        if json.dumps(cal, ensure_ascii=False, sort_keys=True) != before:
            CAL.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"detect_suspected_closure：{verdict}")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 疑似休市判斷失敗，略過（不影響報價流程）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
