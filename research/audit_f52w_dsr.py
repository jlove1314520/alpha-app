# -*- coding: utf-8 -*-
"""審.一步驟4（總司令2026-09-23裁示【修正alpha量尺＋f52w補完審查＋
稽核續跑】）：以目前N_valid計算f52w VAL期的DSR(Deflated Sharpe Ratio)，
並列Bonferroni。事前宣告：DSR未過就不得核准，不因p值好看放寬。

用法：python research/audit_f52w_dsr.py
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
from scipy import stats as sstats

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2
from f52w_high_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn

from candidate_report import (
    CandidateStats, deflated_sharpe, trials_sharpe_variance, default_n_trials, DSR_MIN,
)

OUT_JSON = Path(__file__).parent / "data" / "audit_f52w_dsr.json"


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_f52w_dsr")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    start, end = "2021-01-01", holdout.VAL_END
    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="f52w_dsr_val")
    result = run_backtest(signal_fn, data, market_df, cfg)

    daily_ret = result.equity_curve["equity"].pct_change().dropna()
    sharpe_daily = float(daily_ret.mean() / daily_ret.std())
    skew = float(sstats.skew(daily_ret, bias=False))
    kurt = float(sstats.kurtosis(daily_ret, bias=False, fisher=False))  # 非超額峰態，常態=3.0
    n_obs = len(daily_ret)

    print(f"VAL期daily return: n={n_obs}, sharpe(日)={sharpe_daily:.4f}"
          f"（年化約{sharpe_daily*np.sqrt(252):.3f}）, skew={skew:.4f}, kurtosis(非超額)={kurt:.4f}", flush=True)

    cstats = CandidateStats(sharpe=sharpe_daily, n_obs=n_obs, skew=skew, kurtosis=kurt, freq_label="每日")

    n_trials, n_src = default_n_trials()
    var_v, n_v = trials_sharpe_variance()
    print(f"N_trials={n_trials}（來源：{n_src}）", flush=True)
    print(f"試驗間Sharpe變異數V={var_v}（樣本數={n_v}）", flush=True)

    out = {"sharpe_daily": sharpe_daily, "n_obs": n_obs, "skew": skew, "kurtosis": kurt,
           "n_trials": n_trials, "n_trials_source": n_src, "var_sr_trials": var_v, "n_v": n_v}

    if var_v is None:
        print(f"\n**DSR無法計算**：TRIALS_REGISTRY.jsonl只有{n_v}筆已登記Sharpe，"
              f"需要>=2筆才能估變異數V。依裁示「事前宣告：DSR未過就不得核准」，"
              f"算不出來同樣視為未過，不得核准AWAITING_REVIEW。", flush=True)
        out["dsr"] = None
        out["dsr_admissible"] = False
        out["blocked_reason"] = f"TRIALS_REGISTRY.jsonl只有{n_v}筆已登記Sharpe，不足以估變異數V"
    else:
        dsr_res = deflated_sharpe(cstats, n_trials, var_v)
        admissible = dsr_res["dsr"] >= DSR_MIN
        print(f"\nDSR={dsr_res['dsr']:.4f}（門檻{DSR_MIN}，{'通過' if admissible else '未通過'}）", flush=True)
        print(f"觀測Sharpe(日)={dsr_res['sr_observed']:.4f}  SR0門檻(N={n_trials})={dsr_res['sr0_threshold']:.4f}", flush=True)
        out["dsr"] = dsr_res
        out["dsr_admissible"] = admissible

    # Bonferroni並列（跟trial_registry.py既有慣例一致：alpha=0.05/N）
    bonf_alpha = 0.05 / n_trials
    from portfolio_backtest_v2 import alpha_significance
    alpha_res = alpha_significance(result.equity_curve, market_df)
    bonf_pass = alpha_res["alpha_pvalue"] == alpha_res["alpha_pvalue"] and alpha_res["alpha_pvalue"] < bonf_alpha
    print(f"\nBonferroni：alpha p={alpha_res['alpha_pvalue']:.6f} vs 校正門檻{bonf_alpha:.6f}"
          f"（N={n_trials}）：{'通過' if bonf_pass else '未通過'}", flush=True)
    out["bonferroni_alpha_threshold"] = bonf_alpha
    out["bonferroni_pass"] = bonf_pass
    out["alpha_pvalue"] = alpha_res["alpha_pvalue"]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
