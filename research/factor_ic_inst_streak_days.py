"""`HYPOTHESIS_QUEUE.md` #13 台股三大法人連續買超持續性：`f_inst_streak_days`
（三大法人合計淨買超連續同方向天數，天數越長排名越高）的第1關cheap IC gate。

經濟理由：三大法人（外資/投信/自營商）在台股普遍被視為資訊優勢方
（informed flow），連續買超天數代表持續性的資訊優勢累積，比單日買賣超金額
更能過濾雜訊（單日大額買超可能只是換股操作或程式交易雜訊，連續多日同方向
才更可能反映真實的資訊優勢）。跟已經FAIL的`f_foreign_streak`（`TRIALS_
LEDGER.md`#3，2026-08-22，打散對照76.0百分位+train/val正負號相反）刻意做
兩點區隔：(1)這裡用三大法人合計，`f_foreign_streak`只算外資單一法人；
(2)這裡衡量連續天數本身（計數統計量），`f_foreign_streak`衡量的是用成交量
正規化的連續期間累積買超金額（連續量的大小），是根本不同的統計量，不是
換皮重測。見`HYPOTHESIS_QUEUE.md`#13、`factors.py::_consecutive_positive_
streak_days()`docstring完整說明。

沿用`factor_ic.py`既有cross-sectional IC + 洗牌null分布測試框架（跟
f_low_vol/f_dividend_yield_ttm/f_residual_momentum等既有測試同一套機制）。
Standalone single-factor test (bonferroni_n=1)。

2026-09-02 由HYPOTHESIS_QUEUE_PROTOCOL.md自動排程新增，佇列#13第1關起跑。
"""
from __future__ import annotations

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, run_ic_test

TARGET_FACTORS = ["f_inst_streak_days"]


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    results = run_ic_test(
        TARGET_FACTORS, sample_ids,
        label="台股三大法人連續買超持續性 (f_inst_streak_days, 三大法人合計連續買超天數), HYPOTHESIS_QUEUE.md#13新假設, standalone (bonferroni_n=1)",
        bonferroni_n=1,
    )
    return results


if __name__ == "__main__":
    main()
