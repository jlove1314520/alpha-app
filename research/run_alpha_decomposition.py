"""驅動腳本：Cowork 稽核第2點——純多前decile的 alpha/beta 拆解 + 成本敏感度。
用本機已快取的樣本跑，不額外呼叫任何新的 API。
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
from long_only_vs_market import decompose_alpha_beta, run_cost_sensitivity_with_alpha, run_long_only, _longonly_legs
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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_alpha_decomposition")
    market_df = prepare_market_data(market_raw)

    data = load_universe_with_factors(candidate_ids, market_df, max_names=None)
    industry_map = load_industry_map()
    print(f"樣本：{len(data)} 檔可用")

    all_rows = []
    for cadence_name, rebalance_days in [("weekly", 5), ("monthly", 21)]:
        for period_name, start, end in [("TRAIN", "2015-01-01", holdout.TRAIN_END), ("VALIDATION", "2021-01-01", holdout.VAL_END)]:
            print(f"\n=== {period_name}({cadence_name})：{start}..{end} ===")
            # 1x 成本的完整拆解（主結果）
            result_1x = run_long_only(data, market_df, start, end, rebalance_days, industry_map, _longonly_legs, cost_multiplier=1.0)
            decomp_1x = decompose_alpha_beta(result_1x, market_df)
            print(f"  總報酬={decomp_1x['total_return_pct']:+.2f}%  "
                  f"= beta貢獻({decomp_1x['beta']:+.3f}×大盤)={decomp_1x['beta_contribution_pct']:+.2f}%  "
                  f"+ 純選股alpha={decomp_1x['alpha_total_return_pct']:+.2f}%")
            print(f"  純alpha年化={decomp_1x['alpha_ann_pct']:+.2f}%  alpha_Sortino={decomp_1x['alpha_sortino']:.3f}  "
                  f"alpha_MDD={decomp_1x['alpha_mdd_pct']:.2f}%")

            print("  成本敏感度（1x/2x/3x）：")
            cost_rows = run_cost_sensitivity_with_alpha(data, market_df, industry_map, start, end, rebalance_days)

            for row in cost_rows:
                row.update({"period": period_name, "cadence": cadence_name, "start": start, "end": end})
                all_rows.append(row)

    print("\n=== Alpha/Beta 拆解總結（1x成本，各期主結果） ===")
    df = pd.DataFrame(all_rows)
    main_rows = df[df["cost_multiplier"] == 1]
    for _, r in main_rows.iterrows():
        print(f"  {r['period']}({r['cadence']}): beta={r['beta']:+.3f}  "
              f"純alpha年化={r['alpha_ann_pct']:+.2f}%  alpha_Sortino={r['alpha_sortino']:.3f}  "
              f"alpha_MDD={r['alpha_mdd_pct']:.2f}%")

    print("\n=== 成本敏感度：純alpha報酬是否隨成本提高仍維持正值 ===")
    for (period, cadence), grp in df.groupby(["period", "cadence"]):
        grp = grp.sort_values("cost_multiplier")
        vals = "  ".join(f"{m}x:{a:+.2f}%" for m, a in zip(grp["cost_multiplier"], grp["alpha_total_return_pct"]))
        still_positive = "全部維持正值" if (grp["alpha_total_return_pct"] > 0).all() else "有翻負，見上方明細"
        print(f"  {period}({cadence})：{vals}  --> {still_positive}")

    df.to_csv("data/alpha_beta_decomposition.csv", index=False)
    print("\n已存 data/alpha_beta_decomposition.csv")
    return df


if __name__ == "__main__":
    main()
