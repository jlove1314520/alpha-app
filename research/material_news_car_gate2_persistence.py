"""`HYPOTHESIS_QUEUE.md` #52 事件反應速度 — 第2關方向性/延續性檢定（PEAD式）。

**背景**：gate1（`material_news_car_gate.py`）用絕對值CAR證明「併購/增減資/財務/人事」
四類在VAL期反應強度顯著大於控制組，但絕對值本身不能拿來下單——絕對值恆為正，無法
判斷該買還該賣。本關測試的是：**事件反應方向本身能不能預測後續延續（PEAD drift），
而不是瞬間反應完就結束（efficient market立即消化）**。這才是能不能實際下單的關鍵，
效果量級（gate1的magnitude）本身不等於可交易性。

**事前綁定設計（不因結果回頭調整）**：
1. reaction CAR（T0~T0+1，跟gate1同一個窗口/基準邏輯）取**帶符號**版本（非絕對值），
   依正負分成 shock_pos / shock_neg 兩組（CAR恰好=0的事件排除，理論上機率極低）。
2. forward CAR：從reaction窗口結束後的下一個交易日開始（T0+2），到T0+2+H的市場調整
   累積報酬，H取兩個事前綁定的horizon：5個交易日、10個交易日。
3. **PEAD延續假設**：shock_pos組forward CAR均值 > 0，且shock_neg組forward CAR均值 < 0
   （同號延續，不是反轉）。
4. 控制組：打亂shock_pos/shock_neg分組標籤（forward CAR值固定不動），重新分組計算
   「正組均值 - 負組均值」的差距，N_PERMUTATIONS=200次，得null分布。真實的
   (pos組均值-neg組均值)差距要嚴格大於這400次(matched+unmatched兩變體共用同一套
   forward CAR值，僅重排標籤，故只需一種洗牌控制組，不重複套用gate1的
   matched_stock/unmatched_universe兩變體邏輯——那是拿來檢驗「反應存在」，這裡檢驗的
   是「分組標籤本身是否帶有可預測資訊」，隨機重貼標籤是唯一正確的控制組設計)。
5. **零新增API呼叫**：完全複用`material_news_car_gate.py`已載入的價格/市場快取邏輯
   （直接import該模組的既有函式，不重寫、不重新fetch）。

2026-09-09 hypothesis_queue排程接續新增。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import material_news_car_gate as g1
from validation import holdout

OUT_JSON = Path(__file__).parent / "data" / "material_news_car_gate2_persistence_result.json"
HORIZONS = (5, 10)  # 交易日，事前綁定，兩個都要看
N_PERMUTATIONS = 200
PERM_SEED = 20260909
PASS_CATEGORIES = ("併購", "增減資", "財務", "人事")  # gate1已PASS的4類，事前綁定


def _signed_car(dates: list[str], close: np.ndarray, mkt_idx: dict, mkt_close: np.ndarray,
                 reaction_idx: int | None) -> float | None:
    """跟gate1的_car()同一套基準邏輯，但回傳帶符號版本（不取abs）。"""
    if reaction_idx is None:
        return None
    baseline_idx = reaction_idx - 1
    end_idx = reaction_idx + g1.CAR_HORIZON
    if baseline_idx < 0 or end_idx >= len(dates):
        return None
    p0, p1 = close[baseline_idx], close[end_idx]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[baseline_idx], dates[end_idx]
    mi0, mi1 = mkt_idx.get(d0), mkt_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0 or np.isnan(m0) or np.isnan(m1):
        return None
    mkt_ret = m1 / m0 - 1
    return stock_ret - mkt_ret


def _forward_car(dates: list[str], close: np.ndarray, mkt_idx: dict, mkt_close: np.ndarray,
                  reaction_idx: int | None, horizon: int) -> float | None:
    """從reaction窗口結束後下一交易日(reaction_idx+CAR_HORIZON+1)開始算horizon天的
    市場調整累積報酬。基準價=該起點前一天收盤（即reaction窗口終點收盤，跟gate1
    reaction CAR的終點銜接，不重疊、不留空隙也不重複計算同一段報酬）。"""
    if reaction_idx is None:
        return None
    start_idx = reaction_idx + g1.CAR_HORIZON  # reaction窗口終點，當forward的基準日
    end_idx = start_idx + horizon
    if start_idx < 0 or end_idx >= len(dates):
        return None
    p0, p1 = close[start_idx], close[end_idx]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[start_idx], dates[end_idx]
    mi0, mi1 = mkt_idx.get(d0), mkt_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0 or np.isnan(m0) or np.isnan(m1):
        return None
    mkt_ret = m1 / m0 - 1
    return stock_ret - mkt_ret


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None)
    ap.add_argument("--max-categories", type=int, default=None)
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS)
    args = ap.parse_args()

    print("=== 假設#52 事件反應速度 gate2 方向性/延續性檢定（PEAD式） ===")
    cats = list(PASS_CATEGORIES) if args.max_categories is None else list(PASS_CATEGORIES)[:args.max_categories]
    ev, meta = g1._build_events(max_stocks=args.max_stocks, max_categories=None)
    ev = ev[ev["type"].isin(cats)].copy()
    print(f"事件表過濾後（{cats}類+已快取股票）：{len(ev)}筆，涉及股票{ev['stock_id'].nunique()}檔")

    holdout.assert_no_holdout_leakage(ev, date_col="price_date", context="material_news_car_gate2 events (raw)")

    mkt = g1._market_map()

    price_cache: dict[str, dict] = {}
    stock_ids = sorted(ev["stock_id"].unique())
    for i, sid in enumerate(stock_ids):
        pm = g1._load_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm
        if (i + 1) % 200 == 0:
            print(f"  價格載入進度 {i+1}/{len(stock_ids)}，{len(price_cache)}檔可用")
    print(f"價格可用股票數：{len(price_cache)}/{len(stock_ids)}")

    rows = []
    for r in ev.itertuples(index=False):
        pm = price_cache.get(r.stock_id)
        if pm is None:
            continue
        ridx = g1._reaction_idx(pm["dates"], r.price_date, bool(r.after_close))
        s_car = _signed_car(pm["dates"], pm["close"], mkt["idx"], mkt["close"], ridx)
        if s_car is None or s_car == 0:
            continue
        rec = {"stock_id": r.stock_id, "type": r.type,
               "reaction_idx_date": pm["dates"][ridx] if ridx is not None else None,
               "signed_car": s_car, "shock": "pos" if s_car > 0 else "neg"}
        ok_any_horizon = False
        for h in HORIZONS:
            fc = _forward_car(pm["dates"], pm["close"], mkt["idx"], mkt["close"], ridx, h)
            rec[f"fwd_car_{h}d"] = fc
            if fc is not None:
                ok_any_horizon = True
        if ok_any_horizon:
            rows.append(rec)

    if not rows:
        print("SANITY FAIL：零事件可用forward CAR（不是無訊號，是資料層有問題）。")
        result = {"sanity_fail": True}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(df, date_col="reaction_idx_date",
                                       context="material_news_car_gate2 events (final)")
    print(f"\n可用事件總數：{len(df)}（{df['stock_id'].nunique()}檔股票）")

    train_mask = df["reaction_idx_date"] <= holdout.TRAIN_END
    val_mask = (df["reaction_idx_date"] > holdout.TRAIN_END) & (df["reaction_idx_date"] <= holdout.VAL_END)

    rng = np.random.RandomState(PERM_SEED)
    results = {}
    for cat in cats:
        cat_results = {}
        for period_name, mask in (("train", train_mask), ("val", val_mask)):
            cat_df = df[(df["type"] == cat) & mask]
            per_h = {}
            for h in HORIZONS:
                col = f"fwd_car_{h}d"
                sub = cat_df.dropna(subset=[col])
                pos = sub[sub["shock"] == "pos"][col]
                neg = sub[sub["shock"] == "neg"][col]
                if len(pos) < 10 or len(neg) < 10:
                    per_h[f"{h}d"] = {"n_pos": len(pos), "n_neg": len(neg),
                                       "skipped": "n_pos或n_neg<10樣本太少"}
                    continue
                mean_pos, mean_neg = float(pos.mean()), float(neg.mean())
                real_gap = mean_pos - mean_neg  # PEAD延續假設：這個值應該>0

                # 控制組：固定forward CAR值，隨機重貼pos/neg標籤，N次
                vals = sub[col].to_numpy()
                n_pos_real = len(pos)
                null_gaps = []
                for _ in range(args.n_permutations):
                    perm = rng.permutation(len(vals))
                    p_idx = perm[:n_pos_real]
                    n_idx = perm[n_pos_real:]
                    null_gaps.append(float(vals[p_idx].mean() - vals[n_idx].mean()))
                null_gaps_arr = np.array(null_gaps)
                pctl = float((null_gaps_arr < real_gap).mean() * 100)
                per_h[f"{h}d"] = {
                    "n_pos": int(n_pos_real), "n_neg": int(len(neg)),
                    "mean_fwd_car_pos_shock": mean_pos, "mean_fwd_car_neg_shock": mean_neg,
                    "real_gap": real_gap,
                    "pead_direction_correct": bool(mean_pos > 0 and mean_neg < 0),
                    "null_control_max": float(null_gaps_arr.max()),
                    "null_control_percentile_of_real_gap": pctl,
                    "passed_gate2": bool(real_gap > null_gaps_arr.max() and mean_pos > 0 and mean_neg < 0),
                }
            cat_results[period_name] = per_h
        results[cat] = cat_results
        print(f"\n[{cat}]")
        for period_name, per_h in cat_results.items():
            for h_key, r in per_h.items():
                if "skipped" in r:
                    print(f"  {period_name} {h_key}: 跳過（{r['skipped']}）")
                else:
                    print(f"  {period_name} {h_key}: pos均值={r['mean_fwd_car_pos_shock']:.4f} "
                          f"neg均值={r['mean_fwd_car_neg_shock']:.4f} gap={r['real_gap']:.4f} "
                          f"控制組最大值={r['null_control_max']:.4f} "
                          f"{'PASS' if r['passed_gate2'] else 'FAIL'}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
