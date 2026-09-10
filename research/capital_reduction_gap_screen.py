"""`HYPOTHESIS_QUEUE.md` #71 台股減資事件研究：價格跳空候選偵測腳本。

背景見`HYPOTHESIS_QUEUE.md`#71條目「判定：全市場『歷年曾減資公司清單』
不可及」段落——FinMind`TaiwanStockCapitalReductionReferencePrice`只能逐檔
查詢、TWSE/TPEx官方openapi無減資彙總資料集、GitHub/社群無可信全市場清單。
依`CLAUDE.md`資料原則「主來源→備援→由已有欄位推導」，改用「由已有欄位推導」
路徑：`adjust.py`已在module docstring明文記錄「capital reductions (減資) are
NOT handled here...a stock that underwent a capital reduction will show an
unadjusted jump」——這正是可推導的訊號：掃描原始（未還原）收盤價的單日
報酬，找出無法用除權息事件（`adjustment_events()`）解釋、且超過台股漲跌停
±10%物理上限的異常跳空，當作候選再逐檔驗證。

**零新增API呼叫**：完全使用`data/raw/`既有快取（`TaiwanStockPrice`與
`TaiwanStockDividend`皆以`start_date='2010-01-01', end_date=VAL_END`
2010-01-01~2024-12-31快取），只掃兩個資料集都已快取的股票交集，
`load_dev()`碰到快取會直接命中，不觸發任何HTTP呼叫。

**候選宇宙化簡（誠實揭露的簡化，非全市場）**：只取4位數字代號且不以
'00'開頭（排除ETF，00xx/00xxA類代號多為ETF，減資機制與個股不同經濟意涵）。
這不是`listed_universe.json`時點宇宙的完整交集，是「兩個資料集都恰好已
快取」這個實用子集，樣本數見執行輸出，若下一輪要擴大覆蓋需另外對缺快取
的股票批次補抓（比照`#69`checkpoint分批模式）。

**跳空判準**：單日（前一交易日收盤→當日收盤）原始報酬絕對值 > 0.15
（漲跌停自2015-06-01起為±10%，之前為±7%，留0.05以上安全邊界排除正常
極端盤但仍是合法漲跌停內的日子；減資換股比例常見1股換0.3~0.7股，換算
單日跳空遠超過15%，此閾值刻意偏寬鬆以求高recall，精確度留給下一輪逐檔
`TaiwanStockCapitalReductionReferencePrice`驗證），且該日期不在
`adjustment_events()`回傳的`ex_date`集合裡（排除正常除權息可解釋的跳空）。

**已知限制（誠實揭露）**：
1. 只用日收盤價比對，無法排除股票分割、面額變動等其他也會造成跳空的
   公司行動（`#71`已知風險第4點呼應）——這是**候選**產生器，不是最終判定。
2. 減資基準日附近通常會停止交易數日再復牌，`TaiwanStockPrice`原始資料
   若本身已跳過停牌期間（只記錄實際成交日），這裡偵測到的就是「復牌
   當日相對停牌前最後一個交易日」的跳空，天然對齊減資機制本身
   （停牌前最後一天→復牌新股上市首日），不需要額外處理停牌天數。
3. 部分跳空可能是資料品質問題（错误row、單位換算錯誤）而非真實市場
   事件，逐檔驗證階段需要交叉核對成交量是否同時異常（真實減資復牌通常
   伴隨當日成交量放大，資料錯誤通常不會）。

2026-09-10 hypothesis_queue排程接續（鎖檔陳舊回收接手，本輪工作單位：
建置並執行此偵測腳本，產出候選清單，供下一輪逐檔驗證，不逐關跳過）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from adjust import adjustment_events
from finmind_client import load_dev

START_DATE = "2010-01-01"  # 必須跟快取檔名的日期完全相符才能命中快取，見上方docstring
JUMP_THRESHOLD = 0.15  # 單日原始報酬絕對值門檻，見上方docstring判準說明
OUT_PATH = Path(__file__).parent.parent / "data" / "capital_reduction_gap_candidates.json"


def _cached_ids(dataset: str) -> set[str]:
    """從`data/raw/`檔名反推哪些stock_id已用同一個日期範圍快取過，
    不觸發任何HTTP呼叫（純檔名字串解析）。"""
    pattern = re.compile(rf"^{re.escape(dataset)}__(.+?)__{START_DATE}__2024-12-31\.parquet$")
    ids = set()
    for f in (Path(__file__).parent / "data" / "raw").glob(f"{dataset}__*__{START_DATE}__2024-12-31.parquet"):
        m = pattern.match(f.name)
        if m:
            ids.add(m.group(1))
    return ids


def candidate_universe() -> list[str]:
    price_ids = _cached_ids("TaiwanStockPrice")
    div_ids = _cached_ids("TaiwanStockDividend")
    both = price_ids & div_ids
    ordinary = sorted(i for i in both if re.match(r"^\d{4}$", i) and not i.startswith("00"))
    return ordinary


def scan_one(stock_id: str) -> list[dict]:
    """回傳這檔股票所有「無法用除權息解釋的異常跳空」候選列。零新增API呼叫
    （全部經由`load_dev()`命中`start_date='2010-01-01'`快取）。

    **2026-09-10本輪修正（首次執行後發現的資料品質bug，非事前設計）**：
    FinMind `TaiwanStockPrice`對零成交量（`Trading_Volume==0`，當天完全
    沒有成交，非停牌，只是掛單但無人成交）的日子回傳`close=0.0`，不是
    延續前一日收盤或省略該列。首次執行未過濾這個情況，導致「有成交→
    零成交日」與「零成交日→下一個有成交日」各自被誤判成-100%/+inf%的
    假跳空，把全市場零成交日這個極常見現象（尤其小型股、興櫃剛轉上市股）
    當成候選減資事件，第一次執行產出149,030筆候選（涉1243檔股票）——
    這個量級遠超台股歷年減資公告的合理筆數，人工核對前幾筆candidate
    後發現全部都是`close: 0.0`或`prev_close: 0.0`，證實是這個bug而非
    真實現象。修法：先過濾掉`Trading_Volume==0`的列（視為當日無觀測值，
    不當作一個有效收盤價），再計算報酬率，`prev_close`因而自然對齊到
    「前一個真正有成交的交易日」。"""
    raw = load_dev("TaiwanStockPrice", stock_id, START_DATE)
    if raw.empty or len(raw) < 2:
        return []
    raw = raw.sort_values("date").reset_index(drop=True)
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
    if "Trading_Volume" in raw.columns:
        raw["Trading_Volume"] = pd.to_numeric(raw["Trading_Volume"], errors="coerce")
        raw = raw[raw["Trading_Volume"] > 0]
    raw = raw[raw["close"] > 0]
    raw = raw.dropna(subset=["close"])
    if len(raw) < 2:
        return []
    raw["prev_close"] = raw["close"].shift(1)
    raw["pct_change"] = (raw["close"] - raw["prev_close"]) / raw["prev_close"]

    events = adjustment_events(stock_id, START_DATE)
    explained_dates = set(events["ex_date"]) if not events.empty else set()

    out = []
    for _, row in raw.iloc[1:].iterrows():
        if pd.isna(row["pct_change"]):
            continue
        if abs(row["pct_change"]) <= JUMP_THRESHOLD:
            continue
        if row["date"] in explained_dates:
            continue
        out.append({
            "stock_id": stock_id,
            "date": row["date"],
            "prev_close": round(float(row["prev_close"]), 4),
            "close": round(float(row["close"]), 4),
            "pct_change": round(float(row["pct_change"]), 4),
        })
    return out


def main() -> None:
    universe = candidate_universe()
    all_candidates: list[dict] = []
    scanned = 0
    errors = 0
    for stock_id in universe:
        scanned += 1
        try:
            all_candidates.extend(scan_one(stock_id))
        except Exception as exc:  # noqa: BLE001 -- 單檔資料異常不能讓整個掃描中斷
            errors += 1
            print(f"[warn] {stock_id} 掃描失敗，略過：{exc}")

    all_candidates.sort(key=lambda r: (r["date"], r["stock_id"]))
    n_stocks_with_candidates = len({c["stock_id"] for c in all_candidates})

    by_year: dict[str, int] = {}
    for c in all_candidates:
        y = c["date"][:4]
        by_year[y] = by_year.get(y, 0) + 1

    result = {
        "generated_at_note": "hypothesis_queue #71 gap-screen, 2026-09-10 接續",
        "start_date": START_DATE,
        "jump_threshold": JUMP_THRESHOLD,
        "stocks_scanned": scanned,
        "stocks_scan_errors": errors,
        "candidates_total": len(all_candidates),
        "stocks_with_candidates": n_stocks_with_candidates,
        "candidates_by_year": dict(sorted(by_year.items())),
        "candidates": all_candidates,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"掃描完成：{scanned} 檔股票（快取交集，零新增API呼叫），{errors} 檔失敗")
    print(f"候選跳空事件：{len(all_candidates)} 筆，涉及 {n_stocks_with_candidates} 檔股票")
    print(f"依年份分布：{dict(sorted(by_year.items()))}")
    print(f"輸出：{OUT_PATH}")


if __name__ == "__main__":
    main()
