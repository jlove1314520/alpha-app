"""共用工具：月頻regime/timing類cheap gate的「不重疊觀測對齊」與
「circular shift虛無分布」，供`cbi_signal_gate.py`(#81)與後續
`#76~#80`同款月頻macro訊號gate重用（`PENDING_QUEUE.md`驗.三，
2026-09-23）。

**修正的問題**：舊版做法（`cbi_signal_gate.py`修正前、`dgbas_unemployment_
gate.py`／`margin_debt_level_gate.py`等既有gate檔案的現行做法）是把
月頻訊號用`merge_asof(direction="backward")`貼到「每一個交易日」，
導致：
1. 同一個月的訊號值被重複貼到約20個交易日上，這些交易日各自算出的
   M=20日前瞻報酬視窗又高度重疊（相鄰交易日的M=20報酬視窗重疊19/20），
   實際獨立資訊量遠小於表面上的n（例如n=6724天但真正獨立的月頻訊號
   只有約280個）。
2. 虛無分布用逐點`rng.permutation(signal)`打散，這對高度序列自相關的
   月頻macro訊號（例如景氣對策信號本身月對月變化平緩）不是保守的虛無
   假設——逐點打散會把訊號自身的自相關結構完全破壞掉，讓虛無分布的
   離散度被低估、真實訊號看起來比實際上更容易「贏過」虛無分布。

**修正做法**：
1. `align_monthly_nonoverlap()`：訊號發布後第一個交易日進場，下一次
   發布前（即下一次發布的進場日）出場，逐次訊號只產生一筆不重疊觀測，
   n等於實際訊號發布次數，不是交易日數。
2. `circular_shift_null()`：虛無分布改用circular shift（把訊號序列
   整體平移隨機期數，保留訊號自身的序列相關結構，只打散訊號與目標的
   對齊關係），比逐點打散更保守、更不容易產生假陽性。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def align_monthly_nonoverlap(signal_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """月頻訊號 x 日頻價格 -> 不重疊觀測對齊。

    signal_df: columns=[available_date(可市場得知日), score]，已排序。
    price_df: columns=[date, close]，已排序、去重、無缺值。

    每一筆訊號i的觀測窗口＝[進場日_i, 進場日_{i+1})，進場日_i＝該訊號
    available_date之後第一個交易日（嚴格晚於，不含當天，因為
    available_date本身是「該資訊已可被市場消化」的日期，交易在隔天
    才反映）。最後一筆訊號因為沒有下一筆界定出場日，捨棄（不臆測未來）。

    回傳 columns=[entry_date, exit_date, score, fwd_ret]，每一列彼此
    時間區間不重疊。
    """
    dates = price_df["date"].to_numpy()
    closes = price_df["close"].to_numpy()

    entry_idxs = []
    for adate in signal_df["available_date"].to_numpy():
        idx = int(np.searchsorted(dates, adate, side="right"))
        entry_idxs.append(idx if idx < len(dates) else None)

    rows = []
    scores = signal_df["score"].to_numpy()
    for i in range(len(entry_idxs) - 1):
        e_idx = entry_idxs[i]
        x_idx = entry_idxs[i + 1]
        if e_idx is None or x_idx is None or x_idx <= e_idx:
            continue
        fwd_ret = float(closes[x_idx] / closes[e_idx] - 1.0)
        rows.append({
            "entry_date": dates[e_idx], "exit_date": dates[x_idx],
            "score": float(scores[i]), "fwd_ret": fwd_ret,
        })
    return pd.DataFrame(rows)


def sample_nonoverlapping_blocks(df: pd.DataFrame, date_col: str, signal_col: str,
                                  target_col: str, m: int) -> pd.DataFrame:
    """日頻訊號(非月頻訊號)版本的不重疊觀測抽樣（`PENDING_QUEUE.md`常備.12，
    `## #81`結案段落原文：「#76/#78不是月頻訊號的問題，需要另外設計M日
    不重疊區塊抽樣＋circular shift的變體，下一輪不可直接套用
    `align_monthly_nonoverlap()`」——那支函式假設輸入是「訊號發布日」這種
    離散事件序列，VIX/HYG-IEF比值是每個交易日都有值的連續日頻序列，兩者
    需要不同的降採樣邏輯）。

    做法：df已按date_col排序、每列已算好m日前瞻報酬(target_col，逐日重疊
    版本)，這裡只取索引0, m, 2m, 3m, ...的列，讓相鄰兩筆觀測的m日前瞻視窗
    彼此不重疊（索引0的視窗是[0,m)，索引m的視窗是[m,2m)，緊接不重疊）。
    n從原本的逐日筆數降到約 原始筆數/m，是真正獨立的觀測數。
    """
    df = df.sort_values(date_col).reset_index(drop=True)
    idx = list(range(0, len(df), m))
    return df.iloc[idx][[date_col, signal_col, target_col]].reset_index(drop=True)


def circular_shift_null(signal: np.ndarray, target: np.ndarray, n: int, seed: int) -> dict:
    """circular shift虛無分布：保留訊號自身序列相關結構，只打散訊號與
    目標的對齊關係。shift量從1到len-1隨機抽（排除0＝不打散的恆等位移）。
    """
    real_pearson, real_p = stats.pearsonr(signal, target)
    m = len(signal)
    if m < 3:
        return {"pearson": float(real_pearson), "pearson_p": float(real_p),
                "null_median_abs": float("nan"), "percentile": float("nan"),
                "n_shuffle": 0, "note": "n<3, circular shift無法產生有意義的虛無分布"}
    rng = np.random.default_rng(seed)
    shifts = rng.integers(1, m, size=n)
    shuffled = np.empty(n)
    for i, s in enumerate(shifts):
        shuffled[i] = stats.pearsonr(np.roll(signal, int(s)), target)[0]
    pctl = 100.0 * float(np.mean(np.abs(shuffled) <= abs(real_pearson)))
    return {"pearson": float(real_pearson), "pearson_p": float(real_p),
            "null_median_abs": float(np.median(np.abs(shuffled))), "percentile": pctl,
            "n_shuffle": n}
