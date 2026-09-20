# -*- coding: utf-8 -*-
"""2026-09-20總司令裁示【Q4前視與#23無法重現】一.3：用修正後的
`pit.py::quarterly_pit()`（Q4改法定期限3/31，不是舊版期末+45日=2/14）
重跑三個PASS因子（f_eps_growth/f_eps_surprise/f_revenue_surprise），
比對`TRIALS_LEDGER.md`已登記的舊數字（percentile：100.0/100.0/99.0，
bonferroni_n=6），回報IC與PASS判定有沒有變。

**沿用原始評估參數**（不得為了讓結果好看而調整）：`SAMPLE_SEED`/
`SAMPLE_SIZE`（300，跟`factor_ic.py`模組常數一致，即原始評估用的
抽樣）、`bonferroni_n=6`（原始評估的因子家族大小）。

用法：
    python research/rerun_pit_fix_impact.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import factor_ic as fi
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data

FACTORS = ["f_eps_growth", "f_eps_surprise", "f_revenue_surprise"]
BONFERRONI_N = 6  # 原始評估的因子家族大小，見TRIALS_LEDGER.md #2/#7/#8

OLD_REGISTERED = {
    "f_eps_growth": {"percentile": 100.0, "ledger_id": 2},
    "f_eps_surprise": {"percentile": 100.0, "ledger_id": 7},
    "f_revenue_surprise": {"percentile": 99.0, "ledger_id": 8},
}

OUT_PATH = Path(__file__).parent / "pit_fix_impact_result.json"


def main() -> None:
    print(f"樣本：SAMPLE_SIZE={fi.SAMPLE_SIZE}, SAMPLE_SEED={fi.SAMPLE_SEED}"
          f"（沿用原始評估參數，不調整）")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", fi.START_DATE)
    market_df = prepare_market_data(market_raw)
    calendar = sorted(market_df["date"].unique())
    snapshots = fi.build_snapshots(calendar, calendar[0], calendar[-1])
    print(f"snapshots: {len(snapshots)}")

    ids = fi.sample_universe_ids(fi.SAMPLE_SIZE)
    print(f"樣本宇宙: {len(ids)}檔，開始載入價格+因子（含修正後的quarterly_pit）...")
    data = fi.load_sample_with_factors(ids, market_df)
    print(f"可用股票: {len(data)}/{len(ids)}")

    results = {}
    for factor in FACTORS:
        r = fi.evaluate_factor(factor, data, snapshots, bonferroni_n=BONFERRONI_N)
        old = OLD_REGISTERED[factor]
        pass_changed = (r.passes is False)  # 原本全部PASS，只要現在不是PASS就是變化
        results[factor] = {
            "old_percentile": old["percentile"],
            "old_ledger_id": old["ledger_id"],
            "new_train_mean_ic": r.train_mean_ic,
            "new_val_mean_ic": r.val_mean_ic,
            "new_same_sign": r.same_sign,
            "new_null_percentile": r.null_percentile,
            "new_required_percentile": r.required_percentile,
            "new_passes": r.passes,
            "new_reasons": r.reasons,
            "pass_status_changed_from_pass": pass_changed,
        }
        print(f"\n=== {factor} ===")
        print(f"  舊登記：percentile={old['percentile']}（TRIALS_LEDGER #{old['ledger_id']}，PASS）")
        print(f"  新結果：train_ic={r.train_mean_ic:.4f} val_ic={r.val_mean_ic:.4f} "
              f"same_sign={r.same_sign} percentile={r.null_percentile:.1f} "
              f"required={r.required_percentile:.1f} passes={r.passes}")
        if pass_changed:
            print(f"  !!! 重大變化：原本PASS，修正PIT後變成不PASS，理由：{r.reasons}")
        else:
            print(f"  維持PASS（前視存在但不足以改變結論）")

    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存：{OUT_PATH}")

    any_changed = any(v["pass_status_changed_from_pass"] for v in results.values())
    print(f"\n總結：{'有因子失去PASS，屬重大更正，需要回頭檢查portfolio_v2/core_tilt/score.py' if any_changed else '三個因子皆維持PASS，前視存在但不足以改變結論'}")


if __name__ == "__main__":
    main()
