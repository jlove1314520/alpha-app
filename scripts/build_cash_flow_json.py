# -*- coding: utf-8 -*-
"""台股現金流量表／自由現金流（FCF）摘要 → data/cash_flow.json（常備.開發-7，2026-10-11）。

資料來源：FinMind `TaiwanStockCashFlowsStatement`，**只讀本機研究快取**
（research/data/raw/TaiwanStockCashFlowsStatement__{code}__*__latest.parquet，
由 research/backfill_cashflow_gap.py 等研究腳本抓取，gitignore），本腳本
**不發出任何網路請求**，不額外消耗 FinMind 額度。

為什麼不是官方源：TWSE／TPEx openapi swagger（2026-10-11 重新下載比對，143＋225
路徑）沒有任何現金流量表端點；MOPS t164sb04 有反爬阻擋（見
.github/scripts/update_stock_financials.py 檔頭）。三路查證紀錄見
docs/DATA_SOURCE_MAP.md「現金流量表／FCF」一節。

為什麼不在 GitHub Actions 跑：快取只在本機（gitignore），且現金流量表一季才變一次；
Actions 端若逐檔打 FinMind（約 1,900 檔）會超過免費層每小時數百次的上限。
所以這支是**每季手動跑一次**（財報公布後研究快取更新時），輸出檔帶 as_of，
App 端照實顯示資料季別。

計算：FinMind 現金流量表為**年初至今累計數**。
  TTM ＝ 最新累計 ＋ 上一年度全年 − 上一年度同季累計（最新為 Q4 時 TTM＝全年）
  營業現金流 CFO ＝ CashFlowsFromOperatingActivities（營業活動之淨現金流入（流出））
  資本支出 CAPEX ＝ PropertyAndPlantAndEquipment（取得不動產、廠房及設備，負值）
  FCF ＝ CFO ＋ CAPEX
缺任一必要季度就不算（寧可空，不湊數），並記錄原因分類。
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "data" / "raw"
OUT = ROOT / "data" / "cash_flow.json"
CFO, CAPEX = "CashFlowsFromOperatingActivities", "PropertyAndPlantAndEquipment"
TW = timezone(timedelta(hours=8))


def ttm(cum: dict, key: str, latest: str):
    """cum: {date: {type: value}}；latest: 'YYYY-MM-DD'。回傳 TTM 或 None。"""
    y, md = latest[:4], latest[5:]
    cur = (cum.get(latest) or {}).get(key)
    if cur is None:
        return None
    if md == "12-31":
        return cur
    prev_annual = (cum.get(f"{int(y) - 1}-12-31") or {}).get(key)
    prev_same = (cum.get(f"{int(y) - 1}-{md}") or {}).get(key)
    if prev_annual is None or prev_same is None:
        return None
    return cur + prev_annual - prev_same


def main() -> int:
    files = sorted(glob.glob(str(RAW / "TaiwanStockCashFlowsStatement__*__latest.parquet")))
    stocks, why = {}, Counter()
    for f in files:
        code = Path(f).name.split("__")[1]
        try:
            d = pd.read_parquet(f, columns=["date", "type", "value"])
        except Exception:
            why["快取檔讀取失敗"] += 1
            continue
        d = d[d["type"].isin([CFO, CAPEX])]
        if d.empty:
            why["無營業現金流／資本支出欄位"] += 1
            continue
        cum = {}
        for r in d.itertuples(index=False):
            cum.setdefault(str(r.date)[:10], {})[r.type] = float(r.value)
        latest = max(k for k, v in cum.items() if CFO in v)
        cfo = ttm(cum, CFO, latest)
        capex = ttm(cum, CAPEX, latest)
        if cfo is None:
            why["缺上一年度同季或全年累計，無法算 TTM"] += 1
            continue
        stocks[code] = {
            "as_of": latest,
            "cfo_ttm": round(cfo),
            "capex_ttm": round(capex) if capex is not None else None,
            "fcf_ttm": round(cfo + capex) if capex is not None else None,
        }
    asof = Counter(v["as_of"] for v in stocks.values())
    out = {
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "source": "FinMind TaiwanStockCashFlowsStatement（本機研究快取，非官方；TWSE／TPEx openapi 無現金流量表端點）",
        "method": "TTM＝最新累計＋上年全年−上年同季累計；FCF＝營業活動淨現金流＋取得不動產廠房及設備（負值）；單位：新台幣元",
        "refresh": "每季財報公布、研究快取更新後手動執行 python scripts/build_cash_flow_json.py；不在 GitHub Actions 排程",
        "as_of_counts": dict(asof.most_common(6)),
        "skipped": dict(why),
        "count": len(stocks),
        "stocks": stocks,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[ok] data/cash_flow.json：{len(stocks)} 檔；最新季分布 {dict(asof.most_common(4))}；略過 {dict(why)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
