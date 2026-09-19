"""重構.A5：GATE6（逐年一致性）檢定力，補測`n_years=6`（TRAIN期）與
`n_years=4`（VAL期），對應3筆範圍外GATE6 FAIL舊假設實際用的年數
（`PENDING_QUEUE.md`「重構.A5」條目，2026-09-19查核發現後排入）。

背景：`synthetic_power_curve_gate74.py::run_pilot()`（重構.A2已修好逐年
demean bug）目前只測過`n_years=10`（TRAIN+VAL合併，2015-2024）在強度
{0.3,0.5,0.8}下的GATE6通過率（0%/40%/60%）。但`#17 f_52w_high_prox`／
`#29 equal_weight_rebalance`用的是TRAIN期單獨6年（2015-2020，門檻
>=5/6=至少5年正報酬），`#49 overnight_intraday`用的是VAL期單獨4年
（2021-2024，門檻>=5/6換算成N=4等同要求4/4全數正報酬）——年數與門檻的
「有效嚴格度」都跟n_years=10不同，不能直接套用既有10年期數字。

本檔案複用`synthetic_power_curve_gate74.py`全部既有函式（`inject_
synthetic_alpha`／`gate6_yearly_consistency`／逐年demean邏輯），只把
`base_raw`依`validation.holdout.TRAIN_END`/`VAL_END`切成兩段分開重跑，
不修改任何既有关卡门槛数字、不修改`run_pilot()`本身（避免影響既有
n_years=10网格的可重现性），零新增外部API呼叫（複用同一份300檔快取）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from equal_weight_rebalance_sanity import build_panel, load_prices
from factor_ic import SAMPLE_SIZE, SAMPLE_SEED, sample_universe_ids
from synthetic_power_curve_gate74 import (
    annualized_sharpe, inject_synthetic_alpha, gate6_yearly_consistency,
)
from validation import costs as _costs  # noqa: F401  (未使用，僅確認模組可載入，維持與gate74一致的相依環境)
from validation import holdout

STRENGTHS = (0.3, 0.5, 0.8)
N_SEEDS = 5
BASE_SEED = 20260919


def _demean_per_year(s: pd.Series) -> pd.Series:
    return s.groupby(s.index.year).transform(lambda x: x - x.mean())


def run_scope(base_raw_full: pd.Series, scope_name: str, start: str | None, end: str) -> dict:
    scoped = base_raw_full[base_raw_full.index <= pd.Timestamp(end)]
    if start is not None:
        scoped = scoped[scoped.index > pd.Timestamp(start)]
    base = _demean_per_year(scoped)
    n_years_available = base.index.year.nunique()
    print(f"[{scope_name}] n_obs={len(base)}, n_years={n_years_available}, "
          f"母體Sharpe(demean後,應~0)={annualized_sharpe(base):.4f}")

    result = {"scope": scope_name, "n_years": int(n_years_available), "by_strength": {}}
    for strength in STRENGTHS:
        passes = []
        details = []
        for i in range(N_SEEDS):
            seed = BASE_SEED + 100 * (i + 1)
            combined = inject_synthetic_alpha(base, strength, seed)
            g6 = gate6_yearly_consistency(combined)
            passes.append(g6["passed"])
            details.append({"seed": seed, "n_positive": g6["n_positive"],
                             "n_years": g6["n_years"], "passed": g6["passed"]})
        pass_rate = sum(passes) / len(passes)
        result["by_strength"][str(strength)] = {"pass_rate": pass_rate, "details": details}
        print(f"[{scope_name}] strength={strength}: GATE6通過率={pass_rate:.0%} "
              f"({sum(passes)}/{len(passes)})")
    return result


def main() -> None:
    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    base_raw_full = panel.pct_change().mean(axis=1).dropna()
    base_raw_full = base_raw_full[base_raw_full.index <= pd.Timestamp(holdout.VAL_END)]
    print(f"base_raw_full: {len(base_raw_full)}筆，"
          f"{base_raw_full.index[0].date()}..{base_raw_full.index[-1].date()}")

    train6 = run_scope(base_raw_full, "train6（對應#17/#29，2015-2020，門檻>=5/6）",
                        start=None, end=holdout.TRAIN_END)
    val4 = run_scope(base_raw_full, "val4（對應#49，2021-2024，門檻>=5/6即N=4需4/4）",
                      start=holdout.TRAIN_END, end=holdout.VAL_END)

    out = {"generated_from": "gate6_power_curve_scoped_years.py（重構.A5）",
           "n_seeds": N_SEEDS, "strengths": list(STRENGTHS), "scopes": [train6, val4]}
    out_path = Path(__file__).parent / "data" / "gate6_power_curve_scoped_years.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"完成，輸出已寫入 {out_path.relative_to(Path(__file__).parent)}")

    print(f"is_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"


if __name__ == "__main__":
    main()
