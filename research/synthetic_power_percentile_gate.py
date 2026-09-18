# -*- coding: utf-8 -*-
"""通用「percentile-vs-隨機控制組」類測試的注入式檢定力量測工具
（2026-09-18 總司令裁示【研究方向重構】階段一.3 的獨立待辦落地——
`reclassify_underpowered.py` docstring 明文：36筆`not_assessed_needs_
simulation`候選需要「比照#74`synthetic_power_curve_gate74.py`的做法」建
一個工具，本檔即為該工具）。

**問題背景**：`reclassify_underpowered.py`已用Fisher z封閉公式處理10筆
乾淨的Pearson/Spearman IC+n格式候選，但`TRIALS_FAILED_GATES_BACKFILL.jsonl`
另外36筆是「訊號 vs 模擬隨機控制組percentile」這種**經驗分布比對**（例如
`validation/control_group.py::run_control_group()`跑出來的
`ControlGroupResult.percentile`），沒有封閉形式SE，無法直接套Fisher z。

**方法（bootstrap-shift，標準的置換檢定檢定力估計手法）**：
若已經有該候選的null分布經驗樣本（`random_metrics`，即`run_control_group()`
在`n_random`次隨機抽樣下算出的null分布），可以直接把這個null分布**平移**
一個合成效果量`S`，視為「如果真的存在強度S的訊號，候選自己的統計量分布
長什麼樣子」的近似（假設效果對統計量是可加的、平移不變的——這是簡化
假設，非精確推導，下方docstring會誠實列出這個假設的限制）。平移後的分布
超過**原始null分布**的第90百分位門檻的比例，就是「檢定力」（在效果量S下
偵測到訊號的機率）。

**兩種模式**：
1. `bootstrap_detection_power()`——有完整null draws時用，最忠實。
2. `normal_approx_detection_power()`——只有null分布的mean/std摘要統計時
   的備援（多數既有候選只在TRIALS_REGISTRY留下percentile文字敘述，沒有
   把`random_metrics`原始陣列存檔，這種情況下只能退而求其次用常態近似，
   若null分布本身明顯厚尾/偏態，這個近似會失真，使用時必須誠實揭露）。

**本輪範圍（誠實記錄，不誇大）**：本檔完成方法論建置＋用**合成常態null**
自我驗證（見`_self_test()`），證明兩種模式在已知答案的情境下都給出正確
方向與合理數字。**尚未套用到36筆真實候選**——那需要逐一回頭確認每筆候選
當初的`random_metrics`原始陣列是否還留有快取（多數已被清除，只剩摘要
文字），沒有快取的話需要重新執行該候選當初的資料管線並重新產生null
分布，是遠大於本輪「一個有界工作單位」的工作量，留給下一輪
hypothesis_queue接續，不在本輪勉強做。

跑法：`python research/synthetic_power_percentile_gate.py`（純本機蒙地卡羅
計算，`numpy`已是既有依賴，零外部API呼叫，`is_holdout_consumed()`本輪
開工/收工前皆為False，未動任何holdout解鎖）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.stats import norm

TZ = timezone(timedelta(hours=8))
OUT = Path(__file__).parent / "SYNTHETIC_POWER_PERCENTILE_SELFTEST.json"


@dataclass
class PowerCurveResult:
    """一組效果量對應的檢定力估計，附方法論與假設揭露。"""

    threshold_percentile: float
    threshold_value: float
    effect_sizes: list[float]
    detection_rates: dict[float, float] = field(default_factory=dict)
    method: str = ""
    caveat: str = ""


def bootstrap_detection_power(
    null_draws: Sequence[float],
    effect_sizes: Sequence[float],
    threshold_percentile: float = 90.0,
) -> PowerCurveResult:
    """有完整null draws時的忠實估計。

    做法：`threshold = percentile(null_draws, threshold_percentile)`（跟
    `run_control_group()`判定PASS/FAIL用的門檻完全同一個定義）；對每個
    效果量S，把null_draws逐一平移+S，計算平移後超過`threshold`的比例，
    即為該效果量下的檢定力估計。

    **假設與限制（必須誠實揭露，不可省略）**：
    1. 平移不變性假設——真實效果對這個統計量的影響，未必是簡單相加；
       某些統計量（例如Sharpe ratio、percentile排名本身）效果可能是
       乘性或非線性的，平移只是最簡單、最常見的近似起點，不是精確推導。
    2. `null_draws`的變異結構被假設在「有訊號」與「無訊號」情境下大致
       相同——如果真實訊號會系統性改變變異數（例如降低波動），這個假設
       會失真。
    3. 樣本量受限於原始`n_random`次數（通常100~500次），效果量網格
       越細，單點的蒙地卡羅雜訊越大，報告時應同時附上`n_random`。
    """
    if len(null_draws) < 10:
        raise ValueError(f"null_draws樣本數過少({len(null_draws)})，估計不可靠")
    arr = np.asarray(null_draws, dtype=float)
    threshold = float(np.percentile(arr, threshold_percentile))
    rates: dict[float, float] = {}
    for s in effect_sizes:
        shifted = arr + s
        rates[float(s)] = float(np.mean(shifted > threshold))
    return PowerCurveResult(
        threshold_percentile=threshold_percentile,
        threshold_value=threshold,
        effect_sizes=[float(s) for s in effect_sizes],
        detection_rates=rates,
        method="bootstrap_shift（用原始null draws平移，忠實但假設平移不變性）",
        caveat=f"n_random={len(arr)}，效果量網格越細單點蒙地卡羅雜訊越大",
    )


def normal_approx_detection_power(
    null_mean: float,
    null_std: float,
    effect_sizes: Sequence[float],
    threshold_percentile: float = 90.0,
) -> PowerCurveResult:
    """只有null分布摘要統計（mean/std）時的備援估計，假設null近似常態。

    **假設與限制（比bootstrap_detection_power更弱，必須更謹慎使用）**：
    1. 假設null分布近似常態——若原始null分布明顯厚尾/偏態（例如報酬率
       類統計量常見），這個近似會系統性低估或高估尾端機率，使用者必須
       自行判斷是否合理（例如先用`bootstrap_detection_power`在有draws
       時對照兩者是否接近，本檔`_self_test()`即為此對照）。
    2. 同樣假設效果量對統計量是可加的（平移不變），跟bootstrap版同一個
       限制。
    """
    if null_std <= 0:
        raise ValueError("null_std必須為正數")
    z_threshold = norm.ppf(threshold_percentile / 100.0)
    threshold_value = null_mean + z_threshold * null_std
    rates: dict[float, float] = {}
    for s in effect_sizes:
        shifted_mean = null_mean + s
        z = (threshold_value - shifted_mean) / null_std
        rates[float(s)] = float(1.0 - norm.cdf(z))
    return PowerCurveResult(
        threshold_percentile=threshold_percentile,
        threshold_value=threshold_value,
        effect_sizes=[float(s) for s in effect_sizes],
        detection_rates=rates,
        method="normal_approx（假設null分布近似常態，僅在無完整draws時使用）",
        caveat="null分布若厚尾/偏態則此估計失真，需與bootstrap版對照驗證",
    )


def _self_test() -> dict:
    """用合成常態null（已知答案）驗證兩種模式方向正確、數字合理。

    設計：null_draws ~ N(0, 1)，n=500（比照多數既有候選常用的
    `n_random`量級）。理論上：
    - effect_size=0時，超過p90門檻的比例應該約等於「100-90=10%」
      （定義上，p90門檻就是讓10%的null draws超過它）。
    - effect_size越大，檢定力應該單調遞增，最終逼近100%。
    - bootstrap版跟normal_approx版在null本身就是常態的這個測試情境下，
      兩者數字應該高度接近（差距在蒙地卡羅雜訊範圍內），這是對
      normal_approx近似品質的交叉驗證。
    """
    rng = np.random.default_rng(20260918)
    null_draws = rng.normal(loc=0.0, scale=1.0, size=500)
    effect_sizes = [0.0, 0.2, 0.5, 0.8, 1.2, 2.0, 3.0]

    boot = bootstrap_detection_power(null_draws, effect_sizes, threshold_percentile=90.0)
    approx = normal_approx_detection_power(
        null_mean=float(np.mean(null_draws)),
        null_std=float(np.std(null_draws, ddof=1)),
        effect_sizes=effect_sizes,
        threshold_percentile=90.0,
    )

    checks = {}
    # 檢查一：effect_size=0時bootstrap版應接近10%（±蒙地卡羅雜訊，n=500時
    # 標準誤約sqrt(0.1*0.9/500)≈1.3%，用3個標準誤=約4%當寬鬆容忍帶）。
    zero_rate = boot.detection_rates[0.0]
    checks["effect_zero_near_10pct"] = bool(abs(zero_rate - 0.10) < 0.04)

    # 檢查二：檢定力隨效果量單調遞增（bootstrap版）。
    ordered = [boot.detection_rates[s] for s in effect_sizes]
    checks["monotonic_increasing"] = bool(all(a <= b + 1e-9 for a, b in zip(ordered, ordered[1:])))

    # 檢查三：最大效果量(3.0，理論值P(Z>1.2816-3.0)≈97.6%)下檢定力應該非常高
    # （>95%——注意：門檻取決於null分布本身的p90值，效果量的「多大算大」
    # 是相對null std而言，這裡null std=1，所以效果量數字本身沒有普適意義，
    # 只在本次自我驗證的合成情境下成立，不可直接套用到真實候選）。
    max_effect = effect_sizes[-1]
    checks["high_effect_near_100pct"] = bool(boot.detection_rates[max_effect] > 0.95)

    # 檢查四：bootstrap與normal_approx在常態null下應該互相接近
    # （逐點絕對差距容忍0.08，因為n=500的蒙地卡羅雜訊本身就有幾個百分點）。
    max_diff = max(abs(boot.detection_rates[s] - approx.detection_rates[s]) for s in effect_sizes)
    checks["bootstrap_approx_agree"] = bool(max_diff < 0.08)

    all_pass = all(checks.values())

    result = {
        "self_test_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "null_setup": "N(0,1), n=500, seed=20260918",
        "threshold_percentile": 90.0,
        "bootstrap_threshold_value": boot.threshold_value,
        "normal_approx_threshold_value": approx.threshold_value,
        "effect_sizes": effect_sizes,
        "bootstrap_detection_rates": boot.detection_rates,
        "normal_approx_detection_rates": approx.detection_rates,
        "max_abs_diff_bootstrap_vs_approx": max_diff,
        "checks": checks,
        "all_checks_pass": all_pass,
    }
    return result


def main() -> None:
    result = _self_test()
    print("=== synthetic_power_percentile_gate 自我驗證（合成常態null，非真實候選）===")
    print(f"null設定：{result['null_setup']}，門檻百分位={result['threshold_percentile']}")
    print(f"bootstrap門檻值={result['bootstrap_threshold_value']:.4f}  "
          f"normal_approx門檻值={result['normal_approx_threshold_value']:.4f}")
    print(f"{'效果量':>8}  {'bootstrap檢定力':>16}  {'常態近似檢定力':>16}")
    for s in result["effect_sizes"]:
        b = result["bootstrap_detection_rates"][s]
        a = result["normal_approx_detection_rates"][s]
        print(f"{s:>8.2f}  {b:>15.1%}  {a:>15.1%}")
    print(f"\n兩法最大逐點差距：{result['max_abs_diff_bootstrap_vs_approx']:.4f}")
    print("檢查項：")
    for k, v in result["checks"].items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    print(f"\n全部檢查{'PASS' if result['all_checks_pass'] else '未全部PASS——方法論有問題，不得用於真實候選'}")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n寫入 {OUT.name}")
    print(
        "\n【誠實記錄範圍】本輪僅完成方法論建置＋合成常態null自我驗證，"
        "尚未套用到36筆真實not_assessed_needs_simulation候選——那需要逐一"
        "回頭確認每筆候選當初的random_metrics原始陣列是否還有快取，沒有"
        "快取則需重跑該候選當初的資料管線重新產生null分布，是下一輪"
        "hypothesis_queue接續的獨立工作，本輪未做。"
    )


if __name__ == "__main__":
    main()
