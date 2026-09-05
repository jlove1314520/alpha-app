"""`margin_debt_level_v1`（`TRIALS_LEDGER.md`#140/#141/#142）第2關深挖之一：
更嚴謹的隨機控制組——**區塊/循環位移（circular shift）版**，取代原本
`margin_debt_growth_gate.py::_shuffle_percentile()`的「完全打散配對」版本。

**為什麼需要這個、跟round379已完成的查證有什麼不同**：round379查證了「VAL期
corr是否由單一年份/單一回撤事件驅動」（leave-one-year-out），結論是否——四年
各自同號、拿掉任一年仍不變號。但round379/377/375都还沒處理過另一個獨立疑慮：
`level_pct`（trailing 156週百分位排名）本身**變動極慢、自我相關性極強**（連續
幾週的值幾乎不變），`fwd_mdd_abs`（重疊horizon窗口的滾動最大回撤）同樣高度
自相關。原本的洗牌置換檢定（`_shuffle_percentile`，完全隨機打散配對）在虛無
假設下把每個觀測點視為獨立同分布，**沒有保留任一序列自身的自相關結構**——
這樣算出來的null分布變異數可能被低估（因為打散後產生的假相關比真實自相關
序列間可能出現的假相關更小），導致真實corr的百分位被高估（看起來比實際上
更顯著）。這正是round379保留的「TRAIN弱、VAL特別強」形狀的一個可能技術性
解釋（尚未驗證），值得專門查證，不是重複round379已做過的年份查證。

**方法（區塊位移/circular shift）**：對`level_pct`序列做**循環位移**（挑一個
隨機位移量k∈[1, n-1]，`np.roll(level_pct, k)`），`fwd_mdd_abs`維持原始順序
不動。這保留了`level_pct`自身的完整自相關結構（只是相位平移），也保留
`fwd_mdd_abs`自身的自相關結構，**只破壞兩者之間的真實時間對齊**——這才是
正確的虛無假設（"兩個各自有自相關的序列剛好對齊出這個相關係數的機率有多
高"），比完全打散配對更保守、更貼近這筆資料的實際生成過程。

**事前綁定（寫在執行之前）**：只測60d(12w)窗口（20d已在round375明確FAIL，
不重複測）；TRAIN、VAL各自獨立做circular shift（位移量從各自期間內部
[1, n-1]均勻抽樣，不跨期間位移，避免引入期間邊界的人工結構）；N=500次
（<1000，不觸發`CLAUDE.md`「1000 draws規模投入」停下條件）；判準沿用
既有慣例：percentile = 100*mean(shuffled_corr <= real_corr)（單邊，越大
代表真實corr比越多的null更極端）。**若circular-shift null下的百分位遠低於
原本完全打散null的百分位（例如VAL從100.0掉到90左右甚至更低），代表原本的
顯著性有一部分（不一定全部）是自相關結構造成的假顯著；若兩者接近，代表
自相關不是主要解釋，round379保留的疑慮①仍待其他角度查證。**

零新增API呼叫，完全重用`margin_debt_level_gate.py`/`margin_debt_growth_gate.py`
既有函式與`backfill_margin_debt_market.py`662週檔快取。

2026-09-05 馬拉松第380輪（TW軌）新增，接續round379下一步(b)
「隨機控制組≥100 draws獨立版本」，用circular-shift取代單純擴大N的排列檢定
（意義上比單純把N=200改成N≥100更貼近round379原話「非獨立抽樣控制組」的
真正缺口——缺口不是draws數量不夠多，是虛無假設本身沒有保留自相關結構）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from margin_debt_growth_gate import _forward_window_mdd, _load_taiex_daily
from margin_debt_level_gate import TRAILING_WEEKS, _build_pairs, _level_percentile
from margin_debt_growth_gate import _load_margin_series, _split

HORIZON_DAYS = 60
WINDOW_LABEL = "60d(12w)"
N_CIRCULAR = 500
CIRCULAR_SEED = 20260905


def _circular_shift_percentile(level_pct: np.ndarray, fwd_mdd_abs: np.ndarray, n: int, seed: int) -> dict:
    real_corr, real_p = spearmanr(level_pct, fwd_mdd_abs)
    rng = np.random.default_rng(seed)
    n_obs = len(level_pct)
    shuffled = np.empty(n)
    for i in range(n):
        k = int(rng.integers(1, n_obs))  # 1..n_obs-1，排除k=0(等於沒位移)
        shifted = np.roll(level_pct, k)
        shuffled[i], _ = spearmanr(shifted, fwd_mdd_abs)
    pctl = 100.0 * float(np.mean(shuffled <= real_corr))
    return {
        "real_corr": float(real_corr),
        "real_p": float(real_p),
        "null_median": float(np.median(shuffled)),
        "null_std": float(np.std(shuffled)),
        "percentile": pctl,
    }


def main():
    print("=== margin_debt_level_v1 第2關：circular-shift自相關保留版隨機控制組 ===")
    margin = _load_margin_series()
    margin["level_pct"] = _level_percentile(margin["balance"], TRAILING_WEEKS)
    taiex = _load_taiex_daily()

    pairs = _build_pairs(margin, taiex, HORIZON_DAYS, "level_pct")
    train, val = _split(pairs)
    print(f"config: window={WINDOW_LABEL} train_n={len(train)} val_n={len(val)} "
          f"N_CIRCULAR={N_CIRCULAR} seed={CIRCULAR_SEED}")

    rows = []
    for label, df in (("TRAIN", train), ("VAL", val)):
        level = df["level_pct"].to_numpy()
        fwd = df["fwd_mdd_abs"].to_numpy()
        n = len(df)

        # 對照：原本完全打散配對版本（同一份資料，供直接比較）
        rng_full = np.random.default_rng(CIRCULAR_SEED)
        full_shuffled = np.empty(N_CIRCULAR)
        for i in range(N_CIRCULAR):
            perm = rng_full.permutation(n)
            full_shuffled[i], _ = spearmanr(level, fwd[perm])
        real_corr, real_p = spearmanr(level, fwd)
        full_pctl = 100.0 * float(np.mean(full_shuffled <= real_corr))
        full_std = float(np.std(full_shuffled))

        circ = _circular_shift_percentile(level, fwd, N_CIRCULAR, CIRCULAR_SEED)

        print(f"\n--- {label} (n={n}) ---")
        print(f"  real corr = {real_corr:+.4f} (p={real_p:.4f})")
        print(f"  完全打散null: std={full_std:.4f}  percentile={full_pctl:.1f}")
        print(f"  circular-shift null: std={circ['null_std']:.4f}  percentile={circ['percentile']:.1f}")
        print(f"  差距(完全打散 - circular_shift): {full_pctl - circ['percentile']:+.1f}個百分點")

        rows.append({
            "label": label, "n": n, "real_corr": real_corr, "real_p": real_p,
            "full_shuffle_percentile": full_pctl, "full_shuffle_null_std": full_std,
            "circular_shift_percentile": circ["percentile"], "circular_shift_null_std": circ["null_std"],
        })

    result_df = pd.DataFrame(rows)
    result_df.to_csv("data/margin_debt_level_circular_shift_control_results.csv", index=False)

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
        print("判定：差距明顯（>15個百分點），支持「原本完全打散null低估自相關、原本顯著性有部分是假顯著」——"
              "疑慮①增加一個技術性解釋，margin_debt_level_v1需要更保守地重新評估")
    else:
        print("判定：差距不明顯（<=15個百分點），circular-shift null跟完全打散null接近，"
              "自相關結構不是造成原本顯著性的主要原因，疑慮①仍待其他角度查證")
    return result_df


if __name__ == "__main__":
    main()
