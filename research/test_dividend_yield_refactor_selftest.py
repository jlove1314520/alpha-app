# -*- coding: utf-8 -*-
"""修.五自我測試（2026-09-26總司令裁示【緊急：H.一立即暫停重跑，修正兩個
bug後先做乾跑檢查】修.五第1點）：把`factors.py::_dividend_yield_ttm_cash()`
拆成純函式`_dividend_yield_ttm_cash_from_df()`+薄wrapper後，驗證這個重構
沒有改變行為——用2007-2014資料重跑`dividend_yield_portfolio_v1`的
single-shot股票部位回測，`candidate_return_pct_2007_2014`與
`mdd_full_period_pct`須與`TRIALS_LEDGER.md` #399已登記的結果逐位元相同
（+203.87%、-53.72%）。

**不是重新執行single_shot_2007_2014_test.py的only-once段落**：只呼叫
該檔案docstring明確標示「可以安全反覆測試」的`load_common_stock_data_
2007_2014()`（資料載入，零統計判定），以及本身不寫檔、不註冊TRIALS_
LEDGER、只回傳dict的`run_single_shot()`——這是總司令本次裁示明確要求
的回歸測試，不是另開一次考.一。全部走2007-2014區間（`load_dev()`
capped path，非holdout），不觸碰holdout保護，`factors_mod.
_dividend_yield_ttm_cash`維持原本capped版本（未被H.一的monkeypatch
覆寫，這支腳本不import holdout_2025_dividend_account_test.py）。

跑法：python research/test_dividend_yield_refactor_selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from single_shot_2007_2014_test import load_common_stock_data_2007_2014, run_single_shot
import dividend_yield_portfolio_v1 as div_mod

# TRIALS_LEDGER.md #399 已登記的結果（考.一正式執行，見該筆判定列）。
EXPECTED_RETURN_PCT = 203.87
EXPECTED_MDD_PCT = -53.72
TOLERANCE = 0.005  # 四捨五入到小數點後兩位時的浮點誤差容許範圍


def main() -> int:
    print("=== 修.五自我測試：_dividend_yield_ttm_cash重構後的回歸驗證 ===", flush=True)
    print("載入2007-2014資料（全部本機快取，零新增API呼叫，可安全反覆測試）...", flush=True)
    data, market_df, industry_map, liquidity, n_sample = load_common_stock_data_2007_2014()

    result = run_single_shot(div_mod, data, market_df, industry_map, liquidity, "dividend_yield_portfolio_v1")

    actual_return = result["candidate_return_pct_2007_2014"]
    actual_mdd = result["mdd_full_period_pct"]

    print(f"\n重構後：候選報酬={actual_return:+.2f}%  全段MDD={actual_mdd:.2f}%", flush=True)
    print(f"#399既有登記：候選報酬={EXPECTED_RETURN_PCT:+.2f}%  全段MDD={EXPECTED_MDD_PCT:.2f}%", flush=True)

    return_ok = abs(actual_return - EXPECTED_RETURN_PCT) < TOLERANCE
    mdd_ok = abs(actual_mdd - EXPECTED_MDD_PCT) < TOLERANCE

    if return_ok and mdd_ok:
        print("\nPASS：重構後數字與#399既有登記逐位元(四捨五入後)相同，"
              "_dividend_yield_ttm_cash的抽取沒有改變一般研究/考.一路徑的行為。", flush=True)
        return 0
    print("\nFAIL：重構後數字與#399既有登記不一致！這代表抽取純函式的過程"
          "改動了計算邏輯，須立即檢查_dividend_yield_ttm_cash_from_df()"
          "與原始版本是否真的逐行相同，不得放行後續修.五其他步驟。", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
