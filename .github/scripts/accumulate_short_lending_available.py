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

**刻意保留 `short_lending_available.json` 本身不變**（單日快照語意不動）。

**格式選擇：不設滾動視窗上限**（[自行裁量]，理由同前三支累積器）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "data" / "short_lending_available.json"
OUT = ROOT / "data" / "short_lending_available_history.json"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


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
    date_key = fetched_at[:10].replace("-", "")
    if len(date_key) != 8:
        print("! short_lending_available.json 缺 fetched_at，中止")
        return 1

    prior = _load(OUT, {})
    twse_series, twse_added = _accumulate(dict(prior.get("series_twse") or {}), twse_map, date_key)
    otc_series, otc_added = _accumulate(dict(prior.get("series_otc") or {}), otc_map, date_key)

    twse_dates = sorted({d for b in twse_series.values() for d in b})
    otc_dates = sorted({d for b in otc_series.values() for d in b})
    doc = {
        "meta": {
            "generated_at": fetched_at,
            "source": "data/short_lending_available.json（每日管線既有 TWSE SBL/TWT96U 呼叫，"
                      "本腳本零額外請求）",
            "date_key_caveat": "鍵為抓取日期(fetched_at)，非官方公告的資料所屬交易日"
                               "（來源端未提供交易日欄位），可能與實際生效日期有1個交易日內落差",
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
