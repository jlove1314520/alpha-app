# -*- coding: utf-8 -*-
"""Weinstein第二階段v2——GATE_SEQUENCE第1關：sanity（`research/
HYPOTHESIS_QUEUE.md`#1，馬拉松自主循環）。

檢查項目（便宜、快，不是完整回測）：
1. 三個gate（站上150日均線+均線上揚+f_rel_strength>0）通過的股票池大小
   在樣本期間是否合理（不是系統性0檔或系統性全部通過——兩種都代表gate
   邏輯有問題，不是訊號本身的事）。
2. 方向粗檢：通過gate的股票，事後20個交易日的報酬平均，是否高於同期
   全樣本平均（不是嚴謹IC檢定，只是快速確認方向沒有反過來——嚴謹檢定
   留到下一關「隨機控制組」）。

用既有的500檔流動性樣本快取（不是「B24可重現性乾淨重跑」那份_clean
快取——sanity階段不需要100%排除並行寫入疑慮，那個要求只套用在最終
判定的數字上，見`CLAUDE.md`最高投資原則「儀器不穩=不能信」，這裡只是
探索性檢查，沒有要拿這裡的數字當最終證據）。
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from strategies.weinstein_stage2_v2 import prepare_price_data_v2, stage2_signal_v2
from factor_ic import START_DATE

CACHE_PATH = Path(__file__).parent / "data" / "backtests" / "value_board_v2_sample_cache_liquidity500.pkl"


def main():
    print("載入既有500檔流動性樣本快取（sanity用，非最終判定用的乾淨快取）...")
    with open(CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"  {len(data)}檔")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)  # 跟run_value_board_v2_pit_backtest.py同一種用法，market_raw欄位本身已相容

    # 2026-08-29修正：改用跟run_weinstein_unbiased_v2.py/weinstein_v2_alpha_gate.py
    # 同一個prepare_price_data_v2()（獨立算相對強度，不依賴外部欄位），這支sanity
    # 腳本第一版直接用factor_ic.py快取裡現成的f_rel_strength欄位，剛好沒踩到那個
    # bug（那個欄位在那個特定快取裡本來就有），但沒測到後續關卡實際會用的資料
    # 載入路徑——見weinstein_stage2_v2.py docstring「真bug修正」段落完整說明。
    data_prepared = prepare_price_data_v2(data, market_df)

    # 抽樣檢查點：每季一次，2015-2024，共約40個檢查點
    calendar = sorted({d for df in data_prepared.values() for d in df["date"]})
    check_dates = calendar[::63][:40]  # 每63個交易日(約一季)抽一次

    pool_sizes = []
    fwd_rets_eligible = []
    fwd_rets_all = []
    for as_of in check_dates:
        idx = calendar.index(as_of)
        if idx + 20 >= len(calendar):
            continue
        fwd_date = calendar[idx + 20]
        scores = stage2_signal_v2(data_prepared, as_of, market_df)
        pool_sizes.append(len(scores))

        for sid, df in data_prepared.items():
            row_now = df.loc[df["date"] == as_of]
            row_fwd = df.loc[df["date"] == fwd_date]
            if row_now.empty or row_fwd.empty:
                continue
            p0, p1 = row_now.iloc[0]["adj_close"], row_fwd.iloc[0]["adj_close"]
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            ret = p1 / p0 - 1
            fwd_rets_all.append(ret)
            if sid in scores:
                fwd_rets_eligible.append(ret)

    print(f"\n檢查點數：{len(pool_sizes)}")
    print(f"通過三個gate的股票池大小：min={min(pool_sizes)} max={max(pool_sizes)} "
          f"mean={np.mean(pool_sizes):.1f} median={np.median(pool_sizes):.1f}")
    zero_pool_days = sum(1 for p in pool_sizes if p == 0)
    print(f"股票池為0的檢查點數：{zero_pool_days}/{len(pool_sizes)}")

    print(f"\n事後20交易日報酬：")
    print(f"  通過gate的股票（{len(fwd_rets_eligible)}筆觀察）：平均={np.mean(fwd_rets_eligible)*100:.2f}%  "
          f"中位數={np.median(fwd_rets_eligible)*100:.2f}%")
    print(f"  全樣本（{len(fwd_rets_all)}筆觀察）：平均={np.mean(fwd_rets_all)*100:.2f}%  "
          f"中位數={np.median(fwd_rets_all)*100:.2f}%")
    diff = np.mean(fwd_rets_eligible) - np.mean(fwd_rets_all)
    print(f"  差異（通過gate - 全樣本）：{diff*100:+.2f}pp")

    print("\n=== sanity判定 ===")
    pool_ok = (min(pool_sizes) >= 0) and (zero_pool_days < len(pool_sizes) * 0.5) and (np.mean(pool_sizes) < len(data) * 0.9)
    direction_ok = diff > 0
    print(f"股票池大小合理（非系統性0檔、非系統性全部通過）：{pool_ok}")
    print(f"方向正確（通過gate的股票事後報酬 > 全樣本平均）：{direction_ok}")
    print(f"sanity{'PASS' if (pool_ok and direction_ok) else 'FAIL'}")


if __name__ == "__main__":
    main()
