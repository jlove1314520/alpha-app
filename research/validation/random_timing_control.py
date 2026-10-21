"""隨機進出場時點控制組（先.一二七-C，2026-10-21 總司令核准：只新增，不改既有驗證邏輯）。

`control_group.run_matched_control_group()` 保留真實策略的進出場日期、隨機換「股票」；
網格這類**單股時間序列**機制要問的是另一件事：同一檔股票、同樣筆數、同樣持有天數，
只是**進場時點**亂選，能不能也賺到一樣的錢？如果能，網格的「格線觸發」就沒有資訊量，
報酬只是持有那些股票本身的漂移。

做法（每一次抽樣）：
- 每一筆真實交易保留 stock_id 與持有交易日數 h（用該股自己的價格列計算）；
- 進場日改成「同一個日曆月內、該股任一個交易日 d」，出場日＝d 之後第 h 個交易日；
  只從進出場兩端價格都有效（>0、非 NaN）的 d 裡抽；
- 該月沒有任何有效的 d → 這筆交易保留原日期（次數記在 `kept_original`，照實揭露）；
- 部位大小與成本公式和 `run_matched_control_group()` 完全一樣（cost_rates 由呼叫端
  從真實回測傳入，不在這裡另算）。

回傳沿用 `control_group.ControlGroupResult`，另附 `kept_original_per_draw`。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import pandas as pd

from .control_group import ControlGroupResult


@dataclass
class TimingControlResult(ControlGroupResult):
    kept_original_per_draw: list[int] = field(default_factory=list)


def _valid(px: float) -> bool:
    return px > 0  # NaN 比較永遠是 False，同時擋掉 <=0 與 NaN


def run_random_timing_control(
    trade_schedule: list[dict],
    price_data: dict[str, pd.DataFrame],
    strategy_final_equity: float,
    initial_capital: float,
    slot_allocation: float,
    cost_rates: dict[str, float],
    n_random: int = 1000,
    seed: int = 20261021,
    thresholds: tuple[int, ...] = (50, 90, 95, 99),
    date_col: str = "date",
    price_col: str = "adj_open",
) -> TimingControlResult:
    """trade_schedule：每筆 {'stock_id', 'entry_date', 'exit_date'}（日期需在該股價格列裡）。
    price_data：stock_id → 含 date_col／price_col 的 DataFrame（日期遞增）。"""
    rng = random.Random(seed)
    series = {}
    for sid, df in price_data.items():
        s = df[[date_col, price_col]].dropna(subset=[date_col]).sort_values(date_col)
        series[sid] = (list(pd.to_datetime(s[date_col])), [float(x) for x in s[price_col]])

    # 事先算好每筆交易的持有天數與「同月可抽的進場位置」，抽樣時只做隨機選擇
    plans = []
    for t in trade_schedule:
        sid = t["stock_id"]
        if sid not in series:
            continue
        dates, px = series[sid]
        pos = {d: i for i, d in enumerate(dates)}
        e, x = pd.Timestamp(t["entry_date"]), pd.Timestamp(t["exit_date"])
        if e not in pos or x not in pos or pos[x] <= pos[e]:
            continue
        ei, h = pos[e], pos[x] - pos[e]
        cands = [i for i, d in enumerate(dates)
                 if d.year == e.year and d.month == e.month and i + h < len(dates)
                 and _valid(px[i]) and _valid(px[i + h])]
        plans.append((px, ei, h, cands))

    def pnl(px: list[float], i: int, h: int) -> float:
        entry_price, exit_price = px[i], px[i + h]
        if not _valid(entry_price) or not _valid(exit_price):
            return 0.0
        shares = int(slot_allocation // (entry_price * (1 + cost_rates["buy"])))
        if shares <= 0:
            return 0.0
        entry_notional = shares * entry_price
        exit_notional = shares * exit_price
        return ((exit_notional - exit_notional * cost_rates["sell"])
                - (entry_notional + entry_notional * cost_rates["buy"]))

    random_metrics, kept = [], []
    for _ in range(n_random):
        total, k = 0.0, 0
        for px, ei, h, cands in plans:
            if cands:
                total += pnl(px, rng.choice(cands), h)
            else:
                k += 1
                total += pnl(px, ei, h)
        random_metrics.append(initial_capital + total)
        kept.append(k)

    beats = sum(1 for m in random_metrics if strategy_final_equity > m)
    percentile = 100.0 * beats / len(random_metrics) if random_metrics else float("nan")
    return TimingControlResult(
        candidate_metric=strategy_final_equity,
        random_metrics=random_metrics,
        percentile=percentile,
        n_random=n_random,
        beats_random_at={t: percentile >= t for t in thresholds},
        kept_original_per_draw=kept,
    )
