"""`HYPOTHESIS_QUEUE.md` #71 台股减資事件研究：候選逐檔驗證腳本（第二步）。

背景見`capital_reduction_gap_screen.py`docstring——上一步用價格跳空偵測
產出`data/capital_reduction_gap_candidates.json`（3,490筆候選、涉805檔
股票），這是**高recall低precision**的候選產生器（已知會混入股票分割、
面額變動、資料品質問題等非减資跳空）。本腳本是`#71`判定「全市場歷年
減資公司清單不可及，必須改用由已有欄位推導」段落規劃的下一輪待辦
(2)：對候選清單裡的每一檔股票，逐檔呼叫FinMind
`TaiwanStockCapitalReductionReferencePrice`（唯一已確認欄位含
`ReasonforCapitalReduction`能區分現金减資/彌補虧損减資的資料集），
用「這檔股票是否真的有减資紀錄、且减資參考價日期是否接近候選跳空日」
交叉驗證，把候選從「跳空事件」精煉成「已驗證的减資事件」。

**checkpoint可續跑機制**（比照`short_sale_utilization_portfolio_v1.py`/
`margin_utilization_regime_portfolio_v1.py`同一套模式，理由同—805檔
股票逐檔查詢在FinMind跨process節流3秒/次下，單輪417秒時間預算內只能
處理約140檔，必須能跨輪接續，不能每輪從頭來過）：checkpoint記錄
「已查詢過的stock_id → 該檔FinMind回傳的原始列（可能為空list代表
真的沒有减資紀錄，區別於『還沒查過』）」，每次執行先讀checkpoint，
只查詢還沒查過的stock_id，時間預算到就存檔收工。

**零風險保證**：`TaiwanStockCapitalReductionReferencePrice`資料集含
`date`欄位，走`load_dev()`一律holdout-safe（見`finmind_client.py`
docstring），且本腳本只讀取`data/capital_reduction_gap_candidates.json`
（上一輪已產出，不重算）與呼叫`load_dev()`，不涉及任何holdout解鎖路徑。

**交叉比對邏輯（事前綁定，避免看到數字才決定判準）**：
- 一檔股票若FinMind回傳非空的减資參考價列，視為「該股票確實曾減資」。
- 對每一筆减資參考價列，找候選清單裡同一檔股票、日期在
  [减資參考價日期-3, 减資參考價日期+3]（含）交易日窗口內的候選跳空
  事件視為「匹配」——減資參考價的`date`欄位語意是「恢復買賣日」
  （`#71`已查證確認，非公告日），跳空偵測抓的正是「復牌當日相對停牌前
  最後交易日」的價格斷點，兩者理論上應為同一天或極接近，±3個交易日
  是保守容錯（跨週末/國定假日/資料來源記錄方式微小差異）。
- 未匹配到任何候選跳空事件的减資參考價列，仍記錄下來（可能代表跳空
  閾值0.15過於嚴格漏掉了小比例减資，或减資恢復買賣日剛好落在
  `Trading_Volume==0`被過濾掉的日子），但**不計入「已驗證候選」**，
  留給下一輪評估閾值是否需要調整。

2026-09-10 hypothesis_queue排程接續（鎖檔陳舊回收接手，本輪工作單位：
建置並執行此逐檔驗證腳本，對候選清單進行時間預算內的部分批次驗證，
checkpoint存檔供下一輪接續，不強求一次查完805檔）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from finmind_client import load_dev

START_DATE = "2010-01-01"
CANDIDATES_PATH = Path(__file__).parent.parent / "data" / "capital_reduction_gap_candidates.json"
CHECKPOINT_PATH = Path(__file__).parent / "data" / "capital_reduction_verify_checkpoint.json"
OUT_PATH = Path(__file__).parent.parent / "data" / "capital_reduction_verified.json"
MATCH_WINDOW_DAYS = 3  # 交易日窗口，見docstring交叉比對邏輯
TIME_BUDGET_SECONDS = float(os.environ.get("CRV_TIME_BUDGET_SECONDS", "420"))


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {"queried": {}}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8")


def _candidate_universe() -> tuple[list[str], dict[str, list[dict]]]:
    """讀候選清單，回傳(去重排序後的stock_id清單, {stock_id: [候選事件...]})。"""
    data = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    by_stock: dict[str, list[dict]] = {}
    for c in data["candidates"]:
        by_stock.setdefault(c["stock_id"], []).append(c)
    return sorted(by_stock.keys()), by_stock


def _date_within_window(a: str, b: str, window: int) -> bool:
    """粗略天數差（非交易日曆精確版，但候選/减資日期皆為YYYY-MM-DD字串，
    用曆日差近似交易日窗口——`window=3`已預留跨週末容錯，曆日/交易日
    誤差在此容錯範圍內可忽略，不需要引入完整交易日曆增加複雜度）。"""
    from datetime import date

    da = date.fromisoformat(a)
    db = date.fromisoformat(b)
    return abs((da - db).days) <= window


def main() -> None:
    universe, candidates_by_stock = _candidate_universe()
    ckpt = _load_checkpoint()
    queried: dict = ckpt["queried"]

    pending = [s for s in universe if s not in queried]
    print(f"候選宇宙共{len(universe)}檔，已查詢{len(queried)}檔，本輪待查{len(pending)}檔")

    deadline = time.time() + TIME_BUDGET_SECONDS
    n_this_round = 0
    n_errors = 0
    for stock_id in pending:
        if time.time() > deadline:
            print(f"時間預算已到（{TIME_BUDGET_SECONDS}秒），本輪查詢{n_this_round}檔，已checkpoint，下次執行接續")
            break
        try:
            df = load_dev("TaiwanStockCapitalReductionReferencePrice", data_id=stock_id, start_date=START_DATE)
            rows = [] if df.empty else df.to_dict(orient="records")
            queried[stock_id] = rows
            n_this_round += 1
            if n_this_round % 20 == 0:
                _save_checkpoint(ckpt)
                print(f"  進度 {n_this_round}/{len(pending)}（本輪）")
        except RuntimeError as exc:
            # 資料源禮儀：封鎖冷卻中直接停止本輪，不重試、不換來源硬取
            print(f"[stop] 觸發節流/斷路器，停止本輪：{exc}")
            break
        except Exception as exc:  # noqa: BLE001 -- 單檔查詢異常不能讓整個批次中斷
            n_errors += 1
            print(f"[warn] {stock_id} 查詢失敗，略過：{exc}")
            queried[stock_id] = {"error": str(exc)}

    _save_checkpoint(ckpt)

    # 產生目前累積的驗證結果報告（每次執行都重新彙整，不只彙整本輪新查的）
    verified_stocks = []
    for stock_id, rows in queried.items():
        if not isinstance(rows, list) or not rows:
            continue
        cand_events = candidates_by_stock.get(stock_id, [])
        for r in rows:
            reduction_date = r.get("date")
            if not reduction_date:
                continue
            matched = [
                c for c in cand_events
                if _date_within_window(c["date"], reduction_date, MATCH_WINDOW_DAYS)
            ]
            verified_stocks.append({
                "stock_id": stock_id,
                "reduction_date": reduction_date,
                "reason": r.get("ReasonforCapitalReduction"),
                "matched_gap_candidates": matched,
                "matched": bool(matched),
            })

    n_queried = len(queried)
    n_with_data = sum(1 for v in queried.values() if isinstance(v, list) and v)
    n_errors_total = sum(1 for v in queried.values() if isinstance(v, dict) and "error" in v)
    by_reason: dict[str, int] = {}
    for v in verified_stocks:
        r = v["reason"] or "(空)"
        by_reason[r] = by_reason.get(r, 0) + 1
    n_matched = sum(1 for v in verified_stocks if v["matched"])

    result = {
        "generated_at_note": "hypothesis_queue #71 candidate verify, 2026-09-10 接續",
        "candidate_universe_size": len(universe),
        "stocks_queried_total": n_queried,
        "stocks_queried_this_round": n_this_round,
        "stocks_query_errors": n_errors_total,
        "stocks_with_reduction_data": n_with_data,
        "reduction_events_total": len(verified_stocks),
        "reduction_events_matched_to_gap_candidate": n_matched,
        "reduction_events_by_reason": by_reason,
        "reduction_events": verified_stocks,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n累積查詢：{n_queried}/{len(universe)} 檔（本輪新查{n_this_round}、失敗{n_errors}）")
    print(f"有减資紀錄：{n_with_data} 檔，共{len(verified_stocks)}筆减資事件")
    print(f"依原因分布：{by_reason}")
    print(f"與跳空候選匹配：{n_matched}/{len(verified_stocks)}")
    print(f"輸出：{OUT_PATH}")


if __name__ == "__main__":
    main()
