"""weinstein_stage2_v2的alpha/beta顯著性關卡——跟`weinstein_alpha_gate.py`
（v1）完全同一套方法論，**唯一差異是重用`strategies.run_weinstein_
unbiased_v2`（v2訊號函式）而不是v1**。沿用既有工具
（`long_only_vs_market.decompose_alpha_beta()`、
`validation.control_group.extract_trade_schedule()`）。

這不會呼叫`unlock_holdout_once()`——通過關卡只代表「可以回報使用者由
使用者決定」，不是自動解鎖。

Run with: `python weinstein_v2_alpha_gate.py` from research/.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from finmind_client import load_dev
from validation import holdout
from validation.control_group import extract_trade_schedule
from backtest.engine import BacktestConfig, run_backtest, buy_leg_rate, sell_leg_rate
from strategies.weinstein_stage2 import prepare_market_data, prepare_price_data
from strategies.weinstein_stage2_v2 import stage2_signal_v2
from strategies.run_weinstein_unbiased_v2 import (
    SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_price_data,
    main as run_weinstein_v2_main,
)
from universe import universe as build_universe
from long_only_vs_market import decompose_alpha_beta

N_RANDOM = 200
CONTROL_SEED = 20260822
SINGLE_TEST_THRESHOLD = 90.0


def _matched_draw_equity_curve(trade_schedule, indexed_price_data, calendar, initial_capital,
                                slot_allocation, cost_rates, rng, price_col="adj_close") -> pd.DataFrame:
    events_by_entry: dict[str, list] = {}
    events_by_exit: dict[str, list] = {}
    for i, trade in enumerate(trade_schedule):
        entry_date, exit_date = trade["entry_date"], trade["exit_date"]
        candidates = [sid for sid, df in indexed_price_data.items()
                      if entry_date in df.index and exit_date in df.index]
        if not candidates:
            continue
        sid = rng.choice(candidates)
        entry_price = float(indexed_price_data[sid].loc[entry_date, price_col])
        if entry_price <= 0:
            continue
        shares = int(slot_allocation // (entry_price * (1 + cost_rates["buy"])))
        if shares <= 0:
            continue
        events_by_entry.setdefault(entry_date, []).append((i, sid, shares, entry_price))
        events_by_exit.setdefault(exit_date, []).append(i)

    cash = initial_capital
    open_positions: dict[int, dict] = {}
    rows = []
    for day in calendar:
        for (i, sid, shares, entry_price) in events_by_entry.get(day, []):
            notional = shares * entry_price
            cash -= notional * (1 + cost_rates["buy"])
            open_positions[i] = {"sid": sid, "shares": shares, "entry_price": entry_price}
        for i in events_by_exit.get(day, []):
            pos = open_positions.pop(i, None)
            if pos is None:
                continue
            sid, shares = pos["sid"], pos["shares"]
            df = indexed_price_data[sid]
            exit_price = float(df.loc[day, price_col]) if day in df.index else pos["entry_price"]
            notional = shares * exit_price
            cash += notional * (1 - cost_rates["sell"])
        mtm = cash
        for pos in open_positions.values():
            sid = pos["sid"]
            df = indexed_price_data[sid]
            price = float(df.loc[day, price_col]) if day in df.index else pos["entry_price"]
            mtm += pos["shares"] * price
        rows.append({"date": day, "equity": mtm})
    return pd.DataFrame(rows)


def run_alpha_gate_for_period(label, result, market_df, indexed_price_data, n_random=N_RANDOM,
                               seed=CONTROL_SEED) -> dict:
    print(f"\n=== alpha/beta 拆解關卡：{label} ===")
    real_decomp = decompose_alpha_beta(result.equity_curve, market_df)
    print(f"  真實策略：beta={real_decomp['beta']:+.4f}  純alpha年化={real_decomp['alpha_ann_pct']:+.2f}%  "
          f"純alpha累積={real_decomp['alpha_total_return_pct']:+.2f}%  alpha_Sortino={real_decomp['alpha_sortino']:.3f}  "
          f"alpha_MDD={real_decomp['alpha_mdd_pct']:.2f}%  beta貢獻={real_decomp['beta_contribution_pct']:+.2f}%  "
          f"總報酬={real_decomp['total_return_pct']:+.2f}%")

    schedule = extract_trade_schedule(result.trades)
    print(f"  交易排程：{len(schedule)} 組進出場（trades={result.n_trades}）")
    if not schedule:
        print("  無交易紀錄，無法建立配對式隨機控制組，略過")
        return {"label": label, "real": real_decomp, "random_alpha_returns": [], "percentile": float("nan"),
                "n_trades": result.n_trades}

    cfg = result.config
    cost_rates = {"buy": buy_leg_rate(cfg), "sell": sell_leg_rate(cfg)}
    slot_allocation = cfg.initial_capital / cfg.max_positions
    calendar = sorted(market_df[(market_df["date"] >= cfg.start_date) &
                                 (market_df["date"] <= cfg.end_date)]["date"])

    random_alpha_returns = []
    for i in range(n_random):
        rng = random.Random(seed + i)
        curve = _matched_draw_equity_curve(schedule, indexed_price_data, calendar, cfg.initial_capital,
                                            slot_allocation, cost_rates, rng)
        decomp = decompose_alpha_beta(curve, market_df)
        random_alpha_returns.append(decomp["alpha_total_return_pct"])

    real_alpha = real_decomp["alpha_total_return_pct"]
    valid = [v for v in random_alpha_returns if not np.isnan(v)]
    pct = 100.0 * float(np.mean([real_alpha > v for v in valid])) if valid else float("nan")
    print(f"  配對式隨機控制組（n={len(valid)}/{n_random} 有效抽樣）：")
    if valid:
        print(f"    真實策略純alpha累積={real_alpha:+.2f}%  隨機分布中位數={np.median(valid):+.2f}%  "
              f"隨機分布[5%,95%]=[{np.percentile(valid,5):+.2f}%, {np.percentile(valid,95):+.2f}%]")
    print(f"    percentile={pct:.1f}（單測門檻{SINGLE_TEST_THRESHOLD}）")

    return {"label": label, "real": real_decomp, "random_alpha_returns": random_alpha_returns,
            "percentile": pct, "n_trades": result.n_trades}


def run_cost_sensitivity(price_data, market_df, start, end, label):
    print(f"\n=== 成本敏感度（1x/2x/3x，alpha拆解版）：{label} ===")
    rows = []
    for mult in (1, 2, 3):
        cfg = BacktestConfig(start_date=start, end_date=end, cost_multiplier=mult)
        r = run_backtest(stage2_signal_v2, price_data, market_df, cfg)
        decomp = decompose_alpha_beta(r.equity_curve, market_df)
        print(f"  {mult}x成本：總報酬={decomp['total_return_pct']:+.2f}%  beta={decomp['beta']:+.4f}  "
              f"純alpha累積={decomp['alpha_total_return_pct']:+.2f}%（年化{decomp['alpha_ann_pct']:+.2f}%）  "
              f"trades={r.n_trades}")
        rows.append({"cost_multiplier": mult, **decomp, "n_trades": r.n_trades})
    return rows


def main():
    print("=== weinstein_stage2_v2 alpha/beta 顯著性關卡 ===")
    print("is_holdout_consumed() 開始前檢查：", holdout.is_holdout_consumed())
    assert not holdout.is_holdout_consumed(), "holdout已被使用，這個任務不該在這個狀態下執行"

    print("\n步驟1-3：重用 run_weinstein_unbiased_v2.main()（同一批快取樣本）")
    results, train_result, val_result, cg = run_weinstein_v2_main()

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in weinstein_v2_alpha_gate")
    market_df = prepare_market_data(market_raw)

    print("\n重建與 run_weinstein_v2_main() 內部同一批 price_data（同SAMPLE_SEED，完全命中本機快取）...")
    u = build_universe()
    rng = random.Random(SAMPLE_SEED)
    sample_ids = rng.sample(list(u["stock_id"]), SAMPLE_SIZE)
    raw_price_data = load_sample_price_data(sample_ids)
    price_data = prepare_price_data(raw_price_data)
    indexed_price_data = {sid: df.set_index("date") for sid, df in price_data.items()}
    print(f"  {len(price_data)}/{SAMPLE_SIZE} 檔可用（應與run_weinstein_v2_main()內部一致）")

    val_gate = run_alpha_gate_for_period("VALIDATION", val_result, market_df, indexed_price_data)
    train_gate = run_alpha_gate_for_period("TRAIN", train_result, market_df, indexed_price_data)

    val_cost = run_cost_sensitivity(price_data, market_df, val_result.config.start_date,
                                     val_result.config.end_date, "VALIDATION")
    train_cost = run_cost_sensitivity(price_data, market_df, train_result.config.start_date,
                                       train_result.config.end_date, "TRAIN")

    print("\nis_holdout_consumed() 結束前複查：", holdout.is_holdout_consumed())
    assert not holdout.is_holdout_consumed(), "本輪執行途中holdout狀態被改變，這不該發生"

    pd.DataFrame([
        {"period": "validation", **val_gate["real"], "control_percentile": val_gate["percentile"],
         "n_trades": val_gate["n_trades"]},
        {"period": "train", **train_gate["real"], "control_percentile": train_gate["percentile"],
         "n_trades": train_gate["n_trades"]},
    ]).to_csv("data/weinstein_v2_alpha_gate_summary.csv", index=False)
    pd.DataFrame(val_cost).to_csv("data/weinstein_v2_alpha_gate_val_cost_sensitivity.csv", index=False)
    pd.DataFrame(train_cost).to_csv("data/weinstein_v2_alpha_gate_train_cost_sensitivity.csv", index=False)
    print("\n輸出：data/weinstein_v2_alpha_gate_summary.csv、"
          "data/weinstein_v2_alpha_gate_{val,train}_cost_sensitivity.csv（皆gitignored）")

    return {"val": val_gate, "train": train_gate, "val_cost": val_cost, "train_cost": train_cost}


if __name__ == "__main__":
    main()
