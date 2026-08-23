"""Cowork 稽核第 2 點：月頻多空訓練期 −9.66% vs 驗證期 +66.5%，違反跨週期方向
一致的關卡（呼應 CONSTITUTION.md「多子期間方向一致」），需要查原因。

方法：重跑月頻多空回測，但把「本來只回傳彙總結果」的 `run_long_short()`
輸出的逐期報酬攤開來看，檢查：
  1. 是不是被少數幾個月主導（離群月份），還是全期普遍偏負。
  2. 換股名單的組成穩定度——月頻換股次數少（訓練期 6 年只有約 72 次換股，
     不像週頻有 300+ 次），任何一次換股決策的雜訊都被放大，樣本內生的變異
     可能本來就比週頻大很多，不一定是 bug。
  3. 跟現有 170 檔樣本數對照：decile=17 檔/腳，訓練期換股次數少，這兩個因素
     疊加，統計上本來就容易出現跨期方向不一致——這不代表「找到訊號」也不
     代表「沒有訊號」，代表這個樣本規模/頻率組合下的估計值信賴區間很寬，
     跟 Cowork 第 1 點「宇宙太小不可信」是同一個根源問題，不是各自獨立的巧合。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from finmind_client import load_dev
from long_short_backtest import (
    START_DATE, _decile_legs, run_long_short, load_universe_with_factors,
)
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe
from validation import holdout


def monthly_breakdown(data, market_df, industry_map, start, end, label):
    result = run_long_short(data, market_df, industry_map, start, end, rebalance_days=21, leg_fn=_decile_legs)
    result["date"] = pd.to_datetime(result["date"])
    result["ym"] = result["date"].dt.to_period("M")
    monthly = result.groupby("ym")["spread_return"].apply(lambda s: (1 + s).prod() - 1)
    print(f"\n=== {label} 逐月價差報酬（未扣成本，看方向分布） ===")
    print(f"  正報酬月數：{(monthly > 0).sum()}/{len(monthly)}  負報酬月數：{(monthly < 0).sum()}/{len(monthly)}")
    print(f"  平均月報酬：{monthly.mean()*100:+.2f}%  中位數：{monthly.median()*100:+.2f}%  標準差：{monthly.std()*100:.2f}%")
    worst5 = monthly.nsmallest(5)
    best5 = monthly.nlargest(5)
    print(f"  最差 5 個月：{[(str(k), f'{v*100:+.1f}%') for k, v in worst5.items()]}")
    print(f"  最好 5 個月：{[(str(k), f'{v*100:+.1f}%') for k, v in best5.items()]}")
    total_from_worst5 = worst5.sum() * 100
    print(f"  最差 5 個月合計對總報酬的貢獻：{total_from_worst5:+.2f}pp（若總報酬本身接近這個量級，代表被少數月份主導）")
    return monthly


def main():
    import pickle
    cache_path = Path("data/ls_data_cache.pkl")
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
        data, industry_map = cache["data"], cache["industry_map"]
    else:
        # 快取檔案這次 session 已被清掉，用 170 檔候選重新從本機 parquet 快取組一次（零額外 API 呼叫）
        u = build_universe()
        market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
        market_df_tmp = prepare_market_data(market_raw)
        import glob, os
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
        data = load_universe_with_factors(candidate_ids, market_df_tmp, max_names=None)
        industry_map = load_industry_map()

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in diagnose_monthly_inconsistency")
    market_df = prepare_market_data(market_raw)

    print(f"樣本：{len(data)} 檔")
    train_monthly = monthly_breakdown(data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END, "TRAIN(月頻)")
    val_monthly = monthly_breakdown(data, market_df, industry_map, "2021-01-01", holdout.VAL_END, "VALIDATION(月頻)")

    # 換股穩定度檢查：train 期逐次換股名單的重疊率（相鄰兩次換股，多空兩腳分別重疊幾檔）
    print("\n=== 換股名單穩定度（train 期，相鄰兩次月頻換股的重疊率） ===")
    calendar = sorted(d for d in market_df["date"] if "2015-01-01" <= d <= holdout.TRAIN_END)
    rebalance_dates = calendar[::21]
    prev_longs, prev_shorts = None, None
    overlaps_long, overlaps_short = [], []
    for d in rebalance_dates:
        longs, shorts = _decile_legs(d, data, industry_map)
        if prev_longs and longs:
            ov = len(set(longs) & set(prev_longs)) / len(longs)
            overlaps_long.append(ov)
        if prev_shorts and shorts:
            ov = len(set(shorts) & set(prev_shorts)) / len(shorts)
            overlaps_short.append(ov)
        prev_longs, prev_shorts = longs, shorts
    if overlaps_long:
        print(f"  多頭腳相鄰換股重疊率：平均 {np.mean(overlaps_long)*100:.1f}%（越低代表換手越頻繁/名單越不穩定）")
    if overlaps_short:
        print(f"  空頭腳相鄰換股重疊率：平均 {np.mean(overlaps_short)*100:.1f}%")
    print(f"  train 期總共 {len(rebalance_dates)} 次月頻換股決策點")


if __name__ == "__main__":
    main()
