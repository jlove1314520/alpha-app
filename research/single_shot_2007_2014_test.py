# -*- coding: utf-8 -*-
"""考.一（2026-09-25總司令裁示【2007-2014 單發檢定放行＋daily_price
日期欄位緊急查核】）：2007-2014單發檢定，#396(f52w_high_portfolio_v1)／
#397(dividend_yield_portfolio_v1)，依`SINGLE_SHOT_2007_2014_SPEC.md`
（含2.1節宇.二修訂一／4.2節規.五修訂）執行。

**ONLY-ONCE 鐵律（裁示原文）**：只跑一次。若程式在產出任何結果數字之前
就崩潰，可以修bug後重跑，但必須在TRIALS_LEDGER記錄崩潰原因與修正內容。
一旦有任何結果數字被印出或寫檔，就視為已考過，不得重跑。**本檔案的
`load_common_stock_data_2007_2014()`（資料載入，零統計判定）可以安全
反覆測試；`run_single_shot()`與`main()`一旦執行到印出任何統計數字，
即視為已消耗這次單發檢定資格。**

用法：python research/single_shot_2007_2014_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mem_guard  # 稽核.六續一：全市場多檔全歷史常駐記憶體安全閥
mem_guard.install()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd
from scipy import stats as sstats

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from factors import prepare_factors
from adjust import adjusted_price_series
from finmind_client import _fetch, load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from universe import classify_security, universe as build_universe
import portfolio_backtest_v2 as pbv2
from comparable_trial_variance import dimson_ir
from survival_constraint_allocation_test import load_0050_full_history, segment_mdd, compute_mdd
import f52w_high_portfolio_v1 as f52w_mod
import dividend_yield_portfolio_v1 as div_mod
import trial_registry

EXTENDED_START = "2006-01-01"
OOS_START, OOS_END = "2007-01-01", "2014-12-31"
SUB1_START, SUB1_END = "2007-01-01", "2009-12-31"
SUB2_START, SUB2_END = "2010-01-01", "2014-12-31"
MDD_2008_BENCHMARK_PCT = -55.75  # 規.五算出的0050 2008 MDD，候選須嚴格優於此值
BONFERRONI_ONE_TAIL_ALPHA = 0.025  # 2個候選，family-wise 0.05/2

OUT_JSON = Path(__file__).parent / "data" / "single_shot_2007_2014_result.json"


def _info_lookup() -> dict[str, dict]:
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    lookup = info.set_index("stock_id")[["stock_name", "industry_category"]].to_dict("index")
    combined = build_universe()
    for _, row in combined.iterrows():
        sid = row["stock_id"]
        if sid not in lookup:
            lookup[sid] = {"stock_name": row["stock_name"], "industry_category": row.get("industry_category")}
    return lookup


def load_common_stock_data_2007_2014():
    """讀取300樣本、限普通股(宇.二common_stock_only精神)、載入2006-01-01起
    的還原股價+因子（全部讀本機快取，零新增API呼叫——`資料.一`已於
    2026-09-24完成300/300檔fetch，本函式只是重新走一次prepare_factors()
    確定性重現，不觸發任何新請求）。可安全反覆測試，本身不產生任何
    統計判定結果。"""
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    info_lookup = _info_lookup()
    common_ids = [sid for sid in sample_ids
                  if classify_security(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                        (info_lookup.get(sid) or {}).get("industry_category")) == "普通股"]
    print(f"300檔樣本中普通股(宇.二common_stock_only)={len(common_ids)}檔", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", EXTENDED_START)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in single_shot_2007_2014_test")
    market_df = prepare_market_data(market_raw)

    data: dict[str, pd.DataFrame] = {}
    n_price_fail, n_factor_fail = 0, 0
    for i, sid in enumerate(common_ids):
        try:
            px = adjusted_price_series(sid, EXTENDED_START)
        except Exception:  # noqa: BLE001
            n_price_fail += 1
            continue
        if px.empty or len(px) < 260:
            n_price_fail += 1
            continue
        try:
            d = prepare_factors(sid, px, market_df, EXTENDED_START)
        except Exception:  # noqa: BLE001
            n_factor_fail += 1
            continue
        data[sid] = d
        if (i + 1) % 50 == 0:
            print(f"  進度 {i+1}/{len(common_ids)}（累計可用 {len(data)} 檔）", flush=True)

    print(f"資料載入完成：可用{len(data)}檔（價格不足/失敗{n_price_fail}檔、"
          f"factor失敗{n_factor_fail}檔）", flush=True)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    return data, market_df, industry_map, liquidity, len(common_ids)


def _period_return_pct(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    return float(equity.iloc[-1] / equity.iloc[0] - 1) * 100


def _yearly_table(equity_curve: pd.DataFrame, mkt_0050: pd.Series) -> list[dict]:
    eq = equity_curve.set_index("date")["equity"]
    rows = []
    for yr in range(2007, 2015):
        y_start, y_end = f"{yr}-01-01", f"{yr}-12-31"
        eq_w = eq[(eq.index >= y_start) & (eq.index <= y_end)]
        mkt_w = mkt_0050[(mkt_0050.index >= y_start) & (mkt_0050.index <= y_end)]
        cand_ret = _period_return_pct(eq_w) if len(eq_w) >= 2 else float("nan")
        mkt_ret = _period_return_pct(mkt_w) if len(mkt_w) >= 2 else float("nan")
        rows.append({"year": yr, "candidate_return_pct": round(cand_ret, 2) if cand_ret == cand_ret else None,
                     "0050_return_pct": round(mkt_ret, 2) if mkt_ret == mkt_ret else None})
    return rows


def _one_tailed_ir_test(equity_curve: pd.DataFrame, market_df: pd.DataFrame) -> dict:
    """SPEC 4.1：沿用comparable_trial_variance.dimson_ir()的主動報酬建構法
    （日頻主動報酬=策略日報酬−Dimson beta(lag 0/1/2)×0050日報酬），
    顯著性檢定改用portfolio_backtest_v2.alpha_significance()同一套
    Newey-West HAC(maxlags=5)+Dimson beta迴歸（兩者beta_dimson建構完全
    一致，alpha_significance()的截距項p值就是對「主動報酬均值是否顯著
    不為0」的HAC檢定，等價於對IR顯著性的檢定）。兩尾p值依裁示要求換算
    成單尾（H1: IR>0，方向由候選既有VAL期表現事前決定，不依看到本次
    數字後才選）。"""
    ir_info = dimson_ir(equity_curve, "FULL_2007_2014")
    alpha_info = pbv2.alpha_significance(equity_curve, market_df)
    two_tailed_p = alpha_info["alpha_pvalue"]
    alpha_positive = alpha_info["alpha_ann_pct"] > 0
    if two_tailed_p == two_tailed_p:  # not NaN
        one_tailed_p = two_tailed_p / 2 if alpha_positive else 1 - two_tailed_p / 2
    else:
        one_tailed_p = float("nan")
    return {
        "ir_annualized": ir_info.get("ir_annualized"), "ir_daily": ir_info.get("ir_daily"),
        "beta_dimson": alpha_info["beta"], "alpha_ann_pct": alpha_info["alpha_ann_pct"],
        "n_obs": alpha_info["n_days"],
        "two_tailed_p": two_tailed_p, "one_tailed_p": one_tailed_p,
        "direction_positive": alpha_positive,
        "passes_bonferroni_0025": bool(one_tailed_p == one_tailed_p and one_tailed_p < BONFERRONI_ONE_TAIL_ALPHA),
    }


def run_single_shot(strategy_mod, data, market_df, industry_map, liquidity, label: str) -> dict:
    """執行一次完整2007-2014回測並產出全部裁示要求的統計量。**呼叫這個
    函式並印出/使用其回傳值，即視為已消耗這次單發檢定資格（裁示第3點）。**
    """
    signal_fn = strategy_mod.make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=OOS_START, end_date=OOS_END,
                          max_positions=strategy_mod.TOP_N, rebalance_every_n_days=strategy_mod.REBALANCE_DAYS,
                          commission_discount=0.18, instrument_type="normal",
                          book_name=f"single_shot_2007_2014_{label}")
    result = run_backtest(signal_fn, data, market_df, cfg)
    holdout.assert_no_holdout_leakage(result.trades, date_col="date", context=f"single_shot {label}")
    holdout.assert_no_holdout_leakage(result.equity_curve, date_col="date", context=f"single_shot {label} equity")

    eq_curve = result.equity_curve
    ir_test = _one_tailed_ir_test(eq_curve, market_df)

    mdd_full = compute_mdd(eq_curve["equity"])
    eq_for_segment = eq_curve[["date", "equity"]]
    mdd_2008 = segment_mdd(eq_for_segment, "2008-01-01", "2008-12-31")
    mdd_2008_pass = bool(mdd_2008 == mdd_2008 and mdd_2008 > MDD_2008_BENCHMARK_PCT)
    mdd_full_pass = bool(mdd_full == mdd_full and mdd_full > -50.0)

    cand_return_full = result.total_return_pct
    bh_0050_full = pbv2.buy_and_hold_index_pct(market_df, OOS_START, OOS_END)

    mkt_0050 = pbv2._load_0050_total_return_series()
    yearly = _yearly_table(eq_curve, mkt_0050)

    eq_indexed = eq_curve.set_index("date")["equity"]
    sub1_eq = eq_indexed[(eq_indexed.index >= SUB1_START) & (eq_indexed.index <= SUB1_END)]
    sub2_eq = eq_indexed[(eq_indexed.index >= SUB2_START) & (eq_indexed.index <= SUB2_END)]
    sub1 = {"return_pct": round(_period_return_pct(sub1_eq), 2) if len(sub1_eq) >= 2 else None,
            "mdd_pct": round(segment_mdd(eq_for_segment, SUB1_START, SUB1_END), 2),
            "0050_return_pct": round(pbv2.buy_and_hold_index_pct(market_df, SUB1_START, SUB1_END), 2)}
    sub2 = {"return_pct": round(_period_return_pct(sub2_eq), 2) if len(sub2_eq) >= 2 else None,
            "mdd_pct": round(segment_mdd(eq_for_segment, SUB2_START, SUB2_END), 2),
            "0050_return_pct": round(pbv2.buy_and_hold_index_pct(market_df, SUB2_START, SUB2_END), 2)}

    gate_ir_pass = ir_test["passes_bonferroni_0025"]
    overall_pass = bool(gate_ir_pass and mdd_2008_pass and mdd_full_pass)

    out = {
        "label": label, "period": [OOS_START, OOS_END], "n_trades": result.n_trades,
        "candidate_return_pct_2007_2014": round(cand_return_full, 2),
        "benchmark_0050_return_pct_2007_2014": round(bh_0050_full, 2),
        "ir_test": ir_test,
        "mdd_2008_pct": round(mdd_2008, 2), "mdd_2008_benchmark_pct": MDD_2008_BENCHMARK_PCT,
        "mdd_2008_strictly_better_than_0050": mdd_2008_pass,
        "mdd_full_period_pct": round(mdd_full, 2), "mdd_full_period_over_neg50": mdd_full_pass,
        "yearly_table": yearly,
        "sub_period_2007_2009_reference_only": sub1,
        "sub_period_2010_2014_reference_only": sub2,
        "gate_ir_pass": gate_ir_pass, "gate_mdd_2008_pass": mdd_2008_pass, "gate_mdd_full_pass": mdd_full_pass,
        "overall_verdict": "PASS" if overall_pass else "FAIL",
    }
    print(f"\n========== {label} 2007-2014單發檢定結果 ==========", flush=True)
    print(f"  候選報酬={cand_return_full:+.2f}%  0050含息總報酬={bh_0050_full:+.2f}%  trades={result.n_trades}", flush=True)
    print(f"  IR(年化)={ir_test['ir_annualized']:.4f}  beta_dimson={ir_test['beta_dimson']:+.3f}  "
          f"單尾p={ir_test['one_tailed_p']:.4f}（<{BONFERRONI_ONE_TAIL_ALPHA}才過）："
          f"{'PASS' if gate_ir_pass else 'FAIL'}", flush=True)
    print(f"  2008年MDD={mdd_2008:.2f}%（須嚴格優於{MDD_2008_BENCHMARK_PCT}%）："
          f"{'PASS' if mdd_2008_pass else 'FAIL'}", flush=True)
    print(f"  2007-2014全段MDD={mdd_full:.2f}%（須>-50%）：{'PASS' if mdd_full_pass else 'FAIL'}", flush=True)
    print(f"  **綜合判定：{out['overall_verdict']}**", flush=True)
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    print("=== 資料載入（可安全反覆測試的部分）===", flush=True)
    data, market_df, industry_map, liquidity, n_common = load_common_stock_data_2007_2014()

    print(f"\n{'='*70}\n即將執行考.一單發檢定正式回測——此行以後印出的任何統計數字，\n"
          f"依裁示視為已消耗這次only-once資格，不得重跑。\n{'='*70}", flush=True)

    results = {}
    results["f52w_high_portfolio_v1"] = run_single_shot(f52w_mod, data, market_df, industry_map, liquidity,
                                                          "f52w_high_portfolio_v1")
    results["dividend_yield_portfolio_v1"] = run_single_shot(div_mod, data, market_df, industry_map, liquidity,
                                                               "dividend_yield_portfolio_v1")

    out = {
        "generated_for": "考.一（2026-09-25裁示【2007-2014單發檢定放行＋daily_price日期欄位緊急查核】）",
        "spec": "SINGLE_SHOT_2007_2014_SPEC.md（含2.1節宇.二修訂一／4.2節規.五修訂）",
        "n_common_stock_universe": n_common, "n_usable_data": len(data),
        "results": results,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    return out


if __name__ == "__main__":
    main()
