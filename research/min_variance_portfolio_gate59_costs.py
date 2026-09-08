"""`HYPOTHESIS_QUEUE.md` #59 最小變異數投資組合建構
Minimum-Variance Portfolio Construction（共變異數矩陣版）第4關
成本/稅/滑價敏感度（1x/2x/3x）。

**沿用`equal_weight_rebalance_costs_v1.py`（#29第4關）同一套框架**（同一個
`round_trip_cost_pct()`成本模型、同一組COST_MULTIPLIERS=(1,2,3)、同一種
「buyhold路徑除t0外不額外收費」慣例），但**換手率定義必須改寫**——#29的目標
權重永遠是固定的1/n，換手率=`0.5*sum(|w_before - 1/n|)`；#59每次再平衡的
目標權重都是**重新求解的Ledoit-Wolf最小變異數解**（非固定常數），所以換手率
改成`0.5*sum(|w_before_rebal - new_w|)`——「再平衡前因報酬drift掉的權重」跟
「這次重新求解出來的目標權重」之間的差距，才是這次拉回真正需要成交的量。

**這關對#59特別重要的理由**（`HYPOTHESIS_QUEUE.md` #59 GATE2/GATE3段落已
預告）：`#59`每次拉回都要重新求解全域最小變異數解，跟#29永遠拉回同一個固定
點（1/n）不同——**沒有理由假設換手率會跟#29相近**，必須實際量化，不能沿用
#29第4關「三情境皆正」的結論。

2026-09-08 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#59第4關接續
第3關（`min_variance_portfolio_gate59_plateau.py`，已PASS：13/13網格點
TRAIN/VAL溢酬同時為正）執行。
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

COST_MULTIPLIERS = (1, 2, 3)


def simulate_with_costs(
    panel: pd.DataFrame, rebal_freq: int, cov_window: int, cost_multiplier: float
) -> pd.DataFrame:
    """跟`min_variance_portfolio_gate59.simulate()`同一套權重演算法，額外在每次
    再平衡事件對`minvar_ret`路徑扣除turnover成本（buyhold路徑除t0外不交易，不
    額外收費，沿用#29 costs腳本慣例）。回傳index=交易日、欄位
    buyhold_ret/minvar_ret_net（已扣成本）的DataFrame，attrs記錄再平衡次數與
    累計turnover供稽核。"""
    rets = panel.pct_change().dropna(how="all").fillna(0.0)
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_minvar = np.full(n, 1.0 / n)
    buyhold_rets, minvar_rets_net = [], []
    rebal_events = 0
    total_turnover = 0.0
    round_trip = costmod.round_trip_cost_pct(slippage_bps=costmod.DEFAULT_SLIPPAGE_BPS)
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
            cost_today = turnover * round_trip * cost_multiplier
            w_minvar = new_w
            rebal_events += 1

        minvar_rets_net.append(day_ret_mv - cost_today)

    out = pd.DataFrame(
        {"buyhold_ret": buyhold_rets, "minvar_ret_net": minvar_rets_net}, index=rets.index
    )
    out.attrs["rebal_events"] = rebal_events
    out.attrs["total_turnover"] = total_turnover
    out.attrs["round_trip_cost_pct_1x"] = round_trip
    return out


def main():
    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟#29/#58/#59前3關共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(
        f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
        f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
        f"應與#59前3關159檔一致（交叉確認）"
    )

    if panel.shape[1] < 30:
        print(f"COST GATE FAIL: panel({panel.shape[1]}檔)過少，判結構性不可靠，不繼續")
        return

    records = []
    for mult in COST_MULTIPLIERS:
        sim = simulate_with_costs(panel, REBAL_FREQ, COV_WINDOW, mult)
        if mult == 1:
            avg_turnover = sim.attrs["total_turnover"] / sim.attrs["rebal_events"]
            print(
                f"\n再平衡事件數：{sim.attrs['rebal_events']}次；"
                f"累計turnover：{sim.attrs['total_turnover']:.3f}"
                f"（單邊換手率總和，每次事件平均{avg_turnover:.4f}）；"
                f"單次1x round-trip成本率：{sim.attrs['round_trip_cost_pct_1x']:.4%}"
            )
        train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
        val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
        for label, mask in (("train", train_mask), ("val", val_mask)):
            sub = sim[mask]
            bh = summarize(sub["buyhold_ret"])
            mv_net = summarize(sub["minvar_ret_net"])
            premium_net = mv_net["total_return"] - bh["total_return"]
            records.append(
                {
                    "cost_multiplier": mult,
                    "period": label,
                    "buyhold_total_return": bh["total_return"],
                    "minvar_net_total_return": mv_net["total_return"],
                    "premium_net": premium_net,
                }
            )

    df = pd.DataFrame(records)
    print(f"\n=== 第4關成本/稅/滑價敏感度（1x/2x/3x，turnover×round_trip_cost×倍數） ===")
    any_negative = False
    for period in ("train", "val"):
        print(f"\n--- {period.upper()} ---")
        for _, row in df[df["period"] == period].iterrows():
            neg_mark = ""
            if row["premium_net"] < 0:
                any_negative = True
                neg_mark = "  <-- 淨溢酬轉負"
            print(
                f"  {int(row['cost_multiplier'])}x成本: buyhold={row['buyhold_total_return']:+.2%}  "
                f"minvar(淨){row['minvar_net_total_return']:+.2%}  "
                f"淨溢酬={row['premium_net']:+.2%}{neg_mark}"
            )

    print(f"\n=== 第4關結論 ===")
    if any_negative:
        print(
            "**至少一個成本情境下淨溢酬轉負，依協定誠實記錄，不隱瞞。**"
            "仍需人工/下一輪判讀轉負發生在哪個情境、幅度多大，決定是否值得"
            "繼續投入第5關以後，不由本腳本自動下PASS/FAIL判定。"
        )
    else:
        print(
            "三個成本情境（1x/2x/3x）下TRAIN與VAL淨溢酬皆維持為正，"
            "turnover成本未能吃光diversification return，支持繼續往第5關"
            "（leave-one-out）推進。不代表最終PASS——仍待leave-one-out/"
            "逐年一致性/樣本外/前向paper/下檔保護。"
        )

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    out_path = Path(__file__).parent / "data" / "min_variance_portfolio_gate59_costs_grid.csv"
    df.to_csv(out_path, index=False)
    print(f"\n明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")


if __name__ == "__main__":
    main()
