"""`HYPOTHESIS_QUEUE.md` #53 全市場報酬離散度速度（Cross-Sectional Return
Dispersion Velocity）GATE_SEQUENCE 第2關：隨機控制組（2026-09-08
hypothesis_queue排程接續，取鎖時發現陳舊鎖檔pid115512已回收）。

**接續脈絡**：上一輪（`MARATHON_LOG.md` 2026-09-07T05:56 條目）已完成第1關
sanity（`cross_sectional_dispersion_gate53.py`，登記為`TRIALS_LEDGER.md`#192，
verdict=未結案），三項sanity皆PASS。本輪從sanity沿用同一份`disp`/`vel`/
`level_pctile`/`vel_pctile`序列，往下走第2關，比照『2026-09-07 Cowork 更正一】
#53～#57 市場總開關假設軸』共同規格：曝險函數
`exposure_t = clip(1 - pctile_{t-1}, 0, 1)`（`shift(1)`，事前固定線性映射
`f(z)=1-z`，唯一選點，不掃描斜率——見下方`selection_spec`），控制組是
「同樣縮放幅度、訊號內容無意義」版本（保留exposure序列邊際分布與平均曝險，
只打散它與報酬的時序對齊），比照`control_group_standard.py::evaluate_vs_control()`
（Cybex.債務4）標準：只有「嚴格大於所有控制組抽樣最大值」或「配對式20/20全勝」
才算通過。

**控制組3個變體**（滿足共同規格「控制組自身參數至少兩個變體」下限，這裡選擇
「隨機化機制本身」當變體維度，而非映射斜率——事前綁定的f(z)只有一個固定選擇，
不做斜率掃描，因為斜率掃描屬於訊號本身的多重比較，不是控制組穩健性檢查；
控制組要掃的是「不同隨機化強度下都贏不了才算真的贏」）：
1. `circular_shift`：`np.roll`整條exposure序列隨機位移k∈[1,n-1]。
2. `block_shuffle_5`：把exposure序列切成長度5的區塊、打亂區塊順序（保留短期
   局部結構，只破壞跨區塊的時序對齊）。
3. `block_shuffle_20`：同上但區塊長度20（跟`VEL_WINDOW`一致，測試更粗粒度的
   隨機化下是否仍然贏不了）。

三者皆嚴格保留exposure序列的邊際分布與平均值（只是重新排列/位移，不改變
任何一個數值本身），只打散跟真實報酬序列的時序對齊——完全對應共同規格「同樣
縮放幅度、訊號內容無意義」的要求。每個變體N=100次抽樣（>=`MIN_DRAWS_PER_VARIANT`
且滿足`HYPOTHESIS_QUEUE_PROTOCOL.md`「至少100 draws」的協定要求，遠低於
`CLAUDE.md`「1000 draws規模投入」停下條件，不觸發停下）。

**統計量**：年化Sharpe（策略日報酬 = exposure_t * TAIEX日報酬，無槓桿、
現金部位報酬簡化假設為0%——不含無風險利率，這是已知的保守簡化，若進入
更深入的關卡需要重新評估）。TRAIN(<=`TRAIN_END`)/VAL(`TRAIN_END`之後
到`VAL_END`)分開判定，跟既有慣例（alpha顯著性須兩期皆成立）同一把尺——
一個規格（level或vel）要兩期都贏過控制組才算這一關PASS。

**相位敏感度**：共同規格「任何週頻／月頻的重平衡」要求本輪不適用——這個
建構是**逐日連續曝險**（每個交易日都用當日expanding百分位重新計算曝險，
不是固定週期性重平衡），沒有「起始相位」這個自由度可以平移，因此明確跳過
（不是遺漏，是這個規則對這個特定建構不適用）。

`is_holdout_consumed()`開工/收工前皆須確認`False`。零新增API呼叫，全部
複用`cross_sectional_dispersion_gate53.py`既有快取與sanity計算結果。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from cross_sectional_dispersion_gate53 import build_dispersion_series, _load_taiex_close
from validation.holdout import TRAIN_END, VAL_END, is_holdout_consumed

N_DRAWS = 100
BASE_SEED = 20260908
TRADING_DAYS_PER_YEAR = 252

SELECTION_SPEC = (
    "事前綁定（2026-09-08 hypothesis_queue排程，#53 GATE_SEQUENCE第2關）："
    "exposure_t = clip(1 - pctile_{t-1}, 0, 1)，f(z)=1-z固定線性映射、不掃描斜率；"
    "level_pctile與vel_pctile兩個規格各自獨立判定；TRAIN(<=2020-12-31)/VAL"
    "(2021-01-01~2024-12-31)分開判定，兩期皆須贏過控制組才算這一關PASS；"
    "統計量=年化Sharpe(daily strategy return=exposure_t*TAIEX日報酬，無槓桿，"
    "現金報酬簡化為0%)；控制組3變體(circular_shift/block_shuffle_5/"
    "block_shuffle_20)各N=100次抽樣，比較基準取三變體合併後的最大值；"
    "唯一選點，不挑訊號好的規格/期間事後報告。"
)


def _annualized_sharpe(daily_ret: np.ndarray) -> float:
    if len(daily_ret) < 2:
        return float("nan")
    sd = daily_ret.std(ddof=1)
    if sd <= 0:
        return float("nan")
    return float(daily_ret.mean() / sd * np.sqrt(TRADING_DAYS_PER_YEAR))


def _block_shuffle(arr: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    n = len(arr)
    n_blocks = int(np.ceil(n / block))
    blocks = [arr[i * block: min((i + 1) * block, n)] for i in range(n_blocks)]
    order = rng.permutation(n_blocks)
    return np.concatenate([blocks[i] for i in order])


def _circular_shift(arr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    k = int(rng.integers(1, len(arr)))
    return np.roll(arr, k)


def build_exposure_frame() -> pd.DataFrame:
    """回傳index重設的DataFrame，欄位date/ret/level_exposure/vel_exposure，
    只保留TAIEX報酬與兩個exposure皆非NaN的交易日（level/vel分開dropna，
    在下面依規格各自取用，這裡先合併方便一次載入）。"""
    disp_df = build_dispersion_series()
    taiex = _load_taiex_close()
    taiex = taiex.assign(ret=taiex["close"].pct_change())
    merged = disp_df[["date", "level_pctile", "vel_pctile"]].merge(
        taiex[["date", "ret"]], on="date", how="inner"
    )
    merged = merged.sort_values("date").reset_index(drop=True)
    # shift(1)：t日的曝險用t-1日收盤後才完整可得的百分位，套用在t日的報酬上。
    merged["level_pctile_lag1"] = merged["level_pctile"].shift(1)
    merged["vel_pctile_lag1"] = merged["vel_pctile"].shift(1)
    merged["level_exposure"] = (1.0 - merged["level_pctile_lag1"]).clip(0.0, 1.0)
    merged["vel_exposure"] = (1.0 - merged["vel_pctile_lag1"]).clip(0.0, 1.0)
    return merged


def _period_mask(dates: pd.Series, label: str) -> pd.Series:
    train_end = pd.Timestamp(TRAIN_END)
    val_end = pd.Timestamp(VAL_END)
    if label == "TRAIN":
        return dates <= train_end
    if label == "VAL":
        return (dates > train_end) & (dates <= val_end)
    raise ValueError(label)


def run_one(spec: str, period: str, df: pd.DataFrame) -> dict:
    exposure_col = f"{spec}_exposure"
    sub = df.dropna(subset=[exposure_col, "ret"])
    sub = sub.loc[_period_mask(sub["date"], period)]
    exposure = sub[exposure_col].to_numpy()
    ret = sub["ret"].to_numpy()
    n = len(sub)

    real_daily = exposure * ret
    signal_stat = _annualized_sharpe(real_daily)
    mean_exposure = float(exposure.mean())

    control_draws: dict[str, list[float]] = {}
    for variant, fn in (
        ("circular_shift", _circular_shift),
        ("block_shuffle_5", lambda a, rng: _block_shuffle(a, 5, rng)),
        ("block_shuffle_20", lambda a, rng: _block_shuffle(a, 20, rng)),
    ):
        rng = np.random.default_rng(hash((BASE_SEED, spec, period, variant)) % (2**32))
        draws = []
        for _ in range(N_DRAWS):
            shuffled_exposure = fn(exposure, rng)
            daily = shuffled_exposure * ret
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
    print("=== #53 全市場報酬離散度速度 GATE_SEQUENCE第2關：隨機控制組 ===")
    df = build_exposure_frame()
    print(f"合併後總交易日數: {len(df)}")

    rows = []
    for spec in ("level", "vel"):
        for period in ("TRAIN", "VAL"):
            r = run_one(spec, period, df)
            rows.append(r)
            print(
                f"\n--- spec={spec} period={period} (n={r['n']}, mean_exposure={r['mean_exposure']:.3f}) ---"
            )
            print(f"  真實策略年化Sharpe = {r['signal_sharpe']:+.4f}")
            print(f"  控制組最大值 = {r['control_max']:+.4f}  平均 = {r['control_mean']:+.4f}  "
                  f"百分位(僅記錄非判準) = {r['control_percentile']:.1f}")
            print(f"  判定: {'PASS' if r['passed'] else 'FAIL'} — {r['reason']}")

    result_df = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "data" / "cross_sectional_dispersion_gate53_control_results.csv"
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
