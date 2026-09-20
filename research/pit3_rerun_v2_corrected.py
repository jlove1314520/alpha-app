"""財報PIT.三（2026-09-20，驗證帽）：量化「portfolio_multifactor_v2 的 p=0.053 alpha
有多少來自 Q4 財報前視」。

設計（執行前凍結，結果出來後不得回頭改）：
- 同一批樣本（`safe_pool_ids()` 排序後前300檔，跟 round327 `run_bigsample_300.py`
  與 `train_only_ic_weight_bigsample.py` 同一批）、同一個 process 內跑兩個對照臂：
    * `legacy_q4_lookahead`：monkeypatch `pit.statutory_quarterly_pit_date` 回舊行為
      （所有季別一律期末+45日，Q4=次年2/14）——用來確認本腳本能重現舊快照
      （對照 `data/portfolio_backtest_v2_bigsample300_quick_scan.csv`），
      證明兩臂差異只來自 PIT 日期，不是別的東西。
    * `corrected`：現行 `pit.py`（Q4=次年3/31）。
- 每臂6種權重模式（A_4pass 三成分 eps_family/revenue_surprise/low_vol）：
    equal／ic_weighted(寫死舊常數)／regime_weighted(寫死舊常數)／
    ic_weighted_valIC／regime_weighted_valIC（該臂自己的資料重算 val IC，
    複製原設計，含其「用VAL算權重再回測VAL」的洩漏缺陷，僅為量化交辦所問）／
    ic_weighted_train_only（該臂自己的 TRAIN IC，無洩漏版）。
- 月頻＋季頻 × TRAIN(2015~TRAIN_END)＋VALIDATION(2021~VAL_END)，1x成本、
  無隨機控制組（quick scan，跟既有 bigsample300 同口徑）。
- 只用 TRAIN+VAL 資料，不碰 holdout（載入函式內已有 assert_no_holdout_leakage）。
- 零新增 API 呼叫（純讀本機快取）。

判定分支（交辦原文）：修正後 alpha p>0.1 或 alpha 轉負→證據作廢；
仍 p<0.06→仍 FAIL 但標「不依賴前視的alpha殘存」；不得逕稱通過。
"""
from __future__ import annotations
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import pit
import portfolio_backtest_v2 as pv2
from factor_ic import _cross_section, build_snapshots
from finmind_client import load_dev
from portfolio_backtest_v2_bigsample import load_safe_sample, safe_pool_ids
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

START_DATE = "2010-01-01"
SNAPSHOT_START = "2015-01-01"
COMP_COLS = {
    "eps_family": ["f_eps_growth", "f_eps_surprise"],
    "revenue_surprise": ["f_revenue_surprise"],
    "low_vol": ["f_low_vol"],
}
OUT = Path(__file__).parent / "data" / "pit3_rerun_v2_corrected.csv"
OUT_W = Path(__file__).parent / "data" / "pit3_rerun_v2_corrected_weights.json"

_ORIG_STAT = pit.statutory_quarterly_pit_date


def _legacy_pit_date(period_end) -> pd.Timestamp:
    """舊行為：一律期末+45日（Q4=次年2/14，含約6週前視）。"""
    return pd.Timestamp(period_end) + pd.Timedelta(days=45)


def _ic_series(col: str, data, snapshots):
    """回傳 [(as_of, ic)]，門檻與 factor_ic.evaluate_factor 相同（橫斷面≥10檔）。"""
    out = []
    for as_of, fwd in snapshots:
        _ids, fv, ret = _cross_section(col, (as_of, fwd), data)
        if len(fv) < 10:
            continue
        ic, _ = spearmanr(fv, ret)
        if not np.isnan(ic):
            out.append((as_of, float(ic)))
    return out


def _mean_abs(ics):
    return abs(float(np.mean(ics))) if ics else float("nan")


def compute_weight_sets(data, snapshots, trend_regime):
    """回傳 (val_ic_weights, val_ic_regime_weights, train_only_weights, 診斷資訊)。"""
    per_col = {}
    for cols in COMP_COLS.values():
        for c in cols:
            per_col[c] = _ic_series(c, data, snapshots)

    def comp_weight(pred):
        w = {}
        for comp, cols in COMP_COLS.items():
            vals = []
            for c in cols:
                v = _mean_abs([ic for d, ic in per_col[c] if pred(d)])
                if not np.isnan(v):
                    vals.append(v)
            w[comp] = float(np.mean(vals)) if vals else 0.0
        return w

    def in_val(d):
        return holdout.TRAIN_END < d <= holdout.VAL_END

    def in_train(d):
        return d <= holdout.TRAIN_END

    def regime_of(d):
        return trend_regime.loc[d] if d in trend_regime.index else "bull_above_ma"

    val_w = comp_weight(in_val)
    train_w = comp_weight(in_train)
    regime_w = {r: comp_weight(lambda d, r=r: in_val(d) and regime_of(d) == r)
                for r in ("bull_above_ma", "bear_below_ma")}
    n_snap = {r: sum(1 for d, _ in per_col["f_low_vol"] if in_val(d) and regime_of(d) == r)
              for r in ("bull_above_ma", "bear_below_ma")}
    signed_val = {c: float(np.mean([ic for d, ic in per_col[c] if in_val(d)]))
                  if any(in_val(d) for d, _ in per_col[c]) else None for c in per_col}
    return val_w, regime_w, train_w, {"n_val_snapshots_by_regime": n_snap, "signed_val_mean_ic": signed_val}


def run_arm(arm: str, sample_ids, market_df, industry_map, trend_regime, snapshots):
    pit.statutory_quarterly_pit_date = _legacy_pit_date if arm == "legacy_q4_lookahead" else _ORIG_STAT
    print(f"\n######## 臂：{arm} ########", flush=True)
    data = load_safe_sample(sample_ids)
    print(f"  載入 {len(data)}/{len(sample_ids)} 檔", flush=True)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in pit3_rerun {arm}")
    liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}

    val_w, regime_w, train_w, diag = compute_weight_sets(data, snapshots, trend_regime)
    print(f"  valIC權重={val_w}\n  regime valIC權重={regime_w}\n  trainIC權重={train_w}\n  診斷={diag}", flush=True)

    hard_ic = dict(pv2.IC_WEIGHTS)
    hard_reg = {k: dict(v) for k, v in pv2.REGIME_IC_WEIGHTS_TREND.items()}
    modes = [
        ("equal", "equal", hard_ic, hard_reg),
        ("ic_weighted_hardcoded", "ic_weighted", hard_ic, hard_reg),
        ("regime_weighted_hardcoded", "regime_weighted", hard_ic, hard_reg),
        ("ic_weighted_valIC", "ic_weighted", val_w, hard_reg),
        ("regime_weighted_valIC", "regime_weighted", hard_ic, regime_w),
        ("ic_weighted_train_only", "ic_weighted", train_w, hard_reg),
    ]
    rows = []
    try:
        for label_mode, run_mode, ic_w, reg_w in modes:
            pv2.IC_WEIGHTS = ic_w
            pv2.REGIME_IC_WEIGHTS_TREND = reg_w
            for cadence in ("monthly", "quarterly"):
                for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                                          ("VALIDATION", "2021-01-01", holdout.VAL_END)):
                    r = pv2.run_one("A_4pass", run_mode, cadence, label, data, market_df, industry_map,
                                    trend_regime, liquidity, start, end,
                                    do_cost_sensitivity=False, do_random_control=False)
                    r["arm"] = arm
                    r["weight_mode"] = label_mode
                    r["n_stocks"] = len(data)
                    rows.append(r)
                    print(f"  {label_mode}/{cadence}/{label}: 報酬={r['return_pct']:+.2f}% "
                          f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f}) "
                          f"MDD={r['mdd_pct']:.2f}% 大盤={r['buy_and_hold_index_pct']:+.2f}%", flush=True)
    finally:
        pv2.IC_WEIGHTS = hard_ic
        pv2.REGIME_IC_WEIGHTS_TREND = hard_reg
        pit.statutory_quarterly_pit_date = _ORIG_STAT
    return rows, {"val_w": val_w, "regime_w": regime_w, "train_w": train_w, **diag}


def main():
    all_ids = safe_pool_ids()
    sample_ids = all_ids[:300]
    print(f"pool total={len(all_ids)}, using first 300: {sample_ids[0]}..{sample_ids[-1]}", flush=True)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in pit3_rerun_v2_corrected")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    snapshots = build_snapshots(sorted(market_df["date"].tolist()), SNAPSHOT_START, holdout.VAL_END)
    print(f"{len(snapshots)} snapshots {SNAPSHOT_START}..{holdout.VAL_END}", flush=True)

    all_rows, weights = [], {}
    for arm in ("corrected", "legacy_q4_lookahead"):  # 先跑最重要的修正臂，session被砍也有主結果
        rows, w = run_arm(arm, sample_ids, market_df, industry_map, trend_regime, snapshots)
        all_rows += rows
        weights[arm] = w
        pd.DataFrame(all_rows).to_csv(OUT, index=False)
        OUT_W.write_text(json.dumps(weights, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  已存 {OUT.name}（累計 {len(all_rows)} 列）", flush=True)

    df = pd.DataFrame(all_rows)
    piv = df.pivot_table(index=["weight_mode", "cadence", "label"], columns="arm",
                         values=["alpha_ann_pct", "alpha_pvalue"])
    print("\n=== 兩臂對照（alpha年化% / p值）===")
    print(piv.round(4).to_string())

    # 重現檢查：legacy臂 vs 既有快照（equal 與 ic_weighted_hardcoded 兩種在舊CSV裡存在的模式）
    try:
        old = pd.read_csv(Path(__file__).parent / "data" / "portfolio_backtest_v2_bigsample300_quick_scan.csv")
        name_map = {"equal": "equal", "ic_weighted_hardcoded": "ic_weighted",
                    "regime_weighted_hardcoded": "regime_weighted"}
        print("\n=== legacy臂重現檢查（對照既有 bigsample300 快照，alpha p 差）===")
        for lm, om in name_map.items():
            for _, o in old[old["weight_mode"] == om].iterrows():
                m = df[(df["arm"] == "legacy_q4_lookahead") & (df["weight_mode"] == lm)
                       & (df["cadence"] == o["cadence"]) & (df["label"] == o["label"])]
                if not m.empty:
                    print(f"  {lm}/{o['cadence']}/{o['label']}: 舊p={o['alpha_pvalue']:.4f} "
                          f"legacy臂p={m.iloc[0]['alpha_pvalue']:.4f} 差={m.iloc[0]['alpha_pvalue']-o['alpha_pvalue']:+.4f}")
    except Exception as e:  # noqa: BLE001 -- 對照檢查失敗不影響主結果
        print(f"（重現檢查失敗：{e!r}，主結果已存）", flush=True)


if __name__ == "__main__":
    main()
