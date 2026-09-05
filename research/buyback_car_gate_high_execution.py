"""#40庫藏股買回公告效應 第1關cheap gate 執行率分組深挖（unconditional版percentile=
84.5未過90.0門檻但屬「勉強未過」而非「遠低於門檻」，依`HYPOTHESIS_QUEUE.md`#40
條目本身事前已寫明的「台股特有考量」深挖計畫——高/低執行率分組，區分真實信心
表態vs廉價訊號（cheap talk）——在判定最終FAIL前先測這個已預先寫好理由的變體，
不是看到FAIL後才臨時發明的新切法。

沿用`buyback_car_gate.py`全部函式（不重複造輪子），唯一差異：事件先依
`actual_pct_of_planned`（本次已買回股數佔預定買回股數比例）分成高執行率
（>=EXECUTION_THRESHOLD）跟低執行率兩組分別測CAR，事前綁定：僅高執行率組
才代表真實信心表態，若這組能過90.0門檻視為#40條件式版本CHEAP_PASS。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from buyback_car_gate import (
    BASE_ALPHA, BONFERRONI_N, FORWARD_HORIZON, N_PERMUTATIONS, PERM_SEED,
    _car_for, _entry_idx_after, _load_events_sample, _market_map, _period_stats,
    _stock_price_map,
)
from validation import holdout

EXECUTION_THRESHOLD = 80.0  # % 事前綁定門檻：>=80%視為「真的執行了」的高執行率組


def _null_percentile(price_cache, val_events_by_stock, mkt_date_idx, mkt_close, real_val_mean, rng):
    perm_means = []
    for _ in range(N_PERMUTATIONS):
        pseudo = []
        for sid, cnt in val_events_by_stock.items():
            pm = price_cache.get(sid)
            if pm is None:
                continue
            dates = pm["dates"]
            valid_idx = [i for i, d in enumerate(dates)
                         if holdout.TRAIN_END < d <= holdout.VAL_END and i + FORWARD_HORIZON < len(dates)]
            if not valid_idx:
                continue
            picks = rng.choice(valid_idx, size=min(cnt, len(valid_idx)), replace=False)
            for idx in picks:
                car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt_close, int(idx))
                if car is not None:
                    pseudo.append(car)
        if pseudo:
            perm_means.append(float(np.mean(pseudo)))
    perm_means = np.array(perm_means)
    if len(perm_means) > 0 and not pd.isna(real_val_mean):
        return 100.0 * float(np.mean(perm_means <= real_val_mean)), len(perm_means)
    return float("nan"), len(perm_means)


def main():
    events, sample_ids, n_all_ids = _load_events_sample()
    events = events.copy()
    events["exec_pct"] = pd.to_numeric(events["actual_pct_of_planned"], errors="coerce")

    mkt = _market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}
    price_cache = {}
    for sid in sample_ids:
        pm = _stock_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm

    def _build_car_table(sub_events):
        rows = []
        for sid, grp in sub_events.groupby("stock_id"):
            pm = price_cache.get(sid)
            if pm is None:
                continue
            for _, r in grp.iterrows():
                entry_idx = _entry_idx_after(pm["dates"], r["ad_date"])
                car = _car_for(pm["dates"], pm["adj_close"], mkt_date_idx, mkt["close"], entry_idx)
                if car is not None:
                    rows.append({"stock_id": sid, "entry_date": pm["dates"][entry_idx], "car": car})
        return pd.DataFrame(rows)

    for label, mask in [
        ("高執行率(>=80%)", events["exec_pct"] >= EXECUTION_THRESHOLD),
        ("低執行率(<80%)", events["exec_pct"] < EXECUTION_THRESHOLD),
    ]:
        sub = events[mask]
        ev = _build_car_table(sub)
        print(f"\n=== {label}：{len(sub)}筆公告 -> {len(ev)}筆可用事件 ===")
        if ev.empty:
            print("樣本過少，跳過")
            continue
        train = holdout.cap_to_train(ev, date_col="entry_date")
        val = holdout.validation_slice(ev, date_col="entry_date")
        train_stats = _period_stats(train, "TRAIN")
        val_stats = _period_stats(val, "VAL")
        print(f"TRAIN mean_CAR={train_stats['mean_car']:+.4f} (p={train_stats['p_ttest']:.4f}, n={train_stats['n']})")
        print(f"VAL   mean_CAR={val_stats['mean_car']:+.4f} (p={val_stats['p_ttest']:.4f}, n={val_stats['n']})")
        val_events_by_stock = val.groupby("stock_id").size().to_dict()
        rng = np.random.RandomState(PERM_SEED)
        null_pct, n_perm = _null_percentile(price_cache, val_events_by_stock, mkt_date_idx, mkt["close"],
                                             val_stats["mean_car"], rng)
        required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
        same_sign = (not pd.isna(train_stats["mean_car"]) and not pd.isna(val_stats["mean_car"])
                     and np.sign(train_stats["mean_car"]) == np.sign(val_stats["mean_car"]))
        print(f"VAL null percentile={null_pct:.1f}（需要>={required_pct:.1f}, n_perm={n_perm}）, same_sign={same_sign}")
        passes = (train_stats["n"] >= 30 and val_stats["n"] >= 30 and same_sign
                  and not pd.isna(val_stats["mean_car"]) and val_stats["mean_car"] > 0
                  and not pd.isna(null_pct) and null_pct >= required_pct)
        print(f"{label} GATE {'PASS' if passes else 'FAIL'}")


if __name__ == "__main__":
    main()
