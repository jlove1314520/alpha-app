"""第327輪：全量1138檔跑第一次時process不明原因中途消失（stdout被完全緩衝，
沒有任何print flush出來，tasklist確認python.exe已不在執行中，無crash traceback
可查）。改用300檔子樣本（跟factor_ic.py::SAMPLE_SIZE的300對齊，也是可控時間
內能跑完的規模），用-u unbuffered執行以利即時監控是否又中途消失。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from portfolio_backtest_v2_bigsample import safe_pool_ids, load_safe_sample
from portfolio_backtest_v2 import FACTOR_VERSIONS, _liquidity_proxy_series, _trend_regime_series, run_one
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from score import load_industry_map
from validation import holdout
import pandas as pd

START_DATE = "2010-01-01"

def main():
    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    print(f"pool total={len(all_ids)}, using first 300: {sample_ids[0]}..{sample_ids[-1]}", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_bigsample_300")
    market_df = prepare_market_data(market_raw)
    print("market data ready", flush=True)

    data = load_safe_sample(sample_ids)
    print(f"loaded {len(data)}/{len(sample_ids)} usable names", flush=True)

    industry_map = load_industry_map()
    trend_regime = _trend_regime_series(market_df)
    liquidity = {sid: _liquidity_proxy_series(d) for sid, d in data.items()}
    print("prep done, starting quick scan", flush=True)

    results = []
    for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
        for cadence_name in ("monthly", "quarterly"):
            for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                                        ("VALIDATION", "2021-01-01", holdout.VAL_END)):
                r = run_one("A_4pass", weight_mode, cadence_name, label, data, market_df,
                            industry_map, trend_regime, liquidity, start, end,
                            do_cost_sensitivity=False, do_random_control=False)
                r["n_stocks"] = len(data)
                results.append(r)
                print(f"  {weight_mode}/{cadence_name}/{label}: "
                      f"報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
                      f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f})  "
                      f"買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%", flush=True)

    df = pd.DataFrame(results)
    df.to_csv("data/portfolio_backtest_v2_bigsample300_quick_scan.csv", index=False)
    print("saved data/portfolio_backtest_v2_bigsample300_quick_scan.csv", flush=True)

if __name__ == "__main__":
    main()
