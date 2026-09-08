"""`HYPOTHESIS_QUEUE.md` #58 反向波動度加權投資組合建構 第2關：隨機控制組
（2026-09-08 馬拉松第443輪，TW軌）。

**為什麼不能直接套用`#29`的`equal_weight_rebalance_control_v1.py`模板**
（依`HYPOTHESIS_QUEUE.md` #58條目「下一輪」段落已預告需要判斷、本輪判斷結果：
**不適用，需重新設計**）：`#29`的控制組測的是「這個正溢酬是不是恰好靠這159檔
特定組成湊出來的運氣」（bootstrap抽子集，換一批股票進來看效果還在不在）——
這個問法對`#29`成立，因為`#29`的機制主張（機械式再平衡凸性）跟挑中哪些股票
無關，任何子集都該重現。但`#58`的機制主張不是「有沒有波動度分散」，而是
**「權重高低是不是真的對應到個股波動度高低這件事本身有沒有用」**——換一批
股票進來、只要一樣用trailing波動度算權重，機制若成立一樣會重現，這测不出
`#58`真正想問的問題：如果把算好的權重值**亂發**給股票（不管哪支股票波動度
高低），還是不是一樣好？如果亂發也一樣好，代表`#58`量到的效果其實跟`#29`
是同一個「加權後有分散＋定期拉回」的機械式效果，跟「反向波動度」這個具體
機制本身無關（這正是`HYPOTHESIS_QUEUE.md` #58條目「與#29的區別」寫的「加權
規則有沒有真的在做risk parity」這條主張，需要專屬的控制組才能檢驗，`#29`的
子集抽樣模板無法回答）。

**本輪專屬控制組設計（事前綁定）**：固定sanity版本的`REBAL_FREQ=21`／
`VOL_WINDOW=60`不變，在`simulate()`每次再平衡事件、算出`new_w`（正確的
反向波動度權重值）之後，**保留這組權重值的邊際分布完全不變**（每個數值
本身一個不改），只打散「哪個數值分給哪支股票」的對應關係——直接對應
`CLAUDE.md`「同樣縮放幅度、訊號內容無意義」的控制組精神，跟`#53`～`#57`
系列一貫做法同構，只是打散的對象從「時序對齊」換成「股票-權重對應」。

**控制組2個變體**（滿足`control_group_standard.py::MIN_CONTROL_VARIANTS=2`
下限，變體維度是「打散頻率」——每次重新打散 vs 全程固定同一種打散）：
1. `per_rebal_permutation`：每次再平衡事件都獨立重新隨機排列權重-股票對應
   （116次事件、每次都換一種亂發法，測試「即使波動度排名逐期真的在變，
   權重也對不上」是否還有效果）。
2. `fixed_permutation`：整個回測期間固定用同一組隨機排列（backtest開始前
   決定一次，往後每次再平衡都套用同一個permutation），測試「權重-股票的
   長期系統性錯配」下效果是否還在（比`per_rebal_permutation`更保守，因為
   固定錯配仍保留「同一支股票長期拿到差不多的相對權重位階」這個結構，
   只是位階本身是亂發的，不是真的波動度排名）。

兩者皆嚴格保留每次再平衡當下權重向量的邊際分布（數值集合完全相同，只重排
對應到哪支股票），不新增、不刪除、不縮放任何權重值。每個變體`N_DRAWS=100`
次獨立抽樣。

**統計量**：TRAIN/VAL分開，用年化Sharpe（跟`#53`控制組同一把尺，且比`#29`
用的「總報酬溢酬」更能反映`#58`sanity階段已經觀察到的「風險調整後報酬改善」
主張）。真實訊號＝sanity算出的`invvol_ret`序列本身的Sharpe（不扣buyhold，
因為這裡的控制組本身已經是「同樣是一個完整投組」的對照，不是「有沒有加權」
的對照，扣buyhold反而會混入`#29`已經測過的機械式再平衡效果）。

**判準**：比照`control_group_standard.py::evaluate_vs_control()`統一標準——
訊號嚴格大於所有控制組抽樣最大值，或配對式20/20全勝，才算通過；TRAIN/VAL
兩期皆須通過才算第2關PASS。

**相位敏感度**：跟`#29`/`#58`sanity同理不適用於這一關——這是逐次事件式
再平衡（非固定週期起點的問題，`REBAL_FREQ`已固定不掃描），且本關要測的是
權重-股票對應關係本身，不是時間起點。

`is_holdout_consumed()`開工/收工前皆須確認`False`。零新增API呼叫，全部
複用`inverse_vol_weighted_portfolio_gate58.py`既有的`load_prices`/
`build_panel`（同一個159檔panel，交叉確認過與sanity一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from inverse_vol_weighted_portfolio_gate58 import (
    MIN_HISTORY_DAYS,
    REBAL_FREQ,
    VOL_WINDOW,
    WINDOW_END,
    WINDOW_START,
    build_panel,
    load_prices,
    summarize,
)
from validation import holdout

N_DRAWS = 100
BASE_SEED = 20260908

SELECTION_SPEC = (
    "事前綁定（2026-09-08 馬拉松第443輪，#58 GATE_SEQUENCE第2關，專屬控制組，"
    "非套用#29模板，理由見本檔docstring）：固定REBAL_FREQ=21/VOL_WINDOW=60，"
    "每次再平衡事件把正確算出的反向波動度權重值『亂發』給股票（打散股票-權重"
    "對應，保留權重值集合本身邊際分布不變）；2變體：per_rebal_permutation"
    "（每次事件獨立重排）、fixed_permutation（全程固定同一種重排）；各N=100次"
    "抽樣；統計量=年化Sharpe(invvol_ret序列本身，不扣buyhold)；TRAIN"
    "(<=2020-12-31)/VAL(2021-01-01~2024-12-31)分開判定，兩期皆須贏過控制組"
    "才算這一關PASS；比較基準取2變體合併後的最大值；唯一選點，不挑訊號好的"
    "期間事後報告。"
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
    vol_window: int,
    rng: np.random.Generator,
    fixed: bool,
) -> pd.Series:
    """跟`inverse_vol_weighted_portfolio_gate58.simulate()`的invvol腿完全
    同一套機制（t0等權重起跑、滿vol_window才開始算反向波動度權重、兩次
    再平衡間權重隨報酬自然漂移），唯一差異：每次算出`new_w`後，把這組數值
    重新隨機分配給股票（打散股票-權重對應）。`fixed=True`時只在第一次
    再平衡決定一組permutation、之後每次都重用同一組；`fixed=False`時每次
    再平衡都重新抽一組。回傳invvol_ret序列（Series，index跟panel報酬對齊）。
    """
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

        if (t + 1) % rebal_freq == 0 and t + 1 >= vol_window:
            window = ret_values[t + 1 - vol_window : t + 1]
            sigma = window.std(axis=0, ddof=1)
            sigma = np.where(sigma > 0, sigma, np.nan)
            inv_sigma = 1.0 / sigma
            if np.all(np.isnan(inv_sigma)):
                continue
            inv_sigma = np.nan_to_num(inv_sigma, nan=0.0)
            new_w = inv_sigma / inv_sigma.sum()
            if fixed:
                if fixed_perm is None:
                    fixed_perm = rng.permutation(n)
                perm = fixed_perm
            else:
                perm = rng.permutation(n)
            w = new_w[perm]

    return pd.Series(port_rets, index=rets.index, name="invvol_permuted_ret")


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
    print("=== #58 反向波動度加權投資組合建構 GATE_SEQUENCE第2關：隨機控制組 ===")

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），應與sanity完全一致")

    real_daily_returns_path = Path(__file__).parent / "data" / "inverse_vol_weighted_portfolio_gate58_daily_returns.csv"
    real_df = pd.read_csv(real_daily_returns_path, index_col=0, parse_dates=True)
    real_invvol = real_df["invvol_ret"]
    print(f"真實invvol_ret序列已從sanity輸出載入：{real_invvol.index[0].date()}..{real_invvol.index[-1].date()}"
          f"（{len(real_invvol)}個交易日，非本輪重算，交叉確認panel一致性)")

    dates = pd.DatetimeIndex(rets_dates := real_invvol.index)

    rows = []
    for period in ("TRAIN", "VAL"):
        mask = _period_mask(dates, period)
        real_sub = real_invvol.to_numpy()[mask]
        signal_stat = _annualized_sharpe(real_sub)

        control_draws: dict[str, list[float]] = {}
        for variant, fixed in (("per_rebal_permutation", False), ("fixed_permutation", True)):
            rng = np.random.default_rng(hash((BASE_SEED, "gate58", period, variant)) % (2**32))
            draws = []
            for _ in range(N_DRAWS):
                permuted = simulate_permuted(panel, REBAL_FREQ, VOL_WINDOW, rng, fixed=fixed)
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
        print(f"  真實invvol年化Sharpe = {signal_stat:+.4f}")
        print(f"  控制組最大值 = {verdict.control_max:+.4f}  平均 = {verdict.control_mean:+.4f}  "
              f"百分位(僅記錄非判準) = {verdict.control_percentile:.1f}")
        print(f"  判定: {'PASS' if verdict.passed else 'FAIL'} — {verdict.reason}")

    result_df = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "data" / "inverse_vol_weighted_portfolio_gate58_control_results.csv"
    result_df.to_csv(out_path, index=False)
    print(f"\n結果已存: {out_path}")

    both_pass = bool(result_df["passed"].all())
    print(f"\n=== 第2關綜合判定（TRAIN+VAL皆須PASS）：{'PASS' if both_pass else 'FAIL'} ===")

    assert holdout.is_holdout_consumed() is False, "收工前is_holdout_consumed()必須是False"
    return result_df, both_pass


if __name__ == "__main__":
    main()
