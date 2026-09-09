"""盤中零股委託簿失衡度策略層構造 — `HYPOTHESIS_QUEUE.md`#67第2關以後。

**誠實現況（不是重新驗證因子IC）**：`f_odd_lot_imbalance`已通過因子級
cheap IC gate（`TRIALS_LEDGER.md`#231，train mean_ic=-0.0430/val
mean_ic=-0.0249，同號為負、null percentile=90.7>=90.0門檻）。**方向為
負**——零股委託簿買進壓力偏高predict後續報酬下修（貼近處分效應/追高
乏力），依#67條目明文允許的方向彈性例外，這支腳本的持股規則反過來挑
「委託簿失衡度最低（z-score最小、偏賣壓/無買進追價）」的股票做多，跟
`f52w_high_portfolio_v1.py`（正向IC、挑z-score最高）方向相反、其餘架構
逐字比照。

**重大統計但書（承接自#67條目cheap gate段落，本腳本設計時已列入考量）**：
train同號的結論建立在僅3個20交易日快照上，val percentile=90.7距門檻僅
0.7個百分點，兩者皆屬邊緣過關。這支腳本的第2關隨機控制組（≥100 draws）
就是專門用來檢驗這個邊緣訊號能否在portfolio層級站得住腳，不能因為
cheap gate顯示CHEAP_PASS就預設portfolio層也會過。

**TRAIN/VAL自訂切分（事前綁定，#67條目「TRAIN/VAL切分需重新評估」段落
已寫定，非本腳本臨時決定）**：資料源TWTC7U自2020-10-26才可得，晚於標準
`TRAIN_END=2020-12-31`，若沿用標準邊界TRAIN期只剩約2個月、樣本量嚴重
不足。改用：TRAIN=[2020-10-26,2022-12-31]（約2.2年）、
VAL=(2022-12-31,2024-12-31]（約2年）——`VAL_END`本身未變動（仍是
"2024-12-31"這個既有holdout物理邊界），只調整TRAIN/VAL內部分界點，
非動了門柱。

**沿用而非重造的基礎設施**（逐字比照`f52w_high_portfolio_v1.py`架構）：
- `factor_ic.py`：抽樣宇宙、快取樣本+因子。
- `backtest/engine.py`：月頻換股(21交易日)、三成本層級。
- `score.py`：同產業z-score。
- `validation/holdout.py`：TRAIN/VAL切分（本腳本用自訂日期字串，非
  `holdout.TRAIN_END`/`holdout.VAL_END`常數本身，但`assert_no_holdout_
  leakage()`仍用同一套物理防呆，`end`參數不得超過"2024-12-31"）。

2026-09-09 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#67第2關
以後起跑（第1關cheap IC gate已CHEAP_PASS，見`TRIALS_LEDGER.md`#231）。
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map, _zscore_within_group
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2  # 只借用跟因子組成無關的通用機制，見模組docstring

TOP_N = 20
REBALANCE_DAYS = 21  # 月頻
COMPONENTS = ["f_odd_lot_imbalance"]  # 刻意單因子，零股委託簿失衡度假設

# 本假設專用TRAIN/VAL切分（事前綁定，見模組docstring「TRAIN/VAL自訂切分」段落）
TRAIN_START, TRAIN_END_67 = "2020-10-26", "2022-12-31"
VAL_START_67, VAL_END_67 = "2023-01-01", "2024-12-31"
assert VAL_END_67 == holdout.VAL_END, "VAL_END物理邊界不得被本腳本移動，只能調整內部分界點"

CHECKPOINT_PATH = Path(__file__).parent / "data" / "odd_lot_imbalance_portfolio_v1_checkpoint.json"


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, indent=2, ensure_ascii=False), encoding="utf-8")


def _raw_components(row: pd.Series) -> dict[str, float | None]:
    out = {}
    for comp, col in (("f_odd_lot_imbalance", "f_odd_lot_imbalance"),):
        v = row.get(col)
        out[comp] = float(v) if pd.notna(v) else None
    return out


def compute_composite_at_date(as_of, data, industry_map, liquidity) -> pd.DataFrame:
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        raw = _raw_components(d.loc[idx[0]])
        liq = liquidity[sid].get(as_of) if sid in liquidity and as_of in liquidity[sid].index else None
        rows.append({"stock_id": sid, "industry": industry_map.get(sid, "UNKNOWN"),
                     "liquidity_proxy": liq, **raw})
    if not rows:
        return pd.DataFrame(columns=["stock_id", "industry", "composite", "n_components", "liquidity_proxy"])
    cs = pd.DataFrame(rows).set_index("stock_id")

    weighted_sum = pd.Series(0.0, index=cs.index)
    weight_total = pd.Series(0.0, index=cs.index)
    n_components = pd.Series(0, index=cs.index)
    for comp in COMPONENTS:
        z_col = f"z_{comp}"
        cs[z_col] = _zscore_within_group(cs[comp], cs["industry"])
        valid = cs[z_col].notna()
        weighted_sum[valid] += cs.loc[valid, z_col]  # 單因子，w=1.0
        weight_total[valid] += 1.0
        n_components[valid] += 1

    cs["composite"] = np.where(weight_total > 0, weighted_sum / weight_total, np.nan)
    cs["n_components"] = n_components
    return cs.reset_index()[["stock_id", "industry", "composite", "n_components", "liquidity_proxy"]]


def _eligible_single_factor(cs: pd.DataFrame) -> pd.DataFrame:
    """跟`f52w_high_portfolio_v1.py::_eligible_single_factor()`同一套邏輯，
    但排序方向相反：composite**升冪**排序（IC為負，z-score最低=委託簿
    最偏賣壓/無追價買盤，predict後續報酬最高）。"""
    pool = cs[cs["n_components"] >= 1].copy()
    liq = pool["liquidity_proxy"].dropna()
    if len(liq) >= 10:
        floor = np.percentile(liq, pbv2.LIQUIDITY_FLOOR_PERCENTILE)
        pool = pool[pool["liquidity_proxy"].isna() | (pool["liquidity_proxy"] >= floor)]
    return pool.sort_values("composite", ascending=True)  # 負向IC，挑最低值


def make_signal_fn(industry_map, liquidity):
    def signal_fn(price_data, as_of, market_df):
        cs = _eligible_single_factor(compute_composite_at_date(as_of, price_data, industry_map, liquidity))
        top = cs.head(TOP_N)
        return dict(zip(top["stock_id"], [1.0] * len(top)))
    return signal_fn


def make_random_signal_fn(industry_map, liquidity, seed):
    rng = random.Random(seed)

    def signal_fn(price_data, as_of, market_df):
        cs = _eligible_single_factor(compute_composite_at_date(as_of, price_data, industry_map, liquidity))
        pool = cs["stock_id"].tolist()
        picks = pool if len(pool) <= TOP_N else rng.sample(pool, TOP_N)
        return {sid: 1.0 for sid in picks}
    return signal_fn


def run_one(label, data, market_df, industry_map, liquidity, start, end,
            n_random=100, deadline: float | None = None) -> dict | None:
    """逐字比照`f52w_high_portfolio_v1.py::run_one()`同一套checkpoint可
    續跑機制。"""
    ckpt_all = _load_checkpoint()
    ckpt = ckpt_all.setdefault(label, {})

    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="odd_lot_imbalance_portfolio_v1")

    if "real" not in ckpt:
        print(f"  [{label}] 計算真實訊號回測...")
        result = run_backtest(signal_fn, data, market_df, cfg)
        holdout.assert_no_holdout_leakage(result.trades, date_col="date", context=f"odd_lot_imbalance_portfolio_v1 {label}")
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
        rfn = make_random_signal_fn(industry_map, liquidity, seed=20260909 + i)
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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in odd_lot_imbalance_portfolio_v1")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in odd_lot_imbalance_portfolio_v1")

    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    TIME_BUDGET_SECONDS = float(os.environ.get("OLI_TIME_BUDGET_SECONDS", "420"))
    deadline = time.time() + TIME_BUDGET_SECONDS

    print(f"\n========== 第2/7關 train/val樣本外+隨機控制組（月頻/Top20/單因子"
          f"零股委託簿失衡度反向策略，可續跑checkpoint，本次預算{TIME_BUDGET_SECONDS}秒）==========")
    print(f"  本假設專用切分：TRAIN=[{TRAIN_START},{TRAIN_END_67}]  VAL=({VAL_START_67},{VAL_END_67}]"
          f"（VAL_END未變動，只調整內部分界點，見模組docstring）")
    results = {}
    incomplete_label = None
    for label, start, end in (("TRAIN", TRAIN_START, TRAIN_END_67),
                               ("VALIDATION", VAL_START_67, VAL_END_67)):
        r = run_one(label, data, market_df, industry_map, liquidity, start, end,
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
              f"隨機對照組(N={r['n_random']})中位數={r['random_control_median_pct']:+.2f}%  "
              f"percentile={r['random_control_percentile']:.1f}")
        print(f"  成本1x/2x/3x: {r['cost_1x']:+.2f}% / {r['cost_2x']:+.2f}% / {r['cost_3x']:+.2f}%")

    if incomplete_label is not None:
        print(f"\n**本次{TIME_BUDGET_SECONDS}秒時間預算內未跑完（卡在{incomplete_label}），"
              f"進度已存進{CHECKPOINT_PATH}，不做任何PASS/FAIL判定。"
              f"重新執行`python odd_lot_imbalance_portfolio_v1.py`會自動從中斷處接續，"
              f"不會重算已完成的label/隨機控制組筆數。**")
        holdout_ok = holdout.is_holdout_consumed() is False
        print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
        assert holdout_ok, "holdout must remain untouched (after)"
        return

    pd.DataFrame(results.values()).to_csv("data/odd_lot_imbalance_portfolio_v1_results.csv", index=False)
    print("\n已存 data/odd_lot_imbalance_portfolio_v1_results.csv")

    val = results["VALIDATION"]
    gate7_pass = (val["return_pct"] > 0) and (val["random_control_percentile"] >= 90.0)
    print(f"\n第7關判定：{'PASS' if gate7_pass else 'FAIL'}"
          f"（VAL期本身要單獨過關：報酬為正 且 隨機控制組percentile>=90.0）")

    if not gate7_pass:
        print("\n**第7關樣本外未過，直接結案FAIL，不進第8/9關**")
        return

    print("\n========== 第8關 下檔保護 ==========")
    train, val_r = results["TRAIN"], results["VALIDATION"]
    print(f"  TRAIN MDD={train['mdd_pct']:.2f}%  VAL MDD={val_r['mdd_pct']:.2f}%")
    print(f"  TRAIN beta={train['beta']:+.3f}  VAL beta={val_r['beta']:+.3f}"
          f"（做多策略本該有正beta，重點是不能過度槓桿放大，這裡若beta明顯>1.3屬警訊）")
    gate8_pass = (val_r["mdd_pct"] > -35.0) and all(val_r[f"cost_{m}x"] > 0 for m in (1, 2, 3)) and (val_r["beta"] < 1.3)
    print(f"  第8關判定：{'PASS' if gate8_pass else 'FAIL'}"
          f"（門檻：VAL MDD優於-35%、三個成本情境VAL皆正、beta<1.3非過度槓桿）")

    if not gate8_pass:
        print("\n**第8關下檔保護未過，直接結案FAIL，不進第9關**")
        return

    print("\n" + "=" * 70)
    print("**全部7~8關通過（零股委託簿失衡度反向單因子組合，月頻Top20）！**")
    print("下一步：第3關參數密集高原、第5/6關leave-one-out+逐年一致性、"
          "第9關前向paper。")
    print("=" * 70)

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
