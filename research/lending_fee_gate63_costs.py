"""`HYPOTHESIS_QUEUE.md` #63 借券費率異常飆升作為知情放空訊號 — 第4關
成本/稅/滑價敏感度（1x/2x/3x）。

背景：gate1（`lending_fee_gate63.py`）三個N值全部CHEAP_PASS（percentile皆
100.0），gate2參數高原（`lending_fee_gate63_param_plateau.py`）12/12組全數
PASS。依`HYPOTHESIS_QUEUE.md` #63「下一輪待辦」清單第1項，本輪做成本敏感度。

**事前綁定的成本模型（跑數字前定案，不得事後調整）**：

#63條目自己的經濟機制描述明確寫「本階段不設計實際放空部位，先只測『費率
急升是否預測該股未來報酬轉負』」（見#63條目「曝險方向」段落）——因此本關
不套用`short_round_trip_cost_pct()`（含借券成本，那是實際放空才要付的），
而是採用跟本佇列`#29`/`#59`同一套`round_trip_cost_pct()`（commission+
securities tax+slippage，買賣雙邊各一次）：把訊號解讀成「偵測到z-score
急升事件時，把該股從多頭部位剔除／降到目標市場曝險」這個**單次進出**動作
——賣掉該股（此刻）+ 換回大盤曝險，是一次round-trip交易成本，不是每日
計提的借券費。若未來要正式測試「放空」版本的獲利能力，須改用
`short_round_trip_cost_pct(holding_days=N)`並另開一條試驗登記，不可與本次
結果混為一談。

**淨效益定義**：`net_benefit_i = -post_ret_i - cost_pct(mult)`。
`post_ret_i`是gate1既有定義的市場調整超額報酬（個股-TAIEX同期），事前假設
方向為負，`-post_ret_i`即「避開該股後，相對繼續持有該股所省下的損失」
（正值＝真的避開了損失）。`cost_pct(mult) = round_trip_cost_pct() * mult`，
`mult`取1/2/3（跟`equal_weight_rebalance_costs_v1.py`/
`min_variance_portfolio_gate59_costs.py`同一種「整筆round-trip乘上倍數」
慣例，不是只放大slippage那一項）。

**判定路徑（本關不查隨機控制組，只問「扣完成本後還剩不剩」）**：
VAL期`mean(net_benefit)`在1x/2x/3x是否維持為正。任一值轉負皆誠實列出，
不由本腳本自動判PASS/FAIL總結論——是否值得投入第5關（leave-one-out）由
下一輪人工/排程判讀決定，比照`min_variance_portfolio_gate59_costs.py`
同一種「不自動下最終結論」慣例。

**零新增API呼叫**：完全複用`lending_fee_gate63.py`已有的事件建構與價格快取
邏輯（`_build_zscore_events`/`_load_price_map`/`_signed_ret`），只多算一次
成本扣除，不重新抓取或重新計算任何原始資料。

2026-09-09 hypothesis_queue排程接續新增（承接gate1/gate2結果，`TRIALS_
LEDGER.md`#225/#226）。
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
import validation.costs as costmod
from lending_fee_gate63 import N_LIST, _build_zscore_events, _load_price_map
from material_news_car_gate2_continuation import _signed_ret
from validation import holdout

COST_MULTIPLIERS = (1, 2, 3)
OUT_JSON = Path(__file__).parent / "data" / "lending_fee_gate63_costs_result.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None, help="限制股票數（smoke test用）")
    args = ap.parse_args()

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    print("=== 假設#63 借券費率異常飆升 第4關成本/稅/滑價敏感度（1x/2x/3x） ===")
    round_trip_1x = costmod.round_trip_cost_pct()
    print(f"1x round-trip成本率（commission+tax+slippage，買賣雙邊）：{round_trip_1x:.4%}")

    ev = _build_zscore_events(max_stocks=args.max_stocks)
    print(f"z-score急升事件（已按stock_id+date聚合、逐股z-score）：{len(ev)}筆")
    if ev.empty:
        print("COST GATE FAIL：無事件可用，跟gate1一致，判結構性不可靠。")
        OUT_JSON.write_text(json.dumps({"sanity_note": "無事件"}, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    holdout.assert_no_holdout_leakage(ev, date_col="date", context="lending_fee_gate63_costs events")

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
        rows.append({"stock_id": r.stock_id, "date": r.date, "idx": idx})
    if not rows:
        print("COST GATE FAIL：零事件可對應到價格快取，跟gate1一致。")
        OUT_JSON.write_text(json.dumps({"sanity_fail": True}, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    ev_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev_df, date_col="date", context="lending_fee_gate63_costs events (priced)")

    results = {}
    any_negative_at_1x = False
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
        train_rets = _post_rets(ev_train)
        n_val = len(val_rets)
        if n_val < 20:
            results[f"N{n_days}"] = {"n_val_usable": n_val, "skipped": "n_val<20（跟gate1一致）"}
            print(f"\n[N={n_days}] n_val={n_val}<20，跳過")
            continue

        print(f"\n[N={n_days}] n_val={n_val}  n_train={len(train_rets)}")
        val_arr = np.array(val_rets)
        train_arr = np.array(train_rets) if train_rets else np.array([])
        gross_val = float(-val_arr.mean())
        gross_train = float(-train_arr.mean()) if train_arr.size else None
        print(f"  gross（無成本）避開損失：VAL={gross_val:+.4%}"
              + (f"  TRAIN={gross_train:+.4%}" if gross_train is not None else ""))

        per_n = {"n_val_usable": n_val, "n_train": len(train_rets),
                 "gross_avoided_loss_val": gross_val, "gross_avoided_loss_train": gross_train,
                 "by_multiplier": {}}
        for mult in COST_MULTIPLIERS:
            cost_pct = round_trip_1x * mult
            net_val = float((-val_arr - cost_pct).mean())
            net_train = float((-train_arr - cost_pct).mean()) if train_arr.size else None
            neg_mark_val = "  <-- 淨效益轉負" if net_val < 0 else ""
            if mult == 1 and net_val < 0:
                any_negative_at_1x = True
            print(f"  {mult}x成本({cost_pct:.4%}): 淨效益 VAL={net_val:+.4%}{neg_mark_val}"
                  + (f"  TRAIN={net_train:+.4%}" if net_train is not None else ""))
            per_n["by_multiplier"][str(mult)] = {
                "cost_pct": cost_pct, "net_benefit_val": net_val, "net_benefit_train": net_train,
            }
        results[f"N{n_days}"] = per_n

    print("\n=== 第4關結論 ===")
    if any_negative_at_1x:
        print(
            "**至少一個N值在1x成本下淨效益已轉負**——即使gate1/gate2的統計顯著性"
            "（贏過隨機控制組）成立，單筆事件的訊號強度（絕對報酬幅度）不足以"
            "覆蓋一次round-trip交易成本，依誠實記錄鐵律不隱瞞。這跟湊統計顯著性"
            "是兩回事：'贏隨機控制組'只證明訊號不是雜訊，不保證訊號夠大能付得起"
            "交易成本。是否仍值得繼續投入第5關（leave-one-out）以後，由下一輪"
            "人工/排程判讀決定，本腳本不自動下PASS/FAIL。"
        )
    else:
        print(
            "全部N值在1x/2x/3x成本下淨效益皆維持為正，訊號強度足以覆蓋"
            "round-trip交易成本（此為長倉『降曝險/剔除持股』單次進出成本模型，"
            "非放空——若未來要測放空版本須另計借券成本並另開試驗登記）。"
            "不代表最終PASS——仍待逐年一致性（全歷史2012-2024）/"
            "leave-one-year-out/樣本外/前向paper/下檔保護。"
        )

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
