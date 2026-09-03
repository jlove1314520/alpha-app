"""US equity portfolio backtest engine -- Top-N long-only, monthly/quarterly
rebalance (US-track counterpart to `backtest/engine.py`'s TW model).

**Why this is a marathon work unit (2026-09-04 round, US track, protocol
section 5's "US可先建立跟TW同構的組合回測地基")**: the US track already has
factor-level infra (`us_universe.py`/`us_pit.py`/`us_factors.py`/
`us_factor_ic.py`/`validation/us_costs.py`), but no Top-N/rebalance
portfolio engine analogous to TW's `portfolio_backtest_v2.py` (which needs
`backtest/engine.py`). Without this piece, the US track cannot run a
`PORTFOLIO_STRATEGY_SPEC.md`-style multi-factor Top-N backtest at all --
this file is that missing piece, not a factor test itself.

**Why this is a SEPARATE module, not a reuse of `backtest/engine.py`**:
`backtest/engine.py`'s `buy_leg_rate()`/`sell_leg_rate()` call
`validation/costs.py`'s TW-specific flat percentage rates
(`costmod.COMMISSION_RATE`, `costmod.SECURITIES_TX_TAX_NORMAL`) directly --
signature only takes a config, no price/shares. `validation/us_costs.py`'s
functions need `price`/`shares` (US regulatory fees are absolute-dollar/
per-share with floors/caps, not scale-invariant percentages -- see that
module's own docstring). `deep_dive_f_us_low_vol.py` already hit this exact
incompatibility and wrote its own custom loop rather than monkeypatch
`backtest/engine.py`'s `costmod` reference (see that file's module
docstring for the reasoning) -- this module follows the same precedent,
generalized into a reusable Top-N long-only engine instead of a one-off
decile long-short loop, because the portfolio-strategy track (this file's
reason to exist) needs Top-N/rebalance mechanics `deep_dive_f_us_low_vol.py`
never needed.

Mechanics mirrored from `backtest/engine.py` unchanged (see that file's own
docstring for why these rules exist, not repeated here): no look-ahead,
`EXECUTION_LAG_DAYS`-delayed fills (imported from `backtest.engine`, not
redefined, so the two engines can never silently drift on this number),
mark-to-market every day, `assert_no_holdout_leakage()` on every price
DataFrame before the loop touches it.

**Differences from the TW engine, each disclosed rather than silently
inherited:**
1. **No limit-lock detection.** `validation/us_costs.py`'s own docstring:
   "No daily price-limit lock ... does not exist for US-listed common
   stock." A scheduled fill here always executes at the next trading day's
   `adj_close` if a price row exists that day (still subject to
   `EXECUTION_LAG_DAYS`). US exchange circuit breakers (LULD) are a
   different mechanism (halt-and-reopen, not a fixed daily band) and are
   NOT modeled here -- same gap `us_costs.py` already discloses on the
   cost side.
2. **Cost is computed per-fill, not precomputed as a config-level
   fraction.** `us_costs.py`'s regulatory fees (SEC fee has a floor-free
   proportional rate; FINRA TAF has a floor AND a cap) are not
   scale-invariant, so a single "leg rate" constant the way TW's
   `buy_leg_rate()`/`sell_leg_rate()` precompute cannot exist here --
   see `_buy_leg_cost()`/`_sell_leg_cost()` below, which duplicate (not
   import) `us_costs.py`'s private `_sec_fee()`/`_finra_taf()` formulas
   using only that module's PUBLIC constants (`SEC_FEE_RATE_PER_DOLLAR`,
   `FINRA_TAF_PER_SHARE`, `FINRA_TAF_MIN`, `FINRA_TAF_MAX_PER_TRADE`).
   This is a disclosed coupling: if `us_costs.py` ever changes those
   formulas (not just the rate constants), this module's two helpers must
   be updated to match, or the two will silently diverge.
3. **`cost_multiplier` (1x/2x/3x sensitivity) applies to slippage and
   `commission_per_share` only, NOT to the SEC fee/FINRA TAF.** Those two
   are current statutory/regulatory rates (see `us_costs.py`'s
   "rate-vintage honesty note"), not a friction assumption this project
   is uncertain about the way slippage is -- multiplying a statutory fee
   by 3x to "stress test" it would not represent any real scenario.
4. **Column contract is minimal: `date` + `adj_close` only.** Unlike the
   TW engine (which reads `open`/`max`/`min`/`close` for the limit-lock
   check), this engine's fill price AND mark-to-market price are both
   `adj_close` -- there is no separate "the order book might not fill at
   the close" mechanism here (see point 1). `open`/`high`/`low`/`volume`
   columns, if present in a price_data DataFrame (as `us_factors.py`'s
   `prepare_us_factors()` output has), are available to `signal_fn` but
   this engine itself never reads them.
5. **The `ma150`-column tier-1 exit is inherited as dead-but-harmless
   code, not removed.** The daily risk check below still looks for an
   optional `ma150` column exactly like the TW engine does -- today's US
   `price_data` (from `us_factors.py`) never has that column, so this
   tier never fires in practice yet, but keeping the check costs nothing
   and means a future US strategy that adds its own `ma150` column
   upstream gets the same opt-in exit mechanism for free, consistent with
   how the TW engine already treats it as opt-in.

**Not yet run against real US data.** This round only builds the engine and
self-tests (`__main__`) its mechanics against a small synthetic in-memory
price series -- zero FinMind API calls, per protocol section 4's quota-
discipline spirit (no reason to spend API budget validating engine
mechanics that a synthetic fixture can check for free). Wiring this to a
real US universe sample + real factor scores (the `PORTFOLIO_STRATEGY_SPEC.
md`-equivalent for US) is the next work unit, left for a future round.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtest.engine import EXECUTION_LAG_DAYS
from validation import us_costs as us_costmod
from validation.holdout import assert_no_holdout_leakage


@dataclass
class USPortfolioConfig:
    start_date: str
    end_date: str
    rebalance_every_n_days: int = 21  # 21 ~= monthly, 63 ~= quarterly, same trading-day
    # approximation `backtest/engine.py`'s `rebalance_every_n_days` field already uses for TW.
    max_positions: int = 20
    stop_loss_pct: float = 0.15
    initial_capital: float = 1_000_000.0
    slippage_bps: float = us_costmod.DEFAULT_SLIPPAGE_BPS
    commission_per_share: float = us_costmod.COMMISSION_PER_SHARE  # default 0.0 (Schwab/IBKR
    # Lite reality, see us_costs.py docstring); pass IBKR_PRO_COMMISSION_PER_SHARE for sensitivity.
    cost_multiplier: float = 1.0  # applies to slippage + commission_per_share only, see point 3
    book_name: str = "us_portfolio_pilot"


@dataclass
class USPortfolioResult:
    equity_curve: pd.DataFrame  # columns: date, equity
    trades: pd.DataFrame
    config: USPortfolioConfig
    unresolved_at_end: list[str] = field(default_factory=list)

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
        """Same MAR=0 simplification as `backtest.engine.BacktestResult`
        -- see that class's docstring, not repeated here."""
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


def _buy_leg_cost(notional: float, shares: float, config: USPortfolioConfig) -> float:
    """Buy-leg absolute dollar cost: commission + slippage only (no SEC fee
    or FINRA TAF -- both are sell-side only, see us_costs.py docstring)."""
    commission = config.commission_per_share * shares * config.cost_multiplier
    slippage = notional * (config.slippage_bps / 10_000) * config.cost_multiplier
    return commission + slippage


def _sell_leg_cost(notional: float, shares: float, config: USPortfolioConfig) -> float:
    """Sell-leg absolute dollar cost: commission + slippage + SEC fee +
    FINRA TAF. The SEC-fee/TAF formulas duplicate `us_costs._sec_fee()`/
    `_finra_taf()` using only that module's public constants -- see this
    module's docstring point 2 for why, and the disclosed coupling risk."""
    commission = config.commission_per_share * shares * config.cost_multiplier
    slippage = notional * (config.slippage_bps / 10_000) * config.cost_multiplier
    sec_fee = notional * us_costmod.SEC_FEE_RATE_PER_DOLLAR
    taf = min(max(shares * us_costmod.FINRA_TAF_PER_SHARE, us_costmod.FINRA_TAF_MIN),
              us_costmod.FINRA_TAF_MAX_PER_TRADE)
    return commission + slippage + sec_fee + taf


def run_us_backtest(
    signal_fn,
    price_data: dict[str, pd.DataFrame],
    market_df: pd.DataFrame,
    config: USPortfolioConfig,
) -> USPortfolioResult:
    """Walk the calendar day by day, applying `signal_fn` on rebalance days
    and a hard stop-loss every day. See module docstring for how this
    differs from `backtest.engine.run_backtest()` (the TW version).

    signal_fn(price_data, as_of_date, market_df) -> dict[stock_id, float]
        Same contract as the TW engine's `signal_fn` -- called only on
        rebalance days, returns eligible stock_ids with a score (higher =
        more preferred); engine takes the top `max_positions` not already
        held first, then fills remaining open slots by rank.

    `market_df` must have a `date` column spanning the desired calendar
    (e.g. SPY's own price history -- see `deep_dive_f_us_low_vol.py`'s
    `_load_market_benchmark()` for the existing SPY-fetch pattern); this
    engine does not fetch data itself, same separation of concerns as the
    TW engine.
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
    positions: dict[str, dict] = {}
    pending: list[dict] = []
    trades: list[dict] = []
    equity_rows: list[dict] = []
    trade_counter = 0
    slot_allocation = config.initial_capital / config.max_positions

    def next_trading_day(day: str) -> str | None:
        i = calendar.index(day)
        return calendar[i + EXECUTION_LAG_DAYS] if i + EXECUTION_LAG_DAYS < len(calendar) else None

    def schedule(day: str, sid: str, side: str, reason: str) -> None:
        exec_day = next_trading_day(day)
        if exec_day is None:
            return
        if any(p["stock_id"] == sid and p["side"] == side for p in pending):
            return
        pending.append({"execute_date": exec_day, "stock_id": sid, "side": side, "reason": reason})

    for day_i, day in enumerate(calendar):
        # 1) execute anything scheduled for today (no limit-lock check -- see docstring point 1)
        still_pending = []
        for p in pending:
            if p["execute_date"] != day:
                still_pending.append(p)
                continue
            sid = p["stock_id"]
            if sid not in idx or day not in idx[sid].index:
                nd = next_trading_day(day)
                if nd:
                    still_pending.append({**p, "execute_date": nd})
                continue
            fill_price = float(idx[sid].loc[day, "adj_close"])
            if fill_price <= 0 or pd.isna(fill_price):
                nd = next_trading_day(day)
                if nd:
                    still_pending.append({**p, "execute_date": nd})
                continue
            trade_counter += 1
            tid = f"US{trade_counter:06d}"
            if p["side"] == "buy":
                # first-pass share count ignoring cost, then check the true all-in cost fits cash
                shares = int(slot_allocation // fill_price)
                if shares <= 0 or sid in positions:
                    continue
                notional = shares * fill_price
                cost = _buy_leg_cost(notional, shares, config)
                total_cost = notional + cost
                if total_cost > cash:
                    continue
                cash -= total_cost
                positions[sid] = {
                    "shares": shares, "entry_price": fill_price, "entry_date": day,
                    "entry_trade_id": tid, "entry_notional": notional, "entry_fee": cost,
                }
                trades.append({
                    "trade_id": tid, "book": config.book_name, "stock_id": sid, "side": "buy",
                    "date": day, "price": fill_price, "shares": shares, "fees": cost,
                    "reg_fee": 0.0, "realized_pnl": 0.0, "entry_trade_id": "", "note": p["reason"],
                })
            else:  # sell
                pos = positions.pop(sid, None)
                if pos is None:
                    continue
                shares = pos["shares"]
                notional = shares * fill_price
                cost = _sell_leg_cost(notional, shares, config)
                proceeds = notional - cost
                cash += proceeds
                realized_pnl = proceeds - (pos["entry_notional"] + pos["entry_fee"])
                trades.append({
                    "trade_id": tid, "book": config.book_name, "stock_id": sid, "side": "sell",
                    "date": day, "price": fill_price, "shares": shares, "fees": cost,
                    "reg_fee": cost, "realized_pnl": realized_pnl,
                    "entry_trade_id": pos["entry_trade_id"], "note": p["reason"],
                })
        pending = still_pending

        # 2) daily risk check: optional ma150-column exit (dead code today, see docstring point 5)
        #    + hard stop-loss
        for sid in list(positions.keys()):
            if sid not in idx or day not in idx[sid].index:
                continue
            row = idx[sid].loc[day]
            adj_close = float(row["adj_close"])
            pos = positions[sid]
            ma150 = row.get("ma150")
            if ma150 is not None and not pd.isna(ma150) and adj_close < ma150:
                schedule(day, sid, "sell", "tier1_ma_exit")
                continue
            if adj_close <= pos["entry_price"] * (1 - config.stop_loss_pct):
                schedule(day, sid, "sell", "hard_stop")

        # 3) rebalance day
        is_rebalance_day = (day_i % config.rebalance_every_n_days == 0)
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
        mtm = cash
        for sid, pos in positions.items():
            if sid in idx and day in idx[sid].index:
                mtm += pos["shares"] * float(idx[sid].loc[day, "adj_close"])
            else:
                mtm += pos["shares"] * pos["entry_price"]
        equity_rows.append({"date": day, "equity": mtm})

    unresolved = sorted({p["stock_id"] for p in pending})
    return USPortfolioResult(
        equity_curve=pd.DataFrame(equity_rows),
        trades=pd.DataFrame(trades),
        config=config,
        unresolved_at_end=unresolved,
    )


if __name__ == "__main__":
    # Synthetic self-test -- zero API calls, zero real US data. Builds 6 fake
    # tickers with hand-crafted price paths (some winners, some losers, one
    # forced through the hard-stop path) so the mechanics (fills, costs,
    # rebalance rotation, mark-to-market, holdout assertion) can be checked
    # deterministically before this engine is ever pointed at real data.
    import datetime as _dt

    dates = [(_dt.date(2020, 1, 1) + _dt.timedelta(days=i)).isoformat() for i in range(300)]
    # keep every date -- this is a synthetic "trading calendar", weekends don't matter here

    rng = np.random.default_rng(20260904)

    def _make_series(start_price: float, drift: float, vol: float, crash_day: int | None = None):
        prices = [start_price]
        for i in range(1, len(dates)):
            shock = rng.normal(drift, vol)
            if crash_day is not None and i == crash_day:
                shock = -0.30  # force a hard-stop trigger
            prices.append(max(0.01, prices[-1] * (1 + shock)))
        return pd.DataFrame({"date": dates, "adj_close": prices})

    price_data = {
        "WINNER_A": _make_series(50.0, 0.0025, 0.015),
        "WINNER_B": _make_series(80.0, 0.0020, 0.018),
        "LOSER_A": _make_series(40.0, -0.0015, 0.020),
        "CRASH_A": _make_series(30.0, 0.0010, 0.015, crash_day=60),
        "FLAT_A": _make_series(20.0, 0.0000, 0.010),
        "FLAT_B": _make_series(25.0, 0.0002, 0.012),
    }
    market_df = pd.DataFrame({"date": dates})

    def momentum_signal_fn(price_data, as_of_date, market_df):
        scores = {}
        for sid, df in price_data.items():
            past = df[df["date"] <= as_of_date]
            if len(past) < 21:
                continue
            scores[sid] = float(past["adj_close"].iloc[-1] / past["adj_close"].iloc[-21] - 1)
        return scores

    cfg = USPortfolioConfig(
        start_date=dates[25], end_date=dates[-1],
        rebalance_every_n_days=21, max_positions=3, stop_loss_pct=0.15,
        initial_capital=100_000.0,
    )
    result = run_us_backtest(momentum_signal_fn, price_data, market_df, cfg)

    print("=== us_portfolio_backtest.py synthetic self-test ===")
    print(f"trades: {result.n_trades}, final_equity: {result.final_equity:.2f}, "
          f"total_return: {result.total_return_pct:+.2f}%, MDD: {result.max_drawdown_pct:.2f}%, "
          f"Sortino: {result.sortino_ratio:.3f}")
    print(f"unresolved at end: {result.unresolved_at_end}")

    assert result.n_trades > 0, "expected at least one trade with a 3-position rotating book over ~275 days"
    assert not result.trades.empty
    assert (result.trades["fees"] >= 0).all(), "cost must never be negative"
    sell_trades = result.trades[result.trades["side"] == "sell"]
    if not sell_trades.empty:
        assert (sell_trades["reg_fee"] > 0).all(), "every sell leg must carry a positive SEC fee + FINRA TAF"
    buy_trades = result.trades[result.trades["side"] == "buy"]
    if not buy_trades.empty:
        assert (buy_trades["reg_fee"] == 0).all(), "buy legs must never carry SEC fee/FINRA TAF (sell-side only)"
    hard_stop_trades = result.trades[result.trades["note"] == "hard_stop"]
    assert len(hard_stop_trades) >= 1, "CRASH_A's engineered -30% day should have triggered at least one hard stop"
    print(f"hard_stop exits: {len(hard_stop_trades)} (expected >=1 from CRASH_A)")
    print("Smoke test passed.")
