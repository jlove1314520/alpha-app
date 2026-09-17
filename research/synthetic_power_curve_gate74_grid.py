# synthetic_power_curve_gate74_grid.py — #74 閘門統計檢定力量測：完整網格跑法
# 2026-09-17 hypothesis_queue排程接續。沿用synthetic_power_curve_gate74.py的
# run_pilot()（去均值化修正版，母體Sharpe已驗證歸零），本輪把上一輪(第二十輪)
# 留下的「單種子」擴大成{0.3,0.5,0.8}×5種子=15次試跑的有界網格，量測各強度下
# 六關個別通過率，不做完整多重比較掃描（那是另一輪的範圍）。

import json
from pathlib import Path

from synthetic_power_curve_gate74 import run_pilot
from validation import holdout

print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

STRENGTHS = [0.3, 0.5, 0.8]
BASE_SEED = 20260915
N_SEEDS = 5

results = []
for strength in STRENGTHS:
    for i in range(N_SEEDS):
        seed = BASE_SEED + i
        print(f"\n--- target_sharpe={strength}, seed={seed} ---")
        r = run_pilot(target_sharpe=strength, seed=seed)
        results.append(r)

# 彙總：各強度下六關各自通過率
summary = {}
for strength in STRENGTHS:
    subset = [r for r in results if r["target_sharpe"] == strength]
    gate_pass_rate = {}
    for gi in range(1, 7):
        passes = sum(1 for r in subset if r["gates"][gi - 1]["passed"])
        gate_pass_rate[f"gate{gi}"] = passes / len(subset)
    all_pass_rate = sum(1 for r in subset if r["all_passed"]) / len(subset)
    summary[str(strength)] = {
        "n_seeds": len(subset),
        "gate_pass_rate": gate_pass_rate,
        "all_six_pass_rate": all_pass_rate,
    }

print("\n=== 網格彙總（各強度下，5種子中六關各自通過率）===")
for k, v in summary.items():
    print(f"Sharpe={k}: {v}")

out = {"strengths": STRENGTHS, "n_seeds": N_SEEDS, "base_seed": BASE_SEED,
       "summary": summary, "raw_results": results}

out_path = Path(__file__).parent / "data" / "synthetic_power_curve_gate74_grid.json"
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"\n網格結果已存 {out_path.relative_to(Path(__file__).parent)}（gitignored，僅供除錯）")

print(f"\nis_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
