"""補對照組(a)：加碼隨機控制組重抽次數 15→100，只針對`portfolio_backtest_v2.py`
VALIDATION期已完成的12組合中最佳兩組（percentile已達15/15滿分100.0的其中兩組，
IC加權/季頻，A/B兩因子版本），確認N=15的100.0percentile不是重抽次數太少造成的
天花板假象。

背景：2026-08-26暫停規則生效（TW軌`PORTFOLIO_STRATEGY_SPEC.md`待使用者確認前，
禁止新的單因子試驗），但`MARATHON_PROTOCOL.md`第0節明確允許「補參數敏感度、補
對照組」這類既有組合策略回測的補充工作，不需要等待使用者對(a)換更大樣本/(b)
train-only嚴格樣本外這兩個更高成本選項的裁示。這輪(第197輪)屬於這類允許範圍內
的工作——不新增因子、不改SPEC規則、不重跑成本敏感度（1x/2x/3x沿用既有
`data/portfolio_backtest_v2_results.csv`的數字，未變動），只單純把隨機控制組
重抽次數從15次拉高到100次，讓percentile統計量更可信（N=15時，個別隨機草案
只要贏一次就會把percentile拉到93.3%，解析度太粗）。

零額外API呼叫：`load_sample_with_factors`命中既有快取（跟`portfolio_backtest_v2.py`
main()同一批資料）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from portfolio_backtest_v2 import (
    _trend_regime_series, _liquidity_proxy_series, run_one,
)
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

N_RANDOM = 100
TARGET_COMBOS = [
    ("A_4pass", "ic_weighted", "quarterly"),
    ("B_plus_value_pe", "ic_weighted", "quarterly"),
]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in deep_dive_portfolio_v2_random_control_n100")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in deep_dive_portfolio_v2_random_control_n100")

    industry_map = load_industry_map()
    trend_regime = _trend_regime_series(market_df)
    liquidity = {sid: _liquidity_proxy_series(d) for sid, d in data.items()}

    results = []
    for factor_version, weight_mode, cadence_name in TARGET_COMBOS:
        print(f"\n--- {factor_version}/{weight_mode}/{cadence_name} VALIDATION, N_RANDOM={N_RANDOM} ---")
        r = run_one(factor_version, weight_mode, cadence_name, "VALIDATION", data, market_df,
                    industry_map, trend_regime, liquidity, "2021-01-01", holdout.VAL_END,
                    do_cost_sensitivity=False, do_random_control=True, n_random=N_RANDOM)
        results.append(r)
        print(f"  報酬={r['return_pct']:+.2f}%  隨機對照組中位數={r['random_control_median_pct']:+.2f}%  "
              f"percentile(N={N_RANDOM})={r['random_control_percentile']:.1f}")

    df = pd.DataFrame(results)
    df.to_csv("data/portfolio_backtest_v2_random_control_n100.csv", index=False)
    print("\n已存 data/portfolio_backtest_v2_random_control_n100.csv")
    print(df[["factor_version", "weight_mode", "cadence", "return_pct",
              "random_control_median_pct", "random_control_percentile"]].to_string(index=False))
    return df


if __name__ == "__main__":
    main()
