# -*- coding: utf-8 -*-
"""審.二（總司令2026-09-23裁示【DSR單位錯誤修正＋f52w改用資訊比率重審
＋2008延伸】）：f52w用資訊比率重審。

1. f52w對0050含息總報酬的日頻主動報酬(策略-Dimson beta x 0050)與
   資訊比率，TRAIN/VAL/全期分別列出。
2. 用尺.二的方法做DSR(附V敏感度表)。事前宣告判準：可比試驗V點估計
   算出DSR>=0.95才算通過，敏感度表僅參考不得挑有利格。
3. 全期逐年表：f52w vs 0050含息總報酬，逐年報酬、逐年MDD。
4. 真正的集中度檢驗：電子+半導體類合計上限50%名額(TOP_N=20 -> 10)，
   重跑VAL。

用法：python research/audit_f52w_ir_review.py
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

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2
from portfolio_backtest_v2 import _load_0050_total_return_series
from f52w_high_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn, compute_composite_at_date, _eligible_single_factor
from comparable_trial_variance import dimson_ir, comparable_trial_variance, v_sensitivity_table, MIN_COMPARABLE_FOR_POINT_ESTIMATE

OUT_JSON = Path(__file__).parent / "data" / "audit_f52w_ir_review.json"
ELECTRONICS_KEYWORDS = ("半導體", "電子", "光電", "電腦", "通信網路")
ELECTRONICS_CAP_FRACTION = 0.5  # 電子+半導體合計上限50%名額


def make_electronics_capped_signal_fn(industry_map, liquidity):
    cap = int(TOP_N * ELECTRONICS_CAP_FRACTION)  # 10

    def signal_fn(price_data, as_of, market_df):
        cs = _eligible_single_factor(compute_composite_at_date(as_of, price_data, industry_map, liquidity))
        picks, electronics_n = [], 0
        for _, row in cs.iterrows():
            if len(picks) >= TOP_N:
                break
            ind = row["industry"] if pd.notna(row["industry"]) else "未知"
            is_electronics = any(k in ind for k in ELECTRONICS_KEYWORDS)
            if is_electronics and electronics_n >= cap:
                continue
            picks.append(row["stock_id"])
            if is_electronics:
                electronics_n += 1
        return {sid: 1.0 for sid in picks}
    return signal_fn


def run_period(signal_fn, data, market_df, start, end, book_name):
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name=book_name)
    return run_backtest(signal_fn, data, market_df, cfg)


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_f52w_ir_review")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    signal_fn = make_signal_fn(industry_map, liquidity)

    out = {}

    # ── 1. TRAIN/VAL/全期 IR ──────────────────────────────────────────
    periods = {
        "TRAIN": ("2015-01-01", holdout.TRAIN_END),
        "VALIDATION": ("2021-01-01", holdout.VAL_END),
        "FULL": ("2015-01-01", holdout.VAL_END),
    }
    ir_by_period = {}
    equity_full = None
    for label, (start, end) in periods.items():
        result = run_period(signal_fn, data, market_df, start, end, f"f52w_ir_{label}")
        ir = dimson_ir(result.equity_curve, label)
        ir_by_period[label] = ir
        print(f"1. {label}: {ir}", flush=True)
        if label == "FULL":
            equity_full = result.equity_curve
    out["ir_by_period"] = ir_by_period

    # ── 2. DSR（可比試驗V + 敏感度表）──────────────────────────────────
    cached_path = Path(__file__).parent / "data" / "comparable_trial_variance.json"
    if cached_path.exists():
        print("\n2. 讀取已有的可比試驗V快取（comparable_trial_variance.py本輪稍早已跑過）...", flush=True)
        cached = json.loads(cached_path.read_text(encoding="utf-8"))
        v_comp, n_comp, comp_records = cached["comparable_variance"], cached["n_comparable"], cached["records"]
    else:
        print("\n2. 計算可比試驗V...", flush=True)
        v_comp, n_comp, comp_records = comparable_trial_variance()
    out["comparable_v"] = v_comp
    out["n_comparable"] = n_comp
    out["comparable_records"] = comp_records

    val_ir = ir_by_period["VALIDATION"]
    from candidate_report import CandidateStats, deflated_sharpe, default_n_trials
    from scipy import stats as sstats

    # VAL期主動報酬序列的skew/kurtosis（DSR需要，不能只有mean/std）
    mkt = _load_0050_total_return_series()
    mkt_ret = mkt.pct_change()
    val_result = run_period(signal_fn, data, market_df, "2021-01-01", holdout.VAL_END, "f52w_ir_val_for_dsr")
    net_ret = val_result.equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt")], axis=1, join="inner").dropna()
    active = merged["net_return"] - val_ir["beta_dimson"] * merged["mkt"]
    skew = float(sstats.skew(active, bias=False))
    kurt = float(sstats.kurtosis(active, bias=False, fisher=False))

    n_trials, n_src = default_n_trials()
    print(f"\nN_trials={n_trials}（{n_src}）", flush=True)

    dsr_result = None
    if n_comp is not None and n_comp >= 2:
        cstats = CandidateStats(sharpe=val_ir["ir_daily"], n_obs=val_ir["n_obs"],
                                 skew=skew, kurtosis=kurt, periods_per_year=252)
        dsr_result = deflated_sharpe(cstats, n_trials, v_comp, var_periods_per_year=252)
        print(f"事前宣告判準的DSR（可比試驗V點估計）：{dsr_result}", flush=True)
    out["dsr_point_estimate"] = dsr_result
    out["dsr_admissible"] = bool(dsr_result and dsr_result["dsr"] >= 0.95)

    if n_comp is None or n_comp < MIN_COMPARABLE_FOR_POINT_ESTIMATE:
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

    # ── 3. 全期逐年表 ────────────────────────────────────────────────
    eq = equity_full.set_index("date")["equity"]
    bh = _load_0050_total_return_series()
    yearly = []
    for yr in range(2015, 2025):
        eq_w = eq[(eq.index >= f"{yr}-01-01") & (eq.index <= f"{yr}-12-31")]
        bh_w = bh[(bh.index >= f"{yr}-01-01") & (bh.index <= f"{yr}-12-31")]
        row = {"year": yr}
        if len(eq_w) >= 2:
            row["f52w_return_pct"] = float(eq_w.iloc[-1] / eq_w.iloc[0] - 1) * 100
            running_max = eq_w.cummax()
            row["f52w_mdd_pct"] = float(((eq_w - running_max) / running_max).min() * 100)
        if len(bh_w) >= 2:
            row["bh_0050_return_pct"] = float(bh_w.iloc[-1] / bh_w.iloc[0] - 1) * 100
            running_max_bh = bh_w.cummax()
            row["bh_0050_mdd_pct"] = float(((bh_w - running_max_bh) / running_max_bh).min() * 100)
        yearly.append(row)
        print(f"3. {yr}: f52w={row.get('f52w_return_pct', float('nan')):+.2f}%/"
              f"MDD={row.get('f52w_mdd_pct', float('nan')):.2f}%  "
              f"0050={row.get('bh_0050_return_pct', float('nan')):+.2f}%/"
              f"MDD={row.get('bh_0050_mdd_pct', float('nan')):.2f}%", flush=True)
    out["yearly_table"] = yearly

    # ── 4. 電子+半導體合計上限50%，VAL重跑 ──────────────────────────
    capped_fn = make_electronics_capped_signal_fn(industry_map, liquidity)
    capped_result = run_period(capped_fn, data, market_df, "2021-01-01", holdout.VAL_END, "f52w_electronics_capped_val")
    capped_alpha = pbv2.alpha_significance(capped_result.equity_curve, market_df)
    capped_bh = pbv2.buy_and_hold_index_pct(market_df, "2021-01-01", holdout.VAL_END)
    out["electronics_capped_val"] = {
        "return_pct": capped_result.total_return_pct, "mdd_pct": capped_result.max_drawdown_pct,
        "alpha_ann_pct": capped_alpha["alpha_ann_pct"], "beta_dimson": capped_alpha["beta"],
        "alpha_pvalue": capped_alpha["alpha_pvalue"], "buy_and_hold_index_pct": capped_bh,
        "n_trades": capped_result.n_trades,
    }
    print(f"\n4. 電子+半導體上限50%(cap={int(TOP_N*ELECTRONICS_CAP_FRACTION)}) VAL重跑："
          f"報酬={capped_result.total_return_pct:+.2f}% alpha={capped_alpha['alpha_ann_pct']:+.2f}%"
          f"(p={capped_alpha['alpha_pvalue']:.4f}) 大盤={capped_bh:+.2f}%", flush=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
