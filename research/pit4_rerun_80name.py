"""財報PIT.四（2026-09-20，驗證帽）：以「原p=0.053的80檔驗證樣本」直接檢驗Q4前視修正的影響。

背景：財報PIT.三重跑的是295檔bigsample，但`LEADS.md`/`STRATEGY_GRAVEYARD.md`的「p=0.053接近顯著」
出自原80檔驗證樣本（A_4pass/B_plus_value_pe × IC加權 × 季頻，alpha +10.40%/+10.26%）。
`git log`可證明當時`factor_ic.SAMPLE_SIZE`=100（後於甲.3改300），100檔中約80檔可用，
故樣本＝`sample_universe_ids(100, SAMPLE_SEED)`（`random.sample`同種子下k=100是k=300的前綴——
但`build_universe()`若自那時起有變動則樣本會不同，**這點無法事後驗證，本腳本不宣稱精確重現原樣本**）。

**設計（跑之前凍結，先commit再執行，結果出來後不得改）**：
- 樣本：`sample_universe_ids(100, SAMPLE_SEED)`，經`load_sample_with_factors`載入（跟`portfolio_backtest_v2.main()`同路徑）。
- 兩臂同process、同程式碼：`corrected`＝現行`pit.statutory_quarterly_pit_date`（Q4=次年3/31）；
  `legacy_q4_lookahead`＝改回期末+45日（Q4=2/14）。
- 網格＝原`portfolio_backtest_v2.main()`階段1的24種組合（2因子版本×3加權(equal/ic_weighted/regime_weighted，
  皆用檔內寫死的舊IC常數，不重算)×2頻率×TRAIN/VAL），1x成本、無隨機對照組。
- 只用TRAIN+VAL，不碰holdout；零新增API（純讀本機快取，但若快取缺會經load_dev打FinMind——遇402即停）。

**判定分支（凍結）**：
 (a) legacy臂在A_4pass/ic_weighted/季頻VAL重現不出原+10.40%、p≈0.053（判準：alpha落在[+7%,+14%]且p∈[0.03,0.08]才算重現）
     →記錄「舊數字不可重現、前視貢獻不可量化」，不再追；
 (b) legacy臂重現、修正臂VAL p>0.10 或 alpha<=0 →前視貢獻可量化，寫進LEADS/GRAVEYARD；
 (c) legacy臂重現、修正臂VAL p<0.06 →標「不依賴前視的alpha殘存」，仍FAIL不得稱通過。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import pit
import portfolio_backtest_v2 as pv2
from factor_ic import SAMPLE_SEED, START_DATE, load_sample_with_factors, sample_universe_ids
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

OUT = Path(__file__).parent / "data" / "pit4_rerun_80name.csv"
_ORIG_STAT = pit.statutory_quarterly_pit_date


def _legacy_pit_date(period_end) -> pd.Timestamp:
    return pd.Timestamp(period_end) + pd.Timedelta(days=45)


def run_arm(arm, sample_ids, market_df, industry_map, trend_regime):
    pit.statutory_quarterly_pit_date = _legacy_pit_date if arm == "legacy_q4_lookahead" else _ORIG_STAT
    rows = []
    try:
        print(f"\n######## 臂：{arm} ########", flush=True)
        data = load_sample_with_factors(sample_ids, market_df)
        print(f"  載入 {len(data)}/{len(sample_ids)} 檔", flush=True)
        for sid, d in data.items():
            holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in pit4_rerun {arm}")
        liquidity = {sid: pv2._liquidity_proxy_series(d) for sid, d in data.items()}
        for fv in pv2.FACTOR_VERSIONS:
            for wm in ("equal", "ic_weighted", "regime_weighted"):
                for cad in pv2.REBALANCE_CADENCES:
                    for label, start, end in (("TRAIN", "2015-01-01", holdout.TRAIN_END),
                                              ("VALIDATION", "2021-01-01", holdout.VAL_END)):
                        r = pv2.run_one(fv, wm, cad, label, data, market_df, industry_map, trend_regime,
                                        liquidity, start, end, do_cost_sensitivity=False, do_random_control=False)
                        r["arm"] = arm
                        r["n_stocks"] = len(data)
                        rows.append(r)
                        print(f"  {fv}/{wm}/{cad}/{label}: 報酬={r['return_pct']:+.2f}% "
                              f"alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.4f})", flush=True)
    finally:
        pit.statutory_quarterly_pit_date = _ORIG_STAT
    return rows


def main():
    ids = sample_universe_ids(100, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in pit4_rerun_80name")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    trend_regime = pv2._trend_regime_series(market_df)
    all_rows = []
    for arm in ("legacy_q4_lookahead", "corrected"):  # 先跑legacy：分支(a)只看它能否重現舊數字
        all_rows += run_arm(arm, ids, market_df, industry_map, trend_regime)
        pd.DataFrame(all_rows).to_csv(OUT, index=False)
        print(f"  已存 {OUT.name}（累計 {len(all_rows)} 列）", flush=True)
    df = pd.DataFrame(all_rows)
    piv = df.pivot_table(index=["factor_version", "weight_mode", "cadence", "label"], columns="arm",
                         values=["alpha_ann_pct", "alpha_pvalue"])
    print("\n=== 兩臂對照 ===")
    print(piv.round(4).to_string())


if __name__ == "__main__":
    main()
