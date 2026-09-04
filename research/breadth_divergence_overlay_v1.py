"""`HYPOTHESIS_QUEUE.md` #28 市場廣度背離（Breadth Divergence）當regime擇時
訊號 —— 第2關隨機控制組（`HYPOTHESIS_QUEUE_PROTOCOL.md`排程，2026-09-04接續，
接在`breadth_divergence_sanity.py`第1關sanity PASS之後）。

**背景**：第1關sanity（`breadth_divergence_sanity.py`）已確認`breadth_pct`/
`divergence_flag`非結構性no-op、方向正確（危機run-up期領先惡化、觸發後前瞻
報酬確實較低）。這輪把`divergence_flag`轉成具體曝險overlay規則，然後做
`HYPOTHESIS_QUEUE.md`#28條目「對照組設計」明訂的隨機控制組：**打亂
`exposure`的時間順序（保留其邊際分布），重新套用到同一組`raw_return`序列上，
證明贏的是「廣度惡化領先指數走弱」這個時序關係本身，不是任意曝險縮放都會
贏**——跟`vol_targeting_v1.py`（#15，已FAIL，percentile 8.0/3.0）、
`spillover_overlay_v1.py`（#19，已FAIL，第6關）同一種第2關設計精神，
沿用同一套`np.random.default_rng().permutation()`打亂法，不重新發明。

**曝險規則（第一版，事前綁定，非搜尋/優化，比照`spillover_overlay_v1.py`
「單邊防禦型」精神）**：
  `exposure[d] = EXPOSURE_DOWN if divergence_flag[d]==True else EXPOSURE_UP`
  `EXPOSURE_DOWN=0.3`（跟`regime_overlay.py`最差組合、`spillover_overlay_v1.py`
  同一個量級，非優化結果）、`EXPOSURE_UP=1.0`（不因訊號正常就加碼超過100%，
  `divergence_flag`為`NaN`的warm-up期視同「未觸發」，維持1.0，不是額外假設）。

**時序對齊（避免未來函數，比照`vol_targeting_v1.py`而非`spillover_overlay_v1.py`
——這裡要shift）**：`divergence_flag[d]`用的是`taiex_mom20[d]`跟
`breadth_60d_change[d]`，兩者都只用到「收盤後才知道」的當天資料（見
`breadth_divergence_sanity.py::build_divergence_frame`），所以`exposure[d]`
最早只能影響下一個交易日的部位——`exposure_lagged=exposure.shift(1)`，
`overlay_return[d] = raw_return[d] * exposure_lagged[d]`，跟`spillover_
overlay_v1.py`的「美股隔夜報酬本身就是台股開盤前已確定的事實、不用shift」
是不同情境，這裡刻意做shift，不是漏做。

**這輪的判定範圍**：只做第2關（隨機控制組），比照`#28`條目協定「先確認
時序關係本身有沒有加值」，若第2關沒過，依快殺標準（已被控制組拆穿之偽影
家族換皮——跟`vol_targeting_v1.py`同一種「改變曝險力道」偽影嫌疑）直接
結案，不進第3關以後；若第2關過關，下一輪再繼續第3(參數高原)/4(成本)/
5(leave-one-out)/6(逐年一致性)/7(OOS，注意這裡TRAIN/VAL本身就是OOS切分)/
8(alpha顯著性)/9(下檔保護)關。
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from breadth_divergence_sanity import (
    build_divergence_frame,
    compute_breadth_series,
    load_breadth_panel,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

EXPOSURE_DOWN = 0.3
EXPOSURE_UP = 1.0
N_DRAWS = 100
SEED = 20260904


def build_overlay_frame() -> pd.DataFrame:
    """完整比照`breadth_divergence_sanity.py::main()`前半段的資料載入路徑，
    加上`exposure`/`exposure_lagged`/`overlay_return`欄位。"""
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in breadth_divergence_overlay_v1")
    market_df = prepare_market_data(market_raw)
    market_df = holdout.cap_to_dev(market_df)

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    panel = load_breadth_panel(sample_ids)
    breadth_df = compute_breadth_series(panel)
    d = build_divergence_frame(breadth_df, market_df)
    holdout.assert_no_holdout_leakage(d, context="divergence frame in breadth_divergence_overlay_v1")

    d = d.sort_values("date").reset_index(drop=True)
    d["raw_return"] = d["close"].pct_change()
    flag_bool = d["divergence_flag"].map(lambda v: bool(v) if pd.notna(v) else False)
    d["exposure"] = np.where(flag_bool, EXPOSURE_DOWN, EXPOSURE_UP)
    d["exposure_lagged"] = d["exposure"].shift(1)
    d.loc[d["exposure_lagged"].isna(), "exposure_lagged"] = EXPOSURE_UP  # 起跑日假設全曝險
    d["overlay_return"] = d["raw_return"] * d["exposure_lagged"]
    d = d[d["raw_return"].notna()].reset_index(drop=True)
    return d


def _metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if len(ret) < 30 or ret.std() == 0:
        return {"total_return_pct": float("nan"), "sharpe": float("nan"), "mdd_pct": float("nan"), "n_days": len(ret)}
    equity = (1 + ret).cumprod()
    total_return = float(equity.iloc[-1] - 1)
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252))
    mdd = float((equity / equity.cummax() - 1).min())
    return {"total_return_pct": total_return * 100, "sharpe": sharpe, "mdd_pct": mdd * 100, "n_days": len(ret)}


def gate2_random_control(d: pd.DataFrame, label: str, n_draws: int = N_DRAWS, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    exposure_vals = d["exposure_lagged"].to_numpy()
    raw_ret = d["raw_return"].to_numpy()

    real_ret = d["overlay_return"]
    real_m = _metrics(real_ret)

    shuffled_sharpes, shuffled_totals, shuffled_mdds = [], [], []
    for _ in range(n_draws):
        perm = rng.permutation(exposure_vals)
        sim_ret = pd.Series(raw_ret * perm)
        m = _metrics(sim_ret)
        if np.isnan(m["sharpe"]):
            continue
        shuffled_sharpes.append(m["sharpe"])
        shuffled_totals.append(m["total_return_pct"])
        shuffled_mdds.append(m["mdd_pct"])

    n_valid = len(shuffled_sharpes)
    sharpe_pctl = 100.0 * float(np.mean(np.array(shuffled_sharpes) <= real_m["sharpe"])) if n_valid else float("nan")
    total_pctl = 100.0 * float(np.mean(np.array(shuffled_totals) <= real_m["total_return_pct"])) if n_valid else float("nan")
    mdd_pctl = 100.0 * float(np.mean(np.array(shuffled_mdds) <= real_m["mdd_pct"])) if n_valid else float("nan")

    print(f"\n--- 第2關隨機控制組 {label}（打亂exposure時序，N={n_valid}draws）---")
    print(f"  真實：total_return={real_m['total_return_pct']:+.2f}%  sharpe={real_m['sharpe']:.3f}  "
          f"mdd={real_m['mdd_pct']:.2f}%  n_days={real_m['n_days']}")
    print(f"  打亂分布：total_return median={np.median(shuffled_totals):+.2f}%  "
          f"sharpe median={np.median(shuffled_sharpes):.3f}  mdd median={np.median(shuffled_mdds):.2f}%")
    print(f"  真實值percentile：total_return={total_pctl:.1f}  sharpe={sharpe_pctl:.1f}  "
          f"mdd={mdd_pctl:.1f}（mdd percentile越高代表真實MDD比多數打亂分布更淺）")

    return {
        "label": label,
        "real_total_return_pct": real_m["total_return_pct"],
        "real_sharpe": real_m["sharpe"],
        "real_mdd_pct": real_m["mdd_pct"],
        "shuffled_total_median_pct": float(np.median(shuffled_totals)) if n_valid else float("nan"),
        "shuffled_sharpe_median": float(np.median(shuffled_sharpes)) if n_valid else float("nan"),
        "total_return_percentile": total_pctl,
        "sharpe_percentile": sharpe_pctl,
        "mdd_percentile": mdd_pctl,
        "n_draws_valid": n_valid,
    }


def main() -> dict:
    t0 = time.time()
    print(f"曝險規則：EXPOSURE_DOWN={EXPOSURE_DOWN}  EXPOSURE_UP={EXPOSURE_UP}（divergence_flag觸發時降曝險）")
    print("載入資料（沿用breadth_divergence_sanity.py同一條路徑）...")
    d = build_overlay_frame()
    print(f"  全期間: {d['date'].iloc[0]} ~ {d['date'].iloc[-1]}, n={len(d)}天")

    train = holdout.cap_to_train(d)
    val = holdout.validation_slice(d)
    print(f"  TRAIN: n={len(train)}天 ({train['date'].iloc[0]}~{train['date'].iloc[-1]})")
    print(f"  VAL:   n={len(val)}天 ({val['date'].iloc[0]}~{val['date'].iloc[-1]})")

    train_base_m = _metrics(train["raw_return"])
    val_base_m = _metrics(val["raw_return"])
    train_over_m = _metrics(train["overlay_return"])
    val_over_m = _metrics(val["overlay_return"])
    print(f"\n  TRAIN: baseline(買進持有)={train_base_m['total_return_pct']:+.2f}%  "
          f"overlay={train_over_m['total_return_pct']:+.2f}%  "
          f"baseline_mdd={train_base_m['mdd_pct']:.2f}%  overlay_mdd={train_over_m['mdd_pct']:.2f}%")
    print(f"  VAL:   baseline(買進持有)={val_base_m['total_return_pct']:+.2f}%  "
          f"overlay={val_over_m['total_return_pct']:+.2f}%  "
          f"baseline_mdd={val_base_m['mdd_pct']:.2f}%  overlay_mdd={val_over_m['mdd_pct']:.2f}%")

    gate2_train = gate2_random_control(train, "TRAIN")
    gate2_val = gate2_random_control(val, "VAL")

    # 判準（比照vol_targeting_v1.py/spillover_overlay_v1.py同一把尺）：兩期
    # total_return percentile皆需>=90.0，任一期未過即快殺，不進第3關以後。
    train_pass = gate2_train["total_return_percentile"] >= 90.0
    val_pass = gate2_val["total_return_percentile"] >= 90.0
    gate2_pass = train_pass and val_pass

    print("\n" + "=" * 70)
    print("第2關綜合判定（門檻：TRAIN/VAL兩期total_return percentile皆>=90.0）")
    print(f"  TRAIN percentile={gate2_train['total_return_percentile']:.1f}  {'PASS' if train_pass else 'FAIL'}")
    print(f"  VAL   percentile={gate2_val['total_return_percentile']:.1f}  {'PASS' if val_pass else 'FAIL'}")
    print(f"  第2關綜合: {'PASS，可進第3關（參數密集高原）' if gate2_pass else 'FAIL，依快殺標準（偽影家族換皮）直接結案，不進第3關以後'}")
    print("=" * 70)

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    d[["date", "close", "breadth_pct", "divergence_flag", "exposure", "exposure_lagged",
       "raw_return", "overlay_return"]].to_csv(out_dir / "breadth_divergence_overlay_v1_series.csv", index=False)

    result = {
        "final_gate": 2,
        "verdict": "PASS" if gate2_pass else "FAIL",
        "gate2_train": gate2_train,
        "gate2_val": gate2_val,
        "train_baseline_metrics": train_base_m,
        "val_baseline_metrics": val_base_m,
        "train_overlay_metrics": train_over_m,
        "val_overlay_metrics": val_over_m,
    }
    print(f"\n(耗時{time.time()-t0:.1f}s)")
    return result


if __name__ == "__main__":
    main()
