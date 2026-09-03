# -*- coding: utf-8 -*-
"""管線校準探針（總司令2026-09-03裁示甲.3）：拿「橫截面12-1動能」（過去12個月報酬、
跳過最近1個月；Jegadeesh & Titman 1993，跨19國最穩健的股票異常之一）當「已知應該有
訊號」的benchmark，過本專案**同一套**cheap gate（`factor_ic.py::evaluate_factor()`：
train/val同號＋|val_ic|>=0.02＋贏過1000次洗牌null的第90百分位）＋組合層gauntlet縮影
（`portfolio_backtest_v2.py`同一個引擎：20檔/流動性門檻/全成本/隨機對照/CAPM alpha）。

目的**不是找策略，是校準管線**，回答一個問題：這套流程對「應該有訊號的東西」到底
看不看得見？
- 結論(甲) 管線正常：12-1動能清楚過關 → 先前#1~#26全FAIL可以接受為「這些軸沒肉」，
  `portfolio_multifactor_v2`的p=0.053視為真的差一點，照SPEC繼續迭代。
- 結論(乙) 檢定力不足：連12-1動能都過不了 / 或只在較大樣本才過 → 樣本N太小或null
  分布不合理，先修管線，並回頭把先前N<30的FAIL標「未定」。

**範圍與誠實揭露**：
1. 12-1動能在這裡用`adj_close.shift(21)/adj_close.shift(252)-1`自算（純價格、天然PIT），
   刻意**不改`factors.py`**（那是馬拉松三軌共用的因子庫，探針不該順手動它）。
2. 「完整gauntlet」九關全部走完對一個校準用的benchmark是過度投入；這裡走的是
   「cheap gate + 組合層第2/4/7關（隨機對照、成本敏感度、train/val樣本外）」，
   足以回答「管線看不看得見已知訊號」；下檔保護(第9關)不是校準要回答的問題。
3. 檢定力診斷用兩個互補角度：(i)解析式——洗牌null的標準差→80%檢定力下的最小可
   偵測IC（MDE=(z0.90+z0.80)·sd_null）；(ii)經驗式——從300檔樣本抽20組100檔子樣本
   各跑一次cheap gate，看「同一個已知訊號」在N≈80的樣本裡被判FAIL的比率（漏殺率）。

輸出：stdout完整記錄 + `data/calibration_probe_momentum_12_1.csv`（gitignored）。
結論人工整理進`CALIBRATION_PROBE.md`。
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, norm

import factor_ic as fic
from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, START_DATE, SNAPSHOT_START, N_SHUFFLES, SHUFFLE_SEED,
    sample_universe_ids, load_sample_with_factors, build_snapshots, evaluate_factor, _cross_section,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

MOM_COL = "f_momentum_12_1"
SKIP_DAYS = 21      # 跳過最近1個月
LOOKBACK_DAYS = 252  # 過去12個月
LARGE_SAMPLE_SIZE = 300
N_SUBSAMPLES = 20
SUBSAMPLE_SIZE = 100
OUT_CSV = Path(__file__).parent / "data" / "calibration_probe_momentum_12_1.csv"

T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def add_momentum(data: dict[str, pd.DataFrame]) -> None:
    for sid, d in data.items():
        d.sort_values("date", inplace=True)
        d.reset_index(drop=True, inplace=True)
        d[MOM_COL] = d["adj_close"].shift(SKIP_DAYS) / d["adj_close"].shift(LOOKBACK_DAYS) - 1.0


def null_sd_and_mde(data, snapshots, factor_col=MOM_COL) -> dict:
    """重算洗牌null（跟evaluate_factor同一個機制、同一個seed），回傳null標準差與
    80%檢定力下的最小可偵測|IC|，以及每期橫截面N的分布。"""
    cross_sections, ns = [], []
    val_ics = []
    for as_of, fwd in snapshots:
        ids, fv, ret = _cross_section(factor_col, (as_of, fwd), data)
        if len(fv) < 10:
            continue
        ic, _ = spearmanr(fv, ret)
        if np.isnan(ic):
            continue
        ns.append(len(fv))
        if holdout.TRAIN_END < as_of <= holdout.VAL_END:
            val_ics.append(ic)
            cross_sections.append((fv, ret))
    rng = random.Random(SHUFFLE_SEED)
    null_means = []
    for _ in range(N_SHUFFLES):
        ics = []
        for fv, ret in cross_sections:
            idx = list(range(len(fv)))
            rng.shuffle(idx)
            ic, _ = spearmanr(fv[idx], ret)
            if not np.isnan(ic):
                ics.append(ic)
        if ics:
            null_means.append(np.mean(ics))
    sd = float(np.std(null_means)) if null_means else float("nan")
    p90 = float(np.percentile(np.abs(null_means), 90)) if null_means else float("nan")
    mde80 = (norm.ppf(0.90) + norm.ppf(0.80)) * sd  # 單尾90%門檻、80%檢定力
    return {
        "n_cs_min": int(min(ns)) if ns else 0, "n_cs_median": float(np.median(ns)) if ns else 0,
        "n_cs_max": int(max(ns)) if ns else 0, "n_val_dates": len(val_ics),
        "null_sd": sd, "null_abs_p90": p90, "mde_ic_80pct_power": float(mde80),
        "val_mean_ic": float(np.mean(val_ics)) if val_ics else float("nan"),
        "val_ic_sd": float(np.std(val_ics)) if len(val_ics) > 1 else float("nan"),
    }


def cheap_gate(label, data, snapshots) -> dict:
    r = evaluate_factor(MOM_COL, data, snapshots, bonferroni_n=1)
    row = {
        "part": label, "n_names": len(data),
        "train_mean_ic": r.train_mean_ic, "train_ir": r.train_ic_ir, "n_train_dates": r.n_dates_train,
        "val_mean_ic": r.val_mean_ic, "val_ir": r.val_ic_ir, "val_hit_rate": r.val_hit_rate,
        "n_val_dates": r.n_dates_val, "null_percentile": r.null_percentile,
        "required_percentile": r.required_percentile, "same_sign": r.same_sign,
        "passes": r.passes, "reasons": "; ".join(r.reasons),
    }
    log(f"{label}: names={len(data)} train_ic={r.train_mean_ic:+.4f}(n={r.n_dates_train}) "
        f"val_ic={r.val_mean_ic:+.4f} IR={r.val_ic_ir:+.3f} hit={r.val_hit_rate:.2f}(n={r.n_dates_val}) "
        f"null_pct={r.null_percentile:.1f}/{r.required_percentile:.1f} same_sign={r.same_sign} "
        f"PASS={r.passes} {r.reasons}")
    return row


def portfolio_probe(data, market_df, rows: list[dict]) -> None:
    """組合層gauntlet縮影：借`portfolio_backtest_v2.py`同一個引擎，成分只有12-1動能
    （等權；MIN_COMPONENTS_FOR_RANKING暫調為1，因為只有一個成分）。TRAIN期快速版，
    VAL期完整版（成本1x/2x/3x + 30次配對隨機對照）。"""
    import portfolio_backtest_v2 as pb2
    import score as score_mod

    orig_raw = pb2._raw_components
    orig_min = score_mod.MIN_COMPONENTS_FOR_RANKING

    def raw_with_mom(row: pd.Series) -> dict:
        out = orig_raw(row)
        v = row.get(MOM_COL)
        out["momentum_12_1"] = float(v) if pd.notna(v) else None
        return out

    pb2._raw_components = raw_with_mom
    pb2.FACTOR_VERSIONS["MOM_12_1_probe"] = ["momentum_12_1"]
    pb2.IC_WEIGHTS["momentum_12_1"] = 1.0
    score_mod.MIN_COMPONENTS_FOR_RANKING = 1
    try:
        industry_map = pb2.load_industry_map()
        trend_regime = pb2._trend_regime_series(market_df)
        liquidity = {sid: pb2._liquidity_proxy_series(d) for sid, d in data.items()}
        for cadence in ("quarterly", "monthly"):
            for label, start, end, full in (
                ("TRAIN", "2015-01-01", holdout.TRAIN_END, False),
                ("VALIDATION", "2021-01-01", holdout.VAL_END, cadence == "quarterly"),
            ):
                r = pb2.run_one("MOM_12_1_probe", "equal", cadence, label, data, market_df, industry_map,
                                trend_regime, liquidity, start, end,
                                do_cost_sensitivity=full, do_random_control=full, n_random=30)
                r["part"] = f"portfolio_{cadence}_{label}"
                r["n_names"] = len(data)
                rows.append(r)
                log(f"portfolio {cadence}/{label}: ret={r['return_pct']:+.2f}% MDD={r['mdd_pct']:.2f}% "
                    f"Sortino={r['sortino']:.3f} alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f}) "
                    f"beta={r['beta']:+.3f} B&H={r['buy_and_hold_index_pct']:+.2f}% trades={r['n_trades']} "
                    + (f"random_pct={r['random_control_percentile']:.1f} (median {r['random_control_median_pct']:+.2f}%) "
                       f"cost1x/2x/3x={r['cost_1x']:+.2f}/{r['cost_2x']:+.2f}/{r['cost_3x']:+.2f}" if full else ""))
    finally:
        pb2._raw_components = orig_raw
        score_mod.MIN_COMPONENTS_FOR_RANKING = orig_min
        pb2.FACTOR_VERSIONS.pop("MOM_12_1_probe", None)
        pb2.IC_WEIGHTS.pop("momentum_12_1", None)


def save(rows: list[dict]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")
    log(f"已存 {OUT_CSV}（{len(rows)}列）")


def main() -> None:
    rows: list[dict] = []
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in calibration_probe")
    market_df = prepare_market_data(market_raw)
    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    log(f"snapshots={len(snapshots)}（{SNAPSHOT_START}..{holdout.VAL_END}，20交易日不重疊）")

    # ---------- A. 標準100檔樣本（跟#1~#27所有cheap gate同一個樣本/seed） ----------
    ids100 = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    data100 = load_sample_with_factors(ids100, market_df)
    add_momentum(data100)
    log(f"A. 標準樣本可用 {len(data100)}/{len(ids100)} 檔")
    rows.append(cheap_gate("A_cheap_gate_sample100", data100, snapshots))

    # ---------- B. 檢定力診斷（100檔） ----------
    diag = null_sd_and_mde(data100, snapshots)
    diag.update({"part": "B_power_diag_sample100", "n_names": len(data100)})
    rows.append(diag)
    log(f"B. 每期橫截面N min/median/max={diag['n_cs_min']}/{diag['n_cs_median']}/{diag['n_cs_max']}，"
        f"val期數={diag['n_val_dates']}，null sd={diag['null_sd']:.4f}，|null| p90={diag['null_abs_p90']:.4f}，"
        f"80%檢定力最小可偵測|IC|={diag['mde_ic_80pct_power']:.4f}，實際val IC={diag['val_mean_ic']:+.4f}")
    save(rows)

    # ---------- D. 組合層gauntlet縮影（100檔，跟portfolio_multifactor_v2同樣本） ----------
    try:
        portfolio_probe(data100, market_df, rows)
    except Exception as e:  # noqa: BLE001
        log(f"D. 組合層探針失敗（記錄後繼續）：{type(e).__name__}: {e}")
        rows.append({"part": "portfolio_probe_error", "reasons": f"{type(e).__name__}: {e}"})
    save(rows)

    # ---------- C. 300檔大樣本 + 20組100檔子樣本漏殺率 ----------
    ids300 = sample_universe_ids(LARGE_SAMPLE_SIZE, SAMPLE_SEED)
    log(f"C. 載入{LARGE_SAMPLE_SIZE}檔大樣本（含標準100檔的{len(set(ids300) & set(ids100))}檔）...")
    data300 = load_sample_with_factors(ids300, market_df)
    add_momentum(data300)
    log(f"C. 大樣本可用 {len(data300)}/{len(ids300)} 檔")
    rows.append(cheap_gate("C_cheap_gate_sample300", data300, snapshots))
    diag3 = null_sd_and_mde(data300, snapshots)
    diag3.update({"part": "C_power_diag_sample300", "n_names": len(data300)})
    rows.append(diag3)
    log(f"C. 300檔：每期N min/median/max={diag3['n_cs_min']}/{diag3['n_cs_median']}/{diag3['n_cs_max']}，"
        f"null sd={diag3['null_sd']:.4f}，MDE={diag3['mde_ic_80pct_power']:.4f}，val IC={diag3['val_mean_ic']:+.4f}")
    save(rows)

    rng = random.Random(20260904)
    all_ids = sorted(data300.keys())
    n_pass = 0
    sub_rows = []
    for k in range(N_SUBSAMPLES):
        pick = rng.sample(all_ids, min(SUBSAMPLE_SIZE, len(all_ids)))
        sub = {sid: data300[sid] for sid in pick}
        r = evaluate_factor(MOM_COL, sub, snapshots, bonferroni_n=1)
        n_pass += int(r.passes)
        sub_rows.append({"part": f"C_subsample_{k+1}", "n_names": len(sub), "val_mean_ic": r.val_mean_ic,
                         "train_mean_ic": r.train_mean_ic, "null_percentile": r.null_percentile,
                         "same_sign": r.same_sign, "passes": r.passes, "reasons": "; ".join(r.reasons)})
        log(f"C. 子樣本{k+1}/{N_SUBSAMPLES}: val_ic={r.val_mean_ic:+.4f} pct={r.null_percentile:.1f} PASS={r.passes}")
    rows.extend(sub_rows)
    rows.append({"part": "C_subsample_summary", "n_names": SUBSAMPLE_SIZE, "reasons": f"{n_pass}/{N_SUBSAMPLES} PASS",
                 "val_mean_ic": float(np.mean([s['val_mean_ic'] for s in sub_rows]))})
    log(f"C. 100檔子樣本cheap gate通過率 {n_pass}/{N_SUBSAMPLES}（漏殺率 {(N_SUBSAMPLES-n_pass)/N_SUBSAMPLES:.0%}）")
    save(rows)
    log("完成")


if __name__ == "__main__":
    main()
