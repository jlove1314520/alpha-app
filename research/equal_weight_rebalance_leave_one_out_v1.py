"""`HYPOTHESIS_QUEUE.md` #29 等權重再平衡溢酬 Diversification Return /
Equal-Weight Rebalancing Premium 第5關 leave-one-out。

**只測TRAIN期（開發期探索），不動VAL**——跟`f52w_high_gates.py`/
`pair_trading_gates.py`同一個原則：第2~6關屬於開發期探索，可以用開發期資料
反覆測試找出穩健的參數/機制範圍；只有第7關才是正式樣本外判定，VAL期資料不可
被這幾關的探索過程碰到。

**用毛報酬（gross，未扣成本）**——沿用sanity/第3關參數高原同一套口徑，不是
第4關已扣成本的版本。理由：leave-one-out檢查的是「效果是否結構性集中在少數
年份」這個跟成本無關的問題（第4關成本敏感度已經獨立做過、結論是三個情境皆
維持正溢酬），混用net版本只會讓這關的年度型態多一層跟成本相關的雜訊，偏離
`fut_basis_carry`(#35→#37)/`f52w_high`(#17第5關)這兩個既有案例確立的「先看
毛報酬的年度集中度，成本另外一關處理」慣例。

**溢酬的正確定義（不是簡單相減同一條序列）**：`buyhold_ret`跟`rebal_ret`是
兩條獨立的每日報酬率序列（見`equal_weight_rebalance_sanity.py::simulate()`），
溢酬 = rebalanced複利總報酬 - buyhold複利總報酬，這個差本身不是一個可以逐日
複利的報酬率——所以「拿掉某一年」的操作是：把TRAIN期依日曆年切開，各自年度
內分別複利buyhold與rebal的daily return得到「年度total_return」，年度溢酬=
rebal年度total_return - buyhold年度total_return；再平衡溢酬要看的是跨年份
複利後的最終總溢酬是否集中在單一年份——用剩餘年份（拿掉貢獻最大的那年）
分別重新複利buyhold與rebal的年度報酬序列，兩者相減得到leave-one-out溢酬，
跟`f52w_high_gates.py::gate5_leave_one_out()`「逐年複利連乘反推」同一種精神，
只是這裡要對兩條路徑各自做一次、取差，而不是對單一equity curve做。

**事前綁定判準**：拿掉溢酬貢獻最大的那一年後，剩餘複利溢酬仍需>0，才算PASS
（跟`fut_basis_carry`判死的邏輯相同——82倍放大集中在2000-2002三年、拿掉後
轉負，就是leave-one-out要抓的典型失敗模式）。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#29第5關接續
第4關（`equal_weight_rebalance_costs_v1.py`，已PASS：1x/2x/3x情境TRAIN/VAL
淨溢酬皆維持顯著為正）執行。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from equal_weight_rebalance_sanity import (
    REBAL_FREQ,
    WINDOW_START,
    build_panel,
    load_prices,
    simulate,
)
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import holdout


def yearly_total_returns(ret_series: pd.Series, years: list[int]) -> dict[int, float]:
    """把日報酬序列依日曆年切開，各自年度內複利連乘得到年度total_return。
    某年若完全沒有資料（不在panel視窗內）則不放進dict，呼叫端要處理缺年。"""
    out = {}
    for y in years:
        sub = ret_series[ret_series.index.year == y]
        if sub.empty:
            continue
        out[y] = float((1 + sub).prod() - 1)
    return out


def compounded(yearly: dict[int, float], exclude_year: int | None = None) -> float:
    total = 1.0
    for y, v in yearly.items():
        if y == exclude_year:
            continue
        total *= (1 + v)
    return total - 1


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟sanity/第2/3/4關共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"應與前4關159檔一致（交叉確認）")

    if panel.shape[1] < 30:
        print(f"LOO GATE FAIL: panel({panel.shape[1]}檔)過少，判結構性不可靠，不繼續")
        return

    sim = simulate(panel, REBAL_FREQ)
    train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
    train = sim[train_mask]
    print(f"TRAIN期：{train.index[0].date()}..{train.index[-1].date()}"
          f"（{len(train)}個交易日）")

    years = sorted(train.index.year.unique().tolist())
    print(f"TRAIN期涵蓋日曆年：{years}（共{len(years)}年）")

    bh_yearly = yearly_total_returns(train["buyhold_ret"], years)
    rb_yearly = yearly_total_returns(train["rebal_ret"], years)
    missing_years = [y for y in years if y not in bh_yearly or y not in rb_yearly]
    if missing_years:
        print(f"警告：{missing_years}年份缺乏完整資料，兩條路徑年度切分不一致，"
              f"leave-one-out可能失真，需人工檢查")

    premium_yearly = {
        y: rb_yearly[y] - bh_yearly[y]
        for y in years if y in bh_yearly and y in rb_yearly
    }
    print("\n逐年報酬（各自獨立複利，非同一序列相減）：")
    for y in sorted(premium_yearly):
        print(f"  {y}: buyhold={bh_yearly[y]:+.2%}  rebalanced={rb_yearly[y]:+.2%}  "
              f"年度溢酬={premium_yearly[y]:+.2%}")

    if not premium_yearly:
        print("\nLOO GATE FAIL: 無法反推任何年度溢酬，判結構性不可靠。")
        return

    full_bh_total = compounded(bh_yearly)
    full_rb_total = compounded(rb_yearly)
    full_premium = full_rb_total - full_bh_total
    print(f"\n完整TRAIN期複利溢酬（跨{len(premium_yearly)}年連乘後相減）："
          f"buyhold={full_bh_total:+.2%}  rebalanced={full_rb_total:+.2%}  "
          f"溢酬={full_premium:+.2%}"
          f"（比對`equal_weight_rebalance_sanity.py`同期輸出，兩者算法一致，"
          f"應非常接近，微小差異僅可能來自日曆年切分邊界 vs 交易日邊界）")

    max_year = max(premium_yearly, key=lambda y: premium_yearly[y])
    max_year_premium = premium_yearly[max_year]
    print(f"\n溢酬貢獻最大年份={max_year}（該年溢酬={max_year_premium:+.2%}，"
          f"占完整溢酬的{max_year_premium/full_premium*100 if full_premium != 0 else float('nan'):.1f}%）")

    loo_bh_total = compounded(bh_yearly, exclude_year=max_year)
    loo_rb_total = compounded(rb_yearly, exclude_year=max_year)
    loo_premium = loo_rb_total - loo_bh_total
    print(f"拿掉{max_year}後剩餘複利溢酬：buyhold={loo_bh_total:+.2%}  "
          f"rebalanced={loo_rb_total:+.2%}  溢酬={loo_premium:+.2%}"
          f"（{'仍為正，通過leave-one-out' if loo_premium > 0 else '轉負，過度集中在單一年份'}）")

    n_positive_years = sum(1 for v in premium_yearly.values() if v > 0)
    print(f"\n附加診斷（非事前綁定判準，僅供第6關逐年一致性參考）："
          f"{n_positive_years}/{len(premium_yearly)}年年度溢酬為正")

    print("\n=== 第5關結論 ===")
    if loo_premium > 0:
        print("**PASS**——拿掉貢獻最大的單一年份後，剩餘複利溢酬仍為正，"
              "不是靠少數年份撐起全部效果，通過leave-one-out快殺門檻。"
              "不代表最終PASS——仍待第6關逐年一致性、第7關樣本外、"
              "第8關前向paper、第9關下檔保護。")
    else:
        print("**FAIL**——拿掉貢獻最大的單一年份後，剩餘複利溢酬轉負，"
              "效果過度集中在單一年份，依協定快殺標準判定，不進第6關以後。")

    out_path = Path(__file__).parent / "data" / "equal_weight_rebalance_leave_one_out_v1_yearly.csv"
    pd.DataFrame({
        "year": sorted(premium_yearly.keys()),
        "buyhold_total_return": [bh_yearly[y] for y in sorted(premium_yearly.keys())],
        "rebalanced_total_return": [rb_yearly[y] for y in sorted(premium_yearly.keys())],
        "premium": [premium_yearly[y] for y in sorted(premium_yearly.keys())],
    }).to_csv(out_path, index=False)
    print(f"\n逐年明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")


if __name__ == "__main__":
    main()
