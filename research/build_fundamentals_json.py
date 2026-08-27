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

MONTHS_TO_KEEP = 26  # 2026-08-27：從13調高到26——score_live.py的growth_quality因子
# 需要「近12個月營收總和 vs 再前12個月營收總和」比較成長性，24個月是硬性下限，
# 26留一點緩衝。之前只留13個月是只夠算「單月YoY」，不夠算這種12個月滾動窗口。


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
    return out  # 完整保留（up to MONTHS_TO_KEEP），呼叫端自己決定圖表要切幾個月


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

    # 2026-08-27修正（重跑這支腳本時發現的真bug）：這支腳本原本是「一次性種子」，
    # 直接覆寫整份 data/fundamentals.json。但自從那次種子之後，
    # update_fundamentals_daily.py 每天用 TWSE+TPEx 官方 openapi 累積更新，
    # 覆蓋率已經從種子當下的數字漲到 2272 檔（含大量本機 FinMind 快取沒有、
    # 只有 TPEx openapi 才有的股票）。如果重跑這支腳本時直接覆寫，會把那些
    # 每日累積、本機快取沒有的股票整批砍掉（實測：2272→1774，砍掉502檔）——
    # 這正是「單點依賴視為架構缺陷」的同一類問題：這支腳本本身就是那個單點。
    # 改成「merge」：既有欄位（ratios／month_revenue，來自更即時的官方openapi）
    # 保留不動，只在既有欄位缺漏時才用本機快取補上；revenue_history_scoring
    # 是全新欄位、既有檔案本來就沒有，直接寫入或用本機快取比對取較長者。
    existing_payload = {}
    if OUT_PATH.exists():
        try:
            existing_payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing_payload = {}
    fundamentals = dict(existing_payload.get("fundamentals", {}))
    prior_count = len(fundamentals)

    for code in sorted(all_codes):
        entry = fundamentals.setdefault(code, {})
        rev = build_month_revenue(code)
        if rev:
            existing_scoring = entry.get("revenue_history_scoring")
            if not existing_scoring or len(rev) > len(existing_scoring):
                entry["revenue_history_scoring"] = rev
            if "month_revenue" not in entry:
                entry["month_revenue"] = rev[-8:]
        ratios = build_ratios(code)
        if ratios and "ratios" not in entry:
            entry["ratios"] = ratios

    new_count = len(fundamentals)
    if new_count < prior_count:
        raise RuntimeError(
            f"覆蓋率不應該在merge之後下降，但從 {prior_count} 變成 {new_count}——"
            "這代表merge邏輯有bug，已中止寫入，不要用這份結果覆蓋既有檔案。"
        )

    payload = {
        "meta": {
            "snapshot_note": (
                "起始種子是手動執行 build_fundamentals_json.py 讀研究端FinMind歷史"
                "parquet快取整理而成；此後 update_fundamentals_daily.py 排程改用"
                "TWSE+TPEx官方openapi每日累積更新ratios/month_revenue，覆蓋率已超過"
                "種子當下的數字。2026-08-27修正：這支腳本重跑時改成merge既有檔案"
                "（保留daily排程已經更即時的ratios/month_revenue，只補revenue_history_"
                "scoring這個新欄位或本機快取有、daily排程還沒抓到的股票），不再直接"
                "覆寫整份檔案——之前重跑會把daily排程累積的覆蓋率砍掉，是bug。"
            ),
        },
        "fundamentals": fundamentals,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(fundamentals)} 檔有資料（merge前既有 {prior_count} 檔，"
          f"本機快取涵蓋 {len(all_codes)} 檔）")


if __name__ == "__main__":
    main()
