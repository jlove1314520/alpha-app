"""`HYPOTHESIS_QUEUE.md` #29 等權重再平衡溢酬 Diversification Return /
Equal-Weight Rebalancing Premium 第4關 成本/稅/滑價敏感度（1x/2x/3x）。

**為什麼這關對這條假設特別重要**：等權重再平衡不是「選幾檔股票」型策略的換手
（只換入/換出少數標的），而是**每次再平衡都要對全部159檔股票做部分調整**
（漲多的賣一點、跌多的買一點，把每檔都拉回1/159）——即使沒有任何一檔股票
真正「換掉」，這個機械式拉回動作本身就會產生實際成交量與成本。前3關（sanity/
隨機控制組/參數高原）算的都是**毛報酬（gross）溢酬**，`CONSTITUTION.md`
「踩過的雷」第5條明講「真實摩擦全部計入」——如果溢酬扣掉真實交易成本後大幅
縮水甚至轉負，代表這個「diversification return」在真實世界不可實現，只是
理論上的紙上優勢。

**成本計算方式**：沿用`long_only_vs_market.py`既有慣例
`cost = turnover * costmod.round_trip_cost_pct(slippage_bps=..., commission_discount=...) * cost_multiplier`
（`round_trip_cost_pct()`已含手續費×2＋證交稅0.3%＋滑價×2，一次涵蓋買賣兩腳，
不重造成本模型）。**turnover定義**：每次拉回前，個股權重相對1/n的絕對偏離量
總和除以2（標準單邊換手率定義，因為每一份「賣出的多餘部位」都對應一份「買進
的不足部位」，除以2才不會重複計兩次同一筆交易的兩腳）：
`turnover = 0.5 * sum(|w_i - 1/n|)`。買進持有(buyhold)路徑**除了t0建倉外
完全不交易**，t0建倉成本兩條路徑相同、在比較「溢酬」時會抵消，這裡沿用
sanity版本的慣例不對兩者都額外收t0成本（只比較t0之後的差異）。

**1x/2x/3x情境**：`cost_multiplier`直接乘在turnover cost上，1x=商業默認費率、
2x/3x=保守假設（例如折扣沒那麼多、實際滑價更大）。這是`validation/costs.py`
既有費率乘以整數倍的協定既有慣例（`pead_portfolio_v1.py`/`dividend_yield_
portfolio_v1.py`都用同一套倍數情境）。

**事前綁定的判定標準**：三個情境（1x/2x/3x）**任一情境轉負就要誠實記錄，
不能只挑1x講**（`HYPOTHESIS_QUEUE.md`統一關卡第4項原文要求）。這條假設沒有
「通過/不通過」的單一數字門檻（跟因子IC類假設的cheap gate不同），而是要看
「淨溢酬在真實成本情境下是否仍然顯著為正、是否仍支持繼續往下一關（leave-
one-out）走」——如果3x情境下TRAIN或VAL任一期淨溢酬轉負，代表這個機制在
保守成本假設下不再穩健，需要誠實記錄並重新評估是否值得繼續投入第5關以後。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#29第4關
接續第3關（`equal_weight_rebalance_plateau_v1.py`，已PASS：17/17網格點
TRAIN/VAL溢酬同時為正）執行。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import validation.costs as costmod
from equal_weight_rebalance_sanity import REBAL_FREQ, build_panel, load_prices, summarize
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import holdout

COST_MULTIPLIERS = (1, 2, 3)


def simulate_with_costs(panel: pd.DataFrame, rebal_freq: int, cost_multiplier: float) -> pd.DataFrame:
    """跟`equal_weight_rebalance_sanity.simulate()`同一套權重演算法，額外在每次
    再平衡事件對`rebal_ret`路徑扣除turnover成本（buyhold路徑除t0外不交易，不
    額外收費，沿用sanity慣例）。回傳index=交易日、欄位buyhold_ret/rebal_ret_net
    （已扣成本）的DataFrame，attrs記錄再平衡次數與累計turnover供稽核。"""
    rets = panel.pct_change().dropna(how="all").fillna(0.0)
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_rebal = np.full(n, 1.0 / n)
    buyhold_rets, rebal_rets_net = [], []
    rebal_events = 0
    total_turnover = 0.0
    round_trip = costmod.round_trip_cost_pct(slippage_bps=costmod.DEFAULT_SLIPPAGE_BPS)

    for t, (_, r) in enumerate(rets.iterrows()):
        r = r.values
        buyhold_rets.append(float(np.dot(w_buyhold, r)))
        w_buyhold = w_buyhold * (1 + r)
        w_buyhold = w_buyhold / w_buyhold.sum()

        day_ret_rb = float(np.dot(w_rebal, r))
        w_rebal = w_rebal * (1 + r)
        w_rebal = w_rebal / w_rebal.sum()

        cost_today = 0.0
        if (t + 1) % rebal_freq == 0:
            turnover = 0.5 * float(np.sum(np.abs(w_rebal - 1.0 / n)))
            total_turnover += turnover
            cost_today = turnover * round_trip * cost_multiplier
            w_rebal = np.full(n, 1.0 / n)
            rebal_events += 1

        rebal_rets_net.append(day_ret_rb - cost_today)

    out = pd.DataFrame(
        {"buyhold_ret": buyhold_rets, "rebal_ret_net": rebal_rets_net}, index=rets.index
    )
    out.attrs["rebal_events"] = rebal_events
    out.attrs["total_turnover"] = total_turnover
    out.attrs["round_trip_cost_pct_1x"] = round_trip
    return out


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟sanity/第2/3關共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    print(f"panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"應與前3關159檔一致（交叉確認）")

    if panel.shape[1] < 30:
        print(f"COST GATE FAIL: panel({panel.shape[1]}檔)過少，判結構性不可靠，不繼續")
        return

    records = []
    for mult in COST_MULTIPLIERS:
        sim = simulate_with_costs(panel, REBAL_FREQ, mult)
        if mult == 1:
            print(f"\n再平衡事件數：{sim.attrs['rebal_events']}次；"
                  f"累計turnover：{sim.attrs['total_turnover']:.3f}"
                  f"（單邊換手率總和，每次事件約{sim.attrs['total_turnover']/sim.attrs['rebal_events']:.4f}）；"
                  f"單次1x round-trip成本率：{sim.attrs['round_trip_cost_pct_1x']:.4%}")
        train_mask = sim.index <= pd.Timestamp(holdout.TRAIN_END)
        val_mask = sim.index > pd.Timestamp(holdout.TRAIN_END)
        for label, mask in (("train", train_mask), ("val", val_mask)):
            sub = sim[mask]
            bh = summarize(sub["buyhold_ret"])
            rb_net = summarize(sub["rebal_ret_net"])
            premium_net = rb_net["total_return"] - bh["total_return"]
            records.append({
                "cost_multiplier": mult, "period": label,
                "buyhold_total_return": bh["total_return"],
                "rebal_net_total_return": rb_net["total_return"],
                "premium_net": premium_net,
            })

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
            print(f"  {int(row['cost_multiplier'])}x成本: buyhold={row['buyhold_total_return']:+.2%}  "
                  f"rebalanced(淨){row['rebal_net_total_return']:+.2%}  "
                  f"淨溢酬={row['premium_net']:+.2%}{neg_mark}")

    print(f"\n=== 第4關結論 ===")
    if any_negative:
        print("**至少一個成本情境下淨溢酬轉負，依協定誠實記錄，不隱瞞。**"
              "仍需人工/下一輪判讀轉負發生在哪個情境、幅度多大，決定是否值得"
              "繼續投入第5關以後，不由本腳本自動下PASS/FAIL判定。")
    else:
        print("三個成本情境（1x/2x/3x）下TRAIN與VAL淨溢酬皆維持為正，"
              "turnover成本未能吃光diversification return，支持繼續往第5關"
              "（leave-one-out）推進。不代表最終PASS——仍待leave-one-out/"
              "逐年一致性/樣本外/前向paper/下檔保護。")

    out_path = Path(__file__).parent / "data" / "equal_weight_rebalance_costs_v1_grid.csv"
    df.to_csv(out_path, index=False)
    print(f"\n明細已存 {out_path.relative_to(Path(__file__).parent)}（gitignored）")


if __name__ == "__main__":
    main()
