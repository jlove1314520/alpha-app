# -*- coding: utf-8 -*-
"""尺.一「前5支三欄對照表」第3欄（新引擎+新量尺）——總司令2026-09-23
裁示【修正alpha量尺＋f52w補完審查＋稽核續跑】尺.一第4點。

第1欄(舊引擎+舊量尺)＝原始TRIALS_LEDGER登記(#12/#73/#75/#85/#296-303)，
第2欄(新引擎+舊量尺)＝上一輪稽核(#367/#370/#371/#373/#375)，兩欄都已
存在不必重算。這裡只算第3欄：用修正後引擎(compounding+零價格防呆)
+新量尺(0050含息總報酬基準+Newey-West HAC+Dimson beta)重跑「真實訊號」
單次回測，跳過成本敏感度/隨機控制組（那兩者不受benchmark/alpha量尺
影響，維持第2欄已有的數字，不重算——省時間）。

涵蓋：
  - portfolio_backtest_v2（透過pit3_rerun_v2_corrected.run_arm，跟
    第2欄同一組合，do_cost_sensitivity=do_random_control=False，跟
    原quick scan口徑一致，本來就不含這兩項，重跑成本沒有變化）
  - pead_portfolio_v1（do_cost_sensitivity=False, do_random_control=
    False，跳過100-draw隨機控制組，只算alpha/beta/bh）
  - run_score_backtest（因為score_topn_v1.run_period()沒有跳過旗標，
    直接複製其邏輯手動只算真實訊號+新alpha/bh，不呼叫成本敏感度/
    隨機控制組迴圈）
  - f52w_high_portfolio_v1／dividend_yield_portfolio_v1 已在互動視窗
    直接執行過（清空checkpoint的"real"欄位、重跑，成本敏感度/隨機
    控制組讀快取），不在本檔案重複

用法：python research/audit_alpha_scale_recompute.py
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

OUT_JSON = Path(__file__).parent / "data" / "audit_alpha_scale_recompute.json"


def recompute_portfolio_backtest_v2() -> list[dict]:
    import pit3_rerun_v2_corrected as p3
    from portfolio_backtest_v2_bigsample import safe_pool_ids
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout
    from factor_ic import build_snapshots
    import portfolio_backtest_v2 as pv2

    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", p3.START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in recompute_portfolio_backtest_v2")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    snapshots = build_snapshots(sorted(market_df["date"].tolist()), p3.SNAPSHOT_START, holdout.VAL_END)

    rows, _weights = p3.run_arm("corrected", sample_ids, market_df, industry_map, trend_regime, snapshots)
    return rows


def recompute_pead() -> dict:
    import pead_portfolio_v1 as m
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout
    import portfolio_backtest_v2 as pbv2

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in recompute_pead")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    results = {}
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
        results[label] = m.run_one(label, data, market_df, industry_map, liquidity, start, end,
                                    do_cost_sensitivity=False, do_random_control=False)
        print(f"  {label}: 報酬={results[label]['return_pct']:+.2f}% "
              f"alpha={results[label]['alpha_ann_pct']:+.2f}%(p={results[label]['alpha_pvalue']:.4f}) "
              f"beta_dimson={results[label]['beta']:+.3f} beta_ols={results[label].get('beta_ols', float('nan')):+.3f} "
              f"大盤={results[label]['buy_and_hold_index_pct']:+.2f}%", flush=True)
    return results


def recompute_score_topn() -> dict:
    """複製run_score_backtest.run_period()的「真實訊號」那一段，跳過成本
    敏感度(cost_1x/2x/3x)與隨機控制組(N_RANDOM_DRAWS筆)，只重算alpha/bh。"""
    import run_score_backtest as m
    import portfolio_backtest_v2 as pbv2
    from backtest.engine import BacktestConfig, run_backtest
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in recompute_score_topn")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()

    results = {}
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
        cfg = BacktestConfig(start_date=start, end_date=end, max_positions=m.TOP_N, book_name="score_topn_v1")
        result = run_backtest(m.make_score_signal_fn(industry_map, m.TOP_N), data, market_df, cfg)
        alpha = pbv2.alpha_significance(result.equity_curve, market_df)
        bh = pbv2.buy_and_hold_index_pct(market_df, start, end)
        results[label] = {
            "label": label, "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
            "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"], "beta_ols": alpha.get("beta_ols"),
            "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
            "buy_and_hold_pct": bh, "n_trades": result.n_trades,
        }
        print(f"  {label}: score={results[label]['return_pct']:+.2f}% "
              f"alpha={results[label]['alpha_ann_pct']:+.2f}%(p={results[label]['alpha_pvalue']:.4f}) "
              f"大盤(0050含息)={bh:+.2f}%", flush=True)
    return results


if __name__ == "__main__":
    out = {}
    print("=== 1/3: portfolio_backtest_v2 (新量尺) ===", flush=True)
    out["portfolio_backtest_v2"] = recompute_portfolio_backtest_v2()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"（階段性）已寫入 {OUT_JSON}", flush=True)

    print("\n=== 2/3: pead_portfolio_v1 (新量尺) ===", flush=True)
    out["pead_portfolio_v1"] = recompute_pead()
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"（階段性）已寫入 {OUT_JSON}", flush=True)

    print("\n=== 3/3: run_score_backtest (新量尺) ===", flush=True)
    out["run_score_backtest"] = recompute_score_topn()
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n全部完成，已寫入 {OUT_JSON}", flush=True)
