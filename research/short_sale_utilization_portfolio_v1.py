"""個股融券使用率（Short Sale Utilization）portfolio層構造 — `HYPOTHESIS_
QUEUE.md`#36第2關以後。

**事前綁定的方向與構造選擇（測試前寫死，不事後移動門柱）**：第1關cheap IC
gate（`factor_ic_short_sale_utilization.py`，`TRIALS_LEDGER.md`#129）已
確認`f_short_sale_utilization`對未來報酬的IC為負（train/val同號、null
percentile=100.0）——融券使用率越高，未來報酬越差。**這支腳本測的是這個
訊號的鏡像多頭讀法：融券使用率最低的股票（知情放空者最不感興趣的標的）
未來報酬應該相對較好**，直接沿用既有多頭only的`backtest/engine.py`
（`grep -n short backtest/engine.py`確認過完全沒有放空/負權重支援，見
`HYPOTHESIS_QUEUE_PROTOCOL.md`第十輪排程當輪查證），不是重新造一個放空
引擎——這是本輪刻意的範圍限縮，不是忘記測試真正的放空腿。

**誠實的已知限制（不要在收工訊息裡藏起來）**：`HYPOTHESIS_QUEUE.md`#36
條目原文要求portfolio construction階段要把「放空可行性/借券成本/強制
回補風險」計入——這支腳本**沒有**做到，因為現有引擎是多頭only，無法
模擬真實放空部位。這支腳本測的是訊號的多頭鏡像半邊（低使用率長多），
不等於驗證了完整的「賣空高使用率」策略。如果多頭鏡像半邊PASS，代表訊號
本身有可交易的長邊價值，但「放空高使用率那一腿是否也真的可行、扣掉借券
成本後是否仍有alpha」仍是未驗證、需要引擎擴充後才能回答的獨立問題，不能
把這支腳本的PASS/FAIL結果直接當成對完整放空策略的判定。

**沿用而非重造的基礎設施**（逐字比照`margin_utilization_regime_
portfolio_v1.py`checkpoint模式，理由同該檔案docstring：單次完整
TRAIN+VALIDATION執行預期超過無人值守單輪時間預算，需要跨輪落盤接續）：
- `factor_ic.py`：抽樣宇宙（SAMPLE_SIZE=300，跟#116/#129同一個宇宙+seed）、
  快取樣本+因子（含`f_short_sale_utilization`）。
- `backtest/engine.py`：月頻換股(21交易日)、三成本層級。
- `portfolio_backtest_v2.py`：只借用流動性代理/alpha顯著性/Sharpe/
  買進持有基準等跟因子組成無關的通用函式。
- `validation/holdout.py`：TRAIN/VAL切分、holdout防呆。

**控制組設計**（`CONSTITUTION.md`「每個候選都要打贏隨機控制組」鐵律）：
真實策略跟隨機控制組共用同一個流動性篩選後候選池，唯一差異是真實策略挑
「融券使用率最低」的TOP_N檔，隨機控制組從同一個池子「隨機」挑TOP_N檔——
隔離出「刻意挑低使用率個股」相對「隨機留在場內」有沒有加值，不是跟買進
持有大盤比。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續#36第2關以後。
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import portfolio_backtest_v2 as pbv2  # 只借用跟因子組成無關的通用機制，見模組docstring
from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 20
REBALANCE_DAYS = 21  # 月頻，跟本佇列其餘portfolio層構造(#4/#3/#17/#30)同一個節奏，方便比較

CHECKPOINT_PATH = Path(__file__).parent / "data" / "short_sale_utilization_portfolio_v1_checkpoint.json"


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, indent=2, ensure_ascii=False), encoding="utf-8")


def _snapshot(as_of, price_data, liquidity) -> pd.DataFrame:
    rows = []
    for sid, d in price_data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        su = d.loc[idx[0]].get("f_short_sale_utilization")
        if pd.isna(su):
            continue
        liq = liquidity[sid].get(as_of) if sid in liquidity and as_of in liquidity[sid].index else None
        rows.append({"stock_id": sid, "short_sale_utilization": float(su), "liquidity_proxy": liq})
    if not rows:
        return pd.DataFrame(columns=["stock_id", "short_sale_utilization", "liquidity_proxy"])
    df = pd.DataFrame(rows)
    liq_vals = df["liquidity_proxy"].dropna()
    if len(liq_vals) >= 10:  # 分位數樣本太小沒有意義，門檻沿用factor_ic.py/pbv2慣例量級
        floor = np.percentile(liq_vals, pbv2.LIQUIDITY_FLOOR_PERCENTILE)
        df = df[df["liquidity_proxy"].isna() | (df["liquidity_proxy"] >= floor)]
    return df


def signal_fn(price_data, as_of, market_df, liquidity=None):
    df = _snapshot(as_of, price_data, liquidity)
    if df.empty or len(df) < TOP_N:
        return {}
    top = df.sort_values("short_sale_utilization", ascending=True).head(TOP_N)  # 挑使用率最低=知情放空者最不感興趣
    return dict(zip(top["stock_id"], [1.0] * len(top)))


def make_signal_fn(liquidity):
    def fn(price_data, as_of, market_df):
        return signal_fn(price_data, as_of, market_df, liquidity)
    return fn


def make_random_signal_fn(liquidity, seed):
    rng = random.Random(seed)

    def fn(price_data, as_of, market_df):
        df = _snapshot(as_of, price_data, liquidity)
        if df.empty:
            return {}
        pool = df["stock_id"].tolist()
        picks = pool if len(pool) <= TOP_N else rng.sample(pool, TOP_N)
        return {sid: 1.0 for sid in picks}
    return fn


def run_one(label, data, market_df, liquidity, start, end, n_random=100, deadline: float | None = None) -> dict | None:
    """跟`margin_utilization_regime_portfolio_v1.run_one()`同一套checkpoint
    可續跑機制（理由見該檔案docstring）。"""
    ckpt_all = _load_checkpoint()
    ckpt = ckpt_all.setdefault(label, {})

    sfn = make_signal_fn(liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="short_sale_utilization_portfolio_v1")

    if "real" not in ckpt:
        print(f"  [{label}] 計算真實訊號回測...")
        result = run_backtest(sfn, data, market_df, cfg)
        holdout.assert_no_holdout_leakage(result.trades, date_col="date",
                                           context=f"short_sale_utilization_portfolio_v1 {label}")
        alpha = pbv2.alpha_significance(result.equity_curve, market_df)
        sharpe = pbv2.sharpe_ratio(result.equity_curve)
        bh_pct = pbv2.buy_and_hold_index_pct(market_df, start, end)
        ckpt["real"] = {
            "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
            "sortino": result.sortino_ratio, "sharpe": sharpe, "n_trades": result.n_trades,
            "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
            "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
            "buy_and_hold_index_pct": bh_pct, "final_equity": result.final_equity,
        }
        ckpt["cost_returns"] = {"1": result.total_return_pct}
        ckpt.setdefault("random_finals", [])
        _save_checkpoint(ckpt_all)

    if len(ckpt["cost_returns"]) < 3:
        print(f"  [{label}] 計算成本敏感度 2x/3x...")
        for mult in (2, 3):
            if str(mult) in ckpt["cost_returns"]:
                continue
            c = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                                rebalance_every_n_days=REBALANCE_DAYS, book_name=cfg.book_name, cost_multiplier=mult)
            r = run_backtest(sfn, data, market_df, c)
            ckpt["cost_returns"][str(mult)] = r.total_return_pct
        _save_checkpoint(ckpt_all)

    random_finals = ckpt.get("random_finals", [])
    start_i = len(random_finals)
    if start_i < n_random:
        print(f"  [{label}] 隨機控制組進度 {start_i}/{n_random}，接續執行...")
    for i in range(start_i, n_random):
        if deadline is not None and time.time() > deadline:
            print(f"  [{label}] 時間預算已到，隨機控制組進度 {len(random_finals)}/{n_random}，已checkpoint，下次執行接續")
            return None
        rfn = make_random_signal_fn(liquidity, seed=20260905 + i)
        rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                               rebalance_every_n_days=REBALANCE_DAYS, book_name=f"{cfg.book_name}_random")
        rr = run_backtest(rfn, data, market_df, rcfg)
        random_finals.append(rr.final_equity)
        ckpt["random_finals"] = random_finals
        if len(random_finals) % 10 == 0:
            _save_checkpoint(ckpt_all)
            print(f"  [{label}] 隨機控制組進度 {len(random_finals)}/{n_random}")
    ckpt["random_finals"] = random_finals
    _save_checkpoint(ckpt_all)

    if len(random_finals) < n_random:
        return None

    real = ckpt["real"]
    cost_returns = {int(k): v for k, v in ckpt["cost_returns"].items()}
    real_final = real["final_equity"]
    random_percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))

    return {
        "label": label, "start": start, "end": end,
        "return_pct": real["return_pct"], "mdd_pct": real["mdd_pct"],
        "sortino": real["sortino"], "sharpe": real["sharpe"], "n_trades": real["n_trades"],
        "alpha_ann_pct": real["alpha_ann_pct"], "beta": real["beta"],
        "alpha_pvalue": real["alpha_pvalue"], "alpha_significant": real["alpha_significant"],
        "cost_1x": cost_returns[1], "cost_2x": cost_returns[2], "cost_3x": cost_returns[3],
        "buy_and_hold_index_pct": real["buy_and_hold_index_pct"],
        "random_control_median_pct": (float(np.median(random_finals)) / cfg.initial_capital - 1) * 100,
        "random_control_percentile": random_percentile,
        "n_random": len(random_finals),
    }


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in short_sale_utilization_portfolio_v1")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in short_sale_utilization_portfolio_v1")

    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    import os
    TIME_BUDGET_SECONDS = float(os.environ.get("SSUP_TIME_BUDGET_SECONDS", "420"))
    deadline = time.time() + TIME_BUDGET_SECONDS

    print(f"\n========== 第2/7關 train/val樣本外+隨機控制組（做多融券使用率最低分位，"
          f"可續跑checkpoint，本次預算{TIME_BUDGET_SECONDS}秒）==========")
    results = {}
    incomplete_label = None
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
        r = run_one(label, data, market_df, liquidity, start, end, n_random=100, deadline=deadline)
        if r is None:
            incomplete_label = label
            break
        results[label] = r
        print(f"\n--- {label} ({start}..{end}) ---")
        print(f"  報酬={r['return_pct']:+.2f}%  MDD={r['mdd_pct']:.2f}%  Sortino={r['sortino']:.3f}  "
              f"Sharpe={r['sharpe']:.3f}  trades={r['n_trades']}")
        print(f"  alpha(年化)={r['alpha_ann_pct']:+.2f}%  beta={r['beta']:+.3f}  "
              f"p={r['alpha_pvalue']:.4f}  顯著為正={r['alpha_significant']}")
        print(f"  買進持有大盤={r['buy_and_hold_index_pct']:+.2f}%  "
              f"隨機控制組(N={r['n_random']}，同池隨機選股)中位數={r['random_control_median_pct']:+.2f}%  "
              f"percentile={r['random_control_percentile']:.1f}")
        print(f"  成本1x/2x/3x: {r['cost_1x']:+.2f}% / {r['cost_2x']:+.2f}% / {r['cost_3x']:+.2f}%")

    if incomplete_label is not None:
        print(f"\n**本次{TIME_BUDGET_SECONDS}秒時間預算內未跑完（卡在{incomplete_label}），"
              f"進度已存進{CHECKPOINT_PATH}，不做任何PASS/FAIL判定。"
              f"重新執行`python short_sale_utilization_portfolio_v1.py`會自動從中斷處接續，"
              f"不會重算已完成的label/隨機控制組筆數。**")
        holdout_ok = holdout.is_holdout_consumed() is False
        print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
        assert holdout_ok, "holdout must remain untouched (after)"
        return

    pd.DataFrame(results.values()).to_csv("data/short_sale_utilization_portfolio_v1_results.csv", index=False)
    print("\n已存 data/short_sale_utilization_portfolio_v1_results.csv")

    val = results["VALIDATION"]
    gate2_pass = (val["random_control_percentile"] >= 90.0)
    print(f"\n第2/7關判定（打贏『同池隨機選股』對照組，不是跟買進持有大盤比）："
          f"{'PASS' if gate2_pass else 'FAIL'}（VAL期隨機控制組percentile>=90.0）")

    if not gate2_pass:
        print("\n**第2/7關未過，直接結案FAIL，不進第3~9關**")
        return

    print("\n下一步：第3關參數密集高原（TOP_N附近網格）、第4關成本敏感度已算好見上方"
          "1x/2x/3x（尚未含放空借券成本，因引擎不支援放空，見模組docstring已知限制）、"
          "第5/6關leave-one-out+逐年一致性、第7關樣本外、第9關下檔保護。")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
