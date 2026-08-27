"""補上 TAIEX 買進持有基準本身的 MDD/Sortino/Sharpe（2026-08-27 馬拉松第137輪）。

背景：`REPORT.md` 2026-08-26（晚）條目「建議下一步」(c) 明確點出——
`portfolio_multifactor_v2` 的結果表只列了買進持有大盤的總報酬（VAL +54.58%／
TRAIN +58.86%，見 `portfolio_backtest_v2.py::buy_and_hold_index_pct()`），沒有
算過大盤本身同期的 MDD/Sortino，導致「策略 MDD 明顯更低」這個判讀只有質化描述，
沒有量化基準可以對照。這支腳本只做這一件補充分析，不重新跑組合回測本身，也不是
新的單因子/策略假說試驗（不產生 PASS/FAIL 判定，不寫入 TRIALS_LEDGER.md）。

MDD/Sortino 公式跟 `backtest/engine.py::BacktestResult.max_drawdown_pct`／
`.sortino_ratio` 逐行一致（同樣的 running-max drawdown 定義、同樣的 MAR=0 假設），
確保跟策略端的數字可以直接互相比較，不是兩套不同定義各說各話。Sharpe 沿用
`portfolio_backtest_v2.py::sharpe_ratio()` 同一個公式。

全程走 `finmind_client.load_dev()`（holdout-safe，自動截斷在 VAL_END），沒有呼叫
`load_full_history()`/`unlock_holdout_once()`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

START_DATE = "2010-01-01"  # 跟 factor_ic.py/portfolio_backtest_v2.py 同一個暖機起點
PERIODS = {
    "TRAIN": ("2015-01-01", holdout.TRAIN_END),
    "VALIDATION": ("2021-01-01", holdout.VAL_END),
}


def index_series(market_df: pd.DataFrame, start: str, end: str) -> pd.Series:
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    return window.set_index("date")["close"]


def max_drawdown_pct(price: pd.Series) -> float:
    """跟 backtest/engine.py::BacktestResult.max_drawdown_pct 同公式（running-max）。"""
    if price.empty:
        return 0.0
    running_max = price.cummax()
    dd = (price - running_max) / running_max
    return float(dd.min() * 100)


def sortino_ratio(price: pd.Series) -> float:
    """跟 backtest/engine.py::BacktestResult.sortino_ratio 同公式（MAR=0，年化 sqrt(252)）。"""
    if len(price) < 2:
        return float("nan")
    daily_returns = price.pct_change().dropna()
    if daily_returns.empty:
        return float("nan")
    downside = daily_returns[daily_returns < 0]
    downside_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
    if downside_dev == 0:
        return float("nan")
    return float(daily_returns.mean() / downside_dev * np.sqrt(252))


def sharpe_ratio(price: pd.Series) -> float:
    """跟 portfolio_backtest_v2.py::sharpe_ratio 同公式。"""
    if len(price) < 2:
        return float("nan")
    r = price.pct_change().dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(252))


def total_return_pct(price: pd.Series) -> float:
    if len(price) < 2:
        return float("nan")
    return float(price.iloc[-1] / price.iloc[0] - 1) * 100


def main():
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in benchmark_taiex_stats")
    market_df = prepare_market_data(market_raw)

    rows = []
    for label, (start, end) in PERIODS.items():
        price = index_series(market_df, start, end)
        rows.append({
            "period": label, "start": start, "end": end, "n_days": len(price),
            "return_pct": total_return_pct(price),
            "mdd_pct": max_drawdown_pct(price),
            "sortino": sortino_ratio(price),
            "sharpe": sharpe_ratio(price),
        })
        print(f"{label} ({start}~{end}, {len(price)}天)："
              f"報酬={rows[-1]['return_pct']:+.2f}%  MDD={rows[-1]['mdd_pct']:.2f}%  "
              f"Sortino={rows[-1]['sortino']:.3f}  Sharpe={rows[-1]['sharpe']:.3f}")

    out = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "data" / "benchmark_taiex_stats.csv"
    out_path.parent.mkdir(exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"\n已存檔：{out_path}")
    print(f"is_holdout_consumed() = {holdout.is_holdout_consumed()}")


if __name__ == "__main__":
    main()
