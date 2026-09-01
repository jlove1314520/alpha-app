"""股票股利率carry策略層構造 — `HYPOTHESIS_QUEUE.md`#4。

**誠實現況（不是重新驗證因子IC）**：`f_dividend_yield_ttm`（trailing 12個月
現金股利/股價）已經在`TRIALS_LEDGER.md`#74通過因子級cheap IC gate（TRAIN
mean_ic=+0.0606 IR=+0.426、VAL mean_ic=+0.0807 IR=+0.562 hit_rate=0.77，
train/val同號、null percentile=100.0>=90.0門檻）。這支腳本要做的是把這個
已通過cheap gate的單一因子組成一個明確的持股規則（月度再平衡、Top20、
全成本），走完整GATE_SEQUENCE第7/8/9關（樣本外+下檔保護+前向paper準備），
不是重新測IC是否存在。

**跟`pead_portfolio_v1.py`同一套機制、刻意單因子**：這裡只有一個成分
（`dividend_yield`），沒有多因子等權平均的問題——`_zscore_within_group`
仍然做同產業標準化（避免高股息集中在特定產業如金融/傳產時被產業效應
主導），但composite本身就等於這個z-score，不是多因子加總。

**沿用而非重造的基礎設施**（不修改`portfolio_backtest_v2.py`，只import其
通用、跟因子組成無關的部分——寫法逐字比照`pead_portfolio_v1.py`）：
- `factor_ic.py`：抽樣宇宙、快取樣本+因子。
- `backtest/engine.py`：月頻換股(21交易日)、三成本層級。
- `score.py`：同產業z-score。
- `validation/holdout.py`：TRAIN/VAL切分、holdout防呆。

**權重選擇**：單因子本身即排名依據（等權概念下唯一成分權重=1.0），不做
多版本網格掃描——`HYPOTHESIS_QUEUE.md`要的是「一個明確的持股規則」。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import random

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
COMPONENTS = ["dividend_yield"]  # 刻意單因子，carry/股利率假設

CHECKPOINT_PATH = Path(__file__).parent / "data" / "dividend_yield_portfolio_v1_checkpoint.json"
# 2026-09-02新增（第六輪排程）：連續四輪都因為單次完整執行需要約35~40分鐘
# （實測：資料載入~102秒、單次真實回測~14秒、單次隨機回測~17秒，TRAIN+
# VALIDATION各要跑1真實+2成本情境+100隨機=206次回測），而無人值守headless
# 呼叫結束時背景行程會被一併終止（見HYPOTHESIS_QUEUE.md#4 2026-09-02T00:45
# 條目分析），導致每輪都從零重跑、進度沒有累積。這裡把隨機控制組拆成逐筆
# 落盤的checkpoint，讓計算真正跨次執行累積，不再每次從頭開始。


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, indent=2, ensure_ascii=False), encoding="utf-8")


def _raw_components(row: pd.Series) -> dict[str, float | None]:
    out = {}
    for comp, col in (("dividend_yield", "f_dividend_yield_ttm"),):
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
    """跟`pbv2._eligible()`同精神的流動性篩選，但**不套用`n_components>=2`
    門檻**——這支策略刻意單因子（見模組docstring），composite只可能
    n_components=1，若沿用`pbv2._eligible()`（`score.MIN_COMPONENTS_FOR_
    RANKING=2`，多因子組合設計的門檻）會把每一列都篩掉，導致0檔候選、
    0筆交易（2026-09-01自動排程輪次跑出TRAIN/VAL兩期皆0筆交易、報酬
    0.00%的異常結果，回頭查出的根因——不是無訊號，是實作bug，比照
    weinstein_stage2_v2那次「sanity測的不是後續關卡實際資料路徑」的
    教訓，這裡是「借用的共用函式門檻假設跟本策略設計不合」）。改成只
    要求composite本身非NaN（n_components>=1），流動性下限篩選邏輯完全
    不變、逐行沿用`pbv2._eligible()`。"""
    pool = cs[cs["n_components"] >= 1].copy()
    liq = pool["liquidity_proxy"].dropna()
    if len(liq) >= 10:  # 分位數樣本太小沒有意義，門檻沿用factor_ic.py慣例的量級
        floor = np.percentile(liq, pbv2.LIQUIDITY_FLOOR_PERCENTILE)
        pool = pool[pool["liquidity_proxy"].isna() | (pool["liquidity_proxy"] >= floor)]
    return pool.sort_values("composite", ascending=False)


def make_signal_fn(industry_map, liquidity):
    def signal_fn(price_data, as_of, market_df):
        cs = _eligible_single_factor(compute_composite_at_date(as_of, price_data, industry_map, liquidity))
        top = cs.head(TOP_N)
        return dict(zip(top["stock_id"], top["composite"]))
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
    """跑一個label（TRAIN或VALIDATION）的第7關全套（真實訊號+成本敏感度
    2x/3x+n_random筆隨機控制組），可跨次執行續跑（見`CHECKPOINT_PATH`）。

    回傳`None`代表這個label在`deadline`（`time.time()`絕對時間戳）之前
    沒能跑完全部n_random筆隨機控制組——進度已落盤，呼叫端不得用這個結果
    做任何PASS/FAIL判定，下次重跑此腳本會自動從中斷處接續，不重算已完成
    的部分。回傳dict代表這個label已完整跑完。
    """
    ckpt_all = _load_checkpoint()
    ckpt = ckpt_all.setdefault(label, {})

    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="dividend_yield_portfolio_v1")

    if "real" not in ckpt:
        print(f"  [{label}] 計算真實訊號回測...")
        result = run_backtest(signal_fn, data, market_df, cfg)
        holdout.assert_no_holdout_leakage(result.trades, date_col="date", context=f"dividend_yield_portfolio_v1 {label}")
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
        rfn = make_random_signal_fn(industry_map, liquidity, seed=20260901 + i)
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
        return None  # deadline剛好卡在迴圈邊界，保守起見一樣視為未完成

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
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in dividend_yield_portfolio_v1")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in dividend_yield_portfolio_v1")

    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    # 7分鐘算力預算（含前面~102秒資料載入，單次呼叫總耗時安全落在10分鐘的
    # 外層執行工具逾時上限內）。可用環境變數覆寫，方便同一輪session內連續
    # 呼叫多次累積進度而不必每次都改原始碼；也安全落在鎖檔陳舊門檻（25分鐘，
    # 見marathon_lock.py STALE_MINUTES）之內。
    import os
    TIME_BUDGET_SECONDS = float(os.environ.get("DYP_TIME_BUDGET_SECONDS", "420"))
    deadline = time.time() + TIME_BUDGET_SECONDS

    print(f"\n========== 第7關 train/val樣本外（月頻/Top20/單因子股利率，可續跑checkpoint，本次預算{TIME_BUDGET_SECONDS}秒）==========")
    results = {}
    incomplete_label = None
    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                               ("VALIDATION", "2021-01-01", holdout.VAL_END)):
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
              f"重新執行`python dividend_yield_portfolio_v1.py`會自動從中斷處接續，"
              f"不會重算已完成的label/隨機控制組筆數。**")
        holdout_ok = holdout.is_holdout_consumed() is False
        print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
        assert holdout_ok, "holdout must remain untouched (after)"
        return

    pd.DataFrame(results.values()).to_csv("data/dividend_yield_portfolio_v1_results.csv", index=False)
    print("\n已存 data/dividend_yield_portfolio_v1_results.csv")

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
    print("**全部7~8關通過（股利率carry單因子組合，月頻Top20）！**")
    print("下一步：第9關前向paper——接`data/strategy_performance.json`前向模擬機制。")
    print("=" * 70)

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
