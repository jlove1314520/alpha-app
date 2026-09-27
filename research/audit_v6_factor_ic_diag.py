# -*- coding: utf-8 -*-
"""驗.六第三點：#7/#8/#9因子IC診斷（2026-09-27總司令裁示【驗.六：資料
修正後的影響重估（診斷，不改任何判定）】）。

用**當前**（已含修.六/查.二/查.三/修.七四項修正的）`adjust.py`，跟登記
#7(`f_eps_surprise`)/#8(`f_revenue_surprise`)/#9(`f_low_vol`)完全相同
的`factor_ic.py::run_ic_test()`方法論（同一個抽樣種子/300檔樣本、同一套
打散對照null distribution、同一個Bonferroni n=6分母）重算打散對照百分位。
**只作診斷，不改變#7/#8/#9已登記的PASS判定**。factor_ic.py本身不做
common_stock_only()篩選（登記當時就是這樣，這裡沿用同一個宇宙定義，
只是價格資料換成修正後的，避免混入「換宇宙」這個額外變因）。

輸出：research/data/diag_v6_factor_ic.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from pathlib import Path

import pandas as pd

import factor_ic as fic

OUT = Path(__file__).parent / "data" / "diag_v6_factor_ic.json"

REGISTERED = {
    "f_eps_surprise": {"null_percentile": 100.0, "verdict": "PASS"},
    "f_revenue_surprise": {"null_percentile": 99.0, "verdict": "PASS"},
    "f_low_vol": {"null_percentile": 100.0, "verdict": "PASS"},
}


def main() -> None:
    sample_ids = fic.sample_universe_ids(fic.SAMPLE_SIZE, fic.SAMPLE_SEED)
    factors = ["f_eps_surprise", "f_revenue_surprise", "f_low_vol"]
    print(f"[驗.六項三] 重跑{len(factors)}個因子的打散對照百分位（修正後資料層，"
          f"沿用登記當時的300檔樣本/Bonferroni n=6，只作診斷）...", flush=True)
    results = fic.run_ic_test(factors, sample_ids, "驗.六診斷：修正後資料層重算#7/#8/#9", bonferroni_n=6)

    out = {}
    for r in results:
        reg = REGISTERED[r.factor]
        out[r.factor] = {
            "diagnostic_value_verdict_locked": True,
            "registered": reg,
            "diag_v6_corrected": {
                "null_percentile": round(r.null_percentile, 2),
                "required_percentile": round(r.required_percentile, 2),
                "val_mean_ic": round(r.val_mean_ic, 4),
                "passes_diag_only": r.passes,
            },
            "delta_null_percentile": round(r.null_percentile - reg["null_percentile"], 2),
        }
        print(f"  {r.factor}：登記時百分位={reg['null_percentile']}→診斷值={r.null_percentile:.2f}"
              f"（門檻{r.required_percentile:.1f}），診斷判定(不影響鎖定判定)="
              f"{'PASS' if r.passes else 'FAIL'}", flush=True)

    OUT.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "verdict_locked_note": "本檔案全部數字為診斷值，#7/#8/#9已登記PASS判定一律鎖定不變。",
        "sample_size": fic.SAMPLE_SIZE, "sample_seed": fic.SAMPLE_SEED,
        "results": out,
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT}")


if __name__ == "__main__":
    main()
