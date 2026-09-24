# -*- coding: utf-8 -*-
"""宇.一（2026-09-24總司令裁示【開考前修正——宇宙限普通股＋MDD判準回復
原裁示】）：量測f52w(#377)/dividend(#376) VAL期持股組成，以及300樣本本身
組成。**只讀既有結果，不重跑「回測判定」意義上的VAL回測、不登記新試驗**
——為了取得trade-level持股紀錄，仍必須呼叫`run_backtest()`，但呼叫方式
與f377/f376已登記的VAL期回測完全相同（同一套signal_fn/同一套
BacktestConfig/同一份快取資料，零新增API呼叫），是確定性重現，不是產生
新結果——這跟`audit_f52w_attribution.py`（審.一步驟3，已被裁示接受為
「稽核」而非「新試驗」）是同一種先例。不呼叫`trial_registry.register_
trial()`，不寫入TRIALS_LEDGER.md。

用法：python research/audit_universe_composition_val.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import _fetch, load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe, classify_security
from validation import holdout

import portfolio_backtest_v2 as pbv2
import f52w_high_portfolio_v1 as f52w_mod
import dividend_yield_portfolio_v1 as div_mod

OUT_JSON = Path(__file__).parent / "data" / "audit_universe_composition_val.json"

VAL_START = "2021-01-01"

# ────────────────────────────────────────────────────────────────────────
# 分類規則（宇.一第1點：依TaiwanStockInfo的industry_category與代號規則）
# ────────────────────────────────────────────────────────────────────────
# 2026-09-24宇.二：分類規則改由`universe.py::classify_security()`統一維護
# （`common_stock_only()`同一套規則的權威版本，供2007-2014單發檢定候選宇宙
# 限定使用）——這裡不再維護第二份重複邏輯，只是沿用同一個函式名做這支
# 稽核腳本原本的別名，避免下面呼叫端要逐一改名。規則細節見
# `universe.py::classify_security()`docstring（主規則/退回規則）。
classify_holding = classify_security


def _self_test(info_lookup: dict[str, dict]) -> None:
    """自我測試：已知樣本（裁示原文點名）分類必須正確，錯了就直接AssertionError中止。"""
    must_exclude = {
        "00401A": "股票型ETF",  # 主動摩根台灣鑫收，ETF類別，名稱不含「債」
        "2887I": "特別股",       # 台新新光辛特
        "00718B": "債券型ETF",   # 富邦中國政策債
        "2891B": "特別股",       # 中信金乙特（額外核對，同一種命名慣例）
        "0050": "股票型ETF",
        "00878": "股票型ETF",
        "9105": "TDR",           # 泰金寶-DR
    }
    must_be_common = {"2330": "普通股", "2317": "普通股"}
    problems = []
    for sid, expect in {**must_exclude, **must_be_common}.items():
        row = info_lookup.get(sid)
        if row is None:
            problems.append(f"{sid}: 不在TaiwanStockInfo快取裡，無法自我測試")
            continue
        got = classify_holding(sid, row.get("stock_name"), row.get("industry_category"))
        if got != expect:
            problems.append(f"{sid}: 預期={expect} 實際={got}")
    if problems:
        raise AssertionError("宇.一分類規則自我測試失敗：\n" + "\n".join(problems))
    print(f"[自我測試] 通過：{len(must_exclude)}檔應排除樣本 + {len(must_be_common)}檔應保留樣本，分類皆正確", flush=True)


def _load_info_lookup() -> dict[str, dict]:
    """stock_id -> {stock_name, industry_category}，兩層來源：
    1. TaiwanStockInfo全表（keep='last'去重，比照universe.py::active_stock_ids()
       同一套去重邏輯，避免像2330/2317那樣同一檔因為快照疊代出現兩筆不同
       industry_category的列，造成分類不穩定）——這是權威來源，只要有值就用它。
    2. universe.py::universe()（含TaiwanStockDelisting）補stock_name——早期下市、
       已從TaiwanStockInfo現況快照掉出去的股票（見classify_holding()退回規則的
       docstring）只能從這裡拿到名稱，industry_category這層天生是None。
    """
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    lookup = info.set_index("stock_id")[["stock_name", "industry_category"]].to_dict("index")

    combined = build_universe()
    for _, row in combined.iterrows():
        sid = row["stock_id"]
        if sid not in lookup:
            lookup[sid] = {"stock_name": row["stock_name"], "industry_category": row.get("industry_category")}
    return lookup


def _val_trades_for(strategy_mod, data, market_df, industry_map, liquidity) -> pd.DataFrame:
    """確定性重現該策略已登記VAL期回測的signal_fn/BacktestConfig，取得trades。
    跟`f52w_high_portfolio_v1.py::run_one()`/`dividend_yield_portfolio_v1.py::run_one()`
    的VALIDATION分支用的是完全相同的signal_fn建構方式與BacktestConfig參數
    （TOP_N/REBALANCE_DAYS/book_name一致，start/end同樣是VAL_START..holdout.VAL_END），
    不改任何參數，因此是既有VAL結果的確定性重現，不是新試驗。"""
    signal_fn = strategy_mod.make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=VAL_START, end_date=holdout.VAL_END,
                          max_positions=strategy_mod.TOP_N,
                          rebalance_every_n_days=strategy_mod.REBALANCE_DAYS,
                          book_name=f"{strategy_mod.__name__}_composition_audit")
    result = run_backtest(signal_fn, data, market_df, cfg)
    return result.trades


def _holding_periods(trades: pd.DataFrame, val_end: str) -> pd.DataFrame:
    """把buy/sell trades配對成持有區間：[entry_date, exit_date]，
    entry_trade_id把sell連回它對應的buy。VAL_END時仍未平倉的部位
    （engine.py不在回測結束時強制平倉，只做mark-to-market），
    exit_date補上val_end、exit_pnl記為None（未實現損益，見下方限制揭露）。"""
    buys = trades[trades["side"] == "buy"].set_index("trade_id")
    sells = trades[trades["side"] == "sell"]
    closed_entry_ids = set(sells["entry_trade_id"])

    rows = []
    for tid, b in buys.iterrows():
        sell_rows = sells[sells["entry_trade_id"] == tid]
        if len(sell_rows) == 0:
            rows.append({"stock_id": b["stock_id"], "entry_date": b["date"], "exit_date": val_end,
                         "realized_pnl": None, "still_open_at_val_end": True})
        else:
            s = sell_rows.iloc[0]
            rows.append({"stock_id": b["stock_id"], "entry_date": b["date"], "exit_date": s["date"],
                         "realized_pnl": float(s["realized_pnl"]), "still_open_at_val_end": False})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["holding_days"] = (pd.to_datetime(out["exit_date"]) - pd.to_datetime(out["entry_date"])).dt.days
    return out


def _composition_stats(holdings: pd.DataFrame, info_lookup: dict[str, dict]) -> dict:
    holdings = holdings.copy()
    holdings["category"] = holdings["stock_id"].apply(
        lambda sid: classify_holding(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                      (info_lookup.get(sid) or {}).get("industry_category"))
    )
    unclassified = sorted(holdings.loc[holdings["category"] == "無法分類", "stock_id"].unique().tolist())

    by_days = holdings.groupby("category")["holding_days"].sum()
    total_days = float(by_days.sum())
    pct_by_days = {k: (float(v) / total_days * 100.0 if total_days else float("nan")) for k, v in by_days.items()}

    realized = holdings.dropna(subset=["realized_pnl"])
    by_pnl = realized.groupby("category")["realized_pnl"].sum()
    total_pnl = float(by_pnl.sum())
    pct_by_pnl = {k: (float(v) / total_pnl * 100.0 if total_pnl else float("nan")) for k, v in by_pnl.items()}

    n_positions_open_at_val_end = int(holdings["still_open_at_val_end"].sum())
    return {
        "n_holding_periods_total": int(len(holdings)),
        "n_distinct_stock_ids": int(holdings["stock_id"].nunique()),
        "n_positions_still_open_at_val_end_excluded_from_pnl_pct": n_positions_open_at_val_end,
        "pct_of_holding_days_by_category": pct_by_days,
        "pct_of_realized_val_pnl_by_category": pct_by_pnl,
        "total_realized_pnl": total_pnl,
        "unclassified_stock_ids": unclassified,
        "holding_days_raw": {k: float(v) for k, v in by_days.items()},
    }


def main():
    print("=== 宇.一：量測VAL期持股組成（只讀既有快取，零新增API呼叫）===", flush=True)

    info_lookup = _load_info_lookup()
    _self_test(info_lookup)

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_universe_composition_val")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    out = {"generated_for": "宇.一（2026-09-24裁示【開考前修正】）",
           "note": "只讀既有快取資料重現已登記的VAL期回測（VAL_START..holdout.VAL_END，"
                   "與#377/#396、#376/#397相同的signal_fn/BacktestConfig），零新增API呼叫，"
                   "不呼叫register_trial()，不是新試驗。"}

    for label, mod in (("f52w_high_portfolio_v1(#377/#396)", f52w_mod),
                        ("dividend_yield_portfolio_v1(#376/#397)", div_mod)):
        print(f"\n--- {label} VAL期持股重現 ---", flush=True)
        trades = _val_trades_for(mod, data, market_df, industry_map, liquidity)
        holdout.assert_no_holdout_leakage(trades, date_col="date", context=f"{label} composition audit")
        holdings = _holding_periods(trades, holdout.VAL_END)
        stats = _composition_stats(holdings, info_lookup)
        out[label] = stats
        print(f"  持有區間數={stats['n_holding_periods_total']}  相異股票數={stats['n_distinct_stock_ids']}  "
              f"VAL末未平倉(排除於報酬貢獻外)={stats['n_positions_still_open_at_val_end_excluded_from_pnl_pct']}", flush=True)
        print(f"  持股天數佔比：{stats['pct_of_holding_days_by_category']}", flush=True)
        print(f"  VAL已實現報酬貢獻佔比：{stats['pct_of_realized_val_pnl_by_category']}", flush=True)
        if stats["unclassified_stock_ids"]:
            print(f"  ⚠️ 無法分類：{stats['unclassified_stock_ids']}", flush=True)

    print("\n--- 300檔樣本本身組成 ---", flush=True)
    sample_rows = []
    for sid in sample_ids:
        row = info_lookup.get(sid) or {}
        sample_rows.append({"stock_id": sid, "category": classify_holding(sid, row.get("stock_name"), row.get("industry_category"))})
    sample_df = pd.DataFrame(sample_rows)
    sample_counts = sample_df["category"].value_counts().to_dict()
    sample_unclassified = sorted(sample_df.loc[sample_df["category"] == "無法分類", "stock_id"].unique().tolist())
    print(f"  300檔樣本分類計數：{sample_counts}", flush=True)
    if sample_unclassified:
        print(f"  ⚠️ 300檔樣本中無法分類：{sample_unclassified}", flush=True)

    print("\n--- 2007-2014期間實際存在的非普通股數量（只用已成功抓取者，誠實排除未抓者）---", flush=True)
    ext_ckpt_path = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"
    ext_note = None
    if ext_ckpt_path.exists():
        ext_ckpt = json.loads(ext_ckpt_path.read_text(encoding="utf-8"))
        fetched_ids = set(ext_ckpt.get("fetched_ids", []))
        non_common_in_2007_2014 = [sid for sid in fetched_ids
                                    if classify_holding(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                                         (info_lookup.get(sid) or {}).get("industry_category")) != "普通股"]
        ext_note = {
            "source": "f52w_2007_extension_checkpoint.json（資料.一在跑的2007-2014延伸抓取，"
                       "與300樣本同一份sample_universe_ids結果）",
            "n_fetched_of_300": len(fetched_ids),
            "n_non_common_stock_among_fetched": len(non_common_in_2007_2014),
            "non_common_stock_ids": sorted(non_common_in_2007_2014),
            "caveat": "資料.一尚未抓完300檔（見PENDING_QUEUE.md「閘門.一」BLOCKED狀態），"
                      "這裡只統計『已成功抓取』的子集合，不對尚未抓取的部分做任何推測。",
        }
        print(f"  已抓{len(fetched_ids)}/300檔，其中非普通股{len(non_common_in_2007_2014)}檔："
              f"{sorted(non_common_in_2007_2014)}", flush=True)
    else:
        print("  ⚠️ f52w_2007_extension_checkpoint.json不存在，無法統計", flush=True)

    out["sample_300_composition"] = {
        "counts": sample_counts,
        "unclassified_stock_ids": sample_unclassified,
    }
    out["non_common_stock_present_2007_2014"] = ext_note

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
