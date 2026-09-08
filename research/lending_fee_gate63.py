"""`HYPOTHESIS_QUEUE.md` #63 借券費率異常飆升作為知情放空訊號 — 第1關cheap gate。

背景/經濟機制/資料可行性查證見`HYPOTHESIS_QUEUE.md` #63條目（第477/478輪已
判定FEASIBLE，資料已回補完成2012-2024全範圍）。本腳本把該條目「下一輪待辦」
段落的具體規格轉成可執行的cheap gate。

**事前綁定規格（跑數字前定案，不得事後調整）**：

1. **資料源與子集**：`twse_lending_fee_client.load_all_cached()`，只取
   `trade_type in ("競價", "議借")`（依#63條目查證：「定價交易費率是官方
   公告固定值，不反映個股急迫程度」，經濟機制只適用於市場出清價格，排除
   定價；全歷史定價僅7筆，排除不影響樣本量）。

2. **聚合層級**：同一檔股票同一天可能有多筆借券成交（不同費率），為避免
   偽複製，**先按(stock_id, date)聚合成一列**：`fee_rate_agg` = 以volume
   加權的當日費率均值（同`block_trade_gate62.py`的vwap聚合精神），
   `total_volume` = 當日成交量加總，`n_prints` = 當日筆數（僅供描述）。

3. **z-score基準（事前綁定，非日曆60天，是「前60次有觀測的交易」）**：
   借券不是每天每股都有成交，用日曆天数的rolling window會被大量無交易日
   稀釋成偏態分布。改用**該股自己的借券交易序列**（只含有成交的日子，
   依日期排序）計算過去60次觀測的移動平均/標準差（`min_periods=20`，
   不足20次觀測不計算z-score，避免用太薄的基準估計）。
   `z = (fee_rate_agg_today - rolling_mean_prior60) / rolling_std_prior60`，
   `rolling_mean`/`rolling_std`只用**當天以前**的觀測（shift(1)後再rolling，
   不含當天自己，避免用未來/當下資訊污染基準）。

4. **事件定義（事前綁定，不得測完再挑）**：`z >= Z_THRESH = 2.0`。
   `rolling_std_prior60 <= 0`（例如全部觀測費率相同）時無法定義z-score，
   排除該筆。

5. **事前綁定方向**：借券費率急升 → 該股知情放空需求上升 → 未來N日市場
   調整超額報酬為負。只測這個方向，不設計對稱的「費率驟降→正報酬」假設
   （避免`HYPOTHESIS_QUEUE.md` #42/#43「等兩期都顯著才發現方向錯」教訓）。

6. **時間窗口**：進場點 = 事件日（借券成交日）收盤（借券成交資料同T86/
   block trade一樣是盤後公布，用當日收盤價當基準不構成未來函數）。前瞻
   窗口 = [事件日, 事件日+N]，N測三個值：5、10、20交易日（比照本佇列
   `block_trade_gate62.py`慣例，三個N各自獨立判定，都要登記）。

7. **目標變數**：市場調整超額報酬（個股報酬 - TAIEX同期報酬），直接reuse
   `material_news_car_gate2_continuation._signed_ret()`，零新增計算邏輯歧異。

8. **signal_stat**：VAL期（`TRAIN_END < date <= VAL_END`）事件的
   mean(post_ret_N)。事前假設方向為負，依`control_group_standard.py`
   「指標一律越大越好，越小越好者先取負號」規則：signal與控制組抽樣
   同步取負號後比較。

9. **控制組（`control_group_standard.py`2026-09-07升級標準，N=200，
   兩變體，比照`block_trade_gate62.py`同款設計）**：
   (a) `matched_stock`：只從VAL期「該N值下有z-score急升事件」的股票裡，
       抽跟真實事件數相同數量的隨機非事件交易日，算同一種市場調整前瞻
       報酬。
   (b) `unmatched_universe`：從全部有快取價格的股票裡，抽相同數量的
       隨機(股票,交易日)組合。

10. **判定路徑**：訊號（取負號後）嚴格大於全部400次控制組抽樣（取負號後）
    的最大值 —— 等價於「真實急升事件平均前瞻報酬比任一控制組抽樣的平均
    都更負」。`n_val < 20` 時跳過該N，不勉強判定。

**零新增API呼叫**：完全複用`material_news_car_gate.py`已快取的股價與
`_market_map()`（TAIEX），借券費率資料只讀本機`twse_lending_fee_client`
快取，不觸發任何新fetch。

2026-09-09 hypothesis_queue排程接續新增（承接第477/478輪資料可行性查證+
資料落地完成）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import material_news_car_gate as car_gate1
from control_group_standard import evaluate_vs_control
from material_news_car_gate2_continuation import _signed_ret
from twse_lending_fee_client import load_all_cached
from validation import holdout

N_LIST = [5, 10, 20]
MAX_N = max(N_LIST)
N_PERMUTATIONS_DEFAULT = 200
PERM_SEED = 20260909
Z_THRESH = 2.0
ROLLING_WINDOW = 60
ROLLING_MIN_PERIODS = 20
OUT_JSON = Path(__file__).parent / "data" / "lending_fee_gate63_result.json"


def _load_price_map(stock_id: str) -> dict | None:
    """跟`block_trade_gate62.py::_load_price_map`同一個慣例：包一層通用
    MAX_N的valid_idx_val，供三個N值共用一份價格快取。"""
    pm = car_gate1._load_price_map(stock_id)
    if pm is None:
        return None
    dates = pm["dates"]
    idx_map = {d: i for i, d in enumerate(dates)}
    valid_idx_val = np.array(
        [i for i, d in enumerate(dates)
         if holdout.TRAIN_END < d <= holdout.VAL_END and i + MAX_N < len(dates)],
        dtype=np.int64,
    )
    return {"dates": dates, "close": pm["close"], "idx_map": idx_map, "valid_idx_val": valid_idx_val}


def _build_zscore_events(max_stocks: int | None = None) -> pd.DataFrame:
    """讀回全部借券費率快取 -> 過濾trade_type -> (stock_id,date)聚合
    volume加權費率 -> 逐股計算z-score -> 回傳z>=Z_THRESH的事件列。"""
    raw = load_all_cached()
    if raw.empty:
        return pd.DataFrame(columns=["stock_id", "date", "fee_rate_agg", "z", "n_prints"])
    raw = raw[raw["trade_type"].isin(["競價", "議借"])].copy()
    raw = raw.dropna(subset=["fee_rate", "volume", "date", "stock_id"])
    raw = raw[(raw["fee_rate"] > 0) & (raw["volume"] > 0) & (raw["stock_id"] != "")]
    if raw.empty:
        return pd.DataFrame(columns=["stock_id", "date", "fee_rate_agg", "z", "n_prints"])

    if max_stocks is not None:
        keep_ids = sorted(raw["stock_id"].unique())[:max_stocks]
        raw = raw[raw["stock_id"].isin(keep_ids)]

    # 向量化聚合（避免groupby().apply()逐列跑Python函式，1M+筆會慢到無法忍受）：
    # volume加權費率 = sum(fee*vol)/sum(vol)，用groupby().sum()而非.apply(np.average)。
    raw = raw.assign(_weighted=raw["fee_rate"] * raw["volume"])
    grp = raw.groupby(["stock_id", "date"], as_index=False)
    daily = grp.agg(_wsum=("_weighted", "sum"), total_volume=("volume", "sum"), n_prints=("volume", "size"))
    daily["fee_rate_agg"] = daily["_wsum"] / daily["total_volume"]
    daily = daily.drop(columns=["_wsum"]).sort_values(["stock_id", "date"]).reset_index(drop=True)

    out_frames = []
    for sid, g in daily.groupby("stock_id"):
        g = g.sort_values("date").reset_index(drop=True)
        prior_mean = g["fee_rate_agg"].shift(1).rolling(ROLLING_WINDOW, min_periods=ROLLING_MIN_PERIODS).mean()
        prior_std = g["fee_rate_agg"].shift(1).rolling(ROLLING_WINDOW, min_periods=ROLLING_MIN_PERIODS).std()
        z = (g["fee_rate_agg"] - prior_mean) / prior_std
        g["z"] = z
        g = g[(prior_std > 0) & z.notna() & (z >= Z_THRESH)]
        if not g.empty:
            out_frames.append(g[["stock_id", "date", "fee_rate_agg", "z", "n_prints"]])

    if not out_frames:
        return pd.DataFrame(columns=["stock_id", "date", "fee_rate_agg", "z", "n_prints"])
    return pd.concat(out_frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None, help="限制股票數（smoke test用）")
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS_DEFAULT)
    args = ap.parse_args()

    print("=== 假設#63 借券費率異常飆升作為知情放空訊號 第1關cheap gate ===")
    ev = _build_zscore_events(max_stocks=args.max_stocks)
    print(f"z>={Z_THRESH}急升事件（已按stock_id+date聚合、逐股z-score）：{len(ev)}筆")
    if ev.empty:
        print("SANITY：目前資料尚未產生任何z-score急升事件（可能是聚合/門檻設定問題，需檢查）。")
        result = {"sanity_note": "無事件", "n_events_raw": 0}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    holdout.assert_no_holdout_leakage(ev, date_col="date", context="lending_fee_gate63 events")

    mkt = car_gate1._market_map()

    stock_ids = sorted(ev["stock_id"].unique())
    price_cache: dict[str, dict] = {}
    for i, sid in enumerate(stock_ids):
        pm = _load_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm
        if (i + 1) % 300 == 0:
            print(f"  價格載入進度 {i+1}/{len(stock_ids)}，{len(price_cache)}檔可用")
    print(f"價格可用股票數：{len(price_cache)}/{len(stock_ids)}")

    rows = []
    for r in ev.itertuples(index=False):
        pm = price_cache.get(r.stock_id)
        if pm is None:
            continue
        idx = pm["idx_map"].get(r.date)
        if idx is None:
            continue
        rows.append({"stock_id": r.stock_id, "date": r.date, "idx": idx, "z": r.z, "n_prints": r.n_prints})

    if not rows:
        print("SANITY FAIL：零事件可對應到價格快取（不是無訊號，是資料層問題，需檢查）。")
        result = {"sanity_fail": True, "n_events_raw": len(ev)}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    ev_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev_df, date_col="date", context="lending_fee_gate63 events (priced)")
    print(f"\n可對應價格之事件：{len(ev_df)}筆（去重股票數：{ev_df['stock_id'].nunique()}）")

    all_valid_pairs = [(sid, int(idx)) for sid, pm in price_cache.items() for idx in pm["valid_idx_val"]]
    print(f"unmatched_universe候選池大小：{len(all_valid_pairs)}")

    rng = np.random.RandomState(PERM_SEED)
    results = {}
    for n_days in N_LIST:
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
            results[f"N{n_days}"] = {"n_val_raw": len(ev_val), "n_val_usable": n_val, "skipped": "n_val<20"}
            print(f"\n[N={n_days}] n_val={n_val}<20，跳過")
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
        for _ in range(args.n_permutations):
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
            for _ in range(args.n_permutations):
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
            print(f"\n[N={n_days}] 控制組變體不足：{list(control_draws.keys())}")
            continue

        verdict = evaluate_vs_control(
            signal_stat=-signal_stat,
            control_draws=control_draws,
            selection_spec=(f"#63 借券費率異常飆升gate1，事前綁定：N={n_days}交易日，"
                             f"trade_type in (競價,議借)，聚合=volume加權日均費率，"
                             f"z-score=過去{ROLLING_WINDOW}次觀測(shift1後rolling，"
                             f"min_periods={ROLLING_MIN_PERIODS})，事件=z>={Z_THRESH}，"
                             f"signal=VAL期mean(post_ret)，事前假設方向為負（知情放空延續），"
                             f"依control_group_standard.py規則指標與控制組同步取負號後比較；"
                             f"唯一選點，不依結果回頭調整N/Z_THRESH/rolling window定義。"),
        )
        results[f"N{n_days}"] = {
            "n_train": len(ev_train), "n_val_usable": n_val,
            "signal_stat_mean_post_ret": signal_stat,
            "train_mean_post_ret": float(np.mean(_post_rets(ev_train))) if len(ev_train) else None,
            "passed": verdict.passed, "reason": verdict.reason,
            "control_max_negated": verdict.control_max, "control_percentile": verdict.control_percentile,
            "n_variants": verdict.n_variants, "n_draws_total": verdict.n_draws_total,
            "selection_sha256": verdict.selection_sha256,
        }
        print(f"\n[N={n_days}] n_val={n_val} VAL_mean_post_ret={signal_stat:.5f} "
              f"{'PASS' if verdict.passed else 'FAIL'}: {verdict.reason}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
