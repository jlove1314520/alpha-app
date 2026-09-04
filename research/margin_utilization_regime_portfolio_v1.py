"""個股融資使用率regime-conditional避開篩選 — `HYPOTHESIS_QUEUE.md`#30
第2關以後（portfolio層構造）。

**上一輪（deep_dive第一步）發現的關鍵事實**：`f_margin_utilization`的
unconditional cross-sectional IC（`TRIALS_LEDGER.md`#116）雖然train/val
同號、null percentile=100.0過關，但把121個20交易日快照依TAIEX同窗口報酬
正負分成下跌段/上漲段後（`factor_ic_margin_utilization_regime_split.py`，
`TRIALS_LEDGER.md`#117），VAL期下跌段|IC|=0.1817遠大於上漲段|IC|=0.0280
（約6.5倍）——訊號強度高度集中在市場下跌段，unconditional版本其實是被
上漲段的弱訊號稀釋過的結果。這支腳本把這個發現操作化成一個具體的
**regime-conditional個股避開策略**，不是重新測IC本身。

**具體設計（事前綁定，測試前寫死，不事後移動門柱）**：
- 沿用`regime_overlay.py`既有市場層級regime判定（TAIEX 200日均線位階 +
  20日已實現波動度vs擴張窗中位數，兩者皆PIT-safe，不是這輪新發明）。
- **危機regime**（`CRISIS_REGIME = ("bear_below_ma", "high_vol")`，跟
  `regime_overlay.EXPOSURE_MAP`裡曝險最低的那格完全對應）：從流動性
  篩選後的候選池中，挑「融資使用率最低」的TOP_N檔（=避開最危險的
  高融資使用率名單，操作化「危機時該優先避開哪些股票」的核心主張）。
- **非危機regime**：挑「20日均成交金額（流動性代理）最高」的TOP_N檔
  ——這個非危機期的選股規則刻意跟融資使用率完全無關、且在真實策略與
  隨機控制組兩個版本裡逐字相同，讓兩者的績效差異只可能來自「危機期間
  該挑哪些股票」這一件事，不會被非危機期間選股規則的差異污染判定。
- **隨機控制組**：跟真實策略共用同一套非危機期選股規則，只有在危機
  regime時改成「從同一個候選池隨機挑TOP_N檔」而非「挑融資使用率最低
  的TOP_N檔」——直接對應`CONSTITUTION.md`「每個候選都要打贏隨機控制組」
  鐵律，隔離出「刻意挑低融資使用率個股」相對「危機時隨機留在場內」
  有沒有加值，不是跟買進持有大盤比。

**沿用而非重造的基礎設施**（逐字比照`dividend_yield_portfolio_v1.py`
checkpoint模式，理由同該檔案docstring：單次完整TRAIN+VALIDATION執行
預期超過無人值守單輪時間預算，需要跨輪落盤接續）：
- `factor_ic.py`：抽樣宇宙（SAMPLE_SIZE=300，跟#116/#117同一個宇宙+seed）、
  快取樣本+因子（含`f_margin_utilization`）。
- `backtest/engine.py`：月頻換股(21交易日)、三成本層級。
- `regime_overlay.py`：`compute_regime_labels()`——不修改該檔案本身，
  只import它的regime判定函式。
- `portfolio_backtest_v2.py`：只借用流動性代理/alpha顯著性/Sharpe/
  買進持有基準等跟因子組成無關的通用函式。
- `validation/holdout.py`：TRAIN/VAL切分、holdout防呆。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續#30第2關以後。
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
import regime_overlay
from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 20
REBALANCE_DAYS = 21  # 月頻，跟本佇列其餘portfolio層構造(#4/#3/#17)同一個節奏，方便比較
CRISIS_REGIME = ("bear_below_ma", "high_vol")  # 跟regime_overlay.EXPOSURE_MAP曝險最低那格對應

CHECKPOINT_PATH = Path(__file__).parent / "data" / "margin_utilization_regime_portfolio_v1_checkpoint.json"


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, indent=2, ensure_ascii=False), encoding="utf-8")


def build_regime_lookup() -> dict[str, tuple]:
    """回傳 date(str) -> combined_regime(tuple) 的查表，沿用`regime_overlay.py`
    既有函式，不重新發明regime判定邏輯。只用TRAIN+VAL範圍（`holdout.cap_to_dev`），
    不碰holdout。"""
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in margin_utilization_regime_portfolio_v1")
    market_df = prepare_market_data(market_raw)
    dev_df = holdout.cap_to_dev(market_df)
    regime_df = regime_overlay.compute_regime_labels(dev_df)
    return dict(zip(regime_df["date"], regime_df["combined_regime"]))


def _snapshot(as_of, price_data, liquidity) -> pd.DataFrame:
    rows = []
    for sid, d in price_data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        mu = d.loc[idx[0]].get("f_margin_utilization")
        if pd.isna(mu):
            continue
        liq = liquidity[sid].get(as_of) if sid in liquidity and as_of in liquidity[sid].index else None
        rows.append({"stock_id": sid, "margin_utilization": float(mu), "liquidity_proxy": liq})
    if not rows:
        return pd.DataFrame(columns=["stock_id", "margin_utilization", "liquidity_proxy"])
    df = pd.DataFrame(rows)
    liq_vals = df["liquidity_proxy"].dropna()
    if len(liq_vals) >= 10:  # 分位數樣本太小沒有意義，門檻沿用factor_ic.py/pbv2慣例量級
        floor = np.percentile(liq_vals, pbv2.LIQUIDITY_FLOOR_PERCENTILE)
        df = df[df["liquidity_proxy"].isna() | (df["liquidity_proxy"] >= floor)]
    return df


def _non_crisis_pick(df: pd.DataFrame) -> dict[str, float]:
    """非危機regime的中性選股規則：流動性最高的TOP_N檔。刻意跟融資使用率
    無關、且在真實策略與隨機控制組兩版本逐字相同（見模組docstring）。"""
    pool = df.dropna(subset=["liquidity_proxy"])
    if len(pool) < TOP_N:
        pool = df
    top = pool.sort_values("liquidity_proxy", ascending=False).head(TOP_N)
    return dict(zip(top["stock_id"], [1.0] * len(top)))


def make_signal_fn(liquidity, regime_lookup):
    def signal_fn(price_data, as_of, market_df):
        df = _snapshot(as_of, price_data, liquidity)
        if df.empty:
            return {}
        if regime_lookup.get(as_of) == CRISIS_REGIME:
            top = df.sort_values("margin_utilization", ascending=True).head(TOP_N)  # 避開高融資使用率=挑最低的
            return dict(zip(top["stock_id"], [1.0] * len(top)))
        return _non_crisis_pick(df)
    return signal_fn


def make_random_signal_fn(liquidity, regime_lookup, seed):
    rng = random.Random(seed)

    def signal_fn(price_data, as_of, market_df):
        df = _snapshot(as_of, price_data, liquidity)
        if df.empty:
            return {}
        if regime_lookup.get(as_of) == CRISIS_REGIME:
            pool = df["stock_id"].tolist()
            picks = pool if len(pool) <= TOP_N else rng.sample(pool, TOP_N)
            return {sid: 1.0 for sid in picks}
        return _non_crisis_pick(df)  # 非危機期跟真實版本完全相同，差異只隔離在危機期選股
    return signal_fn


def run_one(label, data, market_df, liquidity, regime_lookup, start, end,
            n_random=100, deadline: float | None = None) -> dict | None:
    """跟`dividend_yield_portfolio_v1.run_one()`同一套checkpoint可續跑機制
    （理由見該檔案docstring：單輪headless執行預算跟完整TRAIN+VAL計算量有
    落差，需要跨輪落盤接續，不能假設背景行程能存活到下一輪）。"""
    ckpt_all = _load_checkpoint()
    ckpt = ckpt_all.setdefault(label, {})

    signal_fn = make_signal_fn(liquidity, regime_lookup)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="margin_utilization_regime_portfolio_v1")

    if "real" not in ckpt:
        print(f"  [{label}] 計算真實訊號回測...")
        result = run_backtest(signal_fn, data, market_df, cfg)
        holdout.assert_no_holdout_leakage(result.trades, date_col="date",
                                           context=f"margin_utilization_regime_portfolio_v1 {label}")
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
            r = run_backtest(signal_fn, data, market_df, c)
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
        rfn = make_random_signal_fn(liquidity, regime_lookup, seed=20260904 + i)
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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in margin_utilization_regime_portfolio_v1")
    market_df = prepare_market_data(market_raw)

    print("建立regime查表...")
    regime_lookup = build_regime_lookup()
    n_crisis = sum(1 for v in regime_lookup.values() if v == CRISIS_REGIME)
    print(f"  TRAIN+VAL共{len(regime_lookup)}個交易日，其中{n_crisis}天({100.0*n_crisis/len(regime_lookup):.1f}%)"
          f"落在危機regime{CRISIS_REGIME}")

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in margin_utilization_regime_portfolio_v1")

    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    import os
    TIME_BUDGET_SECONDS = float(os.environ.get("MURP_TIME_BUDGET_SECONDS", "420"))
    deadline = time.time() + TIME_BUDGET_SECONDS

    print(f"\n========== 第2/7關 train/val樣本外+隨機控制組（regime-conditional避開，"
          f"可續跑checkpoint，本次預算{TIME_BUDGET_SECONDS}秒）==========")
    results = {}
    incomplete_label = None
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
        r = run_one(label, data, market_df, liquidity, regime_lookup, start, end,
                    n_random=100, deadline=deadline)
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
              f"隨機控制組(N={r['n_random']}，危機期隨機選股)中位數={r['random_control_median_pct']:+.2f}%  "
              f"percentile={r['random_control_percentile']:.1f}")
        print(f"  成本1x/2x/3x: {r['cost_1x']:+.2f}% / {r['cost_2x']:+.2f}% / {r['cost_3x']:+.2f}%")

    if incomplete_label is not None:
        print(f"\n**本次{TIME_BUDGET_SECONDS}秒時間預算內未跑完（卡在{incomplete_label}），"
              f"進度已存進{CHECKPOINT_PATH}，不做任何PASS/FAIL判定。"
              f"重新執行`python margin_utilization_regime_portfolio_v1.py`會自動從中斷處接續，"
              f"不會重算已完成的label/隨機控制組筆數。**")
        holdout_ok = holdout.is_holdout_consumed() is False
        print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
        assert holdout_ok, "holdout must remain untouched (after)"
        return

    pd.DataFrame(results.values()).to_csv("data/margin_utilization_regime_portfolio_v1_results.csv", index=False)
    print("\n已存 data/margin_utilization_regime_portfolio_v1_results.csv")

    val = results["VALIDATION"]
    gate7_pass = (val["random_control_percentile"] >= 90.0)
    print(f"\n第2/7關判定（本策略核心判準是打贏『危機期隨機選股』對照組，"
          f"不是打贏買進持有大盤——見模組docstring控制組設計說明）："
          f"{'PASS' if gate7_pass else 'FAIL'}（VAL期隨機控制組percentile>=90.0）")

    if not gate7_pass:
        print("\n**第2/7關未過，直接結案FAIL，不進第3~9關**")
        return

    print("\n下一步：第3關參數密集高原（TOP_N/危機regime定義附近網格）、"
          "第4關成本敏感度已算好見上方1x/2x/3x、第5/6關leave-one-out+逐年一致性、"
          "第9關下檔保護（3個已知歷史危機期間逐段檢查）。")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
