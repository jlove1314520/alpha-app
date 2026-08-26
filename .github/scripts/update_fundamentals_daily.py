# -*- coding: utf-8 -*-
"""每日（排程）更新 data/fundamentals.json 的月營收/PER/PBR/殖利率快照，累積式寫回。

背景（2026-08-27）：`research/build_fundamentals_json.py` 產生的 `data/fundamentals.json`
是**手動一次性快照**——讀本機 `research/data/raw/` 底下的 FinMind parquet 快取整理
而成，但那份快取是 gitignored（`.gitignore`: `research/data/`），只存在互動 session
的本機，GitHub Actions runner 每次都是全新 checkout、拿不到，**不能把
`build_fundamentals_json.py` 原封不動掛進排程**（掛了也只會產出幾乎全空的檔案）。

這支腳本改用官方 TWSE openapi 的「最新一期全市場快照」端點（不需要 FinMind、
不需要本機快取），採跟 `fetch_market_tw.py` 的 `institutional_history` 一樣的
**累積式**寫法：讀 repo 裡已經 commit 的 `data/fundamentals.json`（起始種子是
2026-08-27 那次手動全量快照，已有 1749 檔 8 個月歷史）當底，每次執行只把「今天
的最新一筆」merge 進去（同年月覆蓋、新年月則 append 並捨棄超過 8 個月的舊資料），
跑得越久歷史就越完整，不需要一次補歷史區間。

資料源（全部官方開放資料，不需要金鑰，實測見 `research/DATA.md` 第474行附近）：
- 月營收：`openapi.twse.com.tw/v1/opendata/t187ap05_L`——全市場最新一期月營收快照，
  官方已經算好「去年同月增減(%)」，不需要自己拿前期資料做除法。
- 本益比/殖利率/淨值比：`openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`——全市場
  最新一期 PER/PBR/殖利率快照。

**已知限制，誠實揭露**：這兩個端點只涵蓋 TWSE 上市股票，不含 TPEx 上櫃股票——
上櫃股票的月營收/PER只能維持用 2026-08-27 那次手動快照的舊資料，不會被這支腳本
更新（跟`build_fundamentals_json.py`docstring提過的限制是同一類問題，這裡不重複
解一次，範圍內誠實記錄即可）。
"""
from __future__ import annotations

import json
import sys
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "fundamentals.json"
TW_TZ = timezone(timedelta(hours=8))

REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
RATIOS_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"

MONTHS_TO_KEEP = 8


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    """'1150825'（民國年3碼+月2碼+日2碼）-> '2026-08-25'。格式不符就回傳 None，不猜。"""
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def _roc_yearmonth(s: str) -> tuple[int, int] | None:
    """'11507'（民國年3碼+月2碼）-> (2026, 7)。"""
    s = str(s).strip()
    if len(s) != 5 or not s.isdigit():
        return None
    return int(s[:3]) + 1911, int(s[3:5])


def fetch_ratios() -> dict[str, dict]:
    r = requests.get(RATIOS_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("BWIBBU_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("Code")
        if not code:
            continue
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        out[code] = {
            "date": date_iso,
            "per": _num(row.get("PEratio")),
            "pbr": _num(row.get("PBratio")),
            "dividend_yield": _num(row.get("DividendYield")),
        }
    return out


def fetch_revenue() -> dict[str, dict]:
    r = requests.get(REVENUE_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap05_L 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("公司代號")
        ym = _roc_yearmonth(row.get("資料年月", ""))
        revenue_thousand = _num(row.get("營業收入-當月營收"))
        if not code or not ym or revenue_thousand is None:
            continue
        yoy_pct = _num(row.get("營業收入-去年同月增減(%)"))
        out[code] = {
            "year": ym[0],
            "month": ym[1],
            # TWSE官方單位是「仟元」，既有資料（來自FinMind parquet快取整理）是原始
            # 新台幣元，這裡乘1000對齊，否則前端圖表(/1e8換算成億)會整整差1000倍
            # ——實測驗證過：不轉換的話2330 2026/7會顯示成4.68億而不是正確的4676億。
            "revenue": revenue_thousand * 1000,
            "yoy": round(yoy_pct / 100, 4) if yoy_pct is not None else None,
        }
    return out


def merge_revenue(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = list(existing or [])
    rows = [r for r in rows if not (r.get("year") == latest["year"] and r.get("month") == latest["month"])]
    rows.append(latest)
    rows.sort(key=lambda r: (r["year"], r["month"]))
    return rows[-MONTHS_TO_KEEP:]


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在——這支腳本設計上只做累積更新，"
              "第一次的完整快照要用 research/build_fundamentals_json.py 手動產生並 commit。")
        sys.exit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    fundamentals = payload.setdefault("fundamentals", {})

    errors = []
    ratios_updated = revenue_updated = 0

    try:
        ratios = fetch_ratios()
        for code, r in ratios.items():
            fundamentals.setdefault(code, {})["ratios"] = r
        ratios_updated = len(ratios)
    except Exception as e:
        print(f"PER/PBR/殖利率 更新失敗：{e}")
        errors.append(f"ratios: {e}")

    try:
        revenue = fetch_revenue()
        for code, latest in revenue.items():
            entry = fundamentals.setdefault(code, {})
            entry["month_revenue"] = merge_revenue(entry.get("month_revenue"), latest)
        revenue_updated = len(revenue)
    except Exception as e:
        print(f"月營收 更新失敗：{e}")
        errors.append(f"revenue: {e}")

    payload["meta"] = {
        "generated_at": datetime.now(TW_TZ).isoformat(),
        "snapshot_note": (
            "起始種子是 2026-08-27 手動執行 build_fundamentals_json.py 的一次性快照"
            "（讀研究端FinMind歷史parquet快取整理，涵蓋TWSE+TPEx），此後由這支"
            "update_fundamentals_daily.py 排程改用TWSE官方openapi累積更新——"
            "月營收/PER/PBR/殖利率每次只更新TWSE官方端點回傳的「最新一期」，"
            "同年月覆蓋、新年月append且只保留近8個月。TPEx上櫃股票的月營收/PER"
            "官方端點無對應公開資料，維持沿用手動快照的舊值，不會被這支腳本更新。"
        ),
        "ratios_updated_count": ratios_updated,
        "revenue_updated_count": revenue_updated,
        "errors": errors,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：PER/PBR/殖利率更新 {ratios_updated} 檔，月營收更新 {revenue_updated} 檔"
          f"（合計 {len(fundamentals)} 檔有資料）")
    if errors:
        print(f"部分失敗（不中止，維持既有資料）：{errors}")


if __name__ == "__main__":
    main()
