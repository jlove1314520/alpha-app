"""HYPOTHESIS_QUEUE.md #74續 — GATE4（成本敏感度）元分析。

**背景**：2026-09-18「重構.A2」重跑#74合成訊號網格（`synthetic_power_curve_
gate74_grid.py`，去均值化修法生效後），GATE6問題解決，但**GATE4取代GATE6
成為新的主要瓶頸**——Sharpe=0.3強度0%通過、0.5強度僅40%、0.8強度僅60%（見
`HYPOTHESIS_QUEUE.md`「#74續」章節「新發現」小節）。該輪明確標記「留待後續
是否需要對GATE4做同一套元分析的獨立待辦，不在本輪範圍內」，並把「GATE4是否
需要獨立的元分析」交給「總司令或下一輪自走視情況決定是否列入佇列」。

**本輪裁量（2026-09-19，依CLAUDE.md零之一節「不確定但可還原→自行裁量」）**：
選擇繼續做——這跟GATE6問題同一種方法論精神（先問「這是量測設計的產物，還是
GATE4本身真的太嚴」，不是先假設GATE4有問題）。不修改GATE1~6任何門檻數字、
不擴大到#74既有網格之外的強度/種子範圍、不觸碰holdout。

**假說（事前綁定，寫在跑之前）**：GATE4現有實作（`gate4_cost_sensitivity()`）
的成本模型是`REBAL_FREQ=21`（`equal_weight_rebalance_sanity.py`的月頻假設，
借用給#74合成訊號測試使用，而非#74自己選定的參數）× 100%換手率 round-trip
0.685%（1x）。這代表**年化成本drag≈8.2%**（0.685% × 252/21 ≈ 8.22%）。
若假說成立，GATE4低通過率主要是這個被借用的高換手頻率假設造成，而非GATE4
本身的判準（1x/2x/3x皆需為正）設計不合理——換一個較低換手頻率（例如季頻/
半年頻），同樣強度的注入訊號應有顯著更高的GATE4通過率。若假說不成立（即使
換成低頻假設GATE4依然低通過），代表問題出在注入訊號本身的樣本抖動量級，
不是成本假設本身。

**理論breakeven計算（獨立於任何模擬，先算再跑，避免結果出來後才回頭找理由）**：
annualized_cost_drag(REBAL_FREQ) = round_trip_cost_pct(1x) * 252 / REBAL_FREQ
breakeven_sharpe(REBAL_FREQ) 大致上要求 target_sharpe * sigma_annual >
annualized_cost_drag(REBAL_FREQ)，即
breakeven_sharpe ≈ annualized_cost_drag(REBAL_FREQ) / sigma_annual
（用真實300檔等權重日報酬的sigma_annual，非任意假設值）。

is_holdout_consumed()本輪開工/收工前皆確認False。全程複用#74既有快取
（`equal_weight_rebalance_sanity.load_prices`，零新增外部API呼叫）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from equal_weight_rebalance_sanity import build_panel, load_prices
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from synthetic_power_curve_gate74 import (
    TRADING_DAYS_PER_YEAR,
    annualized_sharpe,
    inject_synthetic_alpha,
)
from validation import costs, holdout

print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

# 換手頻率網格：5(週)/10(雙週)/21(月，#74既有值)/63(季)/126(半年)交易日
REBAL_FREQ_GRID = [5, 10, 21, 63, 126]
STRENGTHS = [0.3, 0.5, 0.8]
BASE_SEED = 20260915
N_SEEDS = 5


def gate4_at_freq(combined: pd.Series, rebal_freq: int) -> dict:
    """跟synthetic_power_curve_gate74.gate4_cost_sensitivity()完全同一個公式，
    只把REBAL_FREQ換成參數，不改成本模型本身任何一行（round_trip_cost_pct
    與costs模組原封不動複用）。"""
    results = {}
    for mult, label in ((1, "1x"), (2, "2x"), (3, "3x")):
        rt_cost = costs.round_trip_cost_pct(slippage_bps=costs.DEFAULT_SLIPPAGE_BPS * mult)
        daily_cost = rt_cost / rebal_freq
        net = combined - daily_cost
        total_return = float((1 + net).prod() - 1)
        results[label] = {"total_return": total_return, "positive": total_return > 0}
    passed = all(v["positive"] for v in results.values())
    return {"rebal_freq": rebal_freq, "scenarios": results, "passed": passed}


def load_base() -> pd.Series:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    base_raw = panel.pct_change().mean(axis=1).dropna()
    base_raw = base_raw[base_raw.index <= pd.Timestamp(holdout.VAL_END)]
    base = base_raw.groupby(base_raw.index.year).transform(lambda x: x - x.mean())
    return base


def main() -> None:
    base = load_base()
    sigma_annual = float(base.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    print(f"base(逐年去均值化後)母體Sharpe={annualized_sharpe(base):.4f}（應接近0）")
    print(f"base日報酬標準差年化={sigma_annual:.4f}（用於理論breakeven計算）")

    # 理論breakeven（獨立於模擬，先算）
    theory = {}
    for freq in REBAL_FREQ_GRID:
        rt_cost_1x = costs.round_trip_cost_pct(slippage_bps=costs.DEFAULT_SLIPPAGE_BPS)
        annualized_drag = rt_cost_1x * TRADING_DAYS_PER_YEAR / freq
        breakeven_sharpe = annualized_drag / sigma_annual
        theory[freq] = {
            "round_trip_cost_1x": rt_cost_1x,
            "annualized_cost_drag_1x": annualized_drag,
            "breakeven_sharpe_1x": breakeven_sharpe,
        }
        print(f"REBAL_FREQ={freq}: 1x年化成本drag={annualized_drag:.4f}, "
              f"理論breakeven_sharpe(1x)={breakeven_sharpe:.4f}")

    # 模擬：對既有#74網格(3強度x5種子=15次)的同一批combined序列，換不同REBAL_FREQ跑GATE4
    sim_results = []
    for strength in STRENGTHS:
        for i in range(N_SEEDS):
            seed = BASE_SEED + i
            combined = inject_synthetic_alpha(base, strength, seed)
            for freq in REBAL_FREQ_GRID:
                g4 = gate4_at_freq(combined, freq)
                sim_results.append({
                    "target_sharpe": strength, "seed": seed,
                    "rebal_freq": freq, "passed": g4["passed"],
                    "total_return_1x": g4["scenarios"]["1x"]["total_return"],
                })

    summary = {}
    for strength in STRENGTHS:
        summary[str(strength)] = {}
        for freq in REBAL_FREQ_GRID:
            subset = [r for r in sim_results
                      if r["target_sharpe"] == strength and r["rebal_freq"] == freq]
            pass_rate = sum(1 for r in subset if r["passed"]) / len(subset)
            summary[str(strength)][str(freq)] = {
                "n": len(subset), "gate4_pass_rate": pass_rate,
                "theory_breakeven_sharpe_1x": theory[freq]["breakeven_sharpe_1x"],
            }

    print("\n=== GATE4通過率 vs 換手頻率（各Sharpe強度，5種子）===")
    for s, by_freq in summary.items():
        print(f"Sharpe={s}:")
        for f, v in by_freq.items():
            print(f"  REBAL_FREQ={f}: pass_rate={v['gate4_pass_rate']:.2f}, "
                  f"理論breakeven_sharpe={v['theory_breakeven_sharpe_1x']:.4f}")

    out = {
        "sigma_annual": sigma_annual,
        "rebal_freq_grid": REBAL_FREQ_GRID,
        "theory": theory,
        "summary": summary,
        "raw_results": sim_results,
    }
    out_path = Path(__file__).parent / "data" / "gate4_cost_sensitivity_power_analysis.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n結果已存 {out_path.relative_to(Path(__file__).parent)}（gitignored，僅供除錯）")

    print(f"\nis_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"


if __name__ == "__main__":
    main()
