# -*- coding: utf-8 -*-
"""審.一步驟3（總司令2026-09-23裁示【修正alpha量尺＋f52w補完審查＋
稽核續跑】）：f52w_high_portfolio_v1的VAL報酬歸因——列貢獻最大10檔+
產業，算半導體/電子類報酬佔比；另跑一版「產業中性」(每產業最多N/4檔)
對照，用新量尺(尺.一)重算alpha/beta/p值。

用法：python research/audit_f52w_attribution.py
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
from f52w_high_portfolio_v1 import (
    TOP_N, REBALANCE_DAYS, make_signal_fn, compute_composite_at_date, _eligible_single_factor,
)

OUT_JSON = Path(__file__).parent / "data" / "audit_f52w_attribution.json"

ELECTRONICS_KEYWORDS = ("半導體", "電子", "光電", "電腦", "通信網路")
INDUSTRY_CAP = TOP_N // 4  # N/4 = 5


def make_industry_neutral_signal_fn(industry_map, liquidity):
    def signal_fn(price_data, as_of, market_df):
        cs = _eligible_single_factor(compute_composite_at_date(as_of, price_data, industry_map, liquidity))
        picks, ind_count = [], {}
        for _, row in cs.iterrows():
            if len(picks) >= TOP_N:
                break
            ind = row["industry"] if pd.notna(row["industry"]) else "未知"
            if ind_count.get(ind, 0) >= INDUSTRY_CAP:
                continue
            picks.append(row["stock_id"])
            ind_count[ind] = ind_count.get(ind, 0) + 1
        return {sid: 1.0 for sid in picks}
    return signal_fn


def attribute_val_pnl(result, industry_map) -> dict:
    trades = result.trades
    sells = trades[trades["side"] == "sell"].copy()
    pnl_by_sid = sells.groupby("stock_id")["realized_pnl"].sum().sort_values(ascending=False)
    total_realized = float(pnl_by_sid.sum())
    top10 = pnl_by_sid.head(10)
    top10_rows = []
    electronics_pnl = 0.0
    for sid, pnl in pnl_by_sid.items():
        ind = industry_map.get(sid, "未知")
        if any(k in ind for k in ELECTRONICS_KEYWORDS):
            electronics_pnl += pnl
    for sid, pnl in top10.items():
        ind = industry_map.get(sid, "未知")
        top10_rows.append({"stock_id": sid, "industry": ind, "realized_pnl": pnl,
                            "pct_of_total_realized": (pnl / total_realized * 100) if total_realized else float("nan")})
    return {
        "total_realized_pnl": total_realized,
        "top10": top10_rows,
        "electronics_realized_pnl": electronics_pnl,
        "electronics_pct_of_total": (electronics_pnl / total_realized * 100) if total_realized else float("nan"),
        "n_stocks_with_realized_pnl": len(pnl_by_sid),
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_f52w_attribution")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    from strategies.weinstein_stage2 import prepare_market_data as _pmd  # noqa: F401  (already imported, keep explicit)
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    start, end = "2021-01-01", holdout.VAL_END
    out = {}

    print("=== 1/2: 原始訊號(每產業無上限) VAL期報酬歸因 ===", flush=True)
    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="f52w_attribution_original")
    result = run_backtest(signal_fn, data, market_df, cfg)
    attrib = attribute_val_pnl(result, industry_map)
    out["original"] = {
        "return_pct": result.total_return_pct, "attribution": attrib,
    }
    print(f"  總實現損益={attrib['total_realized_pnl']:,.0f}  "
          f"電子/半導體佔比={attrib['electronics_pct_of_total']:.1f}%", flush=True)
    for row in attrib["top10"]:
        print(f"    {row['stock_id']} ({row['industry']}): {row['realized_pnl']:+,.0f} "
              f"({row['pct_of_total_realized']:+.1f}%)", flush=True)

    print("\n=== 2/2: 產業中性版(每產業最多{}檔) VAL期重跑 ===".format(INDUSTRY_CAP), flush=True)
    neutral_signal_fn = make_industry_neutral_signal_fn(industry_map, liquidity)
    cfg_n = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                            rebalance_every_n_days=REBALANCE_DAYS, book_name="f52w_attribution_industry_neutral")
    result_n = run_backtest(neutral_signal_fn, data, market_df, cfg_n)
    alpha_n = pbv2.alpha_significance(result_n.equity_curve, market_df)
    bh_n = pbv2.buy_and_hold_index_pct(market_df, start, end)
    attrib_n = attribute_val_pnl(result_n, industry_map)
    out["industry_neutral"] = {
        "return_pct": result_n.total_return_pct, "mdd_pct": result_n.max_drawdown_pct,
        "alpha_ann_pct": alpha_n["alpha_ann_pct"], "beta": alpha_n["beta"], "beta_ols": alpha_n.get("beta_ols"),
        "alpha_pvalue": alpha_n["alpha_pvalue"], "alpha_significant": alpha_n["alpha_significant"],
        "buy_and_hold_index_pct": bh_n, "n_trades": result_n.n_trades,
        "attribution": attrib_n,
    }
    print(f"  報酬={result_n.total_return_pct:+.2f}% alpha={alpha_n['alpha_ann_pct']:+.2f}%"
          f"(p={alpha_n['alpha_pvalue']:.4f}) beta_dimson={alpha_n['beta']:+.3f} "
          f"大盤(0050含息)={bh_n:+.2f}%", flush=True)
    print(f"  電子/半導體佔比={attrib_n['electronics_pct_of_total']:.1f}%", flush=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
