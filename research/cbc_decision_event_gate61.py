"""`HYPOTHESIS_QUEUE.md` #61 央行理監事會議決策事件 — 子測試1第1關cheap gate
（事件研究，TAIEX大盤層級，非個股；決策公布日本身，不分方向）。

經濟理由/完整假設定義見`HYPOTHESIS_QUEUE.md` #61條目。事件日資料源見
`cbc_policy_decision_data.py`（既有手刻常數表，人工核對官方頁面）——本輪用
`CBC_ALL_MEETING_DATES_BY_YEAR`（含持平會議），依`hypothesis_queue`已寫死
的fallback，僅涵蓋2018-2024（2015-2017三年官方頁面查證三管道皆已窮盡失敗，
見該檔docstring與`HYPOTHESIS_QUEUE.md` #61條目最新段落），**本結果非完整
涵蓋2015-2020，TRAIN樣本量小於本佇列其他假設慣用的2015起完整窗口**，
不得隱藏此限制。

**事前綁定（本輪執行前寫死，不得看到結果後調整）**：
- 決策公布日本身這一天大盤報酬（前一交易日收盤→決策日收盤），沿用#60的
  post_ret定義但窗口固定為1（POST_WINDOW=1），不測pre窗口——子測試1的假設
  本來就只問「決策公布這天」，不是到期前後這種雙向機制。
- 判準沿用本佇列既有事件研究框架（`fut_settlement_event_gate60.py`同款）：
  VAL期真實mean_ret的|值| vs 隨機非決策日窗口（count-matched，同期間內抽樣）
  null分布的雙尾百分位>=90.0，且TRAIN/VAL同號，standalone測試bonferroni_n=1。
- 大盤層級事件（非個股橫斷面），沒有個股維度的隨機控制組可抽，改用「隨機挑
  非決策週的交易日」當控制組，窗口數與真實事件數在該期間內count-matched。

2026-09-08 馬拉松第457輪(TW)接續`hypothesis_queue`已完成的#61子測試1資料
可行性查證與fallback決策，從第1關cheap gate開始，不跳關。
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
from cbc_policy_decision_data import get_all_meeting_dates, MISSING_MEETING_YEARS

START_DATE = "2010-01-01"  # 跟fut_settlement_event_gate60.py同一個值，提高快取命中率
EVENT_SAMPLE_START = "2018-01-01"  # fallback：2015-2017查無官方頁面，見上方docstring
POST_WINDOW = 1
N_PERMUTATIONS = 500
PERM_SEED = 20260908
BASE_ALPHA = 0.10
BONFERRONI_N = 1  # standalone測試


def _market_series() -> dict:
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="market_raw in cbc_decision_event_gate61")
    m = raw.sort_values("date").reset_index(drop=True)
    return {
        "dates": m["date"].tolist(),
        "close": m["close"].astype(float).to_numpy(),
        "date_to_idx": {d: i for i, d in enumerate(m["date"].tolist())},
    }


def _event_rets(mkt: dict, decision_dates: list[str]) -> pd.DataFrame:
    """每個決策公布日的event_ret（前一交易日收盤→決策日收盤）；決策日必須確實
    存在於TAIEX交易日序列中，不在的（例如遇假日順延，理論上官方公布日應為
    交易日）直接丟棄並列印警告。"""
    dates, close, date_to_idx = mkt["dates"], mkt["close"], mkt["date_to_idx"]
    rows = []
    dropped = 0
    for dd in decision_dates:
        idx_t = date_to_idx.get(dd)
        if idx_t is None:
            dropped += 1
            continue
        idx_prev = idx_t - 1
        idx_post_end = idx_t - 1 + POST_WINDOW
        if idx_prev < 0 or idx_post_end >= len(dates):
            continue
        p0, p1 = close[idx_prev], close[idx_post_end]
        if any(pd.isna(x) or x <= 0 for x in (p0, p1)):
            continue
        rows.append({"decision_date": dd, "event_ret": p1 / p0 - 1})
    if dropped:
        print(f"  警告：{dropped}個決策日不在TAIEX交易日序列中（需查證是否為假日順延問題）")
    return pd.DataFrame(rows)


def _period_stats(df: pd.DataFrame, col: str, label: str) -> dict:
    n = len(df)
    if n < 5:
        return {"label": label, "n": n, "mean": float("nan"), "p_ttest": float("nan")}
    vals = df[col].to_numpy()
    p = float(ttest_1samp(vals, 0.0).pvalue)
    return {"label": label, "n": n, "mean": float(np.mean(vals)), "p_ttest": p}


def _random_window_null(mkt: dict, real_period_start: str, real_period_end: str,
                         n_events: int, n_perm: int, seed: int) -> np.ndarray:
    """在[real_period_start, real_period_end]期間內，隨機抽n_events個交易日當偽事件日，
    重算同樣定義的event_ret，重複n_perm次，回傳每次的mean。"""
    dates, close, date_to_idx = mkt["dates"], mkt["close"], mkt["date_to_idx"]
    valid_idx = [i for i, d in enumerate(dates) if real_period_start <= d <= real_period_end]
    lo_margin = 1
    hi_margin = POST_WINDOW - 1
    valid_idx = [i for i in valid_idx if i - lo_margin >= 0 and i + hi_margin < len(dates)]
    if len(valid_idx) < n_events:
        return np.array([])
    rng = np.random.RandomState(seed)
    perm_means = []
    for _ in range(n_perm):
        picks = rng.choice(valid_idx, size=n_events, replace=False)
        vals = []
        for idx_t in picks:
            p0, p1 = close[idx_t - 1], close[idx_t - 1 + POST_WINDOW]
            if p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
                vals.append(p1 / p0 - 1)
        if vals:
            perm_means.append(float(np.mean(vals)))
    return np.array(perm_means)


def _evaluate(mkt: dict, train: pd.DataFrame, val: pd.DataFrame) -> dict:
    train_stats = _period_stats(train, "event_ret", "TRAIN")
    val_stats = _period_stats(val, "event_ret", "VAL")
    print(f"\n[決策日本身報酬] TRAIN mean={train_stats['mean']:+.4%} "
          f"(p={train_stats['p_ttest']:.4f}, n={train_stats['n']})")
    print(f"[決策日本身報酬] VAL   mean={val_stats['mean']:+.4%} "
          f"(p={val_stats['p_ttest']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["mean"]) and not pd.isna(val_stats["mean"])
        and np.sign(train_stats["mean"]) == np.sign(val_stats["mean"]) and train_stats["mean"] != 0
    )

    perm_means = _random_window_null(
        mkt, holdout.TRAIN_END, holdout.VAL_END, val_stats["n"], N_PERMUTATIONS, PERM_SEED,
    )
    real_val_mean = val_stats["mean"]
    if len(perm_means) > 0 and not pd.isna(real_val_mean):
        null_pct = 100.0 * float(np.mean(np.abs(perm_means) <= abs(real_val_mean)))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"[決策日本身報酬] VAL |mean|={abs(real_val_mean):.4%} vs {len(perm_means)}次隨機交易日null "
          f"雙尾percentile={null_pct:.1f} (需要>={required_pct:.1f}), same_sign={same_sign}")

    reasons = []
    if train_stats["n"] < 10 or val_stats["n"] < 10:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})，"
                        f"已知限制：2015-2017會議日期缺失（見{MISSING_MEETING_YEARS}）")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    passes = len(reasons) == 0
    print(f"[決策日本身報酬] {'CHEAP_PASS' if passes else 'FAIL'}" + (f"  reasons: {reasons}" if reasons else ""))
    return {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct, "same_sign": same_sign,
    }


def main():
    decision_dates = get_all_meeting_dates(start=EVENT_SAMPLE_START, end="2024-12-31")
    mkt = _market_series()
    print("=== 假設#61 央行理監事會議決策事件 子測試1(決策日本身,不分方向) 第1關cheap gate "
          f"(standalone bonferroni_n={BONFERRONI_N}) ===")
    print(f"**已知限制**：fallback樣本僅涵蓋{EVENT_SAMPLE_START}起（2015-2017官方會議日期"
          f"三管道查證皆已窮盡失敗，缺{MISSING_MEETING_YEARS}三年12場會議），"
          f"非完整涵蓋2015-2020，TRAIN樣本少於本佇列其他假設慣用的窗口。")
    print(f"決策日（含持平）共{len(decision_dates)}場（{EVENT_SAMPLE_START}~2024-12），"
          f"POST_WINDOW={POST_WINDOW}交易日")

    events = _event_rets(mkt, decision_dates)
    holdout.assert_no_holdout_leakage(events, date_col="decision_date",
                                       context="cbc_decision_event_gate61 events (final)")
    print(f"\n可用事件數={len(events)}（原始{len(decision_dates)}場會議）")

    train = holdout.cap_to_train(events, date_col="decision_date")
    val = holdout.validation_slice(events, date_col="decision_date")
    print(f"TRAIN: {len(train)}場會議事件 | VAL: {len(val)}場會議事件")

    if len(train) < 5 or len(val) < 5:
        print("SANITY FAIL: TRAIN或VAL事件數過少，無法做cheap gate測試。")
        return {"passes": False, "reason": "insufficient_train_val_events", "n_events": len(events)}

    result = _evaluate(mkt, train, val)
    return {
        "n_events": len(events), "n_train": len(train), "n_val": len(val),
        "subtest1_gate": result,
    }


if __name__ == "__main__":
    main()
