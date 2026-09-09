"""`HYPOTHESIS_QUEUE.md` #63 借券費率異常飆升 — 第2關深挖第1步：Z_THRESH參數高原檢定。

背景：`lending_fee_gate63.py`用事前綁定`Z_THRESH=2.0`跑出N=5/10/20三個N值全部
`CHEAP_PASS`（`TRIALS_LEDGER.md`#225）。依`CLAUDE.md`研究紀律「參數高原：±30%一整片
都好」，本腳本檢驗這個結果是不是剛好卡在2.0這一個點上的巧合，而是一整片閾值都穩健。

**事前綁定規格（跑數字前定案，不得事後調整）**：

1. **測試閾值集合**：{1.5, 2.0, 2.5, 3.0}。2.0的±30%落在[1.4, 2.6]，故1.5/2.5落在高原
   範圍內視為「高原本身」；3.0已超出±30%範圍，視為額外的穩健性延伸檢查（不計入高原
   判定，但仍記錄方向是否一致）。
2. **其餘規格完全沿用`lending_fee_gate63.py`**：僅改變`Z_THRESH`這一個參數，聚合方式、
   rolling window（60次觀測/min_periods=20）、N值集合（5/10/20）、控制組設計
   （matched_stock+unmatched_universe各N=200）、判定路徑（訊號嚴格大於全部400次抽樣
   最大值）全部不變，透過monkeypatch`lending_fee_gate63.Z_THRESH`重用原模組函式，
   零程式碼邏輯分岔，避免兩份規格漂移。
3. **高原判定準則（事前綁定）**：1.5與2.5兩個閾值下，N=5/10/20是否維持
   `control_percentile>=某高標準`且方向不變（訊號為負）。只要有任一N在1.5或2.5下
   FAIL（未嚴格大於控制組最大值）或方向翻正，就判定「非乾淨高原，2.0可能是孤立巧合
   點」；3.0的結果僅供參考不計入此判準（因為超出±30%範圍，理論上样本更少、費率
   更極端事件更稀少是預期中的，不代表2.0附近不穩健）。

零新增API呼叫：完全重用`lending_fee_gate63.py`已快取的借券費率/股價/大盤資料，
只是重新跑聚合與事件偵測（Z_THRESH改變會改變哪些交易日被標記為事件，所以事件偵測
這一步無法跳過重算，但價格快取沿用同一份邏輯）。

2026-09-09 馬拉松第480輪新增。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import lending_fee_gate63 as lf
from control_group_standard import evaluate_vs_control
from material_news_car_gate2_continuation import _signed_ret
from validation import holdout

Z_THRESH_LIST = [1.5, 2.0, 2.5, 3.0]
OUT_JSON = Path(__file__).parent / "data" / "lending_fee_gate63_param_plateau_result.json"


def _run_one_zthresh(z_thresh: float, n_permutations: int, max_stocks: int | None) -> dict:
    lf.Z_THRESH = z_thresh  # monkeypatch：函式內部用module-level全域變數
    ev = lf._build_zscore_events(max_stocks=max_stocks)
    n_events_raw = len(ev)
    if ev.empty:
        return {"n_events_raw": 0, "sanity_note": "無事件"}

    holdout.assert_no_holdout_leakage(ev, date_col="date", context=f"lending_fee_gate63_param_plateau z={z_thresh}")

    mkt = lf.car_gate1._market_map()
    stock_ids = sorted(ev["stock_id"].unique())
    price_cache: dict[str, dict] = {}
    for sid in stock_ids:
        pm = lf._load_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm

    rows = []
    for r in ev.itertuples(index=False):
        pm = price_cache.get(r.stock_id)
        if pm is None:
            continue
        idx = pm["idx_map"].get(r.date)
        if idx is None:
            continue
        rows.append({"stock_id": r.stock_id, "date": r.date, "idx": idx})

    if not rows:
        return {"n_events_raw": n_events_raw, "sanity_fail": True}

    ev_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev_df, date_col="date", context=f"lending_fee_gate63_param_plateau priced z={z_thresh}")

    all_valid_pairs = [(sid, int(idx)) for sid, pm in price_cache.items() for idx in pm["valid_idx_val"]]
    rng = np.random.RandomState(lf.PERM_SEED)
    results = {"n_events_raw": n_events_raw, "n_events_priced": len(ev_df),
               "n_stocks_priced": ev_df["stock_id"].nunique()}

    for n_days in lf.N_LIST:
        ev_val = ev_df[(ev_df["date"] > holdout.TRAIN_END) & (ev_df["date"] <= holdout.VAL_END)]
        ev_train = ev_df[ev_df["date"] <= holdout.TRAIN_END]

        def _post_rets(sub: pd.DataFrame) -> list[float]:
            out = []
            for r in sub.itertuples(index=False):
                pm = price_cache[r.stock_id]
                if r.idx + n_days >= len(pm["dates"]):
                    continue
                v = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], r.idx, r.idx + n_days)
                if v is not None:
                    out.append(v)
            return out

        val_rets = _post_rets(ev_val)
        n_val = len(val_rets)
        if n_val < 20:
            results[f"N{n_days}"] = {"n_val_usable": n_val, "skipped": "n_val<20"}
            continue

        signal_stat = float(np.mean(val_rets))

        ev_stock_ids = sorted(ev_val["stock_id"].unique())
        n_pick_by_stock = ev_val["stock_id"].value_counts().to_dict()
        stock_plan = []
        for sid in ev_stock_ids:
            pm = price_cache.get(sid)
            if pm is None or len(pm["valid_idx_val"]) == 0:
                continue
            n_pick = max(1, int(n_pick_by_stock.get(sid, 1)))
            stock_plan.append((pm, min(n_pick, len(pm["valid_idx_val"]))))

        matched_draws = []
        for _ in range(n_permutations):
            pseudo = []
            for pm, n_pick in stock_plan:
                picks = rng.choice(pm["valid_idx_val"], size=n_pick, replace=False)
                for idx in picks:
                    v = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], int(idx), int(idx) + n_days)
                    if v is not None:
                        pseudo.append(v)
            if pseudo:
                matched_draws.append(float(np.mean(pseudo)))

        unmatched_draws = []
        if all_valid_pairs:
            pool_idx = np.arange(len(all_valid_pairs))
            for _ in range(n_permutations):
                picks = rng.choice(pool_idx, size=min(n_val, len(pool_idx)), replace=False)
                pseudo = []
                for pi in picks:
                    sid, idx = all_valid_pairs[pi]
                    pm = price_cache[sid]
                    v = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], idx, idx + n_days)
                    if v is not None:
                        pseudo.append(v)
                if pseudo:
                    unmatched_draws.append(float(np.mean(pseudo)))

        control_draws = {}
        if len(matched_draws) >= 20:
            control_draws["matched_stock"] = [-x for x in matched_draws]
        if len(unmatched_draws) >= 20:
            control_draws["unmatched_universe"] = [-x for x in unmatched_draws]

        if len(control_draws) < 2:
            results[f"N{n_days}"] = {"n_val_usable": n_val, "signal_stat": signal_stat,
                                      "skipped": f"控制組變體不足({list(control_draws.keys())})"}
            continue

        verdict = evaluate_vs_control(
            signal_stat=-signal_stat,
            control_draws=control_draws,
            selection_spec=(f"#63參數高原檢定，Z_THRESH={z_thresh}（事前綁定集合{Z_THRESH_LIST}），"
                             f"N={n_days}，其餘規格完全沿用lending_fee_gate63.py事前綁定"),
        )
        results[f"N{n_days}"] = {
            "n_train": len(ev_train), "n_val_usable": n_val,
            "signal_stat_mean_post_ret": signal_stat,
            "train_mean_post_ret": float(np.mean(_post_rets(ev_train))) if len(ev_train) else None,
            "passed": verdict.passed, "reason": verdict.reason,
            "control_max_negated": verdict.control_max, "control_percentile": verdict.control_percentile,
        }
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None)
    ap.add_argument("--n-permutations", type=int, default=200)
    args = ap.parse_args()

    orig_z = lf.Z_THRESH
    all_results = {}
    try:
        for z in Z_THRESH_LIST:
            print(f"\n=== Z_THRESH={z} ===")
            r = _run_one_zthresh(z, args.n_permutations, args.max_stocks)
            all_results[str(z)] = r
            for n_days in lf.N_LIST:
                key = f"N{n_days}"
                if key in r and "passed" in r[key]:
                    print(f"  [{key}] n_val={r[key]['n_val_usable']} "
                          f"signal={r[key]['signal_stat_mean_post_ret']:.5f} "
                          f"{'PASS' if r[key]['passed'] else 'FAIL'} "
                          f"percentile={r[key]['control_percentile']}")
                elif key in r:
                    print(f"  [{key}] {r[key].get('skipped', r[key])}")
    finally:
        lf.Z_THRESH = orig_z  # 還原module全域狀態，避免影響同行程內其他import

    OUT_JSON.write_text(json.dumps(all_results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    return all_results


if __name__ == "__main__":
    main()
