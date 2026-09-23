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
SECURITIES_TX_TAX_ETF = 0.001         # 0.1%, sell leg only, 股票型ETF（例如0050）—— 2026-09-23
                                        # 總司令裁示【修正兩個系統性錯誤】修.二：舊版costs.py只有
                                        # 一般股(0.3%)/當沖(0.15%)兩檔，漏了ETF證交稅率，導致任何
                                        # 交易0050/TAIEX代理部位的腳本若誤用SECURITIES_TX_TAX_NORMAL，
                                        # 淨報酬會被多扣0.2個百分點的稅（系統性低估淨報酬）。


def tax_rate(instrument_type: str) -> float:
    """依`instrument_type`回傳賣出證交稅率。呼叫端必須明確傳入
    instrument_type，**不得用代號猜測**（例如不得以「00開頭就是ETF」
    判斷——裁示原文明令禁止，因為代號規則本身不穩定/有例外，猜測會
    製造新的隱藏假設，違反「真實摩擦全部計入」的精神：稅率錯了比沒扣
    稅更難查，因為報表看起來有扣成本、實際扣錯金額）。

    `instrument_type`值域：
        "normal"   -> SECURITIES_TX_TAX_NORMAL（一般股票，非當沖）
        "daytrade" -> SECURITIES_TX_TAX_DAYTRADE（現股當沖，半稅）
        "etf"      -> SECURITIES_TX_TAX_ETF（股票型ETF，例如0050）
    """
    rates = {
        "normal": SECURITIES_TX_TAX_NORMAL,
        "daytrade": SECURITIES_TX_TAX_DAYTRADE,
        "etf": SECURITIES_TX_TAX_ETF,
    }
    if instrument_type not in rates:
        raise ValueError(
            f"tax_rate(): 未知的instrument_type={instrument_type!r}，"
            f"合法值為{sorted(rates)}——呼叫端必須明確指定，不得猜測"
        )
    return rates[instrument_type]
DEFAULT_SLIPPAGE_BPS = 5.0            # 0.05% per leg -- a placeholder assumption, NOT empirically
                                        # calibrated against real fill data yet. Treat any backtest
                                        # result as sensitive to this number until it is.
BORROW_FEE_ANNUAL_PCT = 2.0            # 2%/year placeholder for stock-loan (借券) fee, NOT calibrated
                                        # against any real lender's rate card -- TW borrow fees vary widely
                                        # by name (liquid large caps often <1%/yr, hard-to-borrow names can
                                        # be 5-10%+/yr) and by broker/SBL program. Same status as
                                        # DEFAULT_SLIPPAGE_BPS: treat any short-leg result as sensitive to
                                        # this number until it's been checked against a real quote. Also
                                        # NOT modeled here: hard-to-borrow/recall risk (a short position can
                                        # be forcibly closed if the lender recalls shares), which real TW
                                        # margin shorting is subject to -- this cost model assumes every
                                        # short is borrowable and stays borrowable for the full holding
                                        # period, an optimistic simplification disclosed here, not hidden.


def round_trip_cost_pct(
    daytrade: bool = False,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    commission_discount: float = 1.0,
    instrument_type: str | None = None,
) -> float:
    """Total round-trip (buy + sell) cost as a fraction of notional.

    commission_discount: brokers commonly discount commission (e.g. 6折 =
    0.6 of the published rate). Default 1.0 = full published rate, the
    conservative (higher-cost, harder-to-pass) assumption -- per
    CONSTITUTION.md's cost-sensitivity requirement (1x/2x/3x), 1.0 here
    should be treated as roughly the "1x" case; test at higher slippage/tax
    assumptions too, not just this default.

    instrument_type: optional override for the tax rate (see `tax_rate()`,
    values "normal"/"daytrade"/"etf"). Left as `None` by default so every
    EXISTING caller keeps its exact prior behavior (tax determined solely by
    `daytrade`) -- this parameter exists so a caller trading an ETF (e.g.
    0050) can opt in to the correct 0.1% rate without every other caller's
    cost model silently changing underneath it. 2026-09-23 (修.二): added
    because `costs.py` previously had no ETF rate at all, so any script
    trading 0050/a TAIEX proxy was forced to (wrongly) use the 0.3% ordinary
    rate -- see PENDING_QUEUE.md 修.二 for the full audit of affected callers.
    """
    if instrument_type is not None:
        tax = tax_rate(instrument_type)
    else:
        tax = SECURITIES_TX_TAX_DAYTRADE if daytrade else SECURITIES_TX_TAX_NORMAL
    commission = COMMISSION_RATE * commission_discount * 2  # both legs
    slippage = (slippage_bps / 10_000) * 2                  # both legs
    return commission + tax + slippage


def short_round_trip_cost_pct(
    holding_days: float,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    commission_discount: float = 1.0,
    borrow_fee_annual_pct: float = BORROW_FEE_ANNUAL_PCT,
) -> float:
    """Total round-trip cost of a short position (sell-to-open + hold + buy-
    to-cover) as a fraction of notional. Added 2026-08-24 (Cowork audit --
    market-neutral long-short evaluation needs a real short-side cost, not
    just reusing the long-side model).

    Sell-to-open: commission + securities transaction tax (same NORMAL rate
    as an ordinary sale -- TW margin short sales are taxed the same as
    regular sales, not the day-trade halved rate, unless the position is
    itself opened and closed same-day, which this project doesn't model).
    Buy-to-cover: commission only (no tax on a buy leg, same as the long
    side). Both legs also pay slippage. On top of both legs, the position
    accrues a stock-loan (借券) fee for every day it's held, prorated from
    `borrow_fee_annual_pct` -- see that constant's docstring for what's
    NOT modeled (real per-name rate variance, recall risk).
    """
    sell_to_open = COMMISSION_RATE * commission_discount + SECURITIES_TX_TAX_NORMAL + (slippage_bps / 10_000)
    buy_to_cover = COMMISSION_RATE * commission_discount + (slippage_bps / 10_000)
    borrow_fee = (borrow_fee_annual_pct / 100.0) * (holding_days / 365.0)
    return sell_to_open + buy_to_cover + borrow_fee


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
