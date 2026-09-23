# -*- coding: utf-8 -*-
"""審.三（總司令2026-09-24裁示【value_board 翻案處理＋轉向.一 候選名單
定案＋FinLab 借鏡登記】）：value_board_v2（#390）便宜重審，不重跑完整
九關。

1. VAL期對0050含息總報酬的資訊比率（Dimson beta，日頻＋年化）。
2. 納入comparable_trial_variance重算可比試驗V，DSR（附V敏感度表）。
3. 資料成本估算（不執行抓取）：把value_board納入2007-2014單發檢定需要
   哪些資料、API呼叫次數、以目前FinMind額度需幾小時，與資料.一是否可
   共用快取。

用法：python research/audit_value_board_v2_ir_dsr.py
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd
from scipy import stats as sstats

from backtest.engine import BacktestConfig, run_backtest
from finmind_client import load_dev
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, START_DATE as F52W_START_DATE
from score import load_industry_map
from score_v2 import compute_scores_v2
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2
from portfolio_backtest_v2 import _load_0050_total_return_series
from comparable_trial_variance import dimson_ir, v_sensitivity_table, MIN_COMPARABLE_FOR_POINT_ESTIMATE
from run_value_board_v2_pit_backtest import (
    TOP_N, REBALANCE_DAYS, VALUE_BOARD_SAMPLE_SIZE, START_DATE as VB_START_DATE,
    liquidity_ranked_universe_ids, eligible_for_ranking_v2,
)

OUT_JSON = Path(__file__).parent / "data" / "audit_value_board_v2_ir_dsr.json"
CACHE_PATH = Path(__file__).parent / "data" / "backtests" / f"value_board_v2_sample_cache_liquidity{VALUE_BOARD_SAMPLE_SIZE}.pkl"
CHECKPOINT_PATH = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"


def make_score_v2_signal_fn(industry_map, start_date, top_n=TOP_N):
    def signal_fn(price_data, as_of, market_df):
        cs = compute_scores_v2(as_of, price_data, industry_map, start_date)
        cs = eligible_for_ranking_v2(cs)
        if cs.empty or "total_score" not in cs.columns:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(top_n)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


def main():
    out = {}

    # ── 讀取既有本機快取，零額外API呼叫（FinMind目前額度封鎖中）──────────
    print(f"讀取本機快取 {CACHE_PATH}（不觸發任何網路請求）...", flush=True)
    with open(CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"  {len(data)} 檔可用（來自流動性前{VALUE_BOARD_SAMPLE_SIZE}檔樣本）", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", VB_START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_value_board_v2_ir_dsr")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    signal_fn = make_score_v2_signal_fn(industry_map, VB_START_DATE, TOP_N)

    # ── 1. VAL期IR（Dimson beta，日頻+年化）─────────────────────────────
    val_start, val_end = "2021-01-01", holdout.VAL_END
    cfg = BacktestConfig(start_date=val_start, end_date=val_end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_ir_dsr_val")
    val_result = run_backtest(signal_fn, data, market_df, cfg)
    val_ir = dimson_ir(val_result.equity_curve, "value_board_v2_VAL")
    print(f"1. VAL期IR：{val_ir}", flush=True)
    out["val_ir"] = val_ir

    # ── 2. DSR（可比試驗V點估計 + 敏感度表）─────────────────────────────
    cached_path = Path(__file__).parent / "data" / "comparable_trial_variance.json"
    if cached_path.exists():
        print("\n2. 讀取已有的可比試驗V快取（尺.二/審.二本輪稍早已跑過）...", flush=True)
        cached = json.loads(cached_path.read_text(encoding="utf-8"))
        v_comp, n_comp = cached["comparable_variance"], cached["n_comparable"]
    else:
        from comparable_trial_variance import comparable_trial_variance
        v_comp, n_comp, _ = comparable_trial_variance()
    out["comparable_v"] = v_comp
    out["n_comparable"] = n_comp

    from candidate_report import CandidateStats, deflated_sharpe, default_n_trials

    mkt = _load_0050_total_return_series()
    mkt_ret = mkt.pct_change()
    net_ret = val_result.equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt")], axis=1, join="inner").dropna()
    active = merged["net_return"] - val_ir["beta_dimson"] * merged["mkt"]
    skew = float(sstats.skew(active, bias=False))
    kurt = float(sstats.kurtosis(active, bias=False, fisher=False))

    n_trials, n_src = default_n_trials()
    print(f"\nN_trials={n_trials}（{n_src}）", flush=True)

    dsr_result = None
    if n_comp is not None and n_comp >= 2 and val_ir.get("ok"):
        cstats = CandidateStats(sharpe=val_ir["ir_daily"], n_obs=val_ir["n_obs"],
                                 skew=skew, kurtosis=kurt, periods_per_year=252)
        dsr_result = deflated_sharpe(cstats, n_trials, v_comp, var_periods_per_year=252)
        print(f"事前宣告判準的DSR（可比試驗V點估計）：{dsr_result}", flush=True)
    out["dsr_point_estimate"] = dsr_result
    out["dsr_admissible"] = bool(dsr_result and dsr_result["dsr"] >= 0.95)

    if val_ir.get("ok") and (n_comp is None or n_comp < MIN_COMPARABLE_FOR_POINT_ESTIMATE):
        sens = v_sensitivity_table(n_trials)
        print(f"\n可比試驗數{n_comp}<{MIN_COMPARABLE_FOR_POINT_ESTIMATE}，附V敏感度表（僅供參考）：", flush=True)
        for row in sens:
            v_d = row["v_daily"]
            cstats_s = CandidateStats(sharpe=val_ir["ir_daily"], n_obs=val_ir["n_obs"],
                                       skew=skew, kurtosis=kurt, periods_per_year=252)
            dsr_s = deflated_sharpe(cstats_s, n_trials, v_d, var_periods_per_year=252)
            row["dsr_at_this_v"] = dsr_s["dsr"]
            print(f"  年化SD={row['ann_sd']:.2f}: SR0(日)={row['sr0_daily']:.6f} DSR={dsr_s['dsr']:.4f}", flush=True)
        out["sensitivity_table"] = sens

    # ── 3. 資料成本估算（不執行抓取，純本機集合運算+既有量測外推）──────
    print("\n3. 資料成本估算（不執行任何抓取）...", flush=True)
    vb_ids = set(liquidity_ranked_universe_ids(VALUE_BOARD_SAMPLE_SIZE))
    f52w_ids = set(sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED))
    overlap_with_f52w_sample = vb_ids & f52w_ids

    fetched_by_data_yi = set()
    if CHECKPOINT_PATH.exists():
        ck = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        fetched_by_data_yi = set(ck.get("fetched_ids", []))
    overlap_already_fetched = vb_ids & fetched_by_data_yi
    need_fresh_fetch = vb_ids - fetched_by_data_yi

    # 每檔API呼叫數估計：value_board_v2跟f52w同樣呼叫factor_ic.py::
    # load_sample_with_factors()（adjust.py的TaiwanStockPrice+TaiwanStockDividend
    # ＋factors.py的InstitutionalInvestorsBuySell/MarginPurchaseShortSale(x3)/PER，
    # 皆已由load_dev()走parquet快取，month_revenue_pit()等其餘score_v2.py因子在
    # prepare_factors()階段一併取得，不額外對FinMind發API），跟資料.一已實測的
    # 「約13-15次/檔」屬同一條管線，直接沿用該範圍，不重新臆測。
    CALLS_PER_STOCK_LOW, CALLS_PER_STOCK_HIGH = 13, 15
    est_calls_low = len(need_fresh_fetch) * CALLS_PER_STOCK_LOW
    est_calls_high = len(need_fresh_fetch) * CALLS_PER_STOCK_HIGH

    # 速率估計：沿用資料.一三輪實測「每輪(受FinMind每小時額度硬性限制)約
    # 40-45檔」，每輪約2小時（含封鎖冷卻等待）。
    STOCKS_PER_ROUND_LOW, STOCKS_PER_ROUND_HIGH = 40, 45
    HOURS_PER_ROUND = 2
    rounds_low = len(need_fresh_fetch) / STOCKS_PER_ROUND_HIGH
    rounds_high = len(need_fresh_fetch) / STOCKS_PER_ROUND_LOW
    hours_low = rounds_low * HOURS_PER_ROUND
    hours_high = rounds_high * HOURS_PER_ROUND

    cost = {
        "value_board_universe_size": len(vb_ids),
        "overlap_with_f52w_300sample": len(overlap_with_f52w_sample),
        "already_fetched_by_資料一_checkpoint": len(overlap_already_fetched),
        "need_fresh_fetch": len(need_fresh_fetch),
        "calls_per_stock_range": [CALLS_PER_STOCK_LOW, CALLS_PER_STOCK_HIGH],
        "est_total_api_calls_range": [est_calls_low, est_calls_high],
        "est_rounds_range": [round(rounds_low, 1), round(rounds_high, 1)],
        "est_hours_range": [round(hours_low, 1), round(hours_high, 1)],
        "note": (
            "資料.一與value_board_v2共用同一個FinMind帳號額度，兩者是序列消耗"
            "同一個每小時配額，不是可平行加速的獨立資源——若兩者都要抓2007-2014，"
            "總所需輪次≈(資料.一剩餘輪次)+(本估算輪次)，不能相加後除以2。"
            "所需資料類型：TaiwanStockPrice(價格還原)、TaiwanStockDividend(還原用)、"
            "TaiwanStockInstitutionalInvestorsBuySell、TaiwanStockMarginPurchase"
            "ShortSale、TaiwanStockPER、TaiwanStockMonthRevenue——與f52w/資料.一"
            "完全相同的管線(factor_ic.load_sample_with_factors)，只是股票清單"
            "(流動性前500 vs 隨機300)幾乎不重疊(僅49/500重疊f52w樣本，僅"
            f"{len(overlap_already_fetched)}/500已被資料.一目前132/300進度覆蓋)，"
            "財報PIT對齊沿用pit.py既有邏輯，非額外新建。"
        ),
    }
    out["data_cost_estimate"] = cost
    print(f"  value_board宇宙500檔：與f52w 300樣本重疊{len(overlap_with_f52w_sample)}檔，"
          f"已被資料.一目前進度覆蓋{len(overlap_already_fetched)}檔，"
          f"需全新抓取{len(need_fresh_fetch)}檔", flush=True)
    print(f"  估計API呼叫數：{est_calls_low:,}~{est_calls_high:,}次", flush=True)
    print(f"  估計輪次：{rounds_low:.1f}~{rounds_high:.1f}輪，估計耗時：{hours_low:.1f}~{hours_high:.1f}小時"
          f"（與資料.一序列共用同一FinMind額度，非平行加速）", flush=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)
    return out


if __name__ == "__main__":
    main()
