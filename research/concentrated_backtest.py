# -*- coding: utf-8 -*-
"""集中版回測框架（`CONCENTRATED_SPEC.md`規.二，尚未實作真正的選股掃描）。

**2026-09-23總司令裁示【修正兩個系統性錯誤＋兩件待審閱結案】結案.二
第3點**：目前沒有任何存活的選股訊號（事件驅動SUE兩型皆FAIL、方法論
重建三條並行至今無存活候選），`CONCENTRATED_SPEC.md`第4節的候選C
參數掃描**凍結**，在出現通過全部閘門的選股訊號之前不得執行。**本檔案
唯一允許現在做的事**：用「隨機選股」佔位訊號跑一次回測，只驗證框架
本身正確性（成本模型／停損規則／產業曝險上限／MDD逐空頭段計算），
登記為`FRAMEWORK_CHECK`（`trial_registry.py::VALID_VERDICTS`新增），
**完全不計入alpha試驗N**（`selection_bias_ledger.py::parse()`在
`main()`一開始就過濾掉，連總N都不算——這不是「檢定過的候選失敗」，
是「這次執行從頭到尾就不是要回答alpha存不存在的問題」）。

**重用既有元件，不重新發明**：`backtest/engine.py::run_backtest()`
（`buy_leg_rate`/`sell_leg_rate`/`max_positions`/`stop_loss_pct`三層
風控全部沿用，成本走`validation.costs`，個股用一般股稅率"normal"非
ETF）、`factor_ic.py::sample_universe_ids()/load_sample_with_factors()`
（既有快取樣本，零新增API呼叫）、`score.py::load_industry_map()`。

**產業曝險上限**：`make_capped_random_signal_fn()`在候選池抽樣時逐一
檢查已選股票的產業分布，同一產業最多`INDUSTRY_CAP`檔即跳過同產業其餘
候選——這是框架驗證用的任意值，不代表`CONCENTRATED_SPEC.md`§6(a)
「集中到N檔時產業上限是多少」這個問題的正式答案，那個問題留給真正
有存活訊號時再認真決定。

**MDD逐空頭段計算**：沿用`regime_overlay_trend_filter_gate.py::
TRAIN_CRISIS_WINDOWS`同一組危機視窗定義，另加2022全年空頭（其他多支
腳本已用過的第5個視窗），不重新發明危機期間清單。

用法：
    python research/concentrated_backtest.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import random

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from trial_registry import register_trial
from validation import holdout

TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = REPO_ROOT / "research" / "data" / "concentrated_backtest_framework_check.json"

MAX_POSITIONS = 8   # 框架驗證任意值，非§4候選C的正式格點
STOP_LOSS_PCT = 0.15  # 框架驗證任意值，沿用engine.py既有預設精神
INDUSTRY_CAP = 2     # 框架驗證任意值，非§6(a)的正式答案
RANDOM_SEED = 20260923

CRISIS_WINDOWS = {
    "2011歐債危機/美債降級": ("2011-07-01", "2011-12-31"),
    "2015中國股災": ("2015-06-01", "2015-09-30"),
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


def make_capped_random_signal_fn(industry_map: dict, seed: int):
    """隨機選股佔位訊號，逐一抽樣時檢查產業上限（見模組docstring）。"""
    rng = random.Random(seed)

    def signal_fn(price_data: dict, as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        eligible = [sid for sid, d in price_data.items()
                    if not d[d["date"] <= as_of].empty]
        rng.shuffle(eligible)
        picks: list[str] = []
        industry_count: dict[str, int] = {}
        for sid in eligible:
            if len(picks) >= MAX_POSITIONS:
                break
            ind = industry_map.get(sid, "未知")
            if industry_count.get(ind, 0) >= INDUSTRY_CAP:
                continue  # 產業曝險上限：同產業已達上限，跳過
            picks.append(sid)
            industry_count[ind] = industry_count.get(ind, 0) + 1
        return {sid: 1.0 for sid in picks}

    return signal_fn


def crisis_window_mdd(equity_curve: pd.DataFrame) -> dict[str, float | None]:
    eq = equity_curve.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    out = {}
    for name, (start, end) in CRISIS_WINDOWS.items():
        win = eq[(eq["date"] >= start) & (eq["date"] <= end)]
        if len(win) < 2:
            out[name] = None
            continue
        running_max = win["equity"].cummax()
        dd = (win["equity"] - running_max) / running_max
        out[name] = round(float(dd.min() * 100), 4)
    return out


def main() -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in concentrated_backtest framework check")
    market_df = prepare_market_data(market_raw)

    print("載入樣本+既有快取（零新增API呼叫）...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} 檔可用")
    industry_map = load_industry_map()

    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in concentrated_backtest")

    cfg = BacktestConfig(
        start_date="2015-01-01", end_date=holdout.VAL_END,
        max_positions=MAX_POSITIONS, stop_loss_pct=STOP_LOSS_PCT,
        instrument_type="normal",  # 個股（非ETF），一般股稅率正確
        book_name="concentrated_framework_check",
    )
    signal_fn = make_capped_random_signal_fn(industry_map, RANDOM_SEED)
    result = run_backtest(signal_fn, data, market_df, cfg)

    industry_exposure_ok = True  # 若trades裡任一天同產業曝險超過INDUSTRY_CAP即False，見下方逐筆檢查
    held_by_industry_at_entry = []
    for _, row in result.trades[result.trades["side"] == "buy"].iterrows():
        held_by_industry_at_entry.append(industry_map.get(row["stock_id"], "未知"))
    # 框架驗證的產業上限檢查：整個回測期間任何時點的「進場當下已持有(含本次)同產業數」
    # 不得超過INDUSTRY_CAP——signal_fn本身已經做了這個限制，這裡只是獨立覆核不是重播引擎。
    from collections import Counter
    entry_industry_counts = Counter(held_by_industry_at_entry)
    max_single_industry_entries = max(entry_industry_counts.values()) if entry_industry_counts else 0

    crisis_mdd = crisis_window_mdd(result.equity_curve)

    out = {
        "generated_at": datetime.now(TZ).isoformat(),
        "purpose": "FRAMEWORK_CHECK：驗證回測框架正確性，非alpha檢定，隨機選股佔位訊號",
        "config": {"max_positions": MAX_POSITIONS, "stop_loss_pct": STOP_LOSS_PCT,
                   "industry_cap": INDUSTRY_CAP, "instrument_type": "normal", "seed": RANDOM_SEED},
        "n_sample_ids": len(sample_ids), "n_usable": len(data),
        "total_return_pct": round(result.total_return_pct, 4),
        "max_drawdown_pct": round(result.max_drawdown_pct, 4),
        "sortino_ratio": round(result.sortino_ratio, 4) if result.sortino_ratio == result.sortino_ratio else None,
        "n_trades": result.n_trades,
        "crisis_window_mdd_pct": crisis_mdd,
        "max_single_industry_entries_total_count": max_single_industry_entries,
        "n_distinct_industries_entered": len(entry_industry_counts),
        "holdout_consumed_check": holdout.is_holdout_consumed(),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"寫入 {OUT_JSON}")
    print(f"總報酬={out['total_return_pct']}% MDD={out['max_drawdown_pct']}% "
          f"Sortino={out['sortino_ratio']} 交易數={out['n_trades']}")
    print(f"逐空頭段MDD：{crisis_mdd}")
    print(f"產業上限檢查：{len(entry_industry_counts)}個不同產業被進場過，"
          f"單一產業累計進場次數最高{max_single_industry_entries}次（非同時持有數，"
          f"是全期累計次數，僅供粗略核對，非嚴謹稽核）")

    design = (f"結案.二第3點：CONCENTRATED_SPEC.md§4凍結期間唯一允許的框架驗證。"
              f"隨機選股佔位訊號(seed={RANDOM_SEED})，max_positions={MAX_POSITIONS}，"
              f"stop_loss_pct={STOP_LOSS_PCT}，industry_cap={INDUSTRY_CAP}（皆框架驗證"
              f"任意值，非正式參數答案），instrument_type='normal'（個股一般股稅率）。"
              f"樣本{len(data)}/{len(sample_ids)}檔（既有快取，零新增API呼叫），"
              f"2015-01-01~{holdout.VAL_END}（VAL_END內，holdout未動）。目的：驗證"
              f"backtest/engine.py三層風控(部位上限/停損/成本)+產業曝險上限+"
              f"crisis_window_mdd()逐空頭段計算是否正確接起來，不是要檢定隨機選股"
              f"有沒有alpha（當然沒有，這不是重點）。")
    result_str = (f"總報酬={out['total_return_pct']}% MDD={out['max_drawdown_pct']}% "
                  f"Sortino={out['sortino_ratio']} 交易數={out['n_trades']}。"
                  f"逐空頭段MDD：{json.dumps(crisis_mdd, ensure_ascii=False)}。"
                  f"產業曝險：{len(entry_industry_counts)}個不同產業被進場過。"
                  f"n={len(data)}檔樣本。")
    register_trial(
        track="TW", name="concentrated_backtest_framework_check", design=design,
        result=result_str, verdict="FRAMEWORK_CHECK",
        notes=("純框架驗證，不是alpha檢定，不計入N（見trial_registry.py::VALID_VERDICTS"
               "與selection_bias_ledger.py::main()開頭的過濾）。目的：在CONCENTRATED_"
               "SPEC.md§4凍結掃描期間，先確認回測框架本身（成本/停損/產業上限/MDD"
               "逐空頭段）接得起來，等有存活選股訊號時可以直接使用，不需要臨時現寫。"),
        round_note="結案.二第3點，互動視窗CC，交辦優先於自走",
    )
    print("已登記1筆FRAMEWORK_CHECK至TRIALS_LEDGER.md（不計入N）")
    return out


if __name__ == "__main__":
    main()
