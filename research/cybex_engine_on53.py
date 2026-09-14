"""Cybex.引擎：把`timing_overlay_engine.py`三個on-window機制（進場延遲確認／
出場延遲確認／總開關重新開啟確認期）套用在`#53`（全市場報酬離散度速度）身上，
2026-09-15 開發佇列自走輪。

**為什麼選#53當受測對象**：`PENDING_QUEUE.md`「五條的執行順序」註記#53是
「市場總開關假設軸」五條裡唯一走到GATE_SEQUENCE第2關（隨機控制組）才落敗的
（`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#194），其餘#54/#55/#57死在更早
的第1關sanity。既然這三個引擎機制的設計目的是「降低percentile線性映射對雜訊
敏感、減少不必要的開關翻轉」，理論上唯一有機會被它救回來的只有#53（本身
sanity過關、只是控制組贏不了）——對已經死在sanity的#54/#55/#57補這個引擎
機制沒有意義（訊號方向在sanity就已經反過來，不是雜訊/翻轉頻率的問題）。

**方法論**：完全複用`cross_sectional_dispersion_gate53_control.py`的資料
（`build_exposure_frame()`）、統計量（年化Sharpe）、TRAIN/VAL切分、
控制組框架（`control_group_standard.evaluate_vs_control`，circular_shift／
block_shuffle_5／block_shuffle_20三變體、各N=100）——**唯一差異**是曝險序列
先經過`timing_overlay_engine.apply_confirmed_switch()`轉換（含真實訊號與每次
控制組抽樣都一樣套用這個轉換，確保比較的是「這個引擎機制+真實時序對齊」
vs「這個引擎機制+打亂時序對齊」，不是引擎機制本身的效果）。

**誠實揭露**：套用一個新的執行時機機制到一個已經FAIL的訊號上，屬於
`CLAUDE.md`統計偽影家族⑥「換手／執行時機縮減」，控制組標準完全不放寬
（一樣要求嚴格贏過控制組最大值或配對20/20全勝）。引擎參數
（threshold=0.5／entry_delay=3／exit_delay=3／reopen_cooldown=5）事前固定於
`timing_overlay_engine.py`，本檔案不做任何參數掃描或事後調整。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from cross_sectional_dispersion_gate53_control import (
    _annualized_sharpe,
    _block_shuffle,
    _circular_shift,
    _period_mask,
    build_exposure_frame,
)
from timing_overlay_engine import (
    DEFAULT_ENTRY_DELAY,
    DEFAULT_EXIT_DELAY,
    DEFAULT_REOPEN_COOLDOWN,
    DEFAULT_THRESHOLD,
    apply_confirmed_switch,
)
from validation.holdout import is_holdout_consumed

N_DRAWS = 100
BASE_SEED = 20260915

SELECTION_SPEC = (
    "事前綁定（2026-09-15 開發佇列自走輪，Cybex.引擎套用於#53）：曝險序列先經"
    "timing_overlay_engine.apply_confirmed_switch()轉換"
    f"（threshold={DEFAULT_THRESHOLD}, entry_delay={DEFAULT_ENTRY_DELAY}, "
    f"exit_delay={DEFAULT_EXIT_DELAY}, reopen_cooldown={DEFAULT_REOPEN_COOLDOWN}，"
    "三個參數固定不掃描），再乘TAIEX日報酬得策略日報酬；統計量=年化Sharpe；"
    "TRAIN(<=2020-12-31)/VAL(2021-01-01~2024-12-31)分開判定，兩期皆須贏過"
    "控制組才算通過；控制組3變體(circular_shift/block_shuffle_5/"
    "block_shuffle_20)各N=100，且每次控制組抽樣都重新套用同一個"
    "apply_confirmed_switch()轉換（比較『引擎機制+真實時序』vs『引擎機制+"
    "打亂時序』，不是比引擎機制本身有沒有效果）；level/vel兩規格各自獨立"
    "判定；唯一選點，不挑訊號好的規格/期間事後報告。"
)


def run_one(spec: str, period: str, df: pd.DataFrame) -> dict:
    raw_col = f"{spec}_exposure"
    sub = df.dropna(subset=[raw_col, "ret"])
    sub = sub.loc[_period_mask(sub["date"], period)]
    raw_exposure = sub[raw_col].to_numpy()
    ret = sub["ret"].to_numpy()
    n = len(sub)

    confirmed_exposure = apply_confirmed_switch(raw_exposure)
    real_daily = confirmed_exposure * ret
    signal_stat = _annualized_sharpe(real_daily)
    mean_exposure = float(confirmed_exposure.mean())

    control_draws: dict[str, list[float]] = {}
    for variant, fn in (
        ("circular_shift", _circular_shift),
        ("block_shuffle_5", lambda a, rng: _block_shuffle(a, 5, rng)),
        ("block_shuffle_20", lambda a, rng: _block_shuffle(a, 20, rng)),
    ):
        rng = np.random.default_rng(hash((BASE_SEED, spec, period, variant)) % (2**32))
        draws = []
        for _ in range(N_DRAWS):
            shuffled_raw = fn(raw_exposure, rng)
            shuffled_confirmed = apply_confirmed_switch(shuffled_raw)
            daily = shuffled_confirmed * ret
            draws.append(_annualized_sharpe(daily))
        control_draws[variant] = draws

    verdict = evaluate_vs_control(
        signal_stat=signal_stat,
        control_draws=control_draws,
        selection_spec=SELECTION_SPEC,
    )
    return {
        "spec": spec, "period": period, "n": n, "mean_exposure": mean_exposure,
        "signal_sharpe": signal_stat, "control_max": verdict.control_max,
        "control_mean": verdict.control_mean, "control_percentile": verdict.control_percentile,
        "passed": verdict.passed, "reason": verdict.reason,
    }


def main():
    assert is_holdout_consumed() is False, "開工前is_holdout_consumed()必須是False"
    print("=== Cybex.引擎：三個on-window機制套用於#53，GATE_SEQUENCE第2關重測 ===")
    df = build_exposure_frame()
    print(f"合併後總交易日數: {len(df)}")

    rows = []
    for spec in ("level", "vel"):
        for period in ("TRAIN", "VAL"):
            r = run_one(spec, period, df)
            rows.append(r)
            print(
                f"\n--- spec={spec} period={period} (n={r['n']}, "
                f"確認後平均曝險={r['mean_exposure']:.3f}) ---"
            )
            print(f"  真實策略年化Sharpe = {r['signal_sharpe']:+.4f}")
            print(f"  控制組最大值 = {r['control_max']:+.4f}  平均 = {r['control_mean']:+.4f}  "
                  f"百分位(僅記錄非判準) = {r['control_percentile']:.1f}")
            print(f"  判定: {'PASS' if r['passed'] else 'FAIL'} — {r['reason']}")

    result_df = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "data" / "cybex_engine_on53_results.csv"
    result_df.to_csv(out_path, index=False)
    print(f"\n結果已存: {out_path}")

    print("\n=== 依規格彙總（一個規格要TRAIN+VAL皆PASS才算這一關通過） ===")
    spec_verdict = {}
    for spec in ("level", "vel"):
        sub = result_df[result_df["spec"] == spec]
        both_pass = bool(sub["passed"].all())
        spec_verdict[spec] = both_pass
        print(f"  {spec}: TRAIN passed={sub[sub['period']=='TRAIN']['passed'].iloc[0]}  "
              f"VAL passed={sub[sub['period']=='VAL']['passed'].iloc[0]}  => 第2關{'PASS' if both_pass else 'FAIL'}")

    assert is_holdout_consumed() is False, "收工前is_holdout_consumed()必須是False"
    return result_df, spec_verdict


if __name__ == "__main__":
    main()
