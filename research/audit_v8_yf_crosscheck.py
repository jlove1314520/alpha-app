"""驗.八 四：adjust.py 修正的批次量測（診斷，不是新試驗，不改任何判定）。

對 factor_ic 登記用的 300 檔抽樣（seed 20260822），預設**只讀本機快取、不打 FinMind**
（加 --fetch-budget N 才會有預算地補抓缺的 FinMind 快取，遇任何錯誤/冷卻立刻停手）：
  1. 上市日截斷：幾檔、幾列被截、被截掉的跨度分布；跨度 >3 年者列為
     「可能轉板／需人工核對」（只列出，不處理）。
  2. yfinance vs FinMind重建 交叉比對：受影響股票數與日數（差>2pp 或 yfinance 超過
     漲跌幅門檻而FinMind在門檻內）；FinMind 快取不齊而無法比對的檔數。
所有統計只用 date <= VAL_END（holdout 不碰）。輸出 data/diag_v8_yf_crosscheck.json。
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import adjust as adj
import factor_ic as fic
from universe import listing_date_lookup
from finmind_client import _cache_path, load_dev
from validation import holdout
from yf_price_client import fetch_yf_adjusted

OUT = Path(__file__).parent / "data" / "diag_v8_yf_crosscheck.json"
START = fic.START_DATE
VAL_END = holdout.VAL_END


NEEDED = ["TaiwanStockPrice", "TaiwanStockDividend", "TaiwanStockSplitPrice",
          "TaiwanStockCapitalReductionReferencePrice"]


def backfill(ids: list[str], budget: int) -> dict:
    """有預算的FinMind快取補抓（可續跑：已在快取者不算請求）。遇到任何RuntimeError
    （額度/冷卻/封鎖）立刻停手、不重試，避免把免費額度的2小時冷卻再延長。"""
    used, stopped = 0, None
    todo = [("TaiwanStockParValueChange", "")] + [(ds, s) for s in ids for ds in NEEDED]
    for ds, sid in todo:
        if used >= budget:
            stopped = "budget_exhausted"
            break
        if _cache_path(ds, sid, START, VAL_END).exists():
            continue
        try:
            load_dev(ds, sid, START)
            used += 1
        except RuntimeError as e:
            stopped = f"{type(e).__name__}: {str(e)[:120]}"
            break
    return {"requests_used": used, "budget": budget, "stopped": stopped}


def main() -> None:
    budget = int(sys.argv[sys.argv.index("--fetch-budget") + 1]) if "--fetch-budget" in sys.argv else 0
    ids = fic.sample_universe_ids(300, fic.SAMPLE_SEED)
    backfill_info = None
    if budget > 0:
        listing0 = listing_date_lookup()
        # 優先補「有上市日截斷」的檔（最可能受影響），其餘依原順序
        pri = [s for s in ids if s in listing0]
        backfill_info = backfill(pri + [s for s in ids if s not in listing0], budget)
        print("補抓：", backfill_info)
    listing = listing_date_lookup()
    trunc_rows = []
    hits_all: list[dict] = []
    not_checkable = []
    checked = 0
    no_price = []
    unknown_listing = []
    for i, sid in enumerate(ids):
        try:
            yf = fetch_yf_adjusted(sid, START)
        except Exception as e:  # noqa: BLE001
            no_price.append({"stock_id": sid, "err": f"{type(e).__name__}"})
            continue
        if yf.empty:
            no_price.append({"stock_id": sid, "err": "empty"})
            continue
        yf = yf[yf["date"].astype(str) <= VAL_END].reset_index(drop=True)
        if yf.empty:
            no_price.append({"stock_id": sid, "err": "empty_le_VAL_END"})
            continue
        ld = listing.get(sid)
        if ld is None:
            unknown_listing.append(sid)
        else:
            dropped = yf[yf["date"].astype(str) < ld]
            if len(dropped):
                first = pd.Timestamp(str(dropped["date"].iloc[0]))
                span_days = (pd.Timestamp(ld) - first).days
                trunc_rows.append({
                    "stock_id": sid, "listing_date": ld,
                    "first_price_date": str(dropped["date"].iloc[0]),
                    "rows_dropped": int(len(dropped)),
                    "rows_total": int(len(yf)),
                    "dropped_span_years": round(span_days / 365.25, 2),
                    "possible_board_transfer": span_days / 365.25 > 3.0,
                })
        px = adj._truncate_pre_listing(yf.assign(adj_close=yf["close"]), sid)
        if adj._finmind_cache_ready(sid, START):
            checked += 1
            hits = adj.crosscheck_yf_vs_finmind(px, sid, START)
            hits_all.extend(hits)
        else:
            not_checkable.append(sid)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(ids)}")

    adj._append_crosscheck_log(hits_all)  # 警告清單（去重、append-only）
    spans = sorted(r["dropped_span_years"] for r in trunc_rows)

    def q(p):
        return spans[min(len(spans) - 1, int(p * len(spans)))] if spans else None

    kinds = {}
    for h in hits_all:
        for k in h["kinds"]:
            kinds[k] = kinds.get(k, 0) + 1
    by_stock: dict[str, int] = {}
    for h in hits_all:
        by_stock[h["stock_id"]] = by_stock.get(h["stock_id"], 0) + 1
    hits_sorted = sorted(hits_all, key=lambda h: -h["diff_pp"])

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note": "診斷、非試驗；只讀快取；統計限 date<=VAL_END；不改判定。",
        "backfill": backfill_info,
        "sample": {"n_requested": len(ids), "n_with_price": len(ids) - len(no_price),
                   "n_no_price": len(no_price), "n_unknown_listing_date_untruncated": len(unknown_listing)},
        "truncation": {
            "n_stocks_truncated": len(trunc_rows),
            "n_rows_dropped_total": int(sum(r["rows_dropped"] for r in trunc_rows)),
            "span_years_quantiles": {"min": spans[0] if spans else None, "p50": q(0.5),
                                     "p90": q(0.9), "max": spans[-1] if spans else None},
            "possible_board_transfer_gt3y": [r for r in trunc_rows if r["possible_board_transfer"]],
            "all_truncated": trunc_rows,
        },
        "crosscheck": {
            "threshold_pp": adj.YF_CROSSCHECK_THRESHOLD_PP,
            "n_stocks_checked": checked,
            "n_stocks_not_checkable_no_finmind_cache": len(not_checkable),
            "not_checkable_ids": not_checkable,
            "n_stocks_with_hits": len(by_stock),
            "n_hit_days": len(hits_all),
            "hit_days_by_kind": kinds,
            "hits_per_stock": dict(sorted(by_stock.items(), key=lambda kv: -kv[1])),
            "top_hits_by_diff_pp": hits_sorted[:30],
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫入 {OUT}")
    print(json.dumps({k: out[k] for k in ("sample",)}, ensure_ascii=False))
    t = out["truncation"]
    print("截斷：", t["n_stocks_truncated"], "檔", t["n_rows_dropped_total"], "列", t["span_years_quantiles"],
          "疑轉板>3y:", len(t["possible_board_transfer_gt3y"]))
    c = out["crosscheck"]
    print("交叉比對：可比", c["n_stocks_checked"], "檔；無快取", c["n_stocks_not_checkable_no_finmind_cache"],
          "檔；有警告", c["n_stocks_with_hits"], "檔", c["n_hit_days"], "日", c["hit_days_by_kind"])


if __name__ == "__main__":
    main()
