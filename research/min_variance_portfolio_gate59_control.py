"""`HYPOTHESIS_QUEUE.md` #59 最小變異數投資組合建構 第2關：隨機控制組
（2026-09-08 hypothesis_queue排程接續）。

**沿用`#58`的專屬控制組設計，理由同構**（見`inverse_vol_weighted_portfolio_
gate58_control.py`docstring完整展開，這裡不重複）：`#59`真正要問的問題不是
「有沒有分散」（那是`#29`已經測過的機械式再平衡效果），而是**「權重是不是
真的對應到共變異數結構算出來的最適解這件事本身有沒有用」**——如果把每次
`min_variance_weights()`算出來的權重值集合亂發給股票，還是不是一樣好？

**`#59`專屬考量（docstring原文已預告的開放問題，本輪判斷結果）**：`#59`
sanity段落擔心「最小變異數解本身依賴共變異數結構、打散對應關係可能連權重值
集合本身都會失真」——實際檢視後**這個疑慮不成立**：打散只發生在
`min_variance_weights()`算完`new_w`**之後**，權重值集合（哪些數值存在、
各自大小）完全不受影響，只有「哪個數值分給哪支股票」被重排。跟`#58`控制組
面對的問題結構完全相同（`#58`也是先算出正確權重再打散），可以直接沿用同一套
`per_rebal_permutation`/`fixed_permutation`設計，不需要重新發明。

**統計量**：跟`#58`控制組同一把尺，TRAIN/VAL分開用年化Sharpe（訊號=sanity
輸出的`minvar_ret`序列本身，不扣buyhold，理由同`#58`——避免混入`#29`已測過
的機械式再平衡效果）。

**判準**：`control_group_standard.py::evaluate_vs_control()`統一標準，TRAIN/
VAL兩期皆須通過才算第2關PASS。

**相位敏感度**：跟`#58`控制組同理不適用（逐次事件式再平衡，`REBAL_FREQ`
固定不掃描，本關測的是權重-股票對應關係本身）。

`is_holdout_consumed()`開工/收工前皆須確認`False`。零新增API呼叫，全部複用
`min_variance_portfolio_gate59.py`既有的`load_prices`/`build_panel`/
`min_variance_weights`（同一個159檔panel，交叉確認過與sanity一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from min_variance_portfolio_gate59 import (
    COV_WINDOW,
    MIN_HISTORY_DAYS,
    REBAL_FREQ,
    WINDOW_END,
    WINDOW_START,
    build_panel,
    load_prices,
    min_variance_weights,
    summarize,
)
from validation import holdout

N_DRAWS = 100
BASE_SEED = 20260908

SELECTION_SPEC = (
    "事前綁定（2026-09-08 hypothesis_queue排程接續，#59 GATE_SEQUENCE第2關，"
    "沿用#58同款專屬控制組設計，理由見本檔docstring）：固定REBAL_FREQ=21/"
    "COV_WINDOW=60，每次再平衡事件把min_variance_weights()正確算出的權重值"
    "『亂發』給股票（打散股票-權重對應，保留權重值集合本身邊際分布不變）；"
    "2變體：per_rebal_permutation（每次事件獨立重排）、fixed_permutation"
    "（全程固定同一種重排）；各N=100次抽樣；統計量=年化Sharpe(minvar_ret序列"
    "本身，不扣buyhold)；TRAIN(<=2020-12-31)/VAL(2021-01-01~2024-12-31)分開"
    "判定，兩期皆須贏過控制組才算這一關PASS；比較基準取2變體合併後的最大值；"
    "唯一選點，不挑訊號好的期間事後報告。"
)


def _annualized_sharpe(daily_ret: np.ndarray) -> float:
    if len(daily_ret) < 2:
        return float("nan")
    sd = daily_ret.std(ddof=1)
    if sd <= 0:
        return float("nan")
    return float(daily_ret.mean() / sd * np.sqrt(252))


def simulate_permuted(
    panel: pd.DataFrame,
    rebal_freq: int,
    cov_window: int,
    rng: np.random.Generator,
    fixed: bool,
) -> pd.Series:
    """跟`min_variance_portfolio_gate59.simulate()`的minvar腿完全同一套機制
    （t0等權重起跑、滿cov_window才開始算最小變異數權重、兩次再平衡間權重隨
    報酬自然漂移），唯一差異：每次算出`new_w`後，把這組數值重新隨機分配給
    股票（打散股票-權重對應）。`fixed=True`時只在第一次再平衡決定一組
    permutation、之後每次都重用同一組；`fixed=False`時每次再平衡都重新抽
    一組。回傳minvar_ret序列（Series，index跟panel報酬對齊）。"""
    rets = panel.pct_change().dropna(how="all")
    rets = rets.fillna(0.0)
    n = panel.shape[1]
    w = np.full(n, 1.0 / n)
    port_rets = []
    ret_values = rets.values
    fixed_perm = None
    for t in range(ret_values.shape[0]):
        r = ret_values[t]
        port_rets.append(float(np.dot(w, r)))
        w = w * (1 + r)
        w = w / w.sum()

        if (t + 1) % rebal_freq == 0 and t + 1 >= cov_window:
            window = ret_values[t + 1 - cov_window : t + 1]
            new_w = min_variance_weights(window)
            if fixed:
                if fixed_perm is None:
                    fixed_perm = rng.permutation(n)
                perm = fixed_perm
            else:
                perm = rng.permutation(n)
            w = new_w[perm]

    return pd.Series(port_rets, index=rets.index, name="minvar_permuted_ret")


def _period_mask(dates: pd.DatetimeIndex, label: str) -> np.ndarray:
    train_end = pd.Timestamp(holdout.TRAIN_END)
    val_end = pd.Timestamp(holdout.VAL_END)
    if label == "TRAIN":
        return np.asarray(dates <= train_end)
    if label == "VAL":
        return np.asarray((dates > train_end) & (dates <= val_end))
    raise ValueError(label)


def main():
    assert holdout.is_holdout_consumed() is False, "開工前is_holdout_consumed()必須是False"
    print("=== #59 最小變異數投資組合建構 GATE_SEQUENCE第2關：隨機控制組 ===")

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），應與sanity完全一致")

    real_daily_returns_path = Path(__file__).parent / "data" / "min_variance_portfolio_gate59_daily_returns.csv"
    real_df = pd.read_csv(real_daily_returns_path, index_col=0, parse_dates=True)
    real_minvar = real_df["minvar_ret"]
    print(f"真實minvar_ret序列已從sanity輸出載入：{real_minvar.index[0].date()}..{real_minvar.index[-1].date()}"
          f"（{len(real_minvar)}個交易日，非本輪重算，交叉確認panel一致性)")

    dates = pd.DatetimeIndex(real_minvar.index)

    rows = []
    for period in ("TRAIN", "VAL"):
        mask = _period_mask(dates, period)
        real_sub = real_minvar.to_numpy()[mask]
        signal_stat = _annualized_sharpe(real_sub)

        control_draws: dict[str, list[float]] = {}
        for variant, fixed in (("per_rebal_permutation", False), ("fixed_permutation", True)):
            rng = np.random.default_rng(hash((BASE_SEED, "gate59", period, variant)) % (2**32))
            draws = []
            for _ in range(N_DRAWS):
                permuted = simulate_permuted(panel, REBAL_FREQ, COV_WINDOW, rng, fixed=fixed)
                permuted_sub = permuted.to_numpy()[mask]
                draws.append(_annualized_sharpe(permuted_sub))
            control_draws[variant] = draws
            print(f"  {period}/{variant}: {N_DRAWS} draws完成，mean={np.nanmean(draws):+.4f} max={np.nanmax(draws):+.4f}")

        verdict = evaluate_vs_control(
            signal_stat=signal_stat,
            control_draws=control_draws,
            selection_spec=SELECTION_SPEC,
        )
        rows.append({
            "period": period, "n": int(mask.sum()), "signal_sharpe": signal_stat,
            "control_max": verdict.control_max, "control_mean": verdict.control_mean,
            "control_percentile": verdict.control_percentile,
            "passed": verdict.passed, "reason": verdict.reason,
        })
        print(f"\n--- period={period} (n={int(mask.sum())}) ---")
        print(f"  真實minvar年化Sharpe = {signal_stat:+.4f}")
        print(f"  控制組最大值 = {verdict.control_max:+.4f}  平均 = {verdict.control_mean:+.4f}  "
              f"百分位(僅記錄非判準) = {verdict.control_percentile:.1f}")
        print(f"  判定: {'PASS' if verdict.passed else 'FAIL'} — {verdict.reason}")

    result_df = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "data" / "min_variance_portfolio_gate59_control_results.csv"
    result_df.to_csv(out_path, index=False)
    print(f"\n結果已存: {out_path}")

    both_pass = bool(result_df["passed"].all())
    print(f"\n=== 第2關綜合判定（TRAIN+VAL皆須PASS）：{'PASS' if both_pass else 'FAIL'} ===")

    assert holdout.is_holdout_consumed() is False, "收工前is_holdout_consumed()必須是False"
    return result_df, both_pass


if __name__ == "__main__":
    main()
