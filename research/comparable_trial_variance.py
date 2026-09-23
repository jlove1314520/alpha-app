# -*- coding: utf-8 -*-
"""尺.二第4點（總司令2026-09-23裁示【DSR單位錯誤修正＋f52w改用資訊
比率重審＋2008延伸】）：V的來源改為「可比試驗」——台股多頭組合層、
同一VAL期間、有存equity_curve的既有腳本，每筆重算日頻資訊比率
（策略日報酬 − Dimson beta × 0050日報酬，再算IR=mean/std），取這些IR
的變異數當V。可比試驗<10筆時，不得只報單一DSR，一律附V敏感度表
（年化標準差0.2/0.3/0.4/0.5/0.75）。

**誠實揭露範圍**：本次納入4支已有現成equity_curve產生路徑、資料管線
單純的腳本（f52w_high_portfolio_v1／dividend_yield_portfolio_v1／
pead_portfolio_v1／run_score_backtest）。`piotroski_fscore_gate_v1.py`
（需要先pick_threshold動態選F-score門檻）與`run_value_board_v2_pit_
backtest.py`（PIT財報board建構管線）因資料/訊號建構管線較特殊，本次
未納入，誠實記錄為「未納入」而非硬湊數字——可比試驗數4<10，一律附
V敏感度表，不得只報單一DSR，這正是裁示原文預期的<10情境。
`portfolio_backtest_v2`因是多權重模式組合(6模式x2頻率)沒有單一
代表性equity_curve，同樣未納入，避免主觀挑一個模式當代表。

用法：python research/comparable_trial_variance.py
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
import statsmodels.api as sm

from backtest.engine import BacktestConfig, run_backtest
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2
from portfolio_backtest_v2 import _load_0050_total_return_series, DIMSON_LAGS

OUT_JSON = Path(__file__).parent / "data" / "comparable_trial_variance.json"
V_GRID_ANN_SD = (0.2, 0.3, 0.4, 0.5, 0.75)  # 裁示原文指定的敏感度網格
MIN_COMPARABLE_FOR_POINT_ESTIMATE = 10
VAL_START, VAL_END = "2021-01-01", holdout.VAL_END


def dimson_ir(equity_curve: pd.DataFrame, label: str) -> dict:
    mkt = _load_0050_total_return_series()
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    lag_cols = {f"mkt_lag{lag}": mkt_ret.shift(lag) for lag in DIMSON_LAGS}
    merged = pd.concat([net_ret, pd.DataFrame(lag_cols)], axis=1, join="inner").dropna()
    lag_names = list(lag_cols.keys())
    if len(merged) < 30:
        return {"label": label, "ok": False, "reason": f"樣本不足(n={len(merged)})"}

    X = sm.add_constant(merged[lag_names])
    model = sm.OLS(merged["net_return"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    beta_dimson = float(model.params[lag_names].sum())

    active_ret = merged["net_return"] - beta_dimson * merged["mkt_lag0"]
    ir_daily = float(active_ret.mean() / active_ret.std())
    return {
        "label": label, "ok": True, "n_obs": len(merged), "beta_dimson": beta_dimson,
        "ir_daily": ir_daily, "ir_annualized": ir_daily * float(np.sqrt(252)),
    }


def get_f52w_val_equity():
    from f52w_high_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=VAL_START, end_date=VAL_END, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="comparable_f52w")
    return run_backtest(signal_fn, data, market_df, cfg).equity_curve


def get_dividend_val_equity():
    from dividend_yield_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=VAL_START, end_date=VAL_END, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="comparable_dividend")
    return run_backtest(signal_fn, data, market_df, cfg).equity_curve


def get_pead_val_equity():
    from pead_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=VAL_START, end_date=VAL_END, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="comparable_pead")
    return run_backtest(signal_fn, data, market_df, cfg).equity_curve


def get_score_topn_val_equity():
    import run_score_backtest as m
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    cfg = BacktestConfig(start_date=VAL_START, end_date=VAL_END, max_positions=m.TOP_N,
                          book_name="comparable_score_topn")
    return run_backtest(m.make_score_signal_fn(industry_map, m.TOP_N), data, market_df, cfg).equity_curve


def comparable_trial_variance() -> tuple[float | None, int, list[dict]]:
    """回傳(V或None, 可比試驗數, 逐筆紀錄)。V是IR的樣本變異數（IR已經是
    「相對0050的Dimson beta調整後主動報酬」尺度，不是原始Sharpe，這是
    審.二「DSR應檢定超額報酬而非原始Sharpe」的同一個精神延伸到V本身）。
    """
    getters = {
        "f52w_high_portfolio_v1": get_f52w_val_equity,
        "dividend_yield_portfolio_v1": get_dividend_val_equity,
        "pead_portfolio_v1": get_pead_val_equity,
        "run_score_backtest": get_score_topn_val_equity,
    }
    records = []
    for label, getter in getters.items():
        eq = getter()
        rec = dimson_ir(eq, label)
        records.append(rec)
        print(f"  {label}: {rec}", flush=True)

    ok_records = [r for r in records if r["ok"]]
    irs = [r["ir_daily"] for r in ok_records]
    if len(irs) < 2:
        return None, len(irs), records
    mean_ir = sum(irs) / len(irs)
    var_ir = sum((x - mean_ir) ** 2 for x in irs) / (len(irs) - 1)
    return var_ir, len(irs), records


def v_sensitivity_table(n_trials: int) -> list[dict]:
    """裁示原文指定的V敏感度表：年化標準差0.2/0.3/0.4/0.5/0.75，
    各自算出SR0門檻（日頻與年化並列）。"""
    from selection_bias_ledger import expected_max_sharpe

    rows = []
    for sd_ann in V_GRID_ANN_SD:
        v_daily = (sd_ann ** 2) / 252
        sr0_daily = expected_max_sharpe(n_trials, v_daily)
        rows.append({
            "ann_sd": sd_ann, "v_daily": v_daily,
            "sr0_daily": sr0_daily, "sr0_annualized": sr0_daily * float(np.sqrt(252)),
        })
    return rows


if __name__ == "__main__":
    v, n, records = comparable_trial_variance()
    print(f"\n可比試驗數={n}（{'<' if n < MIN_COMPARABLE_FOR_POINT_ESTIMATE else '>='}"
          f"{MIN_COMPARABLE_FOR_POINT_ESTIMATE}，"
          f"{'需附V敏感度表，不得只報單一DSR' if n < MIN_COMPARABLE_FOR_POINT_ESTIMATE else '可用點估計'}）")
    if v is not None:
        print(f"V(可比試驗IR變異數，日頻)={v:.8f}")

    out = {"comparable_variance": v, "n_comparable": n, "records": records}
    if n < MIN_COMPARABLE_FOR_POINT_ESTIMATE:
        # n_trials用default_n_trials()目前的值，供敏感度表使用
        from candidate_report import default_n_trials
        n_trials, n_src = default_n_trials()
        sens = v_sensitivity_table(n_trials)
        out["sensitivity_table"] = sens
        out["sensitivity_n_trials"] = n_trials
        out["sensitivity_n_trials_source"] = n_src
        print(f"\nV敏感度表（N_trials={n_trials}）：")
        for row in sens:
            print(f"  年化SD={row['ann_sd']:.2f} → SR0(年化)={row['sr0_annualized']:.4f} "
                  f"SR0(日)={row['sr0_daily']:.6f}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}")
