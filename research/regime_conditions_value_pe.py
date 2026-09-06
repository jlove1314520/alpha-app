"""接續`TW_LEADS.md`#2/`CRITERIA_V2_LOCK.md`第39行：`f_value_pe`（FDR重新評分後
「待複驗候選（CANDIDATE）」）進深挖清單前必須先過「情境分群檢驗」這一關，
`regime_conditions.py`（2026-08-26主線1）當初只測了`f_foreign_streak`/`f_rel_strength`/
`f_quality_roe_stability`三個train/val反轉候選+4個已通過因子，未涵蓋`f_value_pe`，
是本專案已知的落差（見`TW_LEADS.md`#2備註原文「還需情境分群+成本敏感度才能進深挖
清單」）。

本腳本重用`regime_conditions.py`既有函式，不修改該檔案本身（避免弄亂已經整理進
`REGIME_CONDITIONS.md`的既有7因子分析），只新增`f_value_pe`一個因子跑同一套四組
條件（大盤位階/波動度/市值規模/流動性）。樣本改用`factor_ic.py`目前的
`SAMPLE_SIZE`(300，`CALIBRATION_PROBE.md`裁示後的新常數，複用已回補快取)，
比原始分析的100檔樣本更大。

執行方式：`python regime_conditions_value_pe.py`，結果印出後人工整理進
`TW_LEADS.md`/`TRIALS_LEDGER.md`，不自動寫入文件（沿用`regime_conditions.py`
一貫的分工原則）。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START, START_DATE, build_snapshots, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from regime_conditions import (
    MIN_OBS_FOR_CONCLUSION, _fmt_group_result, _market_regime_labels,
    _stock_size_and_liquidity, grouped_ic_market_level, grouped_ic_stock_level,
)

FACTOR = "f_value_pe"


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in regime_conditions_value_pe")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    sized_data = {sid: _stock_size_and_liquidity(d) for sid, d in data.items()}
    date_labels = _market_regime_labels(market_df)

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    print(f"\n=== {FACTOR} ===")
    n_with_factor = sum(1 for d in data.values() if FACTOR in d.columns and d[FACTOR].notna().any())
    print(f"  ({n_with_factor}/{len(data)} 檔有這個因子的非空值)")

    print("  (a) 大盤位階:")
    res_a = grouped_ic_market_level(FACTOR, data, snapshots, date_labels, "trend")
    for g in ("bull_above_ma", "bear_below_ma"):
        print(_fmt_group_result(g, res_a.get(g, {})))

    print("  (b) 波動度環境:")
    res_b = grouped_ic_market_level(FACTOR, data, snapshots, date_labels, "vol")
    for g in ("high_vol", "low_vol"):
        print(_fmt_group_result(g, res_b.get(g, {})))

    print("  (c) 市值規模 (流動性替代市值三等分):")
    res_c = grouped_ic_stock_level(FACTOR, data, sized_data, snapshots, "size_proxy", "tercile")
    for g in ("large", "mid", "small"):
        print(_fmt_group_result(g, res_c.get(g, {})))

    print("  (d) 流動性/量能 (20日/120日均量比, 中位數切):")
    res_d = grouped_ic_stock_level(FACTOR, data, sized_data, snapshots, "liq_ratio", "median")
    for g in ("high", "low"):
        print(_fmt_group_result(g, res_d.get(g, {})))


if __name__ == "__main__":
    main()
