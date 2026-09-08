"""`HYPOTHESIS_QUEUE.md` #60 台指選擇權/期貨結算到期日機械性效應：第1關cheap gate
（事件研究，TAIEX大盤層級，非個股）。

經濟理由/完整假設定義見`HYPOTHESIS_QUEUE.md` #60條目。事件日資料源見
`fut_settlement_date_probe60.py`（既有反推歷史結算日，本腳本直接讀其產出的
`data/fut_settlement_dates_derived_tx.csv`，不重新反推）。

**事前綁定（本輪執行前寫死，不得看到結果後調整）**：
- PRE_WINDOW=3、POST_WINDOW=1（結算日前3個交易日的累積報酬 vs 結算日當日報酬），
  這是`HYPOTHESIS_QUEUE.md` #60條目「N=3、M=1~3」範圍裡最保守的一組初始猜測；
  若第1關過關，第3關參數高原務必掃描完整N/M網格，不能只驗證這一點。
- 兩個獨立子測試，各自PASS/FAIL，兩者皆非最終判定：
  (a) 結算日前PRE_WINDOW個交易日大盤報酬（測試「到期前有方向性壓力」）
  (b) 結算日當日/後POST_WINDOW個交易日大盤報酬（測試「到期後部位鬆綁反轉」）
- 判準沿用本佇列既有事件研究框架（`buyback_car_gate.py`#40同款）：VAL期真實
  mean_ret的|值| vs 隨機非結算日窗口（count-matched）null分布的雙尾百分位
  >=90.0，且TRAIN/VAL同號，standalone測試bonferroni_n=1。
- 大盤層級事件（非個股橫斷面），沒有個股維度的隨機控制組可抽，改用「隨機挑
  非結算週的交易日窗口」當控制組，窗口數與真實事件數在該期間內count-matched。

2026-09-08 馬拉松第453輪(TW)接續`hypothesis_queue`已完成的#60資料可行性查證，
從第1關cheap gate開始，不跳關。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp

from finmind_client import load_dev
from validation import holdout

SETTLEMENT_CSV = "data/fut_settlement_dates_derived_tx.csv"
START_DATE = "2010-01-01"  # 跟factor_ic.py/buyback_car_gate.py同一個值，提高快取命中率
PRE_WINDOW = 3
POST_WINDOW = 1
N_PERMUTATIONS = 500
PERM_SEED = 20260908
BASE_ALPHA = 0.10
BONFERRONI_N = 1  # standalone測試


def _market_series() -> dict:
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="market_raw in fut_settlement_event_gate60")
    m = raw.sort_values("date").reset_index(drop=True)
    return {
        "dates": m["date"].tolist(),
        "close": m["close"].astype(float).to_numpy(),
        "date_to_idx": {d: i for i, d in enumerate(m["date"].tolist())},
    }


def _load_settlement_dates() -> list[str]:
    df = pd.read_csv(SETTLEMENT_CSV)
    return sorted(df["settlement_date"].astype(str).tolist())


def _event_rets(mkt: dict, settlement_dates: list[str]) -> pd.DataFrame:
    """每個結算日的pre_ret/post_ret；結算日必須確實存在於TAIEX交易日序列中，
    不在的（理論上不應發生，TAIFEX跟TWSE共用交易日曆）直接丟棄並列印警告。"""
    dates, close, date_to_idx = mkt["dates"], mkt["close"], mkt["date_to_idx"]
    rows = []
    dropped = 0
    for sd in settlement_dates:
        idx_t = date_to_idx.get(sd)
        if idx_t is None:
            dropped += 1
            continue
        idx_pre_start = idx_t - 1 - PRE_WINDOW
        idx_pre_end = idx_t - 1
        idx_post_end = idx_t - 1 + POST_WINDOW
        if idx_pre_start < 0 or idx_post_end >= len(dates):
            continue
        p_pre0, p_pre1 = close[idx_pre_start], close[idx_pre_end]
        p_post0, p_post1 = close[idx_pre_end], close[idx_post_end]
        if any(pd.isna(x) or x <= 0 for x in (p_pre0, p_pre1, p_post0, p_post1)):
            continue
        rows.append({
            "settlement_date": sd,
            "pre_ret": p_pre1 / p_pre0 - 1,
            "post_ret": p_post1 / p_post0 - 1,
        })
    if dropped:
        print(f"  警告：{dropped}個結算日不在TAIEX交易日序列中（理論上應為0，需查證）")
    return pd.DataFrame(rows)


def _period_stats(df: pd.DataFrame, col: str, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "mean": float("nan"), "p_ttest": float("nan")}
    vals = df[col].to_numpy()
    p = float(ttest_1samp(vals, 0.0).pvalue)
    return {"label": label, "n": n, "mean": float(np.mean(vals)), "p_ttest": p}


def _random_window_null(mkt: dict, col_window: int, real_period_start: str, real_period_end: str,
                         n_events: int, is_pre: bool, n_perm: int, seed: int) -> np.ndarray:
    """在[real_period_start, real_period_end]期間內，隨機抽n_events個交易日當偽事件日，
    重算同樣定義的窗口報酬，重複n_perm次，回傳每次的mean。"""
    dates, close, date_to_idx = mkt["dates"], mkt["close"], mkt["date_to_idx"]
    valid_idx = [i for i, d in enumerate(dates) if real_period_start <= d <= real_period_end]
    # 排除窗口會跨出陣列邊界的位置
    lo_margin = PRE_WINDOW + 1
    hi_margin = POST_WINDOW
    valid_idx = [i for i in valid_idx if i - lo_margin >= 0 and i + hi_margin < len(dates)]
    if len(valid_idx) < n_events:
        return np.array([])
    rng = np.random.RandomState(seed)
    perm_means = []
    for _ in range(n_perm):
        picks = rng.choice(valid_idx, size=n_events, replace=False)
        vals = []
        for idx_t in picks:
            if is_pre:
                p0, p1 = close[idx_t - 1 - PRE_WINDOW], close[idx_t - 1]
            else:
                p0, p1 = close[idx_t - 1], close[idx_t - 1 + POST_WINDOW]
            if p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
                vals.append(p1 / p0 - 1)
        if vals:
            perm_means.append(float(np.mean(vals)))
    return np.array(perm_means)


def _evaluate(mkt: dict, train: pd.DataFrame, val: pd.DataFrame, col: str, is_pre: bool, label: str) -> dict:
    train_stats = _period_stats(train, col, "TRAIN")
    val_stats = _period_stats(val, col, "VAL")
    print(f"\n[{label}] TRAIN mean={train_stats['mean']:+.4%} (p={train_stats['p_ttest']:.4f}, n={train_stats['n']})")
    print(f"[{label}] VAL   mean={val_stats['mean']:+.4%} (p={val_stats['p_ttest']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["mean"]) and not pd.isna(val_stats["mean"])
        and np.sign(train_stats["mean"]) == np.sign(val_stats["mean"]) and train_stats["mean"] != 0
    )

    perm_means = _random_window_null(
        mkt, PRE_WINDOW if is_pre else POST_WINDOW,
        holdout.TRAIN_END, holdout.VAL_END,
        val_stats["n"], is_pre, N_PERMUTATIONS, PERM_SEED,
    )
    real_val_mean = val_stats["mean"]
    if len(perm_means) > 0 and not pd.isna(real_val_mean):
        null_pct = 100.0 * float(np.mean(np.abs(perm_means) <= abs(real_val_mean)))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"[{label}] VAL |mean|={abs(real_val_mean):.4%} vs {len(perm_means)}次隨機窗口null "
          f"雙尾percentile={null_pct:.1f} (需要>={required_pct:.1f}), same_sign={same_sign}")

    reasons = []
    if train_stats["n"] < 30 or val_stats["n"] < 30:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    passes = len(reasons) == 0
    print(f"[{label}] {'CHEAP_PASS' if passes else 'FAIL'}" + (f"  reasons: {reasons}" if reasons else ""))
    return {
        "label": label, "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct, "same_sign": same_sign,
    }


def main():
    settlement_dates = _load_settlement_dates()
    mkt = _market_series()
    print("=== 假設#60 台指結算到期日機械性效應 第1關cheap gate "
          f"(standalone bonferroni_n={BONFERRONI_N}) ===")
    print(f"歷史結算日共{len(settlement_dates)}個（2000-01~2024-12），"
          f"PRE_WINDOW={PRE_WINDOW}交易日, POST_WINDOW={POST_WINDOW}交易日")

    events = _event_rets(mkt, settlement_dates)
    holdout.assert_no_holdout_leakage(events, date_col="settlement_date",
                                       context="fut_settlement_event_gate60 events (final)")
    print(f"\n可用事件數={len(events)}（原始{len(settlement_dates)}個結算日）")

    train = holdout.cap_to_train(events, date_col="settlement_date")
    val = holdout.validation_slice(events, date_col="settlement_date")
    print(f"TRAIN: {len(train)}個結算事件 | VAL: {len(val)}個結算事件")

    if len(train) < 10 or len(val) < 10:
        print("SANITY FAIL: TRAIN或VAL事件數過少，無法做cheap gate測試。")
        return {"passes": False, "reason": "insufficient_train_val_events", "n_events": len(events)}

    pre_result = _evaluate(mkt, train, val, "pre_ret", True, "結算前3日報酬(到期前壓力)")
    post_result = _evaluate(mkt, train, val, "post_ret", False, "結算當日報酬(到期後鬆綁)")

    return {
        "n_events": len(events), "n_train": len(train), "n_val": len(val),
        "pre_gate": pre_result, "post_gate": post_result,
    }


if __name__ == "__main__":
    main()
