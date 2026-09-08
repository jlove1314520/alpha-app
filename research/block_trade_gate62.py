"""`HYPOTHESIS_QUEUE.md` #62 鉅額逐筆交易（Block Trade）跟隨訊號 — 第1關cheap gate。

背景/經濟機制/資料可行性查證見`HYPOTHESIS_QUEUE.md` #62條目(a)(b)段落
（第471輪已判定FEASIBLE）。本腳本把該條目的具體假設定義轉成可執行的
cheap gate，**尚未跑正式數字**——資料回補（`backfill_block_trade.py`，
job`block_trade_backfill_62tw`）截至本輪只完成約100/2500個交易日
（2015年初這一段，全部落在TRAIN期），VAL期（2021-2024）事件數為0，
不足以判定，本輪只驗證管線本身正確，正式判定留給VAL期資料回補到位
後的下一輪。

**事前綁定規格（跑數字前定案，不得事後調整）**：

1. **資料源與子集**：`twse_block_trade_client.load_all_cached()`，只取
   `trade_type == "配對交易"`（依#62(b)段落：只有配對交易對應upstairs
   block trade資訊不對稱機制，「拍賣」「標購」是不同競價機制，排除）。

2. **聚合層級**：同一檔股票同一天可能有多筆配對交易（例如鴻海/廣達單日
   2~4筆），為避免偽複製（pseudo-replication，同一天的多筆記錄不是獨立
   事件），**先按(stock_id, date)聚合成一列**：`vwap` = 以volume加權的
   當日配對交易均價，`total_volume`/`total_value` = 當日配對交易量/金額
   加總，`n_prints` = 當日筆數（僅供描述，不進入判定）。

3. **方向代理（未經直接驗證的第二層假設，明確標註）**：原始資料無買方/
   賣方發起方標記。用`vwap`相對事件當日收盤價(`close`)的偏離方向代理：
   `vwap < close` → 視為賣方折價讓利發起（sell-initiated）；
   `vwap > close` → 視為買方溢價發起（buy-initiated）；
   `vwap == close` → 無法判斷方向，排除。**這個代理本身不是文獻驗證過的
   事實，是本假說的第二層假設**，若gate1/gate2最終PASS，代理的有效性
   仍需要在報告裡誠實揭露為前提假設而非已證事實。

4. **事前綁定方向（不對稱，依文獻Kraus & Stoll 1972／Holthausen et al.
   1987）**：只測sell-initiated事件的未來N日超額報酬，事前假設為負
   （賣壓延續）。buy-initiated事件不強行預期對稱的正向延續（避免
   `HYPOTHESIS_QUEUE.md` #42/#43「等兩期都顯著才發現方向錯」的教訓），
   只記錄供對照，不用於判定PASS/FAIL。

5. **時間窗口**：進場點 = 事件日（block trade成交日）收盤（跟T86同類
   官方資料一樣，是**盤後才公布**的資料，收盤價已知，用它當基準不構成
   未來函數）。前瞻窗口 = [事件日, 事件日+N]，N測三個值做敏感度：
   5、10、20交易日（比照本佇列既有慣例，三個N各自獨立判定，都要登記，
   不得只登記PASS的那個N）。

6. **目標變數**：市場調整超額報酬（個股報酬 - TAIEX同期報酬），跟
   `material_news_car_gate.py`/`material_news_car_gate2_continuation.py`
   同一套`_signed_ret()`計算方式（直接reuse，零新增程式碼歧異）。

7. **signal_stat**：VAL期（`TRAIN_END < date <= VAL_END`）sell-initiated
   事件的mean(post_ret_N)。因事前假設方向為負，符合`control_group_standard.py`
   「指標一律越大越好，越小越好者先取負號」規則：**傳入判定函式前對
   signal與全部控制組抽樣同步取負號**，在`selection_spec`裡註明。

8. **控制組（`control_group_standard.py`2026-09-07升級標準，N=200，
   兩變體，比照`material_news_car_gate.py`同款設計）**：
   (a) `matched_stock`：只從VAL期「該N值下有sell-initiated事件」的股票裡，
       抽跟真實事件數相同數量的隨機非事件交易日，算同一種市場調整前瞻
       報酬。
   (b) `unmatched_universe`：從全部有快取價格的股票裡，抽相同數量的
       隨機(股票,交易日)組合。

9. **判定路徑**：訊號（取負號後）嚴格大於全部400次控制組抽樣（取負號後）
   的最大值 —— 等價於「真實sell-initiated平均前瞻報酬比任一控制組抽樣的
   平均都更負」。`n_val < 20` 時跳過該N，不勉強判定。

**零新增API呼叫**：完全複用`material_news_car_gate.py`已快取的股價
（`TaiwanStockPrice__{stock_id}__2010-01-01__2024-12-31.parquet`）與
`_market_map()`（TAIEX），block trade資料只讀本機`twse_block_trade_client`
快取，不觸發任何新fetch。

2026-09-09 馬拉松TW軌round472新增（接續round471資料可行性查證FEASIBLE
判定）。
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
from twse_block_trade_client import load_all_cached
from validation import holdout

N_LIST = [5, 10, 20]
MAX_N = max(N_LIST)
N_PERMUTATIONS_DEFAULT = 200
PERM_SEED = 20260909
OUT_JSON = Path(__file__).parent / "data" / "block_trade_gate62_result.json"


def _load_price_map(stock_id: str) -> dict | None:
    """跟`material_news_car_gate.py::_load_price_map`同一個快取檔案/慣例，
    但valid_idx改成通用MAX_N（供三個N值共用一份快取，不重複載入）。"""
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


def _build_events(max_events: int | None = None) -> pd.DataFrame:
    raw = load_all_cached()
    if raw.empty:
        return pd.DataFrame(columns=["stock_id", "date", "vwap", "total_volume", "total_value", "n_prints"])
    raw = raw[raw["trade_type"] == "配對交易"].copy()
    raw = raw.dropna(subset=["price", "volume"])
    raw = raw[(raw["price"] > 0) & (raw["volume"] > 0)]
    if raw.empty:
        return pd.DataFrame(columns=["stock_id", "date", "vwap", "total_volume", "total_value", "n_prints"])

    def _agg(g: pd.DataFrame) -> pd.Series:
        vol_sum = g["volume"].sum()
        vwap = float(np.average(g["price"], weights=g["volume"])) if vol_sum > 0 else float(g["price"].mean())
        return pd.Series({
            "vwap": vwap,
            "total_volume": float(vol_sum),
            "total_value": float(g["value"].sum(skipna=True)),
            "n_prints": int(len(g)),
        })

    agg = raw.groupby(["stock_id", "date"], as_index=False).apply(_agg, include_groups=False)
    if max_events is not None:
        agg = agg.sort_values("date").head(max_events)
    return agg.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-events", type=int, default=None, help="限制事件數（smoke test用）")
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS_DEFAULT)
    args = ap.parse_args()

    print("=== 假設#62 鉅額逐筆交易（Block Trade）跟隨訊號 第1關cheap gate ===")
    ev = _build_events(max_events=args.max_events)
    print(f"配對交易事件（已按stock_id+date聚合）：{len(ev)}筆")
    if ev.empty:
        print("SANITY：目前快取的block trade資料尚不足以聚合出任何事件（回補中，非管線問題）。")
        result = {"sanity_note": "無事件，回補中，非管線bug", "n_events_raw": 0}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    holdout.assert_no_holdout_leakage(ev, date_col="date", context="block_trade_gate62 events (raw)")

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
        close0 = pm["close"][idx]
        if close0 <= 0 or np.isnan(close0):
            continue
        if r.vwap < close0:
            direction = "sell"
        elif r.vwap > close0:
            direction = "buy"
        else:
            continue  # vwap==close，無法判斷方向，事前排除
        rows.append({"stock_id": r.stock_id, "date": r.date, "idx": idx, "direction": direction,
                     "n_prints": r.n_prints, "total_volume": r.total_volume})

    if not rows:
        print("SANITY FAIL：零事件可判斷方向（不是無訊號，是資料層問題，需檢查）。")
        result = {"sanity_fail": True, "n_events_raw": len(ev)}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    dir_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(dir_df, date_col="date", context="block_trade_gate62 events (direction)")
    n_sell, n_buy = (dir_df["direction"] == "sell").sum(), (dir_df["direction"] == "buy").sum()
    print(f"\n方向判斷後：{len(dir_df)}筆（sell-initiated={n_sell}, buy-initiated={n_buy}）")

    # 全體有快取價格的股票 x VAL期可算前瞻報酬的(股票,交易日)組合，供unmatched_universe抽樣
    all_valid_pairs = [(sid, int(idx)) for sid, pm in price_cache.items() for idx in pm["valid_idx_val"]]
    print(f"unmatched_universe候選池大小：{len(all_valid_pairs)}")

    rng = np.random.RandomState(PERM_SEED)
    results = {}
    for n_days in N_LIST:
        sell_val = dir_df[(dir_df["direction"] == "sell") & (dir_df["date"] > holdout.TRAIN_END)
                           & (dir_df["date"] <= holdout.VAL_END)]
        sell_train = dir_df[(dir_df["direction"] == "sell") & (dir_df["date"] <= holdout.TRAIN_END)]
        buy_val = dir_df[(dir_df["direction"] == "buy") & (dir_df["date"] > holdout.TRAIN_END)
                          & (dir_df["date"] <= holdout.VAL_END)]

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

        sell_val_rets = _post_rets(sell_val)
        n_val = len(sell_val_rets)
        if n_val < 20:
            results[f"N{n_days}"] = {"n_val_raw": len(sell_val), "n_val_usable": n_val, "skipped": "n_val<20"}
            print(f"\n[N={n_days}] sell-initiated n_val={n_val}<20，跳過（回補未完成或事件本身稀少）")
            continue

        signal_stat = float(np.mean(sell_val_rets))
        buy_val_rets = _post_rets(buy_val)

        # 控制組(a) matched_stock：只從有sell-initiated事件的股票VAL期valid_idx裡抽同數量
        sell_stock_ids = sorted(sell_val["stock_id"].unique())
        n_pick_by_stock = sell_val["stock_id"].value_counts().to_dict()
        stock_plan = []
        for sid in sell_stock_ids:
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

        # 控制組(b) unmatched_universe：全體股票VAL期隨機(股票,交易日)組合
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
            selection_spec=(f"#62 Block Trade跟隨訊號gate1，事前綁定：N={n_days}交易日，"
                             f"trade_type=配對交易，方向代理=vwap<close視為sell-initiated，"
                             f"signal=VAL期mean(post_ret)，事前假設方向為負（賣壓延續），"
                             f"依control_group_standard.py規則指標與控制組同步取負號後比較；"
                             f"唯一選點，不依結果回頭調整N或方向代理定義。"),
        )
        results[f"N{n_days}"] = {
            "n_train": len(sell_train), "n_val_usable": n_val,
            "signal_stat_mean_post_ret": signal_stat,
            "train_mean_post_ret": float(np.mean(_post_rets(sell_train))) if len(sell_train) else None,
            "buy_initiated_n_val": len(buy_val), "buy_initiated_mean_post_ret_ref_only": (
                float(np.mean(buy_val_rets)) if buy_val_rets else None),
            "passed": verdict.passed, "reason": verdict.reason,
            "control_max_negated": verdict.control_max, "control_percentile": verdict.control_percentile,
            "n_variants": verdict.n_variants, "n_draws_total": verdict.n_draws_total,
            "selection_sha256": verdict.selection_sha256,
        }
        print(f"\n[N={n_days}] n_val={n_val} VAL_mean_post_ret(sell)={signal_stat:.5f} "
              f"{'PASS' if verdict.passed else 'FAIL'}: {verdict.reason}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
