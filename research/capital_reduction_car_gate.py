"""`HYPOTHESIS_QUEUE.md` #71 上市櫃減資事件效應：第1關cheap gate（CAR事件研究）。

`PENDING_QUEUE.md`【重構.減資】步驟(b)：用`capital_reduction_verify.py`已驗證、已正規化
原因的兩組事件（現金減資／彌補虧損減資），跑跟`buyback_car_gate.py`（#40）同款CAR框架。
複用該檔的價格/大盤/CAR函式，不重新發明。

**事前綁定（看數字前寫死，事後不得改）**
- 事件日t0＝`capital_reduction_verified.json`的`reduction_date`（FinMind
  `TaiwanStockCapitalReductionReferencePrice`的`date`，＝恢復買賣日，#71已查證非公告日）。
  進場＝t0之後第一個交易日（PIT保守處理，不用t0當天價），持有20交易日，
  CAR＝個股還原價報酬－TAIEX同期報酬。
- **已知限制（誠實揭露）**：拿不到公告日／股東會決議日（#71已知風險2），所以這裡測的是
  「恢復買賣後的事後漂移」，不是「公告當下的市場反應」。結論只能說前者。
- 兩組分開檢定，方向事前綁定（#71條目）：現金減資→CAR為正；彌補虧損減資→CAR為負。
  其他原因字串（映射表以外）不納入，只報筆數。
- 多重比較：2組檢定，`BONFERRONI_N=2`，VAL t-test p需<0.10/2=0.05，
  隨機日期控制組百分位需>=95（方向感知：現金組看真實mean贏過null多少%、
  虧損組看真實mean低於null多少%）。
- 每組通過條件（缺一不可）：TRAIN/VAL事件數各>=30；TRAIN與VAL平均CAR同號且符合綁定方向；
  VAL t-test p<0.05；控制組百分位>=95。
- 控制組：只在VAL期間，對每檔有VAL事件的股票抽同數量隨機偽事件日；偽事件的20日窗口
  若涵蓋該股任何已驗證減資日則剔除（避免減資機械跳空污染null）。重複200次。
- 只用horizon=20（不另測N=5，避免多一層多重比較；[自行裁量]）。
- 全程只經`adjusted_price_series`/`load_dev`（holdout-safe，事件進場日再驗一次）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import buyback_car_gate as bcg
from validation import holdout

VERIFIED_PATH = Path(__file__).parent.parent / "data" / "capital_reduction_verified.json"
OUT_PATH = Path(__file__).parent / "data" / "capital_reduction_car_gate_result.json"
GROUPS = {"現金減資": +1, "彌補虧損": -1}  # 事前綁定方向
BONFERRONI_N = 2
BASE_ALPHA = 0.10
N_PERMUTATIONS = 200
PERM_SEED = 20260919
MIN_N = 30


def _load_events() -> tuple[pd.DataFrame, dict]:
    data = json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
    evs = data["reduction_events"]
    df = pd.DataFrame(evs)[["stock_id", "reduction_date", "reason"]].drop_duplicates()
    counts = df["reason"].fillna("(空)").value_counts().to_dict()
    return df, {"by_reason_all": counts, "queried": data["stocks_queried_total"],
                "universe": data["candidate_universe_size"]}


def _group_stats(rows: pd.DataFrame, sign: int, val_events_by_stock: dict, price_cache: dict,
                 mkt_date_idx: dict, mkt_close, all_red_dates: dict, label: str) -> dict:
    train = holdout.cap_to_train(rows, date_col="entry_date")
    val = holdout.validation_slice(rows, date_col="entry_date")
    ts = bcg._period_stats(train, "TRAIN")
    vs = bcg._period_stats(val, "VAL")
    print(f"\n[{label}] TRAIN n={ts['n']} mean_CAR={ts['mean_car']:+.4f} median={ts['median_car']:+.4f} p_t={ts['p_ttest']:.4f}")
    print(f"[{label}] VAL   n={vs['n']} mean_CAR={vs['mean_car']:+.4f} median={vs['median_car']:+.4f} p_t={vs['p_ttest']:.4f}")

    rng = np.random.RandomState(PERM_SEED)
    perm_means = []
    for _ in range(N_PERMUTATIONS):
        pseudo = []
        for sid, cnt in val_events_by_stock.items():
            pm = price_cache.get(sid)
            if pm is None:
                continue
            dates = pm["dates"]
            red = all_red_dates.get(sid, [])
            valid_idx = []
            for i, d in enumerate(dates):
                if not (holdout.TRAIN_END < d <= holdout.VAL_END and i + bcg.FORWARD_HORIZON < len(dates)):
                    continue
                end_d = dates[i + bcg.FORWARD_HORIZON]
                if any(d <= r <= end_d for r in red):
                    continue
                valid_idx.append(i)
            if not valid_idx:
                continue
            picks = rng.choice(valid_idx, size=min(cnt, len(valid_idx)), replace=False)
            for idx in picks:
                car = bcg._car_for(dates, pm["adj_close"], mkt_date_idx, mkt_close, int(idx))
                if car is not None:
                    pseudo.append(car)
        if pseudo:
            perm_means.append(float(np.mean(pseudo)))
    perm_means = np.array(perm_means)
    real = vs["mean_car"]
    if len(perm_means) > 0 and not pd.isna(real):
        # 方向感知：sign=+1看真實mean贏過null幾%；sign=-1看真實mean低於null幾%
        null_pct = 100.0 * float(np.mean(perm_means <= real)) if sign > 0 else 100.0 * float(np.mean(perm_means >= real))
    else:
        null_pct = float("nan")
    req_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    alpha_adj = BASE_ALPHA / BONFERRONI_N
    print(f"[{label}] 控制組 null mean={np.mean(perm_means):+.4f} sd={np.std(perm_means):.4f}（{len(perm_means)}次） "
          f"方向感知percentile={null_pct:.1f}（需>={req_pct:.1f}）")

    reasons = []
    if ts["n"] < MIN_N or vs["n"] < MIN_N:
        reasons.append(f"樣本數不足(train_n={ts['n']}, val_n={vs['n']}, 需各>={MIN_N})")
    tm, vm = ts["mean_car"], vs["mean_car"]
    if pd.isna(tm) or pd.isna(vm) or np.sign(tm) != np.sign(vm):
        reasons.append("TRAIN/VAL平均CAR不同號或無法計算")
    if not pd.isna(vm) and np.sign(vm) != sign:
        reasons.append(f"VAL平均CAR方向與事前綁定方向({'+' if sign > 0 else '-'})相反")
    if pd.isna(vs["p_ttest"]) or vs["p_ttest"] >= alpha_adj:
        reasons.append(f"VAL t-test p={vs['p_ttest']:.4f}未達{alpha_adj}")
    if pd.isna(null_pct) or null_pct < req_pct:
        reasons.append(f"控制組percentile={null_pct:.1f}<{req_pct:.1f}")
    passes = not reasons
    print(f"[{label}] === {'PASS' if passes else 'FAIL'} ===" + (f" {reasons}" if reasons else ""))
    return {"label": label, "direction": sign, "train": ts, "val": vs,
            "null_percentile": null_pct, "required_percentile": req_pct,
            "null_mean": float(np.mean(perm_means)) if len(perm_means) else None,
            "null_sd": float(np.std(perm_means)) if len(perm_means) else None,
            "passes": passes, "reasons": reasons}


def main():
    ev, meta = _load_events()
    print("=== #71 減資事件CAR第1關cheap gate ===")
    print(f"驗證進度：{meta['queried']}/{meta['universe']}檔；原因分布（去重後）：{meta['by_reason_all']}")
    mkt = bcg._market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}
    all_red_dates = ev.groupby("stock_id")["reduction_date"].apply(list).to_dict()

    ev = ev[ev["reason"].isin(GROUPS)].copy()
    price_cache: dict[str, dict] = {}
    rows = []
    n_no_price = 0
    for i, sid in enumerate(sorted(ev["stock_id"].unique())):
        pm = bcg._stock_price_map(sid)
        if pm is None:
            n_no_price += 1
            continue
        price_cache[sid] = pm
        for _, r in ev[ev["stock_id"] == sid].iterrows():
            entry_idx = bcg._entry_idx_after(pm["dates"], r["reduction_date"])
            car = bcg._car_for(pm["dates"], pm["adj_close"], mkt_date_idx, mkt["close"], entry_idx)
            if car is None:
                continue
            rows.append({"stock_id": sid, "reason": r["reason"], "reduction_date": r["reduction_date"],
                         "entry_date": pm["dates"][entry_idx], "car": car})
        if (i + 1) % 25 == 0:
            print(f"  progress {i+1}, no_price={n_no_price}, events so far={len(rows)}")
    if not rows:
        print("SANITY FAIL: 零事件可用")
        return
    all_ev = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(all_ev, date_col="entry_date", context="capital_reduction_car_gate events")
    print(f"\n無價格股票{n_no_price}檔；可用事件{len(all_ev)}筆：{all_ev['reason'].value_counts().to_dict()}")

    results = {}
    for reason, sign in GROUPS.items():
        g = all_ev[all_ev["reason"] == reason]
        val_g = holdout.validation_slice(g, date_col="entry_date")
        val_by_stock = val_g.groupby("stock_id").size().to_dict()
        results[reason] = _group_stats(g, sign, val_by_stock, price_cache, mkt_date_idx, mkt["close"],
                                       all_red_dates, reason)
    out = {"meta": meta, "n_no_price": n_no_price, "n_events_usable": len(all_ev),
           "horizon": bcg.FORWARD_HORIZON, "bonferroni_n": BONFERRONI_N, "results": results}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n輸出：{OUT_PATH}")


if __name__ == "__main__":
    main()
