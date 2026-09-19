# -*- coding: utf-8 -*-
"""重構.A5：把GATE6（逐年一致性）FAIL的3筆範圍外舊假設，依
`gate6_power_curve_scoped_years.py`量出的n_years相符檢定力數字重分類。

跟`reclassify_underpowered.py`（IC類，Fisher z近似）是**不同的統計檢定
族**，不共用同一個判準函式，但沿用同一種「amends_id指回原始
TRIALS_LEDGER.md編號、不改寫原始記錄、append-only精神」的設計。刻意寫
成**獨立檔案**`UNDERPOWERED_RECLASSIFICATION_GATE6.jsonl`而不是併入
`UNDERPOWERED_RECLASSIFICATION.jsonl`：後者由`reclassify_underpowered.py`
用`write_text()`整檔覆寫（見該檔`main()`），若把這3筆手動加進同一個檔案，
下次有人重跑那支IC類腳本會無聲砍掉這裡新增的3筆，是本輪刻意避開的地雷。

**判準**：在強度0.5（`重構.A2`/`HYPOTHESIS_QUEUE.md`#74既有報告慣用的
「中等強度」代表值，非本輪新訂）下，`gate6_yearly_consistency()`理論
通過率若低於80%（統計檢定力慣例門檻），代表即使真的存在中等強度的
效果，用這個`n_years`/門檻組合去測，也有相當機率測不出來（FAIL不能
排除有真實效果存在）——判UNDERPOWERED，不是FAIL_CONFIRMED。這個規則
跟`reclassify_underpowered.py`的MDE判準是同一種精神的不同操作化
（「觀測到的效果量／通過率，是否落在該檢定的偵測能力範圍內」），因為
GATE6這類「經驗分布比對／通過率」測試沒有封閉形式SE公式，必須用模擬
（跟`reclassify_underpowered.py`docstring裡「not_assessed_needs_
simulation」欄位待補的方法完全一致，這裡就是把那個「待補」補上）。

跑法：`python research/reclassify_underpowered_gate6.py`（重跑
`gate6_power_curve_scoped_years.py`的完整計算取得最新數字，不依賴
gitignored的中繼JSON快取，確保每次執行都可從零重現）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equal_weight_rebalance_sanity import build_panel, load_prices
from factor_ic import SAMPLE_SIZE, SAMPLE_SEED, sample_universe_ids
from gate6_power_curve_scoped_years import run_scope
from validation import holdout

TZ = timezone(timedelta(hours=8))
OUT = Path(__file__).parent / "UNDERPOWERED_RECLASSIFICATION_GATE6.jsonl"
POWER_THRESHOLD = 0.80
REFERENCE_STRENGTH = "0.5"

# 人工核對過原文的3筆（見TRIALS_LEDGER.md #86/#114/#184行）。
CANDIDATES = [
    dict(amends_id=86, name="#17 f_52w_high_prox（TRAIN期第6關逐年一致性）",
         scope="train6", n_positive_observed=4, n_years_observed=6,
         source_quote="第3/5關PASS，第6關FAIL（6個年度中僅4個正報酬，未達>=5/6門檻），"
                       "TRIALS_LEDGER.md#86（原HYPOTHESIS_QUEUE.md#17）"),
    dict(amends_id=114, name="#29 equal_weight_rebalance_gate6_yearly（TRAIN期第6關逐年一致性）",
         scope="train6", n_positive_observed=4, n_years_observed=6,
         source_quote="FAIL（第6關逐年一致性未過，快殺結案，佇列#29最終判定FAIL）："
                       "4/6=66.7%，未達事前訂定的>=5/6=83.3%門檻，TRIALS_LEDGER.md#114"),
    dict(amends_id=184, name="#49 overnight_intraday_gate6_consistency（VAL期第6關逐年一致性）",
         scope="val4", n_positive_observed=3, n_years_observed=4,
         source_quote="VAL：3/4年同號=75.0%（2021+24.68%、2022-3.46%異號、2023+14.30%、"
                       "2024+22.28%），未達83.3%門檻，TRIALS_LEDGER.md#184"),
]


def main() -> None:
    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    base_raw_full = panel.pct_change().mean(axis=1).dropna()
    base_raw_full = base_raw_full[base_raw_full.index <= holdout.VAL_END]

    scope_results = {
        "train6": run_scope(base_raw_full, "train6（重分類用）", start=None, end=holdout.TRAIN_END),
        "val4": run_scope(base_raw_full, "val4（重分類用）", start=holdout.TRAIN_END, end=holdout.VAL_END),
    }

    now = datetime.now(TZ).isoformat(timespec="seconds")
    records = []
    n_underpowered = 0
    for c in CANDIDATES:
        power_curve = scope_results[c["scope"]]["by_strength"]
        power_at_ref = power_curve[REFERENCE_STRENGTH]["pass_rate"]
        verdict = "UNDERPOWERED" if power_at_ref < POWER_THRESHOLD else "FAIL_CONFIRMED"
        if verdict == "UNDERPOWERED":
            n_underpowered += 1
        records.append({
            "amends_id": c["amends_id"], "name": c["name"], "scope": c["scope"],
            "n_years_observed": c["n_years_observed"], "n_positive_observed": c["n_positive_observed"],
            "gate6_power_at_strength_0.3": power_curve["0.3"]["pass_rate"],
            "gate6_power_at_strength_0.5": power_curve["0.5"]["pass_rate"],
            "gate6_power_at_strength_0.8": power_curve["0.8"]["pass_rate"],
            "reference_strength_used_for_verdict": REFERENCE_STRENGTH,
            "power_threshold": POWER_THRESHOLD,
            "reclassification": verdict,
            "source_quote": c["source_quote"],
            "method": "synthetic_power_curve_gate74.py方法論（重構.A2逐年demean修正版），"
                      "透過gate6_power_curve_scoped_years.py限縮至觀測時使用的n_years，"
                      "強度{0.3,0.5,0.8}x5種子注入合成alpha量測GATE6理論通過率；"
                      "強度0.5下通過率<80%即判UNDERPOWERED（該檢定本身統計檢定力不足，"
                      "不能用它的FAIL結果排除中等強度真實效果存在）",
            "reclassified_at": now,
        })
        print(f"amends_id={c['amends_id']:>4} {c['name'][:40]:40}  "
              f"power@0.5={power_at_ref:.0%}  → {verdict}")

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    print(f"\n{len(CANDIDATES)}筆GATE6 FAIL裡：{n_underpowered}筆重分類為UNDERPOWERED、"
          f"{len(CANDIDATES) - n_underpowered}筆維持FAIL_CONFIRMED。寫入 {OUT.name}")

    print(f"is_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"


if __name__ == "__main__":
    main()
