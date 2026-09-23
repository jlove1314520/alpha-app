"""Generic backtest engine skeleton (Milestone 4 kickoff, 2026-08-22).

Hard rules enforced structurally here, not just documented:

- **No look-ahead.** The engine walks the calendar one trading day at a
  time. A decision made "as of" day T (whether from the daily risk checks
  or a rebalance-day signal call) may only see price rows already inside
  the DataFrames it was handed, indexed up to and including T -- it never
  peeks at T+1 or later, because those rows simply haven't been reached by
  the loop pointer yet. Every decision executes at T's next trading day's
  close (EXECUTION_LAG_DAYS below), never same-day, so a signal computed
  from T's close can never also fill at T's close.
- **No holdout leakage.** Every price DataFrame handed to run_backtest() is
  checked with validation.holdout.assert_no_holdout_leakage() before the
  engine touches it. This engine never fetches data itself -- that is the
  caller's job, and it must go through finmind_client.load_dev() (directly,
  or via adjust.py / pit.py which already route through it). This engine
  has no knowledge of _fetch() and should never gain any.
- **All costs come from validation.costs.** Commission/tax rates and the
  limit-lock detector are imported from there, never redefined here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from validation import costs as costmod
from validation.holdout import assert_no_holdout_leakage

EXECUTION_LAG_DAYS = 1  # a decision made using day T's close data executes at day T+1's close


@dataclass
class BacktestConfig:
    start_date: str
    end_date: str
    rebalance_weekday: int = 4  # Friday = 4 (Monday = 0); signal_fn is called on rebalance days
    rebalance_every_n_days: int | None = None  # 2026-08-26 新增（portfolio_backtest_v2.py 需要
    # 月頻/季頻換股，`rebalance_weekday` 只能做到「每週固定星期幾」，做不到「每 21/63 個交易日」）。
    # None（預設）＝完全比照舊行為，用 `rebalance_weekday`；設定這個欄位後改用「日曆序位
    # 索引 % N == 0」判斷換股日，`rebalance_weekday` 那個值在這個模式下被忽略。這是純加法
    # 擴充，不影響任何既有呼叫端（它們都沒有設定這個新欄位，維持 None，行為完全不變）。
    rebalance_phase: int = 0  # 2026-09-07 新增（Cybex.債務5 相位敏感度）：換股日的「起始相位」。
    # 固定週期重平衡的相位是**任意選的**——同一個策略只是換個起始日，績效可能差很多
    # （Cybex 第 315 輪跨相位 Calmar 1.006～2.084，差近兩倍）。所以相位必須是可掃的參數，
    # 不能是寫死的 0。兩種模式各自的意義：
    #   - `rebalance_every_n_days` 模式：換股日判定從 `day_i % N == 0` 改為
    #     `(day_i - phase) % N == 0`，phase 取 0..N-1。
    #   - `rebalance_weekday` 模式：換股日判定從 `weekday == W` 改為
    #     `weekday == (W + phase) % 5`，phase 取 0..4（週一到週五）。
    # 預設 0 ＝ 完全比照舊行為，既有呼叫端一個字都不用改，行為位元級相同。
    max_positions: int = 10
    stop_loss_pct: float = 0.15  # tier-3 hard stop, independent of the MA exit
    compounding: bool = True  # 2026-09-23（總司令裁示【三個方法缺陷＋E-c/E-d走正式閘門】
    # 驗.一）：舊行為每筆買進固定用`initial_capital/max_positions`當額度，不管組合當下
    # 實際權益是多少——獲利/虧損留在零息現金，不會被下一筆買進的資金基礎吸收，等於
    # 「引擎不複利」。跟會複利的0050總報酬比較時，換手越高低估越嚴重（實測：240檔
    # 等權重月頻再平衡，舊行為CAGR=0.20% vs pandas直接算12.19%，差近12個百分點；
    # 隨機8檔100 seed同樣崩到中位數CAGR約-0.01%）。**True（新預設）**＝買進額度改用
    # `當下總權益(mtm) / max_positions`（見`_slot_allocation()`），讓資金基礎隨真實
    # 績效更新；**False**＝完全比照舊行為（固定用`initial_capital/max_positions`），
    # 供需要重現舊結果時使用，不強迫所有既有試驗一次全部改判。
    initial_capital: float = 1_000_000.0
    slippage_bps: float = 5.0
    commission_discount: float = 1.0
    cost_multiplier: float = 1.0  # for 1x/2x/3x cost-sensitivity testing
    book_name: str = "weinstein_stage2_pilot"  # 2026-08-23: parameterized -- this was hardcoded into
    # the two trade-row dicts below, which mislabeled every trade's audit book as "weinstein_stage2_pilot"
    # even when run_backtest() is reused for an unrelated strategy (e.g. score.py's top-N portfolio).
    # Default preserves the exact old behavior for existing callers that don't set it.
    instrument_type: str = "normal"  # 2026-09-23（修.二）: passed straight to
    # `validation.costs.tax_rate()`. Default "normal" preserves the EXACT prior
    # behavior (SECURITIES_TX_TAX_NORMAL) for every existing caller -- this engine
    # is shared by many individual-TW-stock strategies for which 0.3% is the
    # correct rate. Set to "etf" only when the backtested position genuinely IS
    # an ETF (e.g. 0050) -- never guess from the ticker string.


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame  # columns: date, equity, zombie_positions（2026-09-23
    # 驗.一新增：當天mark-to-market時有幾檔持倉找不到當日有效價格、退回last_valid_
    # price或entry_price估值——沿用既有欄位的呼叫端不受影響，只多一欄可忽略）
    trades: pd.DataFrame        # matches audit_ledgers.TRADES_SCHEMA
    config: BacktestConfig
    unresolved_at_end: list[str] = field(default_factory=list)  # stock_ids stuck limit-locked at cutoff

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve["equity"].iloc[-1]) if len(self.equity_curve) else self.config.initial_capital

    @property
    def total_return_pct(self) -> float:
        return (self.final_equity / self.config.initial_capital - 1) * 100

    @property
    def max_drawdown_pct(self) -> float:
        eq = self.equity_curve["equity"]
        if eq.empty:
            return 0.0
        running_max = eq.cummax()
        dd = (eq - running_max) / running_max
        return float(dd.min() * 100)

    @property
    def sortino_ratio(self) -> float:
        """Annualized Sortino ratio from the daily equity curve. MAR (minimum
        acceptable return) is 0 -- a simplification disclosed here rather than
        silently assumed: this treats "any daily loss" as downside, not "any
        return below the risk-free rate". Revisit if a risk-free benchmark
        becomes relevant to a specific comparison.
        """
        eq = self.equity_curve["equity"]
        if len(eq) < 2:
            return float("nan")
        daily_returns = eq.pct_change().dropna()
        if daily_returns.empty:
            return float("nan")
        downside = daily_returns[daily_returns < 0]
        downside_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
        if downside_dev == 0:
            return float("nan")
        return float(daily_returns.mean() / downside_dev * np.sqrt(252))


def buy_leg_rate(config: BacktestConfig) -> float:
    """Single source of truth for the buy-leg cost fraction -- also imported
    by validation.control_group.run_matched_control_group() so a random
    control draw can never silently use a different cost assumption than
    the real backtest it's being compared against.
    """
    return costmod.COMMISSION_RATE * config.commission_discount * config.cost_multiplier + \
        (config.slippage_bps / 10_000) * config.cost_multiplier


def sell_leg_rate(config: BacktestConfig) -> float:
    """Single source of truth for the sell-leg cost fraction (commission +
    tax + slippage). See buy_leg_rate()'s docstring. Tax rate comes from
    `config.instrument_type` (default "normal", see `BacktestConfig` field
    docstring) via `validation.costs.tax_rate()` -- not hardcoded here.
    """
    return (costmod.COMMISSION_RATE * config.commission_discount + costmod.tax_rate(config.instrument_type)) \
        * config.cost_multiplier + (config.slippage_bps / 10_000) * config.cost_multiplier


def run_backtest(
    signal_fn,
    price_data: dict[str, pd.DataFrame],
    market_df: pd.DataFrame,
    config: BacktestConfig,
) -> BacktestResult:
    """Walk the calendar day by day, applying `signal_fn` on rebalance days
    and a fixed three-tier risk control every day.

    signal_fn(price_data, as_of_date, market_df) -> dict[stock_id, float]
        Called only on rebalance days. Must return eligible stock_ids with a
        score (higher = more preferred); engine takes the top `max_positions`
        not already held first, then fills remaining open slots by rank.
        signal_fn is responsible for its own look-ahead discipline (it will
        typically pre-index rolling stats on price_data and look them up at
        as_of_date -- see strategies/weinstein_stage2.py for the pattern).

    Three-tier risk control (checked daily on every held position):
        1. MA exit: `ma150` column (if present in price_data[sid]) falls
           below adj_close -- i.e. exit once price closes back below its
           own 150-day moving average (classic stage-2 -> stage-4 signal).
        2. Position limits: enforced at entry time via max_positions and a
           fixed per-slot allocation (initial_capital / max_positions);
           never more than max_positions held at once.
        3. Hard stop-loss: exit if adj_close <= entry_price * (1 - stop_loss_pct),
           independent of the MA -- catches gap-down moves the MA exit
           wouldn't react to until the MA itself turns.
    """
    for sid, df in price_data.items():
        assert_no_holdout_leakage(df, date_col="date", context=f"price_data[{sid}]")
    assert_no_holdout_leakage(market_df, date_col="date", context="market_df")

    idx = {sid: df.set_index("date") for sid, df in price_data.items()}
    calendar = sorted(
        d for d in market_df["date"] if config.start_date <= d <= config.end_date
    )
    if not calendar:
        raise ValueError("empty trading calendar for the given start/end date range")

    cash = config.initial_capital
    positions: dict[str, dict] = {}   # stock_id -> {shares, entry_price, entry_date, entry_trade_id, entry_notional, entry_fee}
    pending: list[dict] = []          # scheduled fills: {execute_date, stock_id, side, reason}
    trades: list[dict] = []
    equity_rows: list[dict] = []
    trade_counter = 0
    slot_allocation = config.initial_capital / config.max_positions  # config.compounding=False專用，見下方_current_slot_allocation()
    last_known_equity = config.initial_capital  # 每日mark-to-market後更新，供compounding=True的動態額度使用
    last_valid_price: dict[str, float] = {}  # sid -> 最近一次有效(非0/非NaN)的adj_close，供補救行情缺口/資料錯誤用

    def _current_slot_allocation() -> float:
        # compounding=True（新預設）：用「最近一次算出的組合總權益」平均分配到
        # max_positions個名額，讓買進額度隨真實績效更新，這是複利的核心修正。
        # compounding=False：完全比照舊行為，固定用initial_capital/max_positions，
        # 不管組合當下實際權益多少（供需要重現舊結果時使用）。
        return (last_known_equity / config.max_positions) if config.compounding else slot_allocation

    def next_trading_day(day: str) -> str | None:
        i = calendar.index(day)
        return calendar[i + EXECUTION_LAG_DAYS] if i + EXECUTION_LAG_DAYS < len(calendar) else None

    def schedule(day: str, sid: str, side: str, reason: str) -> None:
        exec_day = next_trading_day(day)
        if exec_day is None:
            return
        if any(p["stock_id"] == sid and p["side"] == side for p in pending):
            return  # already scheduled, don't double-queue
        pending.append({"execute_date": exec_day, "stock_id": sid, "side": side, "reason": reason})

    for day_i, day in enumerate(calendar):
        # 1) execute anything scheduled for today; re-queue anything blocked by a locked limit
        still_pending = []
        for p in pending:
            if p["execute_date"] != day:
                still_pending.append(p)
                continue
            sid = p["stock_id"]
            row = idx.get(sid, pd.DataFrame()).loc[day] if sid in idx and day in idx[sid].index else None
            if row is None:
                still_pending.append({**p, "execute_date": next_trading_day(day) or day})
                continue
            prev_dates = [d for d in idx[sid].index if d < day]
            prev_close = idx[sid].loc[prev_dates[-1], "close"] if prev_dates else None
            locked = costmod.limit_status(row["open"], row["max"], row["min"], row["close"], prev_close) \
                if prev_close else costmod.LimitStatus(False, False)

            if p["side"] == "buy" and locked.limit_up:
                nd = next_trading_day(day)
                if nd:
                    still_pending.append({**p, "execute_date": nd})
                continue
            if p["side"] == "sell" and locked.limit_down:
                nd = next_trading_day(day)
                if nd:
                    still_pending.append({**p, "execute_date": nd})
                continue

            fill_price = float(row["adj_close"])
            if fill_price <= 0 or pd.isna(fill_price):
                # Bug fixed 2026-08-22 (found via a 100-stock random-universe run): a bad/zero
                # price row (thinly-traded or delisted-adjacent name) reached the division below
                # and raised ZeroDivisionError. Skip this fill; retry next day rather than crash
                # the whole backtest over one stock's one bad row.
                nd = next_trading_day(day)
                if nd:
                    still_pending.append({**p, "execute_date": nd})
                continue
            trade_counter += 1
            tid = f"T{trade_counter:06d}"
            if p["side"] == "buy":
                shares = int(_current_slot_allocation() // (fill_price * (1 + buy_leg_rate(config))))
                if shares <= 0 or sid in positions:
                    continue
                notional = shares * fill_price
                fee = notional * costmod.COMMISSION_RATE * config.commission_discount * config.cost_multiplier
                slip = notional * (config.slippage_bps / 10_000) * config.cost_multiplier
                total_cost = notional + fee + slip
                if total_cost > cash:
                    continue
                cash -= total_cost
                positions[sid] = {
                    "shares": shares, "entry_price": fill_price, "entry_date": day,
                    "entry_trade_id": tid, "entry_notional": notional, "entry_fee": fee + slip,
                }
                trades.append({
                    "trade_id": tid, "book": config.book_name, "stock_id": sid, "side": "buy",
                    "date": day, "price": fill_price, "shares": shares, "fees": fee, "tax": 0.0,
                    "realized_pnl": 0.0, "entry_trade_id": "", "note": p["reason"],
                })
            else:  # sell
                pos = positions.pop(sid, None)
                if pos is None:
                    continue
                shares = pos["shares"]
                notional = shares * fill_price
                tax = notional * costmod.tax_rate(config.instrument_type) * config.cost_multiplier
                fee = notional * costmod.COMMISSION_RATE * config.commission_discount * config.cost_multiplier
                slip = notional * (config.slippage_bps / 10_000) * config.cost_multiplier
                proceeds = notional - tax - fee - slip
                cash += proceeds
                realized_pnl = proceeds - (pos["entry_notional"] + pos["entry_fee"])
                trades.append({
                    "trade_id": tid, "book": config.book_name, "stock_id": sid, "side": "sell",
                    "date": day, "price": fill_price, "shares": shares, "fees": fee, "tax": tax,
                    "realized_pnl": realized_pnl, "entry_trade_id": pos["entry_trade_id"], "note": p["reason"],
                })
        pending = still_pending

        # 2) daily risk checks on held positions (tiers 1 and 3)
        # 2026-09-23（驗.一）：實測發現真實資料裡偶爾出現adj_close恰好等於0.0
        # 的錯誤數值（前後兩天都是正常價格，明顯是資料品質問題不是真實下市/
        # 跌停）——舊版直接拿這個0.0去跟stop_loss_pct比較，`0.0 <= entry_price*
        # (1-1.0) = 0.0`剛好成立，即使stop_loss_pct設成理論上不可能觸發的1.0
        # 也會被這種錯誤資料點誤觸發強制出場。改成：非正值或NaN一律視為當天
        # 沒有可信的價格，跳過風控判斷（不觸發MA-exit也不觸發stop-loss），
        # 但仍更新`last_valid_price`供mark-to-market使用（見步驟4）。
        for sid in list(positions.keys()):
            if sid not in idx or day not in idx[sid].index:
                continue
            row = idx[sid].loc[day]
            adj_close = float(row["adj_close"])
            if adj_close <= 0 or pd.isna(adj_close):
                continue  # 無效價格：不更新last_valid_price、不觸發任何風控判斷
            last_valid_price[sid] = adj_close
            pos = positions[sid]
            ma150 = row.get("ma150")
            if ma150 is not None and not pd.isna(ma150) and adj_close < ma150:
                schedule(day, sid, "sell", "tier1_ma_exit")
                continue
            if adj_close <= pos["entry_price"] * (1 - config.stop_loss_pct):
                schedule(day, sid, "sell", "tier3_hard_stop")

        # 3) rebalance day: run the signal, schedule exits/entries
        is_rebalance_day = (
            ((day_i - config.rebalance_phase) % config.rebalance_every_n_days == 0)
            if config.rebalance_every_n_days is not None
            else (pd.Timestamp(day).weekday() == (config.rebalance_weekday + config.rebalance_phase) % 5)
        )
        if is_rebalance_day:
            scores = signal_fn(price_data, day, market_df)
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            eligible_ids = {sid for sid, _ in ranked}
            for sid in list(positions.keys()):
                if sid not in eligible_ids:
                    schedule(day, sid, "sell", "rebalance_dropped")
            open_slots = config.max_positions - len(positions) - sum(1 for p in pending if p["side"] == "buy")
            for sid, _score in ranked:
                if open_slots <= 0:
                    break
                if sid in positions or any(p["stock_id"] == sid and p["side"] == "buy" for p in pending):
                    continue
                schedule(day, sid, "buy", "rebalance_entry")
                open_slots -= 1

        # 4) mark to market
        # 2026-09-23（驗.一第3點）：找不到價格（下市/長期停牌/當天資料缺漏或
        # 無效）時，舊版mark在entry_price——若股票已經漲跌很多年後才下市，
        # entry_price是進場當下的價格，拿它當「現在」的估值會嚴重失真（可能
        # 高估也可能低估，取決於方向）。改成優先用`last_valid_price`（該檔
        # 最近一次看到的有效價格），沒有任何有效價格紀錄時才退回entry_price
        # （例如上市第一天就遇到資料缺漏，不曾有過有效價格可用）。
        mtm = cash
        zombie_count = 0
        for sid, pos in positions.items():
            has_today_valid = False
            if sid in idx and day in idx[sid].index:
                today_price = float(idx[sid].loc[day, "adj_close"])
                if today_price > 0 and not pd.isna(today_price):
                    mtm += pos["shares"] * today_price
                    has_today_valid = True
            if not has_today_valid:
                mark_price = last_valid_price.get(sid, pos["entry_price"])
                mtm += pos["shares"] * mark_price
                zombie_count += 1
        equity_rows.append({"date": day, "equity": mtm, "zombie_positions": zombie_count})
        last_known_equity = mtm

    unresolved = sorted({p["stock_id"] for p in pending})
    return BacktestResult(
        equity_curve=pd.DataFrame(equity_rows),
        trades=pd.DataFrame(trades),
        config=config,
        unresolved_at_end=unresolved,
    )
