# -*- coding: utf-8 -*-
"""尺.一自我測試（總司令2026-09-23裁示【修正alpha量尺＋f52w補完審查＋
稽核續跑】）：驗證`portfolio_backtest_v2.py`新版`alpha_significance()`/
`buy_and_hold_index_pct()`(0050含息總報酬基準+Newey-West HAC+Dimson
beta)機制本身正確，不是套個公式就信任。

兩個測試：
1. 0050對0050回歸：equity_curve本身就是0050，跟0050基準回歸，
   alpha必須≈0、beta(Dimson與OLS)必須≈1——用自己當基準理論上該是
   完美擬合。
2. 0050報酬落後1天：equity_curve是0050報酬整體平移1天（模擬非同步
   交易/薄交易個股報酬相對大盤晚一天入帳），OLS beta（只看同期）
   必須明顯<1（理想上接近0，因為日報酬近似隨機漫步、跟隔天報酬
   近乎無關），但Dimson beta（同期+落後1/2期加總）必須能抓回≈1
   （因為lag1那項的係數會抓到這個結構性的1天延遲）。

用法：python research/test_alpha_scale_selftest.py
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

import numpy as np
import pandas as pd

from portfolio_backtest_v2 import (
    alpha_significance, buy_and_hold_index_pct,
    BENCHMARK_0050_TOTAL_RETURN, _load_0050_total_return_series,
)

ALPHA_TOL_PP = 1.0   # 年化alpha容忍帶（百分點），0050對0050不必剛好0.0000，允許極小數值誤差
BETA_TOL = 0.05       # beta容忍帶
LAGGED_OLS_BETA_MAX = 0.5  # 「明顯<1」的操作化定義：OLS beta必須低於這個門檻
LAGGED_DIMSON_BETA_TOL = 0.15  # 落後版Dimson beta跟1.0的容忍帶（比第一個測試寬，因為是合成資料不是完美自我對照）


def _make_equity(returns: pd.Series, start_value: float = 1_000_000.0) -> pd.DataFrame:
    eq = start_value * (1 + returns.fillna(0.0)).cumprod()
    return pd.DataFrame({"date": returns.index, "equity": eq.values})


def test_self_regression() -> bool:
    series = _load_0050_total_return_series()
    rets = series.pct_change()
    equity_curve = _make_equity(rets)
    dummy_market_df = pd.DataFrame({"date": series.index, "close": series.values})  # legacy path用不到，這裡只填欄位形狀

    result = alpha_significance(equity_curve, dummy_market_df, benchmark=BENCHMARK_0050_TOTAL_RETURN)
    ok_alpha = abs(result["alpha_ann_pct"]) < ALPHA_TOL_PP
    ok_beta_dimson = abs(result["beta"] - 1.0) < BETA_TOL
    ok_beta_ols = abs(result["beta_ols"] - 1.0) < BETA_TOL
    ok = ok_alpha and ok_beta_dimson and ok_beta_ols
    print(f"[測試1] 0050對0050：alpha={result['alpha_ann_pct']:+.4f}%（應≈0，容忍<{ALPHA_TOL_PP}pp）"
          f" beta_dimson={result['beta']:.4f}（應≈1，容忍±{BETA_TOL}）"
          f" beta_ols={result['beta_ols']:.4f}（應≈1，容忍±{BETA_TOL}）"
          f" n_days={result['n_days']}：{'PASS' if ok else 'FAIL'}")
    return ok


def test_lagged_regression() -> bool:
    series = _load_0050_total_return_series()
    rets = series.pct_change()
    lagged_rets = rets.shift(1)  # 今天的「策略報酬」= 昨天的大盤報酬，純1天延遲、同期完全無關
    equity_curve = _make_equity(lagged_rets)
    dummy_market_df = pd.DataFrame({"date": series.index, "close": series.values})

    result = alpha_significance(equity_curve, dummy_market_df, benchmark=BENCHMARK_0050_TOTAL_RETURN)
    ok_ols = result["beta_ols"] < LAGGED_OLS_BETA_MAX
    ok_dimson = abs(result["beta"] - 1.0) < LAGGED_DIMSON_BETA_TOL
    ok = ok_ols and ok_dimson
    print(f"[測試2] 0050落後1天：beta_ols={result['beta_ols']:.4f}（應明顯<1，門檻<{LAGGED_OLS_BETA_MAX}）"
          f" beta_dimson={result['beta']:.4f}（應≈1，容忍±{LAGGED_DIMSON_BETA_TOL}）"
          f" n_days={result['n_days']}：{'PASS' if ok else 'FAIL'}")
    return ok


def test_benchmark_switch_smoke() -> bool:
    """附帶檢查：新舊benchmark確實回傳不同數字（不是參數沒接上、悄悄還是舊行為）。"""
    from finmind_client import load_dev
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2015-01-01")
    market_df = prepare_market_data(market_raw)
    start, end = "2015-01-01", holdout.VAL_END
    new_bh = buy_and_hold_index_pct(market_df, start, end, benchmark=BENCHMARK_0050_TOTAL_RETURN)
    old_bh = buy_and_hold_index_pct(market_df, start, end, benchmark="taiex_price_legacy")
    ok = (new_bh == new_bh) and (old_bh == old_bh) and abs(new_bh - old_bh) > 1.0
    print(f"[測試3] benchmark切換確實生效：新(0050含息)={new_bh:+.2f}% 舊(TAIEX價格)={old_bh:+.2f}% "
          f"差={new_bh - old_bh:+.2f}pp：{'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    r1 = test_self_regression()
    r2 = test_lagged_regression()
    r3 = test_benchmark_switch_smoke()
    overall = r1 and r2 and r3
    print(f"\n整體結果：{'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)
