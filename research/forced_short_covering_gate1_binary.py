"""`HYPOTHESIS_QUEUE.md` #51 子事件1（融券強制回補）第1關cheap gate —— 二元規格對照。

**背景（`TW_MARATHON_STATE.md`第422輪「下一輪TW軌接手(i)」）**：`forced_short_covering_gate1.py`
用連續比例規格（`short_ratio = ShortSaleTodayBalance/ShortSaleLimit`）測Spearman IC，
FAIL（TRAIN IC=+0.0192、VAL IC=-0.0373，正負號不一致，null percentile=19.0）。該輪誠實
揭露：82.2%事件`short_ratio`為零，樣本高度右偏，連續規格對這種質量分布未必合適。
本輪測**二元規格**：有無融券部位（`short_ratio>0` vs `short_ratio==0`）比較窗口內
mean CAR，這是原本就列在round422待辦清單的獨立對照，非重測——連續IC假設「越大越好」
的線性關係，二元規格只問「有沒有」這個更寬鬆的問題，對右偏樣本更合適的統計形狀。

**沿用**：事件定義、窗口反推公式、宇宙、股價/股利/融券資料存取，全部原樣import自
`forced_short_covering_gate1.py`（同一批已通過本機快取的FinMind資料，零新增API呼叫）。

**判準（比照`buyback_car_gate.py`同一種事件研究框架，改成兩組均值差）**：
VAL期把`short_ratio>0`組跟`==0`組的mean CAR相減，跟`N_PERMUTATIONS`次組別標籤洗牌
的null分布比較，percentile>=90.0（alpha=0.10單邊）才算贏過隨機控制組；事前綁定方向
為正（有融券部位組的mean CAR應高於無部位組，因為只有前者存在強制回補買盤）。

2026-09-07 馬拉松第426輪(TW軌)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from forced_short_covering_gate1 import (
    _car_for,
    _dividend_events,
    _market_map,
    _short_ratio_as_of,
    _short_ratio_series,
    _stock_price_map,
    _stop_transfer_and_window,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import holdout

N_PERMUTATIONS = 200
PERM_SEED = 20260907
BASE_ALPHA = 0.10
MIN_EVENTS_PER_GROUP = 15


def build_events() -> pd.DataFrame:
    universe = sample_universe_ids(SAMPLE_SIZE)
    mkt = _market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}

    rows = []
    for sid in universe:
        pm = _stock_price_map(sid)
        if pm is None:
            continue
        ex_dates = _dividend_events(sid)
        if not ex_dates:
            continue
        short_df = _short_ratio_series(sid)
        dates = pm["dates"]
        for ex_date in ex_dates:
            win = _stop_transfer_and_window(dates, ex_date)
            if win is None:
                continue
            i0, i1 = win
            short_ratio = _short_ratio_as_of(short_df, dates[i0])
            if short_ratio is None:
                continue
            car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt["close"], i0, i1)
            if car is None:
                continue
            rows.append({
                "stock_id": sid, "ex_date": ex_date,
                "window_start": dates[i0], "window_end": dates[i1],
                "short_ratio": short_ratio, "car": car,
                "has_short": short_ratio > 0,
            })
    return pd.DataFrame(rows)


def _group_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    return {
        "label": label, "n": n,
        "mean_car": float(df["car"].mean()) if n else float("nan"),
    }


def main():
    print("=== 假設#51子事件1(融券強制回補) 二元規格對照 (short_ratio>0 vs ==0) ===")
    ev = build_events()
    if ev.empty:
        print("SANITY FAIL: 零事件可用。")
        return {"passes": False, "reason": "no_events"}

    holdout.assert_no_holdout_leakage(ev, date_col="window_end", context="forced_short_covering_gate1_binary events")
    print(f"事件總數={len(ev)}, share_has_short={ev['has_short'].mean():.1%}")

    train = holdout.cap_to_train(ev, date_col="window_end")
    val = holdout.validation_slice(ev, date_col="window_end")

    for name, part in (("TRAIN", train), ("VAL", val)):
        g1 = part[part["has_short"]]
        g0 = part[~part["has_short"]]
        s1 = _group_stats(g1, f"{name} has_short")
        s0 = _group_stats(g0, f"{name} no_short")
        diff = s1["mean_car"] - s0["mean_car"] if s1["n"] and s0["n"] else float("nan")
        print(f"{name}: has_short n={s1['n']} mean_car={s1['mean_car']:+.5f} | "
              f"no_short n={s0['n']} mean_car={s0['mean_car']:+.5f} | diff={diff:+.5f}")

    val_g1 = val[val["has_short"]]
    val_g0 = val[~val["has_short"]]
    val_s1 = _group_stats(val_g1, "VAL has_short")
    val_s0 = _group_stats(val_g0, "VAL no_short")
    train_g1 = train[train["has_short"]]
    train_g0 = train[~train["has_short"]]
    train_diff = (
        train_g1["car"].mean() - train_g0["car"].mean()
        if len(train_g1) and len(train_g0) else float("nan")
    )
    val_diff = (
        val_s1["mean_car"] - val_s0["mean_car"]
        if val_s1["n"] and val_s0["n"] else float("nan")
    )

    same_sign = (
        not pd.isna(train_diff) and not pd.isna(val_diff)
        and np.sign(train_diff) == np.sign(val_diff) and train_diff != 0
    )

    rng = np.random.RandomState(PERM_SEED)
    val_has_short = val["has_short"].to_numpy()
    val_car = val["car"].to_numpy()
    perm_diffs = []
    if val_s1["n"] >= MIN_EVENTS_PER_GROUP and val_s0["n"] >= MIN_EVENTS_PER_GROUP:
        for _ in range(N_PERMUTATIONS):
            shuffled = rng.permutation(val_has_short)
            d = val_car[shuffled].mean() - val_car[~shuffled].mean()
            perm_diffs.append(float(d))
    perm_diffs = np.array(perm_diffs)

    if len(perm_diffs) > 0 and not pd.isna(val_diff):
        null_pct = 100.0 * float(np.mean(perm_diffs <= val_diff))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA)

    print(f"\nVAL diff(mean_CAR has_short - no_short)={val_diff:+.5f} vs "
          f"{len(perm_diffs)}次組別標籤洗牌控制組 percentile={null_pct:.1f}（需要>={required_pct:.1f}）")
    print(f"same_sign(TRAIN/VAL diff)={same_sign}")

    reasons = []
    if val_s1["n"] < MIN_EVENTS_PER_GROUP or val_s0["n"] < MIN_EVENTS_PER_GROUP:
        reasons.append(f"VAL任一組樣本數過少 (has_short_n={val_s1['n']}, no_short_n={val_s0['n']})")
    if not same_sign:
        reasons.append("train/val diff正負號不一致")
    if pd.isna(val_diff) or val_diff <= 0:
        reasons.append("VAL期diff非正（事前綁定方向為正：有融券部位組mean_CAR應高於無部位組）")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")

    passes = len(reasons) == 0
    print(f"\n=== CHEAP GATE (二元規格) {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    return {
        "passes": passes, "reasons": reasons,
        "val_has_short": val_s1, "val_no_short": val_s0,
        "val_diff": val_diff, "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign, "n_events_usable": len(ev),
    }


if __name__ == "__main__":
    main()
