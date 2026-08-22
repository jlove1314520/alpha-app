"""Trading cost & friction model, TW equities.

CONSTITUTION.md: "真實摩擦全部計入(手續費/稅/滑價/市場衝擊/借券成本/漲跌停無法成交)".
Every backtest must route its return calculation through this module before
reporting a number -- a "gross of costs" result is not a result, it's a
different, more optimistic experiment that nobody asked for.

Rates below are the published/regulatory defaults, not calibrated to any
specific broker's actual discount. See DATA.md-style honesty notes inline
for what is and isn't precise here.
"""
from __future__ import annotations

from dataclasses import dataclass

COMMISSION_RATE = 0.001425            # 0.1425%, published rate, each leg (buy AND sell)
SECURITIES_TX_TAX_NORMAL = 0.003      # 0.3%, sell leg only, ordinary (non-day-trade) sale
SECURITIES_TX_TAX_DAYTRADE = 0.0015   # 0.15%, sell leg only, 現股當沖 (halved by regulation)
DEFAULT_SLIPPAGE_BPS = 5.0            # 0.05% per leg -- a placeholder assumption, NOT empirically
                                        # calibrated against real fill data yet. Treat any backtest
                                        # result as sensitive to this number until it is.


def round_trip_cost_pct(
    daytrade: bool = False,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    commission_discount: float = 1.0,
) -> float:
    """Total round-trip (buy + sell) cost as a fraction of notional.

    commission_discount: brokers commonly discount commission (e.g. 6折 =
    0.6 of the published rate). Default 1.0 = full published rate, the
    conservative (higher-cost, harder-to-pass) assumption -- per
    CONSTITUTION.md's cost-sensitivity requirement (1x/2x/3x), 1.0 here
    should be treated as roughly the "1x" case; test at higher slippage/tax
    assumptions too, not just this default.
    """
    tax = SECURITIES_TX_TAX_DAYTRADE if daytrade else SECURITIES_TX_TAX_NORMAL
    commission = COMMISSION_RATE * commission_discount * 2  # both legs
    slippage = (slippage_bps / 10_000) * 2                  # both legs
    return commission + tax + slippage


@dataclass
class LimitStatus:
    limit_up: bool
    limit_down: bool
    limit_up_price: float | None = None
    limit_down_price: float | None = None


def limit_status(open_: float, high: float, low: float, close: float, prev_close: float,
                  tolerance: float = 0.0015) -> LimitStatus:
    """Detect the classic 'hit the daily limit and stayed pinned there' price
    signature: TW's daily move limit is exactly +-10% of the previous
    close. When open==high==low==close all sit at (approximately) the limit
    price, a same-direction order almost certainly could NOT have been
    filled that day -- buys are blocked on a limit-up lock, sells are
    blocked on a limit-down lock.

    Honesty note: `limit_up_price`/`limit_down_price` here are computed as
    a plain 2-decimal round of prev_close * 1.1 / 0.9. TWSE's real tick-size
    table is a step function (bigger tick size at higher price bands), so
    this is an approximation of the true regulatory limit price, not exact.
    It is precise enough to detect the lock SIGNATURE (all four OHLC values
    converging) but should not be trusted to the last cent.

    This is a heuristic, not a certainty: a stock can trade off a touched
    limit intraday and still close there, or vice versa. It flags "very
    likely untradeable in this direction that day" for the backtest to act
    on, not a verified fact from an order book.
    """
    if prev_close in (None, 0) or any(v is None for v in (open_, high, low, close)):
        return LimitStatus(limit_up=False, limit_down=False)

    limit_up_price = round(prev_close * 1.10, 2)
    limit_down_price = round(prev_close * 0.90, 2)

    locked_up = (
        open_ >= limit_up_price * (1 - tolerance)
        and high >= limit_up_price * (1 - tolerance)
        and low >= limit_up_price * (1 - tolerance)
    )
    locked_down = (
        open_ <= limit_down_price * (1 + tolerance)
        and high <= limit_down_price * (1 + tolerance)
        and low <= limit_down_price * (1 + tolerance)
    )
    return LimitStatus(
        limit_up=bool(locked_up), limit_down=bool(locked_down),
        limit_up_price=limit_up_price, limit_down_price=limit_down_price,
    )
