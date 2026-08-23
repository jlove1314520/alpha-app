"""驅動腳本：Cowork 稽核第 3 點——放空可行性查驗 + 純多前decile相對大盤的可執行版本。
用目前本機已快取的樣本跑（不額外呼叫任何新的 API，除了融券資格查詢本身）。
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from finmind_client import load_dev
from long_short_backtest import START_DATE, load_universe_with_factors
from long_only_vs_market import check_shortability, run_period
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout


def main():
    files = glob.glob("data/raw/*.parquet")
    ids_price, ids_fin, ids_rev = set(), set(), set()
    for f in files:
        parts = os.path.basename(f).split("__")
        if len(parts) < 2 or os.path.getsize(f) <= 1000:
            continue
        ds, sid = parts[0], parts[1]
        if ds == "TaiwanStockPrice": ids_price.add(sid)
        if ds == "TaiwanStockFinancialStatements": ids_fin.add(sid)
        if ds == "TaiwanStockMonthRevenue": ids_rev.add(sid)
    candidate_ids = sorted(ids_price & ids_fin & ids_rev)
    print(f"候選：{len(candidate_ids)} 檔（本機快取現有量）")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_shortability_and_longonly")
    market_df = prepare_market_data(market_raw)

    data = load_universe_with_factors(candidate_ids, market_df, max_names=None)
    industry_map = load_industry_map()
    print(f"樣本：{len(data)} 檔可用")

    # 第 3 點 前半：放空可行性查驗（用 validation 期的換股日當抽樣點）
    calendar = sorted(d for d in market_df["date"] if "2021-01-01" <= d <= holdout.VAL_END)
    sample_dates = calendar[::21]  # 月頻換股日，跟月頻回測一致
    shortability = check_shortability(data, industry_map, sample_dates)

    # 第 3 點 後半：純多前decile相對大盤（週頻+月頻 × train/val）
    results = []
    for cadence_name, rebalance_days in [("weekly", 5), ("monthly", 21)]:
        train = run_period(f"TRAIN({cadence_name})", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END, cadence_name, rebalance_days)
        val = run_period(f"VALIDATION({cadence_name})", data, market_df, industry_map, "2021-01-01", holdout.VAL_END, cadence_name, rebalance_days)
        results.extend([train, val])

    print("\n=== 純多前decile相對大盤 總結 ===")
    for r in results:
        print(f"  {r['label']}: 年化={r['annualized_return_pct']:+.2f}%  beta={r['beta']:+.3f}  "
              f"alpha={r['annualized_alpha_pct']:+.2f}%  Sortino={r['sortino']:.3f}  "
              f"對大盤超額={r['excess_vs_market_pp']:+.2f}pp  隨機對照百分位={r['random_control_percentile']:.1f}")

    pd.DataFrame(results).to_csv("data/longonly_vs_market_results.csv", index=False)
    print("已存 data/longonly_vs_market_results.csv")
    print(f"\n放空可行性摘要：{shortability}")
    return results, shortability


if __name__ == "__main__":
    main()
