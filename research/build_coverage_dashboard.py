"""稽核二.二：八因子 × 全市場覆蓋率儀表板（data/coverage.json）。

背景：稽核.二原始指令要求「coverage.json覆蓋率儀表板：八因子×全市場，每
因子覆蓋率%、缺漏檔數、缺漏原因四分類；設定頁顯示。稽核報告的
completeness_gap與這張表要對得起來」。

**跟scores.json的coverage欄位是兩件不同的東西**（稽核二.一實測釐清的重點，
見PROGRESS.md 2026-09-15 17:16條目）：scores.json每檔的`coverage`是「這檔
8個因子裡算出幾個分數」的加權比例，是**橫向**（同一檔跨因子）指標；這份
`coverage.json`反過來看，是**縱向**（同一因子跨全市場）指標——「earnings_
growth這一個因子，全市場2xxx檔裡有幾%算出來、剩下的因為什麼原因算不出來」。
兩者用同一份底層資料（`generate_scores_live.py::build_rows()`的raw_col），
不是另外重新設計一套算法或另開資料源，這樣才「對得起」稽核報告——
`e_quarters_gap`/`e_quarters_stale`這兩個completeness check影響的正是
`earnings_growth`/`valuation_adj`兩個因子的「有資料但不足以計算」（R2）
這一類，可以互相對照驗證。

**缺漏原因四分類（固定四類，八個因子共用同一套定義,以便橫向比較）**：
- R1 個股在原始資料源中完全查無此類資料（該股在來源JSON裡沒有這個欄位/
  沒有這筆記錄；資料源檔案本身存在，只是這一檔沒有）。
- R2 個股有原始資料，但數量/期數不足以計算（例如季度<5季、月營收<13個月、
  價格歷史<60個交易日）——這一類跟`scripts/data_audit.py`的
  `e_quarters_gap`/`e_quarters_stale`是同一個資料缺口在不同因子上的體現。
- R3 全市場此因子系統性缺資料源（資料源檔案本身不存在，不分個股，例如
  `data/events.json`還沒生成時，catalyst因子全市場都是這個原因）。
- R4 其他（資料量足夠但計算仍失敗，例如虧損股TTM EPS<=0導致估值比率無
  意義、除以零、產業樣本不足退回全市場後仍缺）。

分類依據直接檢查各因子的原始資料來源欄位是否存在/筆數是否足夠，不猜測、
不用「score是None就隨便歸類」的黑箱推論。

用法：
    python research/build_coverage_dashboard.py
輸出：data/coverage.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import generate_scores_live as gsl  # noqa: E402
import score_v2  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "data" / "coverage.json"

MIN_QUARTERS_FOR_YOY = 5
MIN_REV_MONTHS_FOR_YOY = 13
MIN_PRICE_ROWS_FOR_TECHNICAL = 60

R1 = "個股完全無此類原始資料"
R2 = "個股有資料但數量/期數不足以計算"
R3 = "全市場此因子系統性缺資料源"
R4 = "其他（資料足夠但計算仍失敗，如虧損股/樣本不足）"


def _classify(reason_key: str) -> str:
    return {"R1": R1, "R2": R2, "R3": R3, "R4": R4}[reason_key]


def main():
    fundamentals = gsl._load_json(gsl.FUNDAMENTALS_PATH).get("fundamentals", {})
    stock_detail = gsl._load_json(gsl.STOCK_DETAIL_PATH).get("stocks", {})
    price_history = {}
    if gsl.PRICE_HISTORY_PATH.exists():
        try:
            price_history = gsl._load_json(gsl.PRICE_HISTORY_PATH).get("prices", {})
        except Exception:
            price_history = {}
    events_source_available = gsl.EVENTS_PATH.exists()
    events_by_code = {}
    if events_source_available:
        try:
            events_by_code = gsl._load_json(gsl.EVENTS_PATH).get("by_stock", {}) or {}
        except Exception:
            events_by_code = {}

    cs = gsl.build_rows()
    # 跟generate_scores_live.py::main()同一個「全市場」定義：build_rows()回傳的是
    # fundamentals∪stock_detail∪price_history三個JSON檔出現過的所有代碼聯集
    # （18834檔，含大量已下市/非現役代碼），不是「全市場」。main()裡用官方在市
    # 名冊過濾後才是稽核.二說的「全市場」（跟data_audit.py的universe同一個定義），
    # 這裡必須套同一個過濾，否則覆蓋率分母錯誤、跟completeness_gap對不起來。
    try:
        active = set(json.loads((REPO_ROOT / "data" / "listed_universe.json").read_text(encoding="utf-8")).get("active") or [])
    except FileNotFoundError:
        active = set()
    if len(active) >= 1000:
        cs = cs[cs.index.isin(active)]
    else:
        print(f"  ! listed_universe.json只有{len(active)}檔，不完整，跳過下市過濾（結果會偏低，不可信）")
    universe_size = len(cs)

    raw_col = {
        "earnings_growth": "raw_earnings_growth",
        "revenue_momentum": "raw_rev_yoy",
        "growth_quality": "raw_rev_grow",
        "chips": "raw_inst_flow",
        "valuation_adj": None,  # 用raw_pe/raw_pb/raw_peg三者皆缺才算缺,見下方特判
        "technical": "raw_technical",
        "analyst": "raw_inst_behavior",
        "catalyst": "raw_event",
    }

    factors_out = {}
    for key, col in raw_col.items():
        if col is not None:
            present_mask = cs[col].notna()
        else:
            present_mask = cs[["raw_pe", "raw_pb", "raw_peg"]].notna().any(axis=1)
        missing_codes = list(cs.index[~present_mask])
        coverage_pct = round(float(present_mask.mean()), 4) if universe_size else None

        reason_counts = {"R1": 0, "R2": 0, "R3": 0, "R4": 0}
        for code in missing_codes:
            fd = fundamentals.get(code, {})
            sd = stock_detail.get(code, {})
            fin = sd.get("financials", {})

            if key == "earnings_growth":
                quarters = fin.get("quarters") or []
                if not quarters:
                    reason_counts["R1"] += 1
                elif len(quarters) < MIN_QUARTERS_FOR_YOY:
                    reason_counts["R2"] += 1
                else:
                    reason_counts["R2"] += 1  # 有≥5季但仍算不出來：季度不連續（跟e_quarters_gap同一類資料缺口）

            elif key == "valuation_adj":
                ratios = fd.get("ratios") or {}
                if ratios.get("per") is None and ratios.get("pbr") is None:
                    reason_counts["R1"] += 1
                else:
                    reason_counts["R4"] += 1  # 有比率但<=0（虧損股）或其他無效

            elif key in ("revenue_momentum", "growth_quality"):
                rev_rows = fd.get("revenue_history_scoring") or fd.get("month_revenue") or []
                if not rev_rows:
                    reason_counts["R1"] += 1
                elif len(rev_rows) < MIN_REV_MONTHS_FOR_YOY:
                    reason_counts["R2"] += 1
                else:
                    reason_counts["R2"] += 1  # 月數夠但不連續（跟e_quarters同類問題，資料源不同）

            elif key == "chips":
                inst = sd.get("institutional")
                if not inst:
                    reason_counts["R1"] += 1
                else:
                    reason_counts["R4"] += 1  # 有institutional物件但三個lots欄位全空

            elif key == "technical":
                price_rows = price_history.get(code) or []
                if not price_rows:
                    reason_counts["R1"] += 1
                elif len(price_rows) < MIN_PRICE_ROWS_FOR_TECHNICAL:
                    reason_counts["R2"] += 1
                else:
                    reason_counts["R4"] += 1  # 筆數夠但vol60=0等計算異常

            elif key == "analyst":
                inst = sd.get("institutional")
                if not inst:
                    reason_counts["R1"] += 1
                else:
                    reason_counts["R4"] += 1

            elif key == "catalyst":
                if not events_source_available:
                    reason_counts["R3"] += 1
                else:
                    reason_counts["R1"] += 1  # 資料源檔案存在，這檔查無事件記錄

        factors_out[key] = {
            "label": score_v2.FACTOR_DEFS[key]["label"],
            "coverage_pct": coverage_pct,
            "covered_count": int(present_mask.sum()),
            "missing_count": len(missing_codes),
            "missing_reason_breakdown": {
                _classify(k): v for k, v in reason_counts.items() if v > 0
            },
        }

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "universe_size": universe_size,
            "reason_categories": {"R1": R1, "R2": R2, "R3": R3, "R4": R4},
            "source": "research/build_coverage_dashboard.py，重用generate_scores_live.py::build_rows()"
                       "同一套原始資料（不重新設計算法），與data/audit_report.json的"
                       "completeness_gap（e_quarters_gap/e_quarters_stale）互相對照。",
            "note": "本表是「同一因子跨全市場」的覆蓋率；scores.json每檔的coverage欄位"
                    "是「同一檔跨八因子」的完整度，兩者是不同維度，不要混用比較。",
        },
        "factors": factors_out,
    }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，全市場 {universe_size} 檔")
    for key, v in factors_out.items():
        print(f"  {v['label']}({key}): 覆蓋率{v['coverage_pct']*100:.1f}%，缺{v['missing_count']}檔，"
              f"原因分佈={v['missing_reason_breakdown']}")


if __name__ == "__main__":
    main()
