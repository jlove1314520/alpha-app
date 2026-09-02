"""`HYPOTHESIS_QUEUE.md`#17（52週高點接近度）GATE_SEQUENCE第3/5/6關補完腳本。

**存在的理由（誠實記錄，不是重造輪子）**：`f52w_high_portfolio_v1.py`（上一輪
排程寫的，逐字比照`dividend_yield_portfolio_v1.py`架構）只做了第2關（隨機
控制組）+第4關（成本1x/2x/3x）+第7關（樣本外train/val）+下檔保護，這正好
複製了`dividend_yield_portfolio_v1.py`/`pead_portfolio_v1.py`/
`deep_dive_f_low_vol.py`三個既有股票策略層腳本共同的缺口——它們都跳過了
第3關（參數密集高原）、第5關（leave-one-out）、第6關（逐年一致性），
直接從第2/4關跳到第7關。這在它們身上沒被抓到是因為三者全部在第7關
alpha顯著性判準就FAIL了，過去沒人回頭補第3/5/6關。**但`HYPOTHESIS_QUEUE.md`
「統一關卡」章節明文「不得跳關」**，而這次任務指示明確要求完整跑
第2→3→4→5→6→7關，所以這裡新增本腳本補上第3/5/6關，不修改
`f52w_high_portfolio_v1.py`本體（它的第2/4/7/9關做法沒有錯，只是不完整）。

**方法論參考**：`pair_trading_gates.py`是本專案目前唯一完整落實
GATE_SEQUENCE第2~9關順序的既有腳本，這裡的第3/5/6關實作方式跟它同一套
精神（第3關參數網格看正報酬點的比例、第6關逐年獨立回測看方向一致性），
唯一差異是**第5關leave-one-out的計算方式**：配對交易是市場中立、有明確
的「進場/出場」回合式交易，可以直接用`net_pnl`依平倉年份加總；這裡是
做多、月頻換股的連續部位策略，沒有回合式交易可以按年份歸屬損益，所以改用
「用完整TRAIN期單次回測的equity curve反推逐年報酬、幾何連乘」的標準做法
——這是leave-one-out在連續複利報酬序列上的標準操作方式，跟`fut_basis_carry`
（`TRIALS_LEDGER.md`#35→#37）判斷「82倍放大集中在2000-2002三年」用的
邏輯是同一種（看拿掉貢獻最大年份後，複利總報酬是否由正轉負）。

**只測TRAIN期（開發期探索），不動VAL**——跟`pair_trading_gates.py`docstring
講的原則一致：第2~6關屬於開發期探索，可以用開發期資料反覆測試找出穩健的
參數/機制範圍；只有第7關（`f52w_high_portfolio_v1.py`已經做了）才是正式
樣本外判定，VAL期資料不可以被這幾關的探索過程碰到。

2026-09-02新增，`HYPOTHESIS_QUEUE.md`#17第2關以後任務接續執行。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

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
    REBALANCE_DAYS as ANCHOR_REBALANCE_DAYS,
    TOP_N as ANCHOR_TOP_N,
    make_signal_fn,
)

TRAIN_START = "2015-01-01"
TRAIN_END = holdout.TRAIN_END  # "2020-12-31"


def _run(signal_fn, data, market_df, start, end, top_n, rebalance_days, cost_multiplier=1.0):
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=top_n,
                          rebalance_every_n_days=rebalance_days, book_name="f52w_high_gates",
                          cost_multiplier=cost_multiplier)
    return run_backtest(signal_fn, data, market_df, cfg)


def gate3_parameter_plateau(data, market_df, industry_map, liquidity) -> dict:
    print("\n" + "=" * 70)
    print("第3關：參數密集高原（TRAIN期，1x成本）")
    print("=" * 70)
    signal_fn = make_signal_fn(industry_map, liquidity)

    rows = []
    top_n_grid = [10, 15, ANCHOR_TOP_N, 25, 30]
    print(f"  掃描一：TOP_N in {top_n_grid}（固定REBALANCE_DAYS={ANCHOR_REBALANCE_DAYS}）")
    for tn in top_n_grid:
        r = _run(signal_fn, data, market_df, TRAIN_START, TRAIN_END, tn, ANCHOR_REBALANCE_DAYS)
        rows.append({"dim": "top_n", "top_n": tn, "rebalance_days": ANCHOR_REBALANCE_DAYS,
                     "return_pct": r.total_return_pct, "n_trades": r.n_trades, "mdd_pct": r.max_drawdown_pct})
        print(f"    TOP_N={tn:>3d}  報酬={r.total_return_pct:+8.2f}%  n_trades={r.n_trades}  MDD={r.max_drawdown_pct:.2f}%")

    rebal_grid = [10, 21, 42, 63]
    print(f"  掃描二：REBALANCE_DAYS in {rebal_grid}（固定TOP_N={ANCHOR_TOP_N}）")
    for rd in rebal_grid:
        if rd == ANCHOR_REBALANCE_DAYS:
            continue  # 已在掃描一算過(TOP_N=20,REBALANCE_DAYS=21)這個錨點，不重算
        r = _run(signal_fn, data, market_df, TRAIN_START, TRAIN_END, ANCHOR_TOP_N, rd)
        rows.append({"dim": "rebalance_days", "top_n": ANCHOR_TOP_N, "rebalance_days": rd,
                     "return_pct": r.total_return_pct, "n_trades": r.n_trades, "mdd_pct": r.max_drawdown_pct})
        print(f"    REBALANCE_DAYS={rd:>3d}  報酬={r.total_return_pct:+8.2f}%  n_trades={r.n_trades}  MDD={r.max_drawdown_pct:.2f}%")

    grid_df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    grid_df.to_csv(out_dir / "f52w_high_gate3_grid.csv", index=False)

    n_positive = int((grid_df["return_pct"] > 0).sum())
    frac_positive = n_positive / len(grid_df)
    anchor_row = grid_df[(grid_df["top_n"] == ANCHOR_TOP_N) & (grid_df["rebalance_days"] == ANCHOR_REBALANCE_DAYS)]
    anchor_return = float(anchor_row["return_pct"].iloc[0]) if len(anchor_row) else float("nan")
    print(f"\n  登錄門檻點(TOP_N={ANCHOR_TOP_N},REBALANCE_DAYS={ANCHOR_REBALANCE_DAYS})報酬={anchor_return:+.2f}%；"
          f"網格{len(grid_df)}點中報酬為正的有{n_positive}點({frac_positive*100:.0f}%)")
    gate3_pass = frac_positive >= 0.60
    print(f"  第3關判定（門檻：網格內>=60%的點報酬為正，不是只有登錄點單點孤峰）："
          f"{'PASS' if gate3_pass else 'FAIL'}")
    return {"pass": gate3_pass, "frac_positive": frac_positive, "anchor_return": anchor_return,
            "grid": grid_df.to_dict("records")}


def _yearly_returns_from_equity_curve(equity_curve: pd.DataFrame, years: list[int], initial_capital: float) -> dict[int, float]:
    """從單次連續回測的equity curve反推逐年報酬（複利連乘用），用日曆年切分。
    第一年的起點用`initial_capital`（回測起點），其餘年份的起點用上一年最後
    一個交易日的equity（確保逐年報酬串接起來的複利連乘等於總報酬，這是驗證
    這個反推方法正確性的關鍵一致性檢查，見`main()`裡的印出比對）。
    """
    ec = equity_curve.copy()
    ec["date"] = pd.to_datetime(ec["date"])
    ec = ec.sort_values("date")
    yearly = {}
    prev_end_equity = initial_capital
    for y in years:
        mask = ec["date"].dt.year == y
        if not mask.any():
            continue
        year_end_equity = float(ec.loc[mask, "equity"].iloc[-1])
        yearly[y] = year_end_equity / prev_end_equity - 1
        prev_end_equity = year_end_equity
    return yearly


def gate5_leave_one_out(equity_curve: pd.DataFrame, initial_capital: float) -> dict:
    print("\n" + "=" * 70)
    print("第5關：leave-one-out（TRAIN期逐年拿掉最大貢獻年份，複利連乘反推）")
    print("=" * 70)
    years = list(range(2015, 2021))
    yearly = _yearly_returns_from_equity_curve(equity_curve, years, initial_capital)
    print(f"  逐年報酬（由equity curve反推）：{ {y: f'{v*100:+.2f}%' for y, v in yearly.items()} }")

    compounded_total = 1.0
    for v in yearly.values():
        compounded_total *= (1 + v)
    compounded_total_pct = (compounded_total - 1) * 100
    print(f"  逐年複利連乘總報酬={compounded_total_pct:+.2f}%"
          f"（用來跟`f52w_high_portfolio_v1_checkpoint.json`裡TRAIN['real']['return_pct']"
          f"比對，確認反推年報酬序列正確，見主程式印出的一致性檢查）")

    if not yearly:
        print("  無法反推任何年度報酬（equity curve可能是空的），第5關判FAIL。")
        return {"pass": False, "yearly": yearly, "compounded_total_pct": compounded_total_pct}

    max_year = max(yearly, key=lambda y: yearly[y])
    max_year_return = yearly[max_year]
    print(f"  貢獻最大年份={max_year}（該年報酬={max_year_return*100:+.2f}%）")

    loo_compounded = 1.0
    for y, v in yearly.items():
        if y == max_year:
            continue
        loo_compounded *= (1 + v)
    loo_total_pct = (loo_compounded - 1) * 100
    print(f"  拿掉{max_year}後剩餘複利總報酬={loo_total_pct:+.2f}%"
          f"（{'仍為正' if loo_total_pct > 0 else '轉負，過度集中在單一年份'}）")

    gate5_pass = not (compounded_total_pct > 0 and loo_total_pct <= 0)
    print(f"  第5關判定（門檻：原本為正報酬的話，拿掉最大貢獻年份後不能整個翻負）："
          f"{'PASS' if gate5_pass else 'FAIL'}")
    return {"pass": gate5_pass, "yearly": yearly, "compounded_total_pct": compounded_total_pct,
            "max_year": max_year, "max_year_return": max_year_return, "loo_total_pct": loo_total_pct}


def gate6_yearly_consistency(data, market_df, industry_map, liquidity) -> dict:
    print("\n" + "=" * 70)
    print("第6關：逐年一致性（TRAIN期6個年度，各自獨立回測，方向vs 0%）")
    print("=" * 70)
    signal_fn = make_signal_fn(industry_map, liquidity)
    years = list(range(2015, 2021))
    rows = []
    for y in years:
        y_start, y_end = f"{y}-01-01", f"{y}-12-31"
        r = _run(signal_fn, data, market_df, y_start, y_end, ANCHOR_TOP_N, ANCHOR_REBALANCE_DAYS)
        rows.append({"year": y, "return_pct": r.total_return_pct, "n_trades": r.n_trades})
        print(f"    {y}: 報酬={r.total_return_pct:+8.2f}%  n_trades={r.n_trades}")
    yearly_df = pd.DataFrame(rows)
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    yearly_df.to_csv(out_dir / "f52w_high_gate6_yearly.csv", index=False)

    n_positive = int((yearly_df["return_pct"] > 0).sum())
    n_years = len(yearly_df)
    print(f"\n  {n_years}個年度中報酬為正的年度數={n_positive}/{n_years}")
    gate6_pass = (n_years >= 6) and (n_positive >= 5)
    print(f"  第6關判定（門檻：至少6個年度區間、其中>=5個方向一致為正）："
          f"{'PASS' if gate6_pass else 'FAIL'}")
    return {"pass": gate6_pass, "n_positive": n_positive, "n_years": n_years,
            "yearly": yearly_df.to_dict("records")}


def main() -> dict:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in f52w_high_gates")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in f52w_high_gates")

    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    t0 = time.time()
    gate3 = gate3_parameter_plateau(data, market_df, industry_map, liquidity)
    if not gate3["pass"]:
        print("\n**第3關參數高原未過，快殺判定FAIL，不進第5/6關。**")
        result = {"final_gate": 3, "verdict": "FAIL", "gate3": gate3}
        print(f"\n(耗時{time.time()-t0:.1f}s)")
        return result

    print("\n計算TRAIN期完整equity curve（用於第5關leave-one-out反推逐年報酬）...")
    signal_fn = make_signal_fn(industry_map, liquidity)
    real_result = _run(signal_fn, data, market_df, TRAIN_START, TRAIN_END, ANCHOR_TOP_N, ANCHOR_REBALANCE_DAYS)
    print(f"  TRAIN(錨點參數,1x成本)報酬={real_result.total_return_pct:+.2f}%"
          f"（比對`f52w_high_portfolio_v1_checkpoint.json`的TRAIN['real']['return_pct']"
          f"應該非常接近，兩者用同一組參數/同一份快取資料，些微差異只可能來自"
          f"浮點/日期邊界，不應有量級落差）")

    gate5 = gate5_leave_one_out(real_result.equity_curve, real_result.config.initial_capital)
    if not gate5["pass"]:
        print("\n**第5關leave-one-out未過，快殺判定FAIL，不進第6關。**")
        result = {"final_gate": 5, "verdict": "FAIL", "gate3": gate3, "gate5": gate5}
        print(f"\n(耗時{time.time()-t0:.1f}s)")
        return result

    gate6 = gate6_yearly_consistency(data, market_df, industry_map, liquidity)
    verdict = "PASS" if gate6["pass"] else "FAIL"
    if not gate6["pass"]:
        print("\n**第6關逐年一致性未過，快殺判定FAIL，不進第7關（第7關由`f52w_high_portfolio_v1.py`另行執行判定）。**")
    else:
        print("\n**第3/5/6關全數PASS**——`f52w_high_portfolio_v1.py`負責的第2/4/7/9關另行判定，"
              "兩支腳本合併起來才是完整GATE_SEQUENCE第2~9關的結果。")

    result = {"final_gate": 6, "verdict": verdict, "gate3": gate3, "gate5": gate5, "gate6": gate6}

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"
    print(f"\n(耗時{time.time()-t0:.1f}s)")
    return result


if __name__ == "__main__":
    r = main()
    print("\n\n=== 第3/5/6關最終結果 ===")
    print(r.get("verdict"), "at gate", r.get("final_gate"))
