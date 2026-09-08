"""`HYPOTHESIS_QUEUE.md` #52 事件反應速度 — 第2關：方向性延續檢定（PEAD式漂移）。

背景：gate1（`material_news_car_gate.py`）測到8類中4類（併購/增減資/財務/人事）
「事件日+次一交易日」CAR絕對值震幅顯著大於控制組，但這只證明「異常反應存在」，
不等於「可交易」——如果反應在T+1當天就完全反應完畢，事後看到訊號時已經來不及
進場。這一關測的是：**看到reaction_day+1的初始反應方向後才進場，接下來H個交易日
是否還有可預測的延續（同向漂移，PEAD-style），而不是均值回歸或雜訊**。

**事前綁定規格（唯一，不事後調整）**：
- 只測gate1已PASS的4類：併購、增減資、財務、人事。
- car0（初始反應，帶正負號）＝跟gate1同一個CAR窗口 [reaction_day前一交易日收盤,
  reaction_day+1收盤]，但**不取絕對值**（gate1只看震幅，這裡要看方向）。
- 延續窗口 = [reaction_day+1, reaction_day+1+H]，H=5個交易日（進場點＝看到car0後才
  進場，即reaction_day+1收盤價，跟gate1的CAR窗口終點同一天，不重疊未來資訊）。
- signal_stat = VAL期（TRAIN_END < reaction_date <= VAL_END）mean(sign(car0_i) *
  post_ret_i)。>0代表「跟著初始反應方向進場、持有H天」平均能賺到超額報酬
  （動能/延續）；<0代表反轉。
- 控制組兩變體、各N=200（同`control_group_standard.py`2026-09-07升級標準，
  訊號須嚴格大於全部400次抽樣最大值）：
  (a) sign_shuffle：固定post_ret_i不動，隨機打散sign(car0)與post_ret的配對關係，
      算mean(shuffled_sign_i * post_ret_i)——測「car0方向本身是否有預測力」，
      不是巧合的post_ret本身均值不為零。
  (b) random_window：固定sign(car0_i)不動，把post_ret_i換成同一檔股票VAL期內
      隨機一段等長(H天)非事件延續窗口的signed超額報酬——測「car0方向對『任意』
      未來窗口是否有效」，排除「這個特定H=5窗口本身剛好有大盤層級趨勢」的偽陽性。
- 零新增API呼叫：完全重用`material_news_car_gate.py`已快取的價格檔案與事件表，
  只新增H天延續窗口所需的valid index，不觸發任何新fetch。

2026-09-09 馬拉松TW軌round467新增（接續hypothesis_queue排程01:57輪次的「下一輪
待辦(1)」）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import material_news_car_gate as gate1
from control_group_standard import evaluate_vs_control
from validation import holdout

H = 5  # 延續窗口長度（交易日）
N_PERMUTATIONS = 200
PERM_SEED = 20260909
PASS_CATEGORIES = ["併購", "增減資", "財務", "人事"]  # gate1已PASS的4類，事前寫死
OUT_JSON = Path(__file__).parent / "data" / "material_news_car_gate2_continuation_result.json"


def _signed_ret(dates: list[str], close: np.ndarray, mkt_idx: dict, mkt_close: np.ndarray,
                 start_idx: int, end_idx: int) -> float | None:
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


def _load_price_map_ext(stock_id: str):
    """複用gate1的_load_price_map，額外附加H天延續窗口的valid index。"""
    pm = gate1._load_price_map(stock_id)
    if pm is None:
        return None
    dates = pm["dates"]
    valid_idx_val_h = np.array(
        [i for i, d in enumerate(dates)
         if holdout.TRAIN_END < d <= holdout.VAL_END and i > 0 and i + H < len(dates)],
        dtype=np.int64,
    )
    pm["valid_idx_val_h"] = valid_idx_val_h
    return pm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None)
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS)
    args = ap.parse_args()

    print("=== 假設#52 事件反應速度 gate2 方向性延續檢定（PEAD式漂移）===")
    ev, meta = gate1._build_events(max_stocks=args.max_stocks, max_categories=None)
    ev = ev[ev["type"].isin(PASS_CATEGORIES)].copy()
    print(f"事件表過濾後（4類gate1-PASS+已快取股票）：{len(ev)}筆，"
          f"涉及股票{ev['stock_id'].nunique()}檔")

    holdout.assert_no_holdout_leakage(ev, date_col="price_date", context="car_gate2 events (raw)")

    mkt = gate1._market_map()

    price_cache: dict[str, dict] = {}
    stock_ids = sorted(ev["stock_id"].unique())
    for i, sid in enumerate(stock_ids):
        pm = _load_price_map_ext(sid)
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
        ridx = gate1._reaction_idx(pm["dates"], r.price_date, bool(r.after_close))
        if ridx is None:
            continue
        car0_end = ridx + gate1.CAR_HORIZON  # = ridx+1，跟gate1同一終點
        car0 = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], ridx - 1, car0_end)
        post_ret = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], car0_end, car0_end + H)
        if car0 is None or post_ret is None or car0 == 0:
            continue
        rows.append({"stock_id": r.stock_id, "type": r.type, "reaction_idx_date": pm["dates"][ridx],
                     "car0": car0, "post_ret": post_ret})

    if not rows:
        print("SANITY FAIL：零事件可用（資料層問題，非無訊號）。")
        result = {"sanity_fail": True}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(df, date_col="reaction_idx_date", context="car_gate2 events (final)")
    print(f"\n可用事件總數：{len(df)}（{df['stock_id'].nunique()}檔股票）")

    train_mask = df["reaction_idx_date"] <= holdout.TRAIN_END
    val_mask = (df["reaction_idx_date"] > holdout.TRAIN_END) & (df["reaction_idx_date"] <= holdout.VAL_END)
    train_df, val_df = df[train_mask], df[val_mask]

    rng = np.random.RandomState(PERM_SEED)
    results = {}
    for cat in PASS_CATEGORIES:
        cat_train = train_df[train_df["type"] == cat]
        cat_val = val_df[val_df["type"] == cat]
        n_train, n_val = len(cat_train), len(cat_val)
        if n_val < 20:
            results[cat] = {"n_train": n_train, "n_val": n_val, "skipped": "n_val<20"}
            print(f"\n[{cat}] n_val={n_val}<20，跳過")
            continue

        signs = np.sign(cat_val["car0"].to_numpy())
        post_rets = cat_val["post_ret"].to_numpy()
        stock_ids_val = cat_val["stock_id"].tolist()
        signal_stat = float(np.mean(signs * post_rets))

        # 控制組(a) sign_shuffle：固定post_rets，隨機打散signs的配對
        shuffle_draws = []
        for _ in range(args.n_permutations):
            perm_signs = rng.permutation(signs)
            shuffle_draws.append(float(np.mean(perm_signs * post_rets)))

        # 控制組(b) random_window：固定signs，post_ret換成同股票VAL期隨機一段H天非事件窗口
        window_draws = []
        for _ in range(args.n_permutations):
            pseudo = []
            for sid, sgn in zip(stock_ids_val, signs):
                pm = price_cache.get(sid)
                if pm is None or len(pm["valid_idx_val_h"]) == 0:
                    continue
                idx = int(rng.choice(pm["valid_idx_val_h"]))
                r = _signed_ret(pm["dates"], pm["close"], mkt["idx"], mkt["close"], idx, idx + H)
                if r is not None:
                    pseudo.append(sgn * r)
            if pseudo:
                window_draws.append(float(np.mean(pseudo)))

        control_draws = {}
        if len(shuffle_draws) >= 20:
            control_draws["sign_shuffle"] = shuffle_draws
        if len(window_draws) >= 20:
            control_draws["random_window"] = window_draws

        if len(control_draws) < 2:
            results[cat] = {"n_train": n_train, "n_val": n_val, "signal_stat": signal_stat,
                             "skipped": f"control_draws變體不足({list(control_draws.keys())})"}
            print(f"\n[{cat}] 控制組變體不足：{list(control_draws.keys())}")
            continue

        verdict = evaluate_vs_control(
            signal_stat=signal_stat,
            control_draws=control_draws,
            selection_spec=(f"#52事件反應速度gate2延續檢定，事前綁定：type={cat}，VAL期"
                             f"mean(sign(car0)*post_ret)，car0=gate1同窗口signed版，"
                             f"post_ret=[reaction_day+1, reaction_day+1+{H}]signed超額報酬；"
                             f"唯一選點，不依結果回頭調整H或分類。"),
        )
        results[cat] = {
            "n_train": n_train, "n_val": n_val, "signal_stat": signal_stat,
            "train_signal_stat": float(np.mean(np.sign(cat_train["car0"]) * cat_train["post_ret"])) if n_train else None,
            "pct_continuation": float(np.mean(np.sign(signs * post_rets) > 0)) if n_val else None,
            "passed": verdict.passed, "reason": verdict.reason,
            "control_max": verdict.control_max, "control_mean": verdict.control_mean,
            "control_percentile": verdict.control_percentile, "n_variants": verdict.n_variants,
            "n_draws_total": verdict.n_draws_total, "selection_sha256": verdict.selection_sha256,
        }
        print(f"\n[{cat}] n_train={n_train} n_val={n_val} "
              f"VAL_signal(mean sign*post_ret)={signal_stat:.5f} "
              f"{'PASS' if verdict.passed else 'FAIL'}: {verdict.reason}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    n_pass = sum(1 for r in results.values() if r.get("passed"))
    print(f"\n=== 4類中共{n_pass}類PASS（方向性延續，非僅震幅）===")
    return results


if __name__ == "__main__":
    main()
