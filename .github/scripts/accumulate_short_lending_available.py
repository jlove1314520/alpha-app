# -*- coding: utf-8 -*-
"""可融券賣出餘額逐檔逐日累積器（稽核.三B組第3類之二，2026-09-29總司令
裁示【驗.八】一）。

背景：`fetch_short_lending_available.py` 每天只覆寫 `data/short_
lending_available.json` 的「最新一天」快照（TWSE SBL/TWT96U「上市可
融券賣出參數」＋ TPEx 對應上櫃清單），前一天的數字不會保留。本腳本
**不額外打任何 TWSE/TPEx 請求**（零成本），只讀當次管線已經抓好的
`data/short_lending_available.json`，把逐檔資料併入一份逐檔逐日的
歷史檔 `data/short_lending_available_history.json`，沿用
`accumulate_foreign_holding.py`／`accumulate_margin_by_stock.py`／
`accumulate_securities_lending_sell.py` 已驗證過的「讀回上次 JSON →
併入今天 → 去重 → 存緊湊陣列格式」慣例。

來源檔每檔只有單一數字（可融券賣出參數股數，非借券餘額變動明細），
twse／otc 各自獨立清單（見來源檔 `note`：可能重疊或不同一批代碼）。

**日期來源**：來源檔本身沒有交易日期欄位（只有 `fetched_at` ISO時間戳，
是抓取時間不是資料所屬交易日），跟另兩支累積器不同——這支改用
`fetched_at` 的日期部分當鍵，並在 `meta` 誠實註記「此為抓取日期，
非官方公告的資料所屬交易日（來源端未提供），可能與實際生效日期有
1個交易日內的落差」，不假裝比實際掌握的精確度更高。

**2026-10-30 先.一三五-1bt 更正（純 bug 修復）**：上面「用 fetched_at 日期部分當鍵」實測錯位。
`fetched_at` 是 UTC；git 歷史 9/15～10/30 共 95 份快照顯示 TWT96U 是**收盤後、隔天凌晨 01:00～07:55
（台北）之間**換成下一個交易時段的「當日可借券賣出股數」（週六凌晨、國定假日早上也會換；
休市沒有收盤就不換，10/23 颱風休市＋10/26 休市期間數字一直是 10/22 收盤後那份）。
舊做法把 05:43 班（UTC 前一天）抓到的新數字記在前一天、蓋掉前一天的真值，週末還多出鍵。
改為 `date_key_for()`，鍵＝這份數字適用的**交易時段日（台北）**——跟官方「當日」同義，
也避免把凌晨才公布的數字當成前一天收盤就知道（前視）：
- 台北 09:00 之後抓 → 台北當天起算的第一個交易日（週六抓 → 下週一）；
- 台北 00:00～00:59 抓 → 還沒換，等於前一天 09:00 後看到的那份＝前一天起算的第一個交易日
  （10/10 週六 00:11 抓的是 10/09 假日早上換的、適用 10/12 那份；直接取「前一個交易日」會跟 10/08 衝突）；
- 台北 01:00～08:59 抓 → 不確定換了沒，不記。
交易日依 `data/trading_calendar.json`（週末＋closed＋unscheduled_closed）。
歷史檔由 `scripts/rebuild_short_lending_history.py` 用 git 歷史快照依同規則重建（零外部請求）。

**刻意保留 `short_lending_available.json` 本身不變**（單日快照語意不動）。

**格式選擇：不設滾動視窗上限**（[自行裁量]，理由同前三支累積器）。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "data" / "short_lending_available.json"
OUT = ROOT / "data" / "short_lending_available_history.json"
CALENDAR = ROOT / "data" / "trading_calendar.json"
TPE = timezone(timedelta(hours=8))
MIN_TPE_HOUR = 9       # 官方凌晨換下一時段的數字（實測最晚 07:55 已換）；09:00 後一定是新的
PRE_PUBLISH_HOUR = 1   # 00:00～00:59 實測一定還沒換
DATE_KEY_CAVEAT = ("鍵為這份數字適用的台北交易時段日（官方「當日」；收盤後隔天凌晨才公布，"
                   "台北 09:00 後抓記當天起第一個交易日、00:00～00:59 抓記前一天起第一個交易日、01:00～08:59 抓不記；"
                   "先.一三五-1bt）。來源端沒有交易日欄位。")


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _load_prior(p: Path):
    """既有累積檔：不存在 → {}（首跑）；存在但讀不到／不是 JSON 物件 → None，呼叫端中止、不覆蓋（先.一三五-1bg）。"""
    if not p.exists():
        return {}
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


def _tw_closed(cal: dict, d: date) -> bool:
    if d.weekday() >= 5:
        return True
    yr = ((cal.get("tw") or {}).get(str(d.year)) or {})
    iso = d.isoformat()
    return iso in (yr.get("closed") or []) or iso in (yr.get("unscheduled_closed") or [])


def _shift_trading(cal: dict, d: date, step: int, include_self: bool):
    cur = d if include_self else d + timedelta(days=step)
    for _ in range(30):
        if not _tw_closed(cal, cur):
            return cur
        cur += timedelta(days=step)
    return None


def date_key_for(fetched_at: str, cal: dict):
    """回 (YYYYMMDD 或 None, 原因)：這份快照適用的台北交易時段日（先.一三五-1bt）。"""
    try:
        t = datetime.fromisoformat(str(fetched_at))
    except ValueError:
        return None, "fetched_at 格式不對"
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    tpe = t.astimezone(TPE)
    if tpe.hour >= MIN_TPE_HOUR:
        d = _shift_trading(cal, tpe.date(), +1, include_self=True)
    elif tpe.hour < PRE_PUBLISH_HOUR:
        d = _shift_trading(cal, tpe.date() - timedelta(days=1), +1, include_self=True)
    else:
        return None, f"台北 {tpe:%m-%d %H:%M} 抓（{PRE_PUBLISH_HOUR:02d}:00～{MIN_TPE_HOUR:02d}:00 官方換數字的時段，不確定換了沒）"
    if d is None:
        return None, "前後 30 天找不到交易日"
    return d.strftime("%Y%m%d"), ""


def _accumulate(prior_series: dict, snap_map: dict, date_key: str) -> tuple[dict, int]:
    series: dict[str, dict[str, float]] = {code: dict(rows) for code, rows in prior_series.items() if isinstance(rows, dict)}
    added = 0
    for code, val in snap_map.items():
        if val is None:
            continue
        bucket = series.setdefault(code, {})
        if date_key not in bucket:
            added += 1
        bucket[date_key] = val
    return series, added


def main() -> int:
    snap = _load(SNAPSHOT, {})
    twse_map = snap.get("twse") or {}
    otc_map = snap.get("otc") or {}
    if not twse_map and not otc_map:
        print("! short_lending_available.json 沒有 twse/otc 資料，中止（不寫出空檔覆蓋既有累積）")
        return 1

    fetched_at = str(snap.get("fetched_at") or "")
    if not fetched_at:
        print("! short_lending_available.json 缺 fetched_at，中止")
        return 1
    date_key, why = date_key_for(fetched_at, _load(CALENDAR, {}))
    if date_key is None:
        print(f"- 略過不記：{why}（先.一三五-1bt）")
        return 0

    prior = _load_prior(OUT)
    if prior is None:
        print(f"! {OUT.name} 存在但讀不到或不是 JSON 物件，中止（不覆蓋既有累積，先.一三五-1bg）")
        return 1
    twse_series, twse_added = _accumulate(dict(prior.get("series_twse") or {}), twse_map, date_key)
    otc_series, otc_added = _accumulate(dict(prior.get("series_otc") or {}), otc_map, date_key)

    twse_dates = sorted({d for b in twse_series.values() for d in b})
    otc_dates = sorted({d for b in otc_series.values() for d in b})
    doc = {
        "meta": {
            "generated_at": fetched_at,
            "source": "data/short_lending_available.json（每日管線既有 TWSE SBL/TWT96U 呼叫，"
                      "本腳本零額外請求）",
            "date_key_caveat": DATE_KEY_CAVEAT,
            "twse_dates_available": len(twse_dates), "twse_date_range": [twse_dates[0], twse_dates[-1]] if twse_dates else None,
            "otc_dates_available": len(otc_dates), "otc_date_range": [otc_dates[0], otc_dates[-1]] if otc_dates else None,
            "twse_stocks": len(twse_series), "otc_stocks": len(otc_series),
            "unit": "可融券賣出參數股數（單一數字，非明細）",
            "note": "往前累積不設滾動視窗上限；short_lending_available.json本身維持單日快照"
                    "語意不變，既有讀取者不受影響。",
        },
        "series_twse": twse_series,
        "series_otc": otc_series,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"short_lending_available_history.json：TWSE {len(twse_series)}檔×{len(twse_dates)}日"
          f"（新增{twse_added}）、OTC {len(otc_series)}檔×{len(otc_dates)}日（新增{otc_added}），{size_mb:.2f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
