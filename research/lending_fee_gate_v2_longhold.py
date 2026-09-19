"""`PENDING_QUEUE.md`「借券費率.放大閾值重測」——`f_lending_fee_spike`（#63）
長持有期／較高閾值的**多頭降曝險版本**重測（明確排除真放空版本，見下）。

背景：`lending_fee_gate63`原死因＝gate1（三N值percentile皆100.0）與gate2（Z高原
12/12）乾淨過關，敗在gate4成本：VAL淨效益N5/N10於1x已轉負、N20於1x為正(+0.21%)
但2x轉負(−0.48%)。`STRATEGY_GRAVEYARD.md`「f_lending_fee_spike」條目建議
「改用更大絕對報酬幅度的閾值/持有期組合，仍值得當獨立新試驗另開登記測試」。

**跑數字前先看已登記的舊數字（誠實揭露，避免假裝沒看過）**：`lending_fee_gate63_
param_plateau_result.json`顯示Z_THRESH 1.5→3.0時VAL的N20平均超額報酬只在
−1.02%~−0.79%之間浮動（沒有隨Z升高而放大），但N5/N10/N20的絕對幅度大致隨持有天數
線性增加（−0.33%/−0.65%/−0.89%）。所以「放大幅度」的合理槓桿是**持有期**，不是Z；
Z只是當作鄰近格的高原檢查，不預期它放大幅度。

**事前綁定規格（跑數字前定案，事後不得調整）**：

1. **資料/事件定義完全沿用`lending_fee_gate63.py`**（trade_type∈{競價,議借}、
   (stock_id,date)聚合volume加權費率、過去60次觀測z-score、min_periods=20）。
   事件為z>=Z。事件建構只跑一次（Z=2.0），較高Z取其z欄位子集（嚴格子集，等價於
   重跑）。
2. **格點（共6格，全部登記，不挑）**：Z∈{2.0, 3.0, 4.0} × N∈{40, 60}交易日。
   主格＝Z=2.0（原事前綁定門檻，不因舊結果挑Z）的N=40與N=60兩個各自獨立判定；
   Z=3.0/4.0為鄰近格（高原檢查）。自由參數只有Z與N兩個（第11關上限5個，未觸及）。
3. **新增：事件冷卻期（相對gate63的唯一機制性變更）**：同一檔股票在一個事件之後N個
   交易日內的後續事件不算（cooldown=N）。理由：(a)長持有期下gate63的做法會把同一檔
   股票連續事件的重疊窗口重複計數，高估有效樣本；(b)真實「剔除持股」動作一旦賣出
   就不會在窗口內重複賣出，重疊事件在可執行性上不存在；(c)matched_stock控制組是
   每檔股票獨立抽點，事件若群聚而控制組不群聚，會使控制組變異偏小、判定偏寬鬆。
   冷卻期版本為**判定用**；無冷卻期版本只報描述性平均（不判定、不計控制組）。
4. **目標變數/方向/控制組/判定**：同gate63——市場調整超額報酬(個股−TAIEX)，事前
   方向為負，訊號與控制組同步取負號後，訊號須**嚴格大於全部400次控制組抽樣**
   （matched_stock+unmatched_universe各200，control_group_standard.py）。
   n_val<20跳過。VAL窗口內price已在`_load_price_map`層截斷於VAL_END，i+N需在
   截斷後價格內（不會外插到holdout）。
5. **成本（gate4）**：沿用`round_trip_cost_pct()`（commission+tax+slippage，買賣
   雙邊各一次），把訊號解讀為「事件日剔除該股、換回大盤曝險」的單次進出；
   **不含借券成本、不做放空**（CLAUDE.md⑩放空腿硬規則：借券成本/可借量未接入真實
   資料前，含放空腿數字一律不得採信，本試驗刻意排除）。淨效益=−post_ret−cost×mult，
   mult∈{1,2,3}，VAL與TRAIN皆報。
6. **格點通過條件（事前綁定）**：gate1控制組PASS **且** VAL淨效益在1x/2x/3x皆>0
   **且** TRAIN淨效益在1x>0（方向一致性）。**整體晉級深挖條件**：兩個主格
   （Z=2.0,N=40）與（Z=2.0,N=60）**都**通過，且6格中至少5格通過（高原）。不滿足
   即整條「長持有期降曝險版」結案，寫`STRATEGY_GRAVEYARD.md`，不再另開第三種
   持有期/閾值變體。
7. **成本前置關卡（協定1a-0）**：單次round-trip 0.685%。保守毛alpha估計取
   已登記的**N20實測平均避開損失0.89%**（不外插到N40/N60，即不假設線性增長）。
   0.89%/0.685%=130% ≥100% → 前置關卡視為通過（3x成本2.055%則為不通過，
   這正是第6點要求3x也活著時最可能的死點，SPEC明寫：本機制對成本高度敏感）。
8. **檢定力（協定1a-0b）**：本腳本另報依「股票」分群的cluster-robust標準誤與t值
   （事件同股票內相依），供判讀「贏控制組」與「有統計意義」是否一致。

**零新增API呼叫**：借券資料只讀`twse_lending_fee_client`本機快取；價格用既有
快取（`material_news_car_gate._load_price_map`）。

2026-09-19 馬拉松軌（驗證帽，承接`PENDING_QUEUE.md`「借券費率.放大閾值重測」）。
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
import lending_fee_gate63 as lf
from control_group_standard import evaluate_vs_control
from material_news_car_gate2_continuation import _signed_ret
from validation import holdout

Z_LIST = [2.0, 3.0, 4.0]
N_LIST = [40, 60]
COST_MULTIPLIERS = (1, 2, 3)
N_PERMUTATIONS_DEFAULT = 200
PERM_SEED = 20260919
OUT_JSON = Path(__file__).parent / "data" / "lending_fee_gate_v2_longhold_result.json"


def _apply_cooldown(df: pd.DataFrame, n_days: int) -> pd.DataFrame:
    """每檔股票依idx排序，事件保留條件：距上一個『被保留』事件>=n_days交易日。"""
    keep = []
    for sid, g in df.sort_values(["stock_id", "idx"]).groupby("stock_id"):
        last = None
        for r in g.itertuples(index=True):
            if last is None or r.idx - last >= n_days:
                keep.append(r.Index)
                last = r.idx
    return df.loc[keep]


def _cluster_t(rets_by_stock: dict[str, list[float]]) -> tuple[float, float, float]:
    """依股票分群的cluster-robust SE。回傳(mean, se, t)。"""
    n = sum(len(v) for v in rets_by_stock.values())
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    allv = np.concatenate([np.array(v) for v in rets_by_stock.values()])
    mu = float(allv.mean())
    num = sum((np.sum(np.array(v) - mu)) ** 2 for v in rets_by_stock.values())
    se = float(np.sqrt(num) / n)
    return mu, se, (mu / se if se > 0 else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None, help="限制股票數（smoke test用）")
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS_DEFAULT)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    out_json = Path(args.out) if args.out else OUT_JSON

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"
    print("=== 借券費率異常飆升 長持有期/較高閾值 降曝險版重測（gate1+gate4，事件冷卻期版）===")

    lf.Z_THRESH = min(Z_LIST)
    ev = lf._build_zscore_events(max_stocks=args.max_stocks)
    print(f"z>={min(Z_LIST)}事件（聚合後）：{len(ev)}筆")
    if ev.empty:
        out_json.write_text(json.dumps({"sanity_note": "無事件"}, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    holdout.assert_no_holdout_leakage(ev, date_col="date", context="lending_v2 events")

    mkt = car_gate1._market_map()
    price_cache: dict[str, dict] = {}
    for i, sid in enumerate(sorted(ev["stock_id"].unique())):
        pm = lf._load_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm
        if (i + 1) % 300 == 0:
            print(f"  價格載入進度 {i+1}，{len(price_cache)}檔可用")
    print(f"價格可用股票數：{len(price_cache)}")

    rows = []
    for r in ev.itertuples(index=False):
        pm = price_cache.get(r.stock_id)
        if pm is None:
            continue
        idx = pm["idx_map"].get(r.date)
        if idx is None:
            continue
        rows.append({"stock_id": r.stock_id, "date": r.date, "idx": int(idx), "z": float(r.z)})
    if not rows:
        print("SANITY FAIL：零事件可對應到價格快取。")
        out_json.write_text(json.dumps({"sanity_fail": True}, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    ev_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev_df, date_col="date", context="lending_v2 events (priced)")

    round_trip_1x = costmod.round_trip_cost_pct()
    print(f"1x round-trip成本率：{round_trip_1x:.4%}")

    rng = np.random.RandomState(PERM_SEED)
    results: dict = {"_meta": {"round_trip_1x": round_trip_1x, "perm_seed": PERM_SEED,
                               "n_permutations": args.n_permutations}}

    for n_days in N_LIST:
        # 各檔VAL期在N日窗口內可算的index（截斷於VAL_END後的價格內）
        valid_val = {}
        for sid, pm in price_cache.items():
            dts = pm["dates"]
            v = np.array([i for i, d in enumerate(dts)
                          if holdout.TRAIN_END < d <= holdout.VAL_END and i + n_days < len(dts)],
                         dtype=np.int64)
            if len(v):
                valid_val[sid] = v
        all_pairs = [(sid, int(i)) for sid, v in valid_val.items() for i in v]

        def _rets(sub: pd.DataFrame) -> dict[str, list[float]]:
            out: dict[str, list[float]] = {}
            for r in sub.itertuples(index=False):
                pm = price_cache[r.stock_id]
                if r.idx + n_days >= len(pm["dates"]):
                    continue
                v = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], r.idx, r.idx + n_days)
                if v is not None:
                    out.setdefault(r.stock_id, []).append(v)
            return out

        for z in Z_LIST:
            key = f"Z{z}_N{n_days}"
            sub_all = ev_df[ev_df["z"] >= z]
            sub = _apply_cooldown(sub_all, n_days)
            ev_val = sub[(sub["date"] > holdout.TRAIN_END) & (sub["date"] <= holdout.VAL_END)]
            ev_tr = sub[sub["date"] <= holdout.TRAIN_END]
            val_by = _rets(ev_val)
            tr_by = _rets(ev_tr)
            n_val = sum(len(v) for v in val_by.values())
            n_tr = sum(len(v) for v in tr_by.values())
            # 描述性：無冷卻期版本VAL平均（不判定）
            nocd_val = _rets(sub_all[(sub_all["date"] > holdout.TRAIN_END) & (sub_all["date"] <= holdout.VAL_END)])
            nocd_mean = (float(np.mean(np.concatenate([np.array(v) for v in nocd_val.values()])))
                         if nocd_val else None)
            print(f"\n[{key}] 冷卻期後 n_train={n_tr} n_val={n_val}（無冷卻期VAL平均={nocd_mean}）")
            if n_val < 20:
                results[key] = {"n_val_usable": n_val, "skipped": "n_val<20"}
                continue

            mu, se, t = _cluster_t(val_by)
            val_arr = np.concatenate([np.array(v) for v in val_by.values()])
            tr_arr = np.concatenate([np.array(v) for v in tr_by.values()]) if tr_by else np.array([])
            signal_stat = float(val_arr.mean())

            # 控制組（同gate63：matched_stock + unmatched_universe）
            n_pick_by_stock = ev_val["stock_id"].value_counts().to_dict()
            plan = []
            for sid in sorted(ev_val["stock_id"].unique()):
                v = valid_val.get(sid)
                if v is None or len(v) == 0:
                    continue
                plan.append((sid, min(max(1, int(n_pick_by_stock.get(sid, 1))), len(v))))
            matched, unmatched = [], []
            for _ in range(args.n_permutations):
                pseudo = []
                for sid, k in plan:
                    pm = price_cache[sid]
                    for idx in rng.choice(valid_val[sid], size=k, replace=False):
                        x = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], int(idx), int(idx) + n_days)
                        if x is not None:
                            pseudo.append(x)
                if pseudo:
                    matched.append(float(np.mean(pseudo)))
            if all_pairs:
                pool = np.arange(len(all_pairs))
                for _ in range(args.n_permutations):
                    pseudo = []
                    for pi in rng.choice(pool, size=min(n_val, len(pool)), replace=False):
                        sid, idx = all_pairs[pi]
                        pm = price_cache[sid]
                        x = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], idx, idx + n_days)
                        if x is not None:
                            pseudo.append(x)
                    if pseudo:
                        unmatched.append(float(np.mean(pseudo)))
            draws = {}
            if len(matched) >= 20:
                draws["matched_stock"] = [-x for x in matched]
            if len(unmatched) >= 20:
                draws["unmatched_universe"] = [-x for x in unmatched]
            if len(draws) < 2:
                results[key] = {"n_val_usable": n_val, "skipped": f"控制組變體不足({list(draws)})"}
                continue
            verdict = evaluate_vs_control(
                signal_stat=-signal_stat, control_draws=draws,
                selection_spec=(f"借券費率v2長持有期gate1，事前綁定：Z>={z}，N={n_days}交易日，事件冷卻期="
                                f"{n_days}交易日（同股票），其餘同#63（競價/議借、volume加權聚合、過去60次觀測"
                                f"z-score、min_periods=20），signal=VAL期mean(市場調整超額報酬)，事前方向為負，"
                                f"與控制組同步取負號比較；格點Z∈{Z_LIST}×N∈{N_LIST}共6格全登記，唯一選點規則見"
                                f"檔頭SPEC，不依結果回頭調整。"),
            )

            by_mult = {}
            all_pos = True
            for m in COST_MULTIPLIERS:
                c = round_trip_1x * m
                nv = float((-val_arr - c).mean())
                nt = float((-tr_arr - c).mean()) if tr_arr.size else None
                by_mult[str(m)] = {"cost_pct": c, "net_val": nv, "net_train": nt}
                if nv <= 0:
                    all_pos = False
            train_1x_ok = bool(by_mult["1"]["net_train"] is not None and by_mult["1"]["net_train"] > 0)
            point_pass = bool(verdict.passed and all_pos and train_1x_ok)
            results[key] = {
                "z": z, "n_days": n_days, "n_train": n_tr, "n_val": n_val,
                "n_stocks_val": len(val_by),
                "val_mean_post_ret": signal_stat, "val_cluster_se": se, "val_cluster_t": t,
                "train_mean_post_ret": float(tr_arr.mean()) if tr_arr.size else None,
                "val_mean_post_ret_no_cooldown_descriptive": nocd_mean,
                "gate1_passed": verdict.passed, "gate1_reason": verdict.reason,
                "control_max_negated": verdict.control_max, "control_percentile": verdict.control_percentile,
                "selection_sha256": verdict.selection_sha256, "n_draws_total": verdict.n_draws_total,
                "by_multiplier": by_mult, "net_val_positive_all_mult": all_pos,
                "train_net_1x_positive": train_1x_ok, "point_pass": point_pass,
            }
            print(f"  gate1={'PASS' if verdict.passed else 'FAIL'}  VAL平均={signal_stat:+.4%} "
                  f"cluster t={t:.2f}  TRAIN平均={results[key]['train_mean_post_ret']}")
            for m in COST_MULTIPLIERS:
                print(f"  {m}x成本({round_trip_1x*m:.3%}) 淨效益 VAL={by_mult[str(m)]['net_val']:+.4%} "
                      f"TRAIN={by_mult[str(m)]['net_train']}")
            print(f"  格點判定：{'PASS' if point_pass else 'FAIL'}")

    pts = {k: v for k, v in results.items() if k.startswith("Z") and "point_pass" in v}
    primary = [pts.get("Z2.0_N40", {}).get("point_pass"), pts.get("Z2.0_N60", {}).get("point_pass")]
    n_pass = sum(1 for v in pts.values() if v["point_pass"])
    overall = bool(all(primary) and n_pass >= 5)
    results["_summary"] = {"n_points_evaluated": len(pts), "n_points_pass": n_pass,
                           "primary_pass": primary, "advance_to_deep_dive": overall}
    print(f"\n=== 總結：{n_pass}/{len(pts)}格通過；主格={primary}；晉級深挖={overall} ===")

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"已存：{out_json}")
    return results


if __name__ == "__main__":
    main()
