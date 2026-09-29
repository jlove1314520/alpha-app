# -*- coding: utf-8 -*-
"""借券賣出逐檔逐日累積器（稽核.三B組第3類之一，2026-09-29總司令裁示【驗.八】一）。

背景：`fetch_securities_lending_sell.py` 每天只覆寫 `data/securities_
lending_sell.json` 的「最新一天」快照（TWSE 借券賣出 TWT93U ＋ TPEx
借券賣出／融券賣出），前一天的數字不會保留。本腳本**不額外打任何
TWSE/TPEx 請求**（零成本），只讀當次管線已經抓好的 `data/securities_
lending_sell.json`，把逐檔資料併入一份逐檔逐日的歷史檔 `data/
securities_lending_sell_history.json`，沿用 `accumulate_foreign_
holding.py`／`accumulate_margin_by_stock.py` 已驗證過的「讀回上次 JSON
→ 併入今天 → 去重 → 存緊湊陣列格式」慣例，第三次套用同一套慣例。

**TWSE／TPEx 欄位不同，分開存**（不用同一個 schema 硬湊）：
- TWSE：`sbl_prev_balance`／`sbl_sell`／`sbl_return`／`sbl_adjust`／
  `sbl_balance`／`sbl_next_day_quota`（借券餘額變動與次一營業日可用餘額）。
- TPEx：`sbl_sell_volume`／`sbl_sell_amount`／`short_sale_volume`／
  `short_sale_amount`（借券賣出量／值＋融券賣出量／值，跟TWSE語意不同，
  見來源檔 `note`：TPEx只有「上櫃融資融券當日成交量與成交值」，非TWSE
  的「餘額變動」）。

**刻意保留 `securities_lending_sell.json` 本身不變**（單日快照語意不動），
累積需求改用本腳本輸出的獨立檔案滿足。

**日期來源**：來源檔本身已有 `twse_date`（西元YYYYMMDD）與 `tpex_date`
（民國年格式，例如"1150924"=民國115年09月24日=2026-09-24），分別轉換
後各自當該交易所那組資料的鍵，不用同一個日期字串套兩個交易所（借券
賣出兩邊實際發布日期可能不同步，混用會製造假象的同步）。

**格式選擇：不設滾動視窗上限**（[自行裁量]，理由同前兩支累積器）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "data" / "securities_lending_sell.json"
OUT = ROOT / "data" / "securities_lending_sell_history.json"

TWSE_FIELDS = ["sbl_prev_balance", "sbl_sell", "sbl_return", "sbl_adjust", "sbl_balance", "sbl_next_day_quota"]
TPEX_FIELDS = ["sbl_sell_volume", "sbl_sell_amount", "short_sale_volume", "short_sale_amount"]


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _roc_to_iso_compact(roc: str) -> str | None:
    """"1150924" -> "20260924"（民國年+115=西元年，其餘月日照抄）。"""
    if not roc or len(roc) not in (6, 7):
        return None
    try:
        roc_year = int(roc[:-4])
        rest = roc[-4:]
        return f"{roc_year + 1911}{rest}"
    except ValueError:
        return None


def _accumulate(prior_series: dict, snap_map: dict, fields: list[str], date_key: str) -> tuple[dict, int]:
    series: dict[str, dict[str, list]] = {code: dict(rows) for code, rows in prior_series.items() if isinstance(rows, dict)}
    added = 0
    for code, rec in snap_map.items():
        if not isinstance(rec, dict):
            continue
        vals = [rec.get(f) for f in fields]
        if all(v is None for v in vals):
            continue
        bucket = series.setdefault(code, {})
        if date_key not in bucket:
            added += 1
        bucket[date_key] = vals
    return series, added


def main() -> int:
    snap = _load(SNAPSHOT, {})
    twse_map = snap.get("twse") or {}
    tpex_map = snap.get("tpex") or {}
    if not twse_map and not tpex_map:
        print("! securities_lending_sell.json 沒有 twse/tpex 資料，中止（不寫出空檔覆蓋既有累積）")
        return 1

    twse_date = str(snap.get("twse_date") or "")
    tpex_date = _roc_to_iso_compact(str(snap.get("tpex_date") or ""))

    prior = _load(OUT, {})
    twse_added = tpex_added = 0
    twse_series: dict = dict(prior.get("series_twse") or {})
    tpex_series: dict = dict(prior.get("series_tpex") or {})

    if twse_map and len(twse_date) == 8:
        twse_series, twse_added = _accumulate(twse_series, twse_map, TWSE_FIELDS, twse_date)
    if tpex_map and tpex_date:
        tpex_series, tpex_added = _accumulate(tpex_series, tpex_map, TPEX_FIELDS, tpex_date)

    twse_dates = sorted({d for b in twse_series.values() for d in b})
    tpex_dates = sorted({d for b in tpex_series.values() for d in b})
    doc = {
        "meta": {
            "generated_at": snap.get("fetched_at"),
            "source": "data/securities_lending_sell.json（每日管線既有 TWSE TWT93U／TPEx "
                      "tpex_short_sell 呼叫，本腳本零額外請求）",
            "twse_dates_available": len(twse_dates), "twse_date_range": [twse_dates[0], twse_dates[-1]] if twse_dates else None,
            "tpex_dates_available": len(tpex_dates), "tpex_date_range": [tpex_dates[0], tpex_dates[-1]] if tpex_dates else None,
            "twse_stocks": len(twse_series), "tpex_stocks": len(tpex_series),
            "twse_fields": TWSE_FIELDS, "tpex_fields": TPEX_FIELDS,
            "note": "TWSE/TPEx欄位語意不同，分開存，不硬湊同一schema；往前累積不設滾動視窗上限；"
                    "securities_lending_sell.json本身維持單日快照語意不變，既有讀取者不受影響。",
        },
        "series_twse": twse_series,
        "series_tpex": tpex_series,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1e6
    print(f"securities_lending_sell_history.json：TWSE {len(twse_series)}檔×{len(twse_dates)}日"
          f"（新增{twse_added}）、TPEx {len(tpex_series)}檔×{len(tpex_dates)}日（新增{tpex_added}），{size_mb:.2f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
