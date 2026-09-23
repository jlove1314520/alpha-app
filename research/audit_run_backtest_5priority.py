# -*- coding: utf-8 -*-
"""驗.一第4點稽核（總司令2026-09-23裁示【稽核解封＋S2對等比較＋凍結
regime家族】）：先跑5支對全專案結論影響最大的run_backtest呼叫者，
用修正後引擎(compounding+零價格防呆)重跑，輸出舊判定/新判定/關鍵數字
新舊對照。只重跑、只比較，不自行改判——翻轉一律進AWAITING_REVIEW。

涵蓋（本檔只做前3支，f52w/dividend因既有checkpoint機制+單次35-40分鐘
成本另外用獨立指令跑，見PENDING_QUEUE.md驗.一條目說明）：
  1. portfolio_backtest_v2.py（透過pit3_rerun_v2_corrected.py的
     run_arm("corrected", ...)，只跑corrected臂，不重跑legacy臂——
     legacy臂是PIT重現檢查，跟這次的引擎稽核無關）→ 對應TRIALS_LEDGER
     #296-#303
  2. pead_portfolio_v1.py → #73（do_cost_sensitivity=True,
     do_random_control=True, n_random=100，跟原始設計一致）
  3. run_score_backtest.py → #12（呼叫既有main()，N_RANDOM_DRAWS=60
     跟原始設計一致）

用法：python audit_run_backtest_5priority.py
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

OUT_JSON = Path(__file__).parent / "data" / "audit_run_backtest_5priority.json"


def audit_portfolio_backtest_v2() -> list[dict]:
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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_portfolio_backtest_v2")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    snapshots = build_snapshots(sorted(market_df["date"].tolist()), p3.SNAPSHOT_START, holdout.VAL_END)

    rows, _weights = p3.run_arm("corrected", sample_ids, market_df, industry_map, trend_regime, snapshots)
    return rows


def audit_pead() -> dict:
    import pead_portfolio_v1 as m
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout
    import portfolio_backtest_v2 as pbv2

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in audit_pead")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    results = {}
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
        results[label] = m.run_one(label, data, market_df, industry_map, liquidity, start, end,
                                    do_cost_sensitivity=True, do_random_control=True, n_random=100)
        print(f"  {label}: 報酬={results[label]['return_pct']:+.2f}% "
              f"alpha={results[label]['alpha_ann_pct']:+.2f}%(p={results[label]['alpha_pvalue']:.4f}) "
              f"大盤={results[label]['buy_and_hold_index_pct']:+.2f}% "
              f"percentile={results[label]['random_control_percentile']:.1f}", flush=True)
    return results


def audit_score_topn() -> dict:
    import run_score_backtest as m
    train_result, val_result = m.main()
    return {"TRAIN": train_result, "VALIDATION": val_result}


if __name__ == "__main__":
    out = {}
    print("=== 1/3: portfolio_backtest_v2 (corrected臂, A_4pass, 6權重模式x2頻率x2期) ===", flush=True)
    out["portfolio_backtest_v2"] = audit_portfolio_backtest_v2()
    print(json.dumps(out["portfolio_backtest_v2"], ensure_ascii=False, indent=2, default=str))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"（階段性）已寫入 {OUT_JSON}", flush=True)

    print("\n=== 2/3: pead_portfolio_v1 ===", flush=True)
    out["pead_portfolio_v1"] = audit_pead()
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"（階段性）已寫入 {OUT_JSON}", flush=True)

    print("\n=== 3/3: run_score_backtest (score_topn_v1) ===", flush=True)
    out["run_score_backtest"] = audit_score_topn()
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n全部完成，已寫入 {OUT_JSON}", flush=True)
