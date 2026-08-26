"""一次性（可重複執行）建置 App 前端用的 data/fundamentals.json（2026-08-27）。

背景：使用者發現「個股頁」的月營收圖／財報比率(PER/PBR)仍在瀏覽器端直接呼叫
FinMind（`index.html` 的 `fm('TaiwanStockMonthRevenue',...)`／`fm('TaiwanStockPER',...)`），
FinMind 免費額度已耗盡，這兩塊在使用者手機上全部顯示連線失敗。

**跟大盤/類股/三大法人那批（`fetch_market_tw.py`）不同，這裡沒有走 GitHub Actions
排程**——理由：TWSE openapi 的月營收/財報比率端點只給「最新一期全市場快照」，
沒有歷史區間查詢（`DATA.md` 2026-08-26 條目已經實測記錄過這件事），排程腳本
沒辦法像抓大盤指數那樣直接跟官方要「這檔股票近8個月月營收」這種歷史數列。

**這裡改用一個不同、但一樣誠實的做法**：這個研究專案的 `research/data/raw/`
底下已經因為過去79輪馬拉松+本次資料源遷移，累積了大量 FinMind 歷史資料的本機
parquet 快取（月營收2096檔、PER 209檔，2026-08-27 這輪清點）——**直接讀這份
已經合法抓到、只是還沒整理成 App 格式的既有快取**，不需要對 FinMind 打任何新的
請求。這不是繞過額度限制，這些資料本來就已經在額度用盡之前抓到、快取在本機。

**已知限制，誠實揭露，不是隱藏**：
  1. 這份 `data/fundamentals.json` 是**這次執行當下的快照**，不會像
     `quotes_tw.json`/`market_tw.json` 那樣有 GitHub Actions 排程自動更新——
     之後要更新，必須有人（互動 session 或另一個有 research 快取的環境）手動
     重跑這支腳本。這點在輸出 JSON 的 `meta.snapshot_note` 裡也會註明。
  2. 只涵蓋「這次執行時，本機快取剛好有資料」的股票，不是全市場——覆蓋率取決於
     過去馬拉松實際抓過哪些代碼，不是由這支腳本控制。
  3. PER/PBR 只給「快取裡最新一筆」，不是即時報價當下的本益比。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_PATH = Path(__file__).parent.parent / "data" / "fundamentals.json"

MONTHS_TO_KEEP = 13  # 留13個月才能算出最近一個月的YoY(需要去年同月)


def _codes_from_cache(dataset: str) -> set[str]:
    pattern = re.compile(rf"^{dataset}__([^_]+(?:_[^_]+)*?)__\d")
    codes = set()
    for p in RAW_DIR.glob(f"{dataset}__*.parquet"):
        m = re.match(rf"^{dataset}__(.+?)__\d{{4}}-\d{{2}}-\d{{2}}", p.name)
        if m:
            codes.add(m.group(1))
    return codes


def _load_concat(dataset: str, code: str) -> pd.DataFrame:
    """同一檔代號可能因為不同時間點的不同抓取範圍而有多個快取檔，全部讀進來
    concat + 去重（同一天/同一年月只留一筆），不假設只有一個檔案。"""
    frames = []
    for p in RAW_DIR.glob(f"{dataset}__{code}__*.parquet"):
        try:
            df = pd.read_parquet(p)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_month_revenue(code: str) -> list[dict] | None:
    df = _load_concat("TaiwanStockMonthRevenue", code)
    if df.empty or "revenue" not in df.columns:
        return None
    df = df.drop_duplicates(subset=["revenue_year", "revenue_month"], keep="last")
    df = df.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    if len(df) < 2:
        return None
    df = df.tail(MONTHS_TO_KEEP).reset_index(drop=True)
    prior = df[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    prior = prior.rename(columns={"revenue": "revenue_prior_year"})
    merged = df.merge(prior, on=["revenue_year", "revenue_month"], how="left")
    out = []
    for _, row in merged.iterrows():
        prev = row.get("revenue_prior_year")
        yoy = (row["revenue"] - prev) / abs(prev) if (prev not in (None, 0) and pd.notna(prev)) else None
        out.append({
            "year": int(row["revenue_year"]), "month": int(row["revenue_month"]),
            "revenue": float(row["revenue"]),
            "yoy": round(float(yoy), 4) if yoy is not None and pd.notna(yoy) else None,
        })
    return out[-8:]  # 只保留最近8個月給圖表用（跟App原本"近8月"設計一致）


def build_ratios(code: str) -> dict | None:
    df = _load_concat("TaiwanStockPER", code)
    if df.empty:
        return None
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    last = df.iloc[-1]
    return {
        "date": str(last.get("date")),
        "per": float(last["PER"]) if pd.notna(last.get("PER")) else None,
        "pbr": float(last["PBR"]) if pd.notna(last.get("PBR")) else None,
        "dividend_yield": float(last["dividend_yield"]) if pd.notna(last.get("dividend_yield")) else None,
    }


def main():
    rev_codes = _codes_from_cache("TaiwanStockMonthRevenue")
    per_codes = _codes_from_cache("TaiwanStockPER")
    all_codes = rev_codes | per_codes
    print(f"快取涵蓋：月營收 {len(rev_codes)} 檔、PER/PBR {len(per_codes)} 檔，聯集 {len(all_codes)} 檔")

    fundamentals = {}
    for code in sorted(all_codes):
        entry = {}
        rev = build_month_revenue(code)
        if rev:
            entry["month_revenue"] = rev
        ratios = build_ratios(code)
        if ratios:
            entry["ratios"] = ratios
        if entry:
            fundamentals[code] = entry

    payload = {
        "meta": {
            "snapshot_note": (
                "這份檔案是手動執行 build_fundamentals_json.py 產生的快照，不是"
                "GitHub Actions排程自動更新——TWSE官方開放資料的月營收/財報比率"
                "端點只有最新一期全市場快照、無歷史區間查詢，沒辦法像大盤指數"
                "那樣排程抓歷史數列，這裡是直接讀研究端已經合法快取的FinMind"
                "歷史資料整理而成，見 build_fundamentals_json.py 說明。"
            ),
        },
        "fundamentals": fundamentals,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(fundamentals)} 檔有資料")


if __name__ == "__main__":
    main()
