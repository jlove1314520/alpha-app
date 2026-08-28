"""round201補充：`deep_dive_portfolio_v2_random_control_n100.py`同一process內跑完
組合1(A_4pass)後、進組合2(B_plus_value_pe)時process無聲消失（疑似OOM，round200
TW_LOG記錄過）。這裡驗證假設「是process內跨組合記憶體累積，不是單一組合N=100本身
太大」——用命令列參數只跑其中一組，兩組分開兩次process呼叫，process結束後記憶體
會被OS完整回收，若假設成立，單獨跑組合2應該能順利完成。

用法：python deep_dive_portfolio_v2_random_control_n100_single.py <A_4pass|B_plus_value_pe>

零額外API呼叫，邏輯與`deep_dive_portfolio_v2_random_control_n100.py`完全一致，只是
拆成單組合、且輸出檔名依組合區分，避免覆蓋彼此結果。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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
COMBOS = {
    "A_4pass": ("A_4pass", "ic_weighted", "quarterly"),
    "B_plus_value_pe": ("B_plus_value_pe", "ic_weighted", "quarterly"),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in COMBOS:
        print(f"用法: python {sys.argv[0]} <{'|'.join(COMBOS)}>")
        sys.exit(1)
    factor_version, weight_mode, cadence_name = COMBOS[sys.argv[1]]

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in n100_single")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in n100_single")

    industry_map = load_industry_map()
    trend_regime = _trend_regime_series(market_df)
    liquidity = {sid: _liquidity_proxy_series(d) for sid, d in data.items()}

    print(f"\n--- {factor_version}/{weight_mode}/{cadence_name} VALIDATION, N_RANDOM={N_RANDOM} ---")
    r = run_one(factor_version, weight_mode, cadence_name, "VALIDATION", data, market_df,
                industry_map, trend_regime, liquidity, "2021-01-01", holdout.VAL_END,
                do_cost_sensitivity=False, do_random_control=True, n_random=N_RANDOM)
    print(f"  報酬={r['return_pct']:+.2f}%  隨機對照組中位數={r['random_control_median_pct']:+.2f}%  "
          f"percentile(N={N_RANDOM})={r['random_control_percentile']:.1f}")

    df = pd.DataFrame([r])
    out_path = f"data/portfolio_backtest_v2_random_control_n100_{sys.argv[1]}.csv"
    df.to_csv(out_path, index=False)
    print(f"\n已存 {out_path}")


if __name__ == "__main__":
    main()
