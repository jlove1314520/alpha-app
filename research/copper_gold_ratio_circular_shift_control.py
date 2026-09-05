"""`copper_gold_ratio_gate`（`TRIALS_LEDGER.md`#125，`HYPOTHESIS_QUEUE.md`#34）
CHEAP_PASS的自相關保留版隨機控制組查核——同`margin_debt_level_circular_shift
_control.py`（round380）的方法論，套用到TW_MARATHON_STATE.md round380「下一步(a)」
點名的具體對象：`copper_gold_ratio_gate.py`是本佇列目前唯一「用完全打散
`_shuffle_percentile()`框架測『慢變訊號 vs 20日重疊窗口TAIEX後續報酬』且
仍未結案（CHEAP_PASS，尚待deep dive）」的候選，風險敞口最高，優先查核。

**為什麼這個候選風險最高**：`copper_gold_ratio`是商品期貨比值水位（level），
逐日取樣、變動極慢（連續幾天幾乎不變，見round380對`level_pct`的同款描述）；
目標`tw_fwd_ret_m`是TAIEX後20個交易日報酬、逐日取樣，代表相鄰兩個觀測點
之間有19天窗口重疊，本身高度自相關。這正是round380/`margin_debt_level_
circular_shift_control.py`發現「完全打散null系統性低估變異數」的同一種
資料結構（慢變訊號×重疊窗口目標），而`copper_gold_ratio_gate`的表面顯著性
（TRAIN/VAL percentile皆100.0，|r|=0.18~0.25，是本佇列regime timing類
候選中訊號最強的一個）比`margin_debt_level_v1`當初的98.0/100.0更極端，
若同樣的偏誤存在，這裡的下修空間可能更大、也更值得在投入deep dive資源
前先查清楚。

**方法**（逐字比照round380）：對`copper_gold_ratio`訊號做circular shift
（`np.roll`，位移量k∈[1,n-1]均勻抽樣，TRAIN/VAL各自獨立位移、不跨期間邊界），
`tw_fwd_ret_m`維持原始時間順序不動，保留兩序列各自的自相關結構、只破壞
兩者間的真實時間對齊。同時重算同一份資料的完全打散版本供直接比較。
N=500（<1000，不觸發`CLAUDE.md`「1000 draws規模投入」停下條件）。
用Pearson相關（跟原始`copper_gold_ratio_gate.py`判準一致，非Spearman）。

**事前綁定判讀**：若circular-shift null下VAL/TRAIN百分位比完全打散版顯著
下修（>15個百分點，同round380門檻），代表原CHEAP_PASS顯著性有部分/全部
是自相關結構造成的假顯著，需要下修判定（至少不能直接進入deep dive視為
穩健候選）；若差距不明顯，代表這條候選的顯著性不是自相關假象，CHEAP_PASS
維持有效。

零新增API呼叫，完全重用`copper_gold_ratio_gate.py`既有`build_aligned_series()`/
`_split()`（讀取`yf_price_client.py`既有快取）。

2026-09-06 馬拉松第384輪（TW軌）新增，接續`TW_MARATHON_STATE.md`round380
「下一步(a)：盤點其他用完全打散`_shuffle_percentile()`框架的cheap gate是否有
同款自相關高估問題」，本輪鎖定風險最高、尚未結案的具體對象優先查核（而非
逐一盤點全部7支同框架腳本——`fx_twd_gate`/`fred_yield_curve_gate`兩者已是
FAIL判定，即使百分位下修也不影響最終結論，優先權低於這個仍待deep dive的
CHEAP_PASS候選；`option_pcr_gate`目標是下一交易日報酬非20日重疊窗口，風險
模式不同；`spillover_overnight_gate`/`turn_of_month_gate`分別是day-level
lead-lag與calendar dummy設計，皆非本輪鎖定的風險模式，不在本輪範圍內）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from copper_gold_ratio_gate import build_aligned_series, _split, TRAIN_END, VAL_END

N_CIRCULAR = 500
CIRCULAR_SEED = 20260906


def _full_shuffle_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_r, real_p = stats.pearsonr(signal, target)
    rng = np.random.default_rng(seed)
    shuffled = np.empty(n)
    for i in range(n):
        perm = rng.permutation(signal)
        shuffled[i] = stats.pearsonr(perm, target)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_r)))
    return {"real_r": float(real_r), "real_p": float(real_p),
            "null_std": float(np.std(shuffled)), "percentile": pctl}


def _circular_shift_percentile(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    real_r, real_p = stats.pearsonr(signal, target)
    rng = np.random.default_rng(seed)
    n_obs = len(signal)
    shuffled = np.empty(n)
    for i in range(n):
        k = int(rng.integers(1, n_obs))  # 1..n_obs-1，排除k=0(等於沒位移)
        shifted = np.roll(signal, k)
        shuffled[i] = stats.pearsonr(shifted, target)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_r)))
    return {"real_r": float(real_r), "real_p": float(real_p),
            "null_std": float(np.std(shuffled)), "percentile": pctl}


def main():
    print("=== copper_gold_ratio_gate 自相關保留版隨機控制組查核 ===")
    aligned = build_aligned_series()
    train, val = _split(aligned)
    print(f"train_n={len(train)} val_n={len(val)} N_CIRCULAR={N_CIRCULAR} seed={CIRCULAR_SEED}")

    rows = []
    for label, df in (("TRAIN", train), ("VAL", val)):
        signal = df["copper_gold_ratio"].to_numpy()
        target = df["tw_fwd_ret_m"].to_numpy()
        n = len(df)

        full = _full_shuffle_percentile(signal, target, N_CIRCULAR, CIRCULAR_SEED)
        circ = _circular_shift_percentile(signal, target, N_CIRCULAR, CIRCULAR_SEED)

        print(f"\n--- {label} (n={n}) ---")
        print(f"  real r = {full['real_r']:+.4f} (p={full['real_p']:.4f})")
        print(f"  完全打散null: std={full['null_std']:.4f}  percentile={full['percentile']:.1f}")
        print(f"  circular-shift null: std={circ['null_std']:.4f}  percentile={circ['percentile']:.1f}")
        print(f"  差距(完全打散 - circular_shift): {full['percentile'] - circ['percentile']:+.1f}個百分點")

        rows.append({
            "label": label, "n": n, "real_r": full["real_r"], "real_p": full["real_p"],
            "full_shuffle_percentile": full["percentile"], "full_shuffle_null_std": full["null_std"],
            "circular_shift_percentile": circ["percentile"], "circular_shift_null_std": circ["null_std"],
        })

    result_df = pd.DataFrame(rows)
    result_df.to_csv("data/copper_gold_ratio_circular_shift_control_results.csv", index=False)

    print("\n=== 判讀 ===")
    val_row = result_df[result_df["label"] == "VAL"].iloc[0]
    train_row = result_df[result_df["label"] == "TRAIN"].iloc[0]
    gap_val = val_row["full_shuffle_percentile"] - val_row["circular_shift_percentile"]
    gap_train = train_row["full_shuffle_percentile"] - train_row["circular_shift_percentile"]
    print(f"VAL: 完全打散{val_row['full_shuffle_percentile']:.1f} vs circular-shift{val_row['circular_shift_percentile']:.1f}"
          f"（差距{gap_val:+.1f}）")
    print(f"TRAIN: 完全打散{train_row['full_shuffle_percentile']:.1f} vs circular-shift{train_row['circular_shift_percentile']:.1f}"
          f"（差距{gap_train:+.1f}）")
    if gap_val > 15 or gap_train > 15:
        print("判定：差距明顯（>15個百分點），支持「原本完全打散null低估自相關、"
              "copper_gold_ratio_gate的CHEAP_PASS顯著性有部分是假顯著」——"
              "需要下修判定，不能直接視為穩健候選進入deep dive")
    else:
        print("判定：差距不明顯（<=15個百分點），circular-shift null跟完全打散null接近，"
              "CHEAP_PASS判定的顯著性不是自相關假象造成，維持有效")
    return result_df


if __name__ == "__main__":
    main()
