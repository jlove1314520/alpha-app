"""`HYPOTHESIS_QUEUE.md` #59 最小變異數投資組合建構 第4關成本敏感度——
成本.二稽核重跑（2026-09-19，總司令裁示【成本模型更正】）。

`min_variance_portfolio_gate59_costs.py`原本的「1x/2x/3x」是`round_trip_cost_pct()`
**預設**`commission_discount=1.0`（無折扣/最貴假設）乘上壓力測試倍數，不是
總司令實際折數。TRAIN期在該檔案定義的「最寬鬆1x」情境下淨溢酬已轉負
（-0.12%，`STRATEGY_GRAVEYARD.md` #59條目），死因是換手率成本——這正是
成本.二清查要求的「因高估成本被拒的高換手方向」候選。

本檔案不改動原檔案（那支是CONSTITUTION.md要求的1x/2x/3x壓力測試，本身
沒有錯，維持原樣），另開一支只做一件事：把`round_trip_cost_pct()`換成
`commission_discount=0.18`（總司令實際折數，乘數固定1.0，不疊加壓力
測試倍數，因為這裡要問的是「用真實成本，原判定還站不站得住」而非
「用更貴的成本會多壞」），其餘完全比照原檔案（同一份`min_variance_
portfolio_gate59.py::min_variance_weights()`/`build_panel()`/`load_prices()`，
同一個TRAIN/VAL切分，同一個turnover定義）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import validation.costs as costmod
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from min_variance_portfolio_gate59 import (
    COV_WINDOW,
    REBAL_FREQ,
    build_panel,
    load_prices,
    min_variance_weights,
    summarize,
)
from validation import holdout

REAL_COMMISSION_DISCOUNT = 0.18


def simulate_with_costs(panel: pd.DataFrame, rebal_freq: int, cov_window: int) -> pd.DataFrame:
    rets = panel.pct_change().dropna(how="all").fillna(0.0)
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_minvar = np.full(n, 1.0 / n)
    buyhold_rets, minvar_rets_net = [], []
    rebal_events = 0
    total_turnover = 0.0
    round_trip = costmod.round_trip_cost_pct(
        slippage_bps=costmod.DEFAULT_SLIPPAGE_BPS,
        commission_discount=REAL_COMMISSION_DISCOUNT,
    )
    ret_values = rets.values

    for t in range(ret_values.shape[0]):
        r = ret_values[t]
        buyhold_rets.append(float(np.dot(w_buyhold, r)))
        w_buyhold = w_buyhold * (1 + r)
        w_buyhold = w_buyhold / w_buyhold.sum()

        day_ret_mv = float(np.dot(w_minvar, r))
        w_minvar = w_minvar * (1 + r)
        w_minvar = w_minvar / w_minvar.sum()

        cost_today = 0.0
        if (t + 1) % rebal_freq == 0 and t + 1 >= cov_window:
            window = ret_values[t + 1 - cov_window : t + 1]
            new_w = min_variance_weights(window)
            turnover = 0.5 * float(np.sum(np.abs(w_minvar - new_w)))
            total_turnover += turnover
            cost_today = turnover * round_trip
            w_minvar = new_w
            rebal_events += 1

        minvar_rets_net.append(day_ret_mv - cost_today)

    out = pd.DataFrame(
        {"buyhold_ret": buyhold_rets, "minvar_ret_net": minvar_rets_net}, index=rets.index
    )
    out.attrs["rebal_events"] = rebal_events
    out.attrs["total_turnover"] = total_turnover
    out.attrs["round_trip_cost_pct"] = round_trip
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日")

    sim = simulate_with_costs(panel, REBAL_FREQ, COV_WINDOW)
    avg_turnover = sim.attrs["total_turnover"] / sim.attrs["rebal_events"]
    print(
        f"再平衡事件數：{sim.attrs['rebal_events']}次；平均單次turnover：{avg_turnover:.4f}；"
        f"round-trip成本率(commission_discount={REAL_COMMISSION_DISCOUNT})："
        f"{sim.attrs['round_trip_cost_pct']:.4%}（舊表1.0折=0.6850%）"
    )

    train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
    print(f"\n=== 第4關成本敏感度（1.8折，commission_discount={REAL_COMMISSION_DISCOUNT}） ===")
    for label, mask in (("TRAIN", train_mask), ("VAL", val_mask)):
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        mv_net = summarize(sub["minvar_ret_net"])
        premium_net = mv_net["total_return"] - bh["total_return"]
        neg_mark = "  <-- 淨溢酬轉負" if premium_net < 0 else "  <-- 淨溢酬為正"
        print(
            f"  {label}: buyhold={bh['total_return']:+.2%}  minvar(淨)={mv_net['total_return']:+.2%}  "
            f"淨溢酬={premium_net:+.2%}{neg_mark}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
