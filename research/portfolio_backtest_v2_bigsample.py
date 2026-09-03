"""第326輪接續第325輪：用「零新API安全樣本池」（yfinance價格快取 ∩ FinMind財報快取
∩ FinMind月營收快取 ∩ universe()成員 = 1138檔，見TW_LOG.md第325輪）重跑
`portfolio_multifactor_v2` A_4pass因子版本（eps_family/revenue_surprise/low_vol，
不含f_value_pe，因為PER資料不在backfill涵蓋範圍），比對p值是否較舊80檔樣本的
0.053/0.0535改善。

跟`portfolio_backtest_v2.py`的唯一差異：資料載入用`factors.py::prepare_score_factors()`
（精簡版，只算A_4pass需要的4個欄位，零PER/零三大法人呼叫）取代
`factor_ic.py::load_sample_with_factors()`（重量版，會觸發PER 402），其餘（
`compute_composite_at_date`/`run_one`/`alpha_significance`/隨機對照組）全部原樣
從`portfolio_backtest_v2.py` import，不重寫、不改邏輯，避免兩份邏輯漂移。

B_plus_value_pe本輪不跑（PER未涵蓋在安全樣本池，會觸發額度問題），維持
TW_LOG.md第325輪記錄的「下一輪待額度恢復後再處理」原狀。

僅唯讀查詢現有快取檔案＋呼叫`prepare_score_factors()`（PIT走`_asof_join`到已快取的
`TaiwanStockFinancialStatements`/`TaiwanStockMonthRevenue`），全程零新FinMind API呼叫。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from adjust import adjusted_price_series
from factors import prepare_score_factors
from finmind_client import load_dev
from portfolio_backtest_v2 import (
    FACTOR_VERSIONS,
    _liquidity_proxy_series,
    _trend_regime_series,
    run_one,
)
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe as build_universe
from validation import holdout

START_DATE = "2010-01-01"


def safe_pool_ids() -> list[str]:
    """重建TW_LOG.md第325輪找到的「零新API」交集池：yfinance價格快取 ∩ FinMind
    財報快取 ∩ FinMind月營收快取 ∩ universe()成員。

    **第327輪修正一個真bug**：舊版`_ids()`只用檔名前綴比對stock_id是否「有任何
    快取檔存在」，沒有檢查快取檔的(start_date, end_date)是否剛好等於
    `adjusted_price_series(sid, '2010-01-01')`實際會請求的那組
    (start='2010-01-01', end=VAL_END='2024-12-31')——`data/raw_yf/`底下混有
    production即時報價路徑留下的快取（end date是抓取當下的「今天」，例如
    `__2026-08-26.parquet`/`__2026-08-27.parquet`，共513個檔案），這類stock_id
    被舊版誤判為「安全」，但實際呼叫時因為exact cache key對不上而觸發真的
    live yfinance連線——這正是第326輪log看到的「possibly delisted; no timezone
    found」根因（不是yfinance/pandas環境問題，是本腳本自己的池子驗證邏輯太鬆）。
    改成直接檢查`fetch_yf_adjusted`會用到的exact cache path是否存在。"""
    from yf_price_client import _cache_path
    from validation.holdout import VAL_END

    yf_dir = Path(__file__).parent / "data" / "raw_yf"
    raw_dir = Path(__file__).parent / "data" / "raw"

    def _ids(dirpath: Path, prefix: str) -> set[str]:
        out = set()
        for p in dirpath.glob(f"{prefix}*.parquet"):
            parts = p.stem.split("__")
            idx = 1 if prefix else 0
            if len(parts) > idx:
                out.add(parts[idx])
        return out

    fin_ids = _ids(raw_dir, "TaiwanStockFinancialStatements__")
    rev_ids = _ids(raw_dir, "TaiwanStockMonthRevenue__")
    uni_ids = set(build_universe()["stock_id"].astype(str))
    candidates = fin_ids & rev_ids & uni_ids

    exact_yf_ids = {
        sid for sid in candidates
        if _cache_path(sid, START_DATE, VAL_END).exists()
    }
    return sorted(exact_yf_ids)


def load_safe_sample(sample_ids: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一套容錯慣例
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < 260:
            continue
        try:
            d = prepare_score_factors(sid, px, START_DATE)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: factor ERROR ({e}), dropping")
            continue
        out[sid] = d
    return out


def main():
    sample_ids = safe_pool_ids()
    print(f"安全樣本池：{len(sample_ids)}檔（zero新API）")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in portfolio_backtest_v2_bigsample")
    market_df = prepare_market_data(market_raw)

    print("Loading safe sample + score factors (cached, zero new API)...")
    data = load_safe_sample(sample_ids)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in portfolio_backtest_v2_bigsample")

    industry_map = load_industry_map()
    trend_regime = _trend_regime_series(market_df)
    liquidity = {sid: _liquidity_proxy_series(d) for sid, d in data.items()}

    print("\n========== A_4pass，全樣本池，階段1快速掃描（1x成本、無隨機控制組）==========")
    quick_results = []
    for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
        for cadence_name in ("monthly", "quarterly"):
            for label, start, end in (
                ("TRAIN", "2015-01-01", holdout.TRAIN_END),
                ("VALIDATION", "2021-01-01", holdout.VAL_END),
            ):
                r = run_one("A_4pass", weight_mode, cadence_name, label, data, market_df,
                            industry_map, trend_regime, liquidity, start, end,
                            do_cost_sensitivity=False, do_random_control=False)
                r["n_stocks"] = len(data)
                quick_results.append(r)
                print(f"  {weight_mode}/{cadence_name}/{label}: "
                      f"報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                      f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f})  "
                      f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%")

    quick_df = pd.DataFrame(quick_results)
    quick_df.to_csv("data/portfolio_backtest_v2_bigsample_quick_scan.csv", index=False)
    print("\n已存 data/portfolio_backtest_v2_bigsample_quick_scan.csv")

    print("\n========== 階段2：VALIDATION期補完整成本敏感度+隨機控制組（15次重抽）==========")
    full_results = []
    for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
        for cadence_name in ("monthly", "quarterly"):
            r = run_one("A_4pass", weight_mode, cadence_name, "VALIDATION", data, market_df,
                        industry_map, trend_regime, liquidity, "2021-01-01", holdout.VAL_END,
                        do_cost_sensitivity=True, do_random_control=True, n_random=15)
            r["n_stocks"] = len(data)
            full_results.append(r)
            print(f"\n--- A_4pass / {weight_mode} / {cadence_name} / VALIDATION（完整版，{len(data)}檔）---")
            print(f"  報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                  f"Sharpe={r['sharpe']:.3f}  trades={r['n_trades']}")
            print(f"  alpha(年化)={r['alpha_ann_pct']:+.2f}%  beta={r['beta']:+.3f}  "
                  f"p={r['alpha_pvalue']:.4f}  顯著為正={r['alpha_significant']}")
            print(f"  買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%  "
                  f"隨機對照組中位數={r['random_control_median_pct']:+.2f}%  percentile={r['random_control_percentile']:.1f}")
            print(f"  成本1x/2x/3x: {r['cost_1x']:+.2f}% / {r['cost_2x']:+.2f}% / {r['cost_3x']:+.2f}%")

    df = pd.DataFrame(full_results)
    df.to_csv("data/portfolio_backtest_v2_bigsample_results.csv", index=False)
    print("\n=== SUMMARY（階段2，VALIDATION完整版，存 data/portfolio_backtest_v2_bigsample_results.csv）===")
    print(df[["weight_mode", "cadence", "n_stocks", "return_pct", "mdd_pct", "sortino", "sharpe",
              "alpha_ann_pct", "alpha_pvalue", "alpha_significant", "buy_and_hold_index_pct",
              "random_control_percentile", "cost_3x"]].to_string(index=False))
    return quick_df, df


if __name__ == "__main__":
    main()
