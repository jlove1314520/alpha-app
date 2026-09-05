"""`HYPOTHESIS_QUEUE.md`#36（個股融券使用率）GATE_SEQUENCE第9關
下檔保護——把`regime_overlay.py`（#10方法論框架）正式接到#36這個選股候選
的日報酬序列上，這正是`regime_overlay.py`自己docstring寫的下一步：「等
佇列裡有選股候選通過1~8關後，把`compute_regime_labels`+`apply_overlay`
兩個函式接到那個候選的日報酬序列上，正式測第9關（下檔保護），不是套在
TAIEX買進持有上」。#36已通過第1/2/3/5/6關（見`TRIALS_LEDGER.md`#129/
#133/#134/#135），是本佇列第一個走到這一步的候選。

**只測TRAIN+VALIDATION（開發期），不動holdout**——沿用既有各腳本同一個
邊界紀律。

**這支腳本要回答的三件事（`CLAUDE.md`最高投資原則第2/3條的具體操作化）**：
①MDD是否受控（overlay後MDD是否較不負，至少沒有顯著惡化）、②地雷率是否
降低（定義見下方`_blowup_rate()`：日報酬低於-3%的天數占比，overlay應該
降低這個比例，因為危機regime曝險被調降）、③已知危機期間overlay是否真的
降低了曝險（沿用`regime_overlay.KNOWN_CRISIS_WINDOWS`，2018Q4/2020Q1落在
TRAIN、2022全年落在VAL）。

**沿用而非重造**：regime判定+曝險疊加邏輯完全複用`regime_overlay.py`的
`compute_regime_labels()`（不重新設計regime規則或EXPOSURE_MAP參數，那是
#10自己的既有先驗，這輪不做參數優化，理由同`regime_overlay.py`docstring
「這輪刻意不做參數優化」段落——現在纔第一次有真實候選可以套用，先看基本
方向對不對，調參數是之後的事）；策略日報酬序列來自`short_sale_utilization_
portfolio_v1.py::make_signal_fn()`單一真實訊號回測的`equity_curve`（1x
成本），不是100次隨機控制組（那是第2關已做過的事，這關要看的是同一條
真實策略曝險調整前後的差異，不是又跟隨機比一次）。

**時序對齊避免未來函數**：regime用`exposure.shift(1)`（收盤後才知道的
狀態只能影響下一交易日），逐字比照`regime_overlay.py::apply_overlay()`
的處理方式，只是把它接到策略自己的報酬而不是TAIEX的報酬上。

**誠實提醒（沿用#36既有已知限制）**：這仍是訊號多頭鏡像半邊（融券使用率
最低分位做多），regime overlay疊加的是「大盤層級」的曝險調整，不是這個
選股訊號本身的risk-off機制——如果選股訊號本身在危機期間选出的個股剛好
跟大盤同步下跌，疊加大盤regime曝險調整仍然合理（規避的是系統性風險，不
是選股訊號的特異性風險）。

2026-09-05 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續#36第5/6關以後。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import portfolio_backtest_v2 as pbv2
import regime_overlay as ro
from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

from short_sale_utilization_portfolio_v1 import REBALANCE_DAYS, TOP_N, make_signal_fn

BLOWUP_THRESHOLD_PCT = -3.0  # 單日報酬低於此門檻視為「地雷日」，門檻選擇見docstring


def _blowup_rate(ret: pd.Series) -> float:
    """地雷率＝單日報酬低於`BLOWUP_THRESHOLD_PCT`的天數占比（百分比）。"""
    if len(ret) == 0:
        return float("nan")
    return 100.0 * float((ret * 100 <= BLOWUP_THRESHOLD_PCT).mean())


def apply_overlay_to_strategy_returns(strategy_ret: pd.Series, regime_df: pd.DataFrame) -> pd.DataFrame:
    """把`regime_overlay.compute_regime_labels()`算出的`exposure`（大盤層級
    trend x vol regime）疊加到任意策略自己的日報酬序列上——不是疊加到TAIEX
    自己的報酬（那是`regime_overlay.apply_overlay()`原本做的事，這裡是把
    同一套曝險規則換一個報酬序列套用）。時序對齊：`exposure.shift(1)`同
    `regime_overlay.py`docstring「曝險/報酬的時序對齊」段落，避免未來函數。
    """
    exposure = regime_df.sort_values("date").set_index("date")["exposure"].shift(1)
    exposure.index = pd.to_datetime(exposure.index)
    strategy_ret = strategy_ret.copy()
    strategy_ret.index = pd.to_datetime(strategy_ret.index)
    merged = pd.DataFrame({"raw_return": strategy_ret}).join(exposure.rename("exposure_lagged"), how="inner")
    merged["overlay_return"] = merged["raw_return"] * merged["exposure_lagged"]
    valid = merged["raw_return"].notna() & merged["overlay_return"].notna()
    merged = merged[valid].copy()
    merged["baseline_equity"] = (1 + merged["raw_return"]).cumprod()
    merged["overlay_equity"] = (1 + merged["overlay_return"]).cumprod()
    return merged.reset_index().rename(columns={"index": "date"})


def crisis_window_exposure_check(merged: pd.DataFrame, windows: dict) -> list[dict]:
    """沿用`regime_overlay.crisis_window_check()`同一個精神，但這裡看的是
    #36策略自己在已知危機窗口內，overlay是否真的把平均曝險壓低、以及那段
    期間內baseline vs overlay的報酬/MDD差異——不是regime標籤本身的sanity
    （那件事`regime_overlay.py`已經在TAIEX層級驗證過，這裡只需確認曝險
    數字有正確傳導到這個策略的報酬上）。"""
    out = []
    for name, (start, end) in windows.items():
        window = merged[(merged["date"] >= start) & (merged["date"] <= end)]
        if window.empty:
            print(f"  {name}: 該期間資料為0筆（不在此period範圍內），跳過")
            continue
        avg_exposure = float(window["exposure_lagged"].mean())
        base_ret = float((1 + window["raw_return"]).prod() - 1) * 100
        over_ret = float((1 + window["overlay_return"]).prod() - 1) * 100
        base_mdd = float((window["baseline_equity"] / window["baseline_equity"].iloc[0]
                           / (window["baseline_equity"] / window["baseline_equity"].iloc[0]).cummax() - 1).min()) * 100
        over_mdd = float((window["overlay_equity"] / window["overlay_equity"].iloc[0]
                           / (window["overlay_equity"] / window["overlay_equity"].iloc[0]).cummax() - 1).min()) * 100
        print(f"  {name} ({start}~{end}, n={len(window)}天): 平均曝險={avg_exposure:.2f}  "
              f"窗內baseline報酬={base_ret:+.2f}% MDD={base_mdd:.2f}%  |  "
              f"窗內overlay報酬={over_ret:+.2f}% MDD={over_mdd:.2f}%")
        out.append({"window": name, "avg_exposure": avg_exposure, "base_ret_pct": base_ret,
                     "over_ret_pct": over_ret, "base_mdd_pct": base_mdd, "over_mdd_pct": over_mdd})
    return out


def run_period(label: str, start: str, end: str, data, market_df, liquidity, regime_df) -> dict:
    print(f"\n{'=' * 70}\n{label} ({start}..{end}) — 真實訊號回測 + regime overlay 疊加\n{'=' * 70}")
    sfn = make_signal_fn(liquidity)
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS,
                          book_name="short_sale_utilization_gate9_regime_overlay")
    result = run_backtest(sfn, data, market_df, cfg)
    holdout.assert_no_holdout_leakage(result.trades, date_col="date",
                                       context=f"short_sale_utilization_gate9_regime_overlay {label}")
    print(f"  單一真實訊號回測總報酬={result.total_return_pct:+.2f}%（應與既有#36結果一致，交叉確認）")

    strategy_ret = result.equity_curve.set_index("date")["equity"].pct_change()
    merged = apply_overlay_to_strategy_returns(strategy_ret, regime_df)

    base = ro._metrics(merged["baseline_equity"], merged["raw_return"])
    over = ro._metrics(merged["overlay_equity"], merged["overlay_return"])
    base_blowup = _blowup_rate(merged["raw_return"])
    over_blowup = _blowup_rate(merged["overlay_return"])

    print(f"  baseline(無overlay，=既有#36策略本身): CAGR={base['cagr_pct']:+.2f}%  "
          f"年化波動={base['ann_vol_pct']:.2f}%  Sharpe={base['sharpe']:.2f}  "
          f"MDD={base['mdd_pct']:.2f}%  Calmar={base['calmar']:.2f}  地雷率(單日<{BLOWUP_THRESHOLD_PCT}%)={base_blowup:.2f}%")
    print(f"  overlay(疊加regime曝險調整): CAGR={over['cagr_pct']:+.2f}%  "
          f"年化波動={over['ann_vol_pct']:.2f}%  Sharpe={over['sharpe']:.2f}  "
          f"MDD={over['mdd_pct']:.2f}%  Calmar={over['calmar']:.2f}  地雷率(單日<{BLOWUP_THRESHOLD_PCT}%)={over_blowup:.2f}%")

    mdd_improved = over["mdd_pct"] > base["mdd_pct"]
    blowup_improved = over_blowup < base_blowup
    print(f"  MDD是否改善: {'是' if mdd_improved else '否'}（{base['mdd_pct']:.2f}% -> {over['mdd_pct']:.2f}%）")
    print(f"  地雷率是否改善: {'是' if blowup_improved else '否'}（{base_blowup:.2f}% -> {over_blowup:.2f}%）")

    crisis_windows = {name: (s, e) for name, (s, e) in ro.KNOWN_CRISIS_WINDOWS.items()
                       if s <= end and e >= start}
    crisis_results = crisis_window_exposure_check(merged, crisis_windows) if crisis_windows else []
    if not crisis_windows:
        print(f"  （此period範圍內無`regime_overlay.KNOWN_CRISIS_WINDOWS`已知危機窗口）")

    return {"label": label, "base": base, "over": over, "base_blowup_pct": base_blowup,
            "over_blowup_pct": over_blowup, "mdd_improved": mdd_improved,
            "blowup_improved": blowup_improved, "crisis_windows": crisis_results,
            "n_days": len(merged)}


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in short_sale_utilization_gate9_regime_overlay")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(
            d, date_col="date", context=f"data[{sid}] in short_sale_utilization_gate9_regime_overlay")

    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    # regime一次算在TRAIN+VAL全期間（不是各period分開算），避免expanding()視窗
    # 在period邊界被人為重置——逐字比照`regime_overlay.py::main()`的作法
    # （`cap_to_dev`只是防呆保證不碰holdout，不是為了分段計算）。
    dev_df = holdout.cap_to_dev(market_df)
    regime_df = ro.compute_regime_labels(dev_df)
    print(f"\nregime標籤已算好（TRAIN+VAL全期間，n={len(regime_df)}天，"
          f"warm-up缺值天數={regime_df['vol_regime'].isna().sum()}）")

    periods = [
        ("TRAIN", "2015-01-01", holdout.TRAIN_END),
        ("VALIDATION", "2021-01-01", holdout.VAL_END),
    ]
    period_results = []
    for label, start, end in periods:
        r = run_period(label, start, end, data, market_df, liquidity, regime_df)
        period_results.append(r)

    print(f"\n{'=' * 70}\n第9關判定總結（`CLAUDE.md`最高投資原則第2/3條：MDD受控+地雷率降低+"
          f"危機期降曝險，凌駕其他關卡）\n{'=' * 70}")
    all_mdd_ok = all(r["mdd_improved"] for r in period_results)
    all_blowup_ok = all(r["blowup_improved"] for r in period_results)
    for r in period_results:
        print(f"  {r['label']}: MDD改善={'是' if r['mdd_improved'] else '否'}  "
              f"地雷率改善={'是' if r['blowup_improved'] else '否'}  "
              f"危機窗口曝險數字見上方逐段輸出（{len(r['crisis_windows'])}個窗口落在此period）")
    print(f"\n第9關判定（兩期MDD跟地雷率皆改善才算過）："
          f"{'PASS' if (all_mdd_ok and all_blowup_ok) else '部分未過，見上方逐項細節'}")
    print("\n**誠實保留**：這只回答「疊加大盤層級regime曝險調整，是否讓#36這個候選的"
          "下檔風險變小」，不等於#36整條候選已完成最終PASS/FAIL判定——TRAIN期alpha"
          "不顯著(p=0.3717) vs VAL期alpha顯著(p=0.0354)這個既有的判斷待定問題"
          "（`TRIALS_LEDGER.md`#135）仍未解決，兩者是獨立的問題，這輪只處理下檔"
          "保護這一項。")

    pd.DataFrame([
        {"label": r["label"], "base_mdd_pct": r["base"]["mdd_pct"], "over_mdd_pct": r["over"]["mdd_pct"],
         "base_cagr_pct": r["base"]["cagr_pct"], "over_cagr_pct": r["over"]["cagr_pct"],
         "base_sharpe": r["base"]["sharpe"], "over_sharpe": r["over"]["sharpe"],
         "base_blowup_pct": r["base_blowup_pct"], "over_blowup_pct": r["over_blowup_pct"],
         "mdd_improved": r["mdd_improved"], "blowup_improved": r["blowup_improved"], "n_days": r["n_days"]}
        for r in period_results
    ]).to_csv("data/short_sale_utilization_gate9_regime_overlay_results.csv", index=False)
    print("\n已存 data/short_sale_utilization_gate9_regime_overlay_results.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
