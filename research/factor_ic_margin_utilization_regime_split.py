"""`HYPOTHESIS_QUEUE.md` #30 個股融資使用率——deep_dive第一步：下跌段vs上漲段
分組IC（regime-conditional IC），而非新的random control組合回測。

**為什麼先做這個而不是直接跳去建portfolio層random control**：`#30`條目
「經濟理由」段落的核心主張是**條件式**的——融資使用率高的股票之所以危險，
是因為下跌時觸發斷頭賣壓（Brunnermeier & Pedersen margin spiral），這個
機制在上漲段未必成立（上漲段融資使用率高可能只是散戶追高的結果，不必然
預測未來報酬）。第1關cheap gate只證明了**unconditional**（不分漲跌）IC
存在（TRAIN/VAL皆負、null percentile=100.0），但這還沒驗證假設的**核心
機制**——下一步理論上該直接測這個，而不是先花7~10分鐘算力去建一個尚未
確認機制對不對的portfolio。這個測試完全複用`factor_ic.py`既有基礎設施
（`load_sample_with_factors`已有磁碟快取、`evaluate_factor`本身就是純
numpy/scipy運算，不需要新的網路請求），便宜且決定性，符合協定「快殺標準：
只能用便宜且決定性的證據」的精神，也直接對應`HYPOTHESIS_QUEUE.md`#30條目
「下檔保護要求」小節明訂的deep_dive第一步。

**分組方法**：沿用`factor_ic.py::build_snapshots()`產生的相同
(as_of, forward)快照配對，用TAIEX大盤在同一個窗口的報酬（`market_df`
的`close`欄位，forward/as_of - 1）分成「下跌段」（大盤報酬<0）與「上漲段」
（大盤報酬>=0）兩組快照，分別餵進`evaluate_factor()`（它本身就會依
`holdout.TRAIN_END`/`VAL_END`把snapshot切成train/val子集，這裡不用重寫
這段邏輯，只是先過濾snapshot清單再呼叫）。

**判讀方式（事前寫明，避免事後移動門柱）**：核心主張若成立，預期看到
下跌段VAL期|mean_ic|明顯大於上漲段VAL期|mean_ic|（且方向仍為負）。這一步
本身不是PASS/FAIL的最終判準（樣本數變小、shuffle null的統計檢定力也會
下降，只是探索性證據），但如果下跌段訊號沒有比上漲段明顯更強（甚至方向
不一致），就是對假設核心機制主張的一個警訊，該記錄下來、供下一輪決定是否
值得投入full portfolio random control時參考，不能只看unconditional IC
就直接判斷「機制成立」。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續新增，佇列#30第2關
（deep_dive）第一步，尚未做隨機控制組（≥100 draws）portfolio層測試。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, START_DATE, SNAPSHOT_START,
    build_snapshots, evaluate_factor, load_sample_with_factors, sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

FACTOR_COL = "f_margin_utilization"


def _classify_snapshots(snapshots: list[tuple[str, str]], market_df: pd.DataFrame) -> tuple[list, list]:
    """依同一個(as_of, fwd)窗口內大盤(TAIEX)報酬正負，把snapshot分成
    down（報酬<0）跟up（報酬>=0）兩組。缺大盤資料的快照（理論上不該發生，
    market_df來源跟snapshot calendar同一份）直接跳過並警告。
    """
    close_by_date = dict(zip(market_df["date"], market_df["close"]))
    down, up = [], []
    skipped = 0
    for as_of, fwd in snapshots:
        p0 = close_by_date.get(as_of)
        p1 = close_by_date.get(fwd)
        if p0 is None or p1 is None or p0 <= 0:
            skipped += 1
            continue
        mkt_ret = p1 / p0 - 1
        (down if mkt_ret < 0 else up).append((as_of, fwd))
    if skipped:
        print(f"  警告：{skipped}個快照缺大盤價格，已跳過（不影響down/up分類，僅記錄）")
    return down, up


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in factor_ic_margin_utilization_regime_split")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    calendar = sorted(market_df["date"].tolist())
    all_snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(all_snapshots)} total non-overlapping 20-trading-day snapshots, "
          f"{SNAPSHOT_START}..{holdout.VAL_END}")

    down_snapshots, up_snapshots = _classify_snapshots(all_snapshots, market_df)
    print(f"  down-market快照={len(down_snapshots)}  up-market快照={len(up_snapshots)}")

    print("\n========== 下跌段（TAIEX窗口報酬<0）分組IC ==========")
    down_result = evaluate_factor(FACTOR_COL, data, down_snapshots, bonferroni_n=1)
    print(f"  train: mean_ic={down_result.train_mean_ic:+.4f} IR={down_result.train_ic_ir:+.3f} (n={down_result.n_dates_train} dates)")
    print(f"  val:   mean_ic={down_result.val_mean_ic:+.4f} IR={down_result.val_ic_ir:+.3f} hit_rate={down_result.val_hit_rate:.2f} (n={down_result.n_dates_val} dates)")
    print(f"  null percentile: {down_result.null_percentile:.1f} (need >={down_result.required_percentile:.1f})  same_sign: {down_result.same_sign}")

    print("\n========== 上漲段（TAIEX窗口報酬>=0）分組IC ==========")
    up_result = evaluate_factor(FACTOR_COL, data, up_snapshots, bonferroni_n=1)
    print(f"  train: mean_ic={up_result.train_mean_ic:+.4f} IR={up_result.train_ic_ir:+.3f} (n={up_result.n_dates_train} dates)")
    print(f"  val:   mean_ic={up_result.val_mean_ic:+.4f} IR={up_result.val_ic_ir:+.3f} hit_rate={up_result.val_hit_rate:.2f} (n={up_result.n_dates_val} dates)")
    print(f"  null percentile: {up_result.null_percentile:.1f} (need >={up_result.required_percentile:.1f})  same_sign: {up_result.same_sign}")

    print("\n========== 比較（探索性，非最終判準）==========")
    down_val_abs = abs(down_result.val_mean_ic) if not np.isnan(down_result.val_mean_ic) else float("nan")
    up_val_abs = abs(up_result.val_mean_ic) if not np.isnan(up_result.val_mean_ic) else float("nan")
    stronger_in_down = (not np.isnan(down_val_abs) and not np.isnan(up_val_abs) and down_val_abs > up_val_abs)
    print(f"  VAL期下跌段|IC|={down_val_abs:.4f}  vs  上漲段|IC|={up_val_abs:.4f}")
    print(f"  核心主張（下跌段訊號應更強）：{'符合' if stronger_in_down else '不符合，需記錄為警訊'}")

    out = pd.DataFrame([
        {"regime": "down", "train_mean_ic": down_result.train_mean_ic, "val_mean_ic": down_result.val_mean_ic,
         "null_percentile": down_result.null_percentile, "same_sign": down_result.same_sign,
         "n_dates_train": down_result.n_dates_train, "n_dates_val": down_result.n_dates_val},
        {"regime": "up", "train_mean_ic": up_result.train_mean_ic, "val_mean_ic": up_result.val_mean_ic,
         "null_percentile": up_result.null_percentile, "same_sign": up_result.same_sign,
         "n_dates_train": up_result.n_dates_train, "n_dates_val": up_result.n_dates_val},
    ])
    out.to_csv("data/factor_ic_margin_utilization_regime_split_results.csv", index=False)
    print("\n已存 data/factor_ic_margin_utilization_regime_split_results.csv")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
