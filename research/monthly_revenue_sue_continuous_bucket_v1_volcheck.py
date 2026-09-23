# -*- coding: utf-8 -*-
"""`monthly_revenue_sue_continuous_bucket_v1.py`（`TRIALS_LEDGER.md`#368，
CHEAP_PASS）的波動度配對複驗——同一輪追加，不是另一天的deep dive。

**為什麼要立刻做這個複驗，不等下一輪**：同一個SUE訊號家族裡，E1財報SUE
（`TRIALS_LEDGER.md`#332，續.A曾判CHEAP_PASS）後來被續.B揭穿是「高SUE
個股波動天生較大」的波動度效應，不是alpha——3維(季度x產業x市值)配對
p90_diff=+0.0413，加計事件前60交易日已實現波動度五分位第4維後崩到
+0.0178（崩掉56.9%，超過50%門檻，最終改判FAIL）。#368用的3維bucket
（`bucket_key`＝季度x產業x市值五分位，直接重用`event_driven_prototype.
build_event_table`的既有欄位）**完全沒有控制波動度**，跟E1續.A曝險同一個
已知假陽性來源；既然地基工程（`pre_event_vol`/`bucket_key_vol`）已經現成
可用，在誠實記錄#368為CHEAP_PASS之前，本檔案追加同一套4維（加計波動度
五分位）複驗，不留一個已知會被同家族其他成員揭穿的漏洞放著沒查。

方法：重用`build_event_table`（E2月營收SUE，跟#368同一個事件表構造），
用`bucket_key_vol`（3維bucket_key + 波動度五分位，`event_driven_prototype.py`
既有欄位，NaN列已被上游排除）取代`bucket_key`做中性化，其餘（Spearman
pooled IC、train/val切分、500次洗牌null、同一套cheap gate三判準）完全
不變，跟#368唯一的差異變量是中性化維度本身。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from event_driven_prototype import EVENT_TYPES, build_event_table
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from monthly_revenue_event_study import _permutation_null_percentile
from monthly_revenue_sue_continuous_bucket_v1 import (
    BASE_ALPHA, BONFERRONI_N, HORIZON, MIN_N, N_PERMUTATIONS, PERM_SEED,
    _bucket_neutralize, _period_stats,
)
from trial_registry import register_trial
from validation import holdout


def main() -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    spec = EVENT_TYPES["E2_月營收公布(SUE)"]
    print("=== #368波動度配對複驗（4維：季度x產業x市值x波動度五分位） ===")

    events = build_event_table(sample_ids, spec["surprise_fn"], spec["surprise_col"], verbose=False)
    ret_col = f"fwd{HORIZON}"

    # --- 3維（複製#368口徑，當同一份事件表上的對照基準） ---
    ev3, n_dropped3 = _bucket_neutralize(events, ret_col)
    neutral_col = f"{ret_col}_neutral"
    holdout.assert_no_holdout_leakage(ev3, date_col="entry_date", context="volcheck 3dim baseline")
    val3 = holdout.validation_slice(ev3, date_col="entry_date")
    train3 = holdout.cap_to_train(ev3, date_col="entry_date")
    val3_stats = _period_stats(val3, "VAL_3dim", neutral_col)
    train3_stats = _period_stats(train3, "TRAIN_3dim", neutral_col)
    print(f"3維(基準,同#368) TRAIN IC={train3_stats['ic']:+.4f}(n={train3_stats['n']})  "
          f"VAL IC={val3_stats['ic']:+.4f}(n={val3_stats['n']})")

    # --- 4維（bucket_key_vol，含波動度五分位；NaN列上游已排除） ---
    has_vol = events["bucket_key_vol"].notna()
    ev4_src = events[has_vol].copy()
    n_dropped_vol_na = int(len(events) - len(ev4_src))
    ev4_src = ev4_src.rename(columns={"bucket_key": "bucket_key_3dim", "bucket_key_vol": "bucket_key"})
    ev4, n_dropped4 = _bucket_neutralize(ev4_src, ret_col)
    holdout.assert_no_holdout_leakage(ev4, date_col="entry_date", context="volcheck 4dim vol-matched")
    val4 = holdout.validation_slice(ev4, date_col="entry_date")
    train4 = holdout.cap_to_train(ev4, date_col="entry_date")
    val4_stats = _period_stats(val4, "VAL_4dim", neutral_col)
    train4_stats = _period_stats(train4, "TRAIN_4dim", neutral_col)
    print(f"4維(波動度配對) TRAIN IC={train4_stats['ic']:+.4f}(n={train4_stats['n']})  "
          f"VAL IC={val4_stats['ic']:+.4f}(n={val4_stats['n']})  "
          f"(波動度五分位查無而排除{n_dropped_vol_na}筆)")

    same_sign4 = (
        not pd.isna(train4_stats["ic"]) and not pd.isna(val4_stats["ic"])
        and np.sign(train4_stats["ic"]) == np.sign(val4_stats["ic"]) and train4_stats["ic"] != 0
    )
    val4_for_perm = val4.rename(columns={"surprise": "revenue_sue", neutral_col: "fwd_ret"})
    null_pct4 = _permutation_null_percentile(val4_for_perm, val4_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)

    # 跟#334同一種「崩掉比例」衡量（用VAL IC量級，3維是基準）
    if val3_stats["ic"] and not pd.isna(val3_stats["ic"]) and val3_stats["ic"] != 0:
        collapse_pct = 1.0 - (val4_stats["ic"] / val3_stats["ic"]) if not pd.isna(val4_stats["ic"]) else float("nan")
    else:
        collapse_pct = float("nan")
    print(f"\nVAL IC 3維->4維：{val3_stats['ic']:+.4f} -> {val4_stats['ic']:+.4f}"
          f"（{'崩掉' if not pd.isna(collapse_pct) and collapse_pct > 0 else '未崩，甚至更強'}"
          f"{abs(collapse_pct)*100:.1f}% 若可計算）")

    reasons4 = []
    if train4_stats["n"] < MIN_N or val4_stats["n"] < MIN_N:
        reasons4.append(f"樣本數過少(train_n={train4_stats['n']}, val_n={val4_stats['n']})")
    if not same_sign4:
        reasons4.append("4維train/val正負號不一致")
    if pd.isna(null_pct4) or null_pct4 < required_pct:
        reasons4.append(f"4維null percentile={null_pct4:.1f}未過門檻{required_pct:.1f}")
    passes4 = len(reasons4) == 0
    # 比照#334門檻：崩掉比例>=50%視為「主要是波動度效應」
    is_vol_artifact = (not pd.isna(collapse_pct)) and collapse_pct >= 0.50
    print(f"4維判準：{'PASS' if passes4 else 'FAIL'}" + (f" reasons={reasons4}" if reasons4 else ""))
    print(f"是否波動度假象(崩掉>=50%)：{is_vol_artifact}")

    final_verdict = "CHEAP_PASS" if (passes4 and not is_vol_artifact) else "FAIL"
    print(f"\n=== 最終判定（含波動度配對）：{final_verdict} ===")

    out = {
        "train_3dim": train3_stats, "val_3dim": val3_stats,
        "train_4dim": train4_stats, "val_4dim": val4_stats,
        "n_dropped_vol_na": n_dropped_vol_na,
        "collapse_pct": collapse_pct, "is_vol_artifact": is_vol_artifact,
        "passes_4dim": passes4, "reasons_4dim": reasons4,
        "null_percentile_4dim": null_pct4, "required_percentile": required_pct,
        "final_verdict": final_verdict,
    }

    result = (
        f"3維(基準,#368) VAL IC={val3_stats['ic']:+.4f}(n={val3_stats['n']})；"
        f"4維(波動度五分位配對) VAL IC={val4_stats['ic']:+.4f}(n={val4_stats['n']}，"
        f"波動度查無排除{n_dropped_vol_na}筆)；"
        f"崩掉比例={'{:.1%}'.format(collapse_pct) if not pd.isna(collapse_pct) else 'N/A'}"
        f"（門檻50%，比照#334同一把尺）；4維null percentile={null_pct4:.1f}(門檻{required_pct:.1f})；"
        f"4維same_sign={same_sign4}"
    )
    notes = (
        f"複驗#368（月營收SUE連續分數bucket中性化cheap gate，CHEAP_PASS）是否為E1同款"
        f"（`TRIALS_LEDGER.md`#332/#334）波動度假陽性——高SUE個股天生波動較大，3維配對"
        f"(季度x產業x市值)未控制波動度時可能把波動度差異誤判成alpha。"
        + (f"複驗結果：崩掉{collapse_pct:.1%}未達50%門檻，4維判準{'PASS' if passes4 else 'FAIL'}，"
           f"維持CHEAP_PASS，非波動度假象。" if final_verdict == "CHEAP_PASS" else
           f"複驗結果：{'崩掉{:.1%}超過50%門檻，判定為波動度假象'.format(collapse_pct) if is_vol_artifact else '4維判準未過('+str(reasons4)+')'}"
           f"，#368的CHEAP_PASS主要來自波動度效應而非SUE本身alpha，改判FAIL。")
        + " 此為#368同一批交付內的即時複驗（非另開新輪次），跟E1續.A/續.B同一天內快速自我修正的紀律一致。"
    )
    register_trial(
        track="hypothesis_queue",
        name="monthly_revenue_sue_continuous_bucket_v1_volcheck",
        design="`TRIALS_LEDGER.md`#368波動度配對複驗（4維：季度x產業x市值x波動度五分位 vs 3維基準），"
               "比照E1`#332`續.A/`#334`續.B同一套方法論，PENDING_QUEUE.md常備.8",
        result=result,
        verdict=final_verdict,
        notes=notes,
        round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.8獨立交辦項，緊接#368同輪複驗",
        failed_gates=(["cheap_gate_precheck"] if final_verdict == "FAIL" else None),
    )
    return out


if __name__ == "__main__":
    import json
    result = main()
    out_path = Path(__file__).parent / "monthly_revenue_sue_continuous_bucket_v1_volcheck_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
