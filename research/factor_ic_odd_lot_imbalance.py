"""`HYPOTHESIS_QUEUE.md` #67 盤中零股委託簿失衡度（Odd-Lot Order Book
Imbalance）第1關cheap IC gate。

經濟理由：零股（不足1張）交易人結構性偏向資金規模小的散戶，跟三大法人/
融資融券戶是不同投資人母體（本佇列第16種正交機制，完整四類排除清單見
`HYPOTHESIS_QUEUE.md` #67條目）。行為財務文獻對散戶交易predict方向存在
分歧（處分效應/正回饋交易），故本因子**未預先鎖死單一方向**——這是#67
條目明文允許的唯一方向彈性例外：跑`evaluate_factor()`本身不假設方向，
只檢查train/val是否同號、且贏過洗牌null，方向由結果本身決定，不是先
選好方向再看數字。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
`factor_ic_margin_utilization.py`同一種一行式模板，本輪查證確認框架
可直接掛載外部資料源，見`twse_odd_lot_client.py::odd_lot_imbalance_
daily()`）。Standalone single-factor test (bonferroni_n=1)。

2026-09-09 hypothesis_queue排程接續新增，佇列#67第1關起跑（回補
1092/1092=100%完成後）。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_odd_lot_imbalance"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label=(
            "盤中零股委託簿失衡度 (f_odd_lot_imbalance, TWTC7U最後揭示買賣量), "
            "HYPOTHESIS_QUEUE.md#67新假設, 方向未預先鎖死(允許的唯一例外), "
            "standalone (bonferroni_n=1)"
        ),
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
