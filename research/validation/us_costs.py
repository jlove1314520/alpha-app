"""Trading cost & friction model, US equities.

Mirrors `validation/costs.py` (TW model) in spirit -- CONSTITUTION.md's
"真實摩擦全部計入" requirement applies equally to the US track. Every US
backtest must route its return calculation through this module before
reporting a number.

US cost structure is genuinely different from TW's, not just "same shape,
different numbers":
  - No securities transaction tax (TW's 0.3%/0.15% STT has no US equivalent).
  - No daily price-limit lock (TW's +-10% limit-up/limit-down mechanism does
    not exist for US-listed common stock -- there is no `limit_status()`
    equivalent in this module, and none is planned; US instead has
    exchange-level circuit breakers (LULD, market-wide) which are a very
    different mechanism -- halted/limit-state, not a fixed daily band -- and
    are NOT modeled here).
  - Retail commission is $0 at the brokers actually relevant to this user
    (Schwab, IBKR Lite -- see CLAUDE.md) as of this writing, verified via
    WebSearch 2026-08-25 (brokerchooser.com/stockbrokers.com summaries of
    Schwab's and IBKR's current pricing pages). IBKR *Pro* is NOT $0 (tiered
    per-share/notional pricing) but this project's relevant accounts are
    Schwab/嘉信/IBKR without a stated Pro-vs-Lite commitment -- see open
    question below.
  - Two small mandatory regulatory fees remain even at $0 commission, both
    sell-side only, both rates that the regulator revises periodically (NOT
    fixed constants across a multi-year backtest -- see rate-vintage note
    below, same lesson already learned the hard way on the PIT side of this
    track re: SEC filing-deadline eras, see `us_pit.py`):
      * SEC Section 31 fee ("SEC fee"): assessed on the notional value of
        covered sales, currently (rate effective 2026-04-04, per FINRA
        Information Notice 20260317 / Federal Register 2026-04233,
        WebSearch 2026-08-25) $20.60 per $1,000,000 sold.
      * FINRA Trading Activity Fee (TAF): assessed per share on the sell
        leg, currently (effective 2026-01-01, per finra.org/rules-guidance
        /guidance/trading-activity-fee, WebSearch 2026-08-25) $0.000195/
        share, with a $0.01 floor and a $9.79-per-trade cap.

**Rate-vintage honesty note (important, do not skip when reusing this
module for a backtest spanning years):** Both SEC_FEE_RATE_PER_DOLLAR and
FINRA_TAF_PER_SHARE are point-in-time snapshots captured 2026-08-25, not
historically-accurate for earlier years. The SEC fee in particular is
revised by the SEC roughly annually (sometimes more often) based on
projected market volume and the agency's funding needs, and has varied
across a wide range historically (this module has NOT independently
verified the multi-year history of that range -- only the current rate was
checked). A backtest that applies today's rate uniformly across, say,
2015-2026 is making a simplifying assumption (constant regulatory-fee
rate) that has NOT been validated and should be disclosed exactly like the
uncalibrated slippage/borrow-fee assumptions below, not silently treated as
exact. Unlike TW's STT (which is a stable statutory rate, not
administratively revised on a schedule), this is a genuinely different kind
of uncertainty than "we haven't checked" -- it's "the true number moves
over time and we're using today's snapshot everywhere."

**Open question, not resolved by this module:** whether the user's actual
brokers (群益複委託／嘉信 Schwab／IBKR, per CLAUDE.md) will, by the time any
of this actually executes real trades (~2028 relocation per CLAUDE.md),
still be on $0-commission Lite-style plans or IBKR Pro tiered pricing.
COMMISSION_PER_SHARE below defaults to 0.0 (the current-reality, Lite/Schwab
assumption) but IBKR_PRO_COMMISSION_PER_SHARE is provided as an explicit
alternative for cost-sensitivity testing (CONSTITUTION.md 1x/2x/3x spirit),
not because either is "the" answer.
"""
from __future__ import annotations

from dataclasses import dataclass

# Regulatory fees, sell-side only. See rate-vintage note above: snapshot as
# of 2026-08-25, not a stable historical constant.
SEC_FEE_RATE_PER_DOLLAR = 20.60 / 1_000_000   # SEC Section 31 fee, effective 2026-04-04
FINRA_TAF_PER_SHARE = 0.000195                # effective 2026-01-01
FINRA_TAF_MIN = 0.01
FINRA_TAF_MAX_PER_TRADE = 9.79

# Commission. Default assumes $0 (Schwab standard / IBKR Lite), verified
# current as of 2026-08-25 (WebSearch, brokerchooser.com + stockbrokers.com
# summaries of each broker's own pricing page -- not independently
# cross-checked against the primary pricing PDFs).
COMMISSION_PER_SHARE = 0.0

# IBKR Pro alternative, NOT the default -- provided for cost-sensitivity
# testing only. IBKR's own published Pro pricing is tiered (per-share,
# roughly $0.0035-0.005/share band depending on monthly volume, with a
# per-order minimum around $1 and a cap around 1% of trade value); this
# constant uses a single representative mid-tier number and does NOT
# reproduce the full tiered schedule or the min/max clamps -- treat as a
# rough sensitivity knob, not an exact IBKR Pro cost calculator.
IBKR_PRO_COMMISSION_PER_SHARE = 0.005
IBKR_PRO_COMMISSION_MIN_PER_ORDER = 1.00

DEFAULT_SLIPPAGE_BPS = 5.0   # same placeholder status as TW model's DEFAULT_SLIPPAGE_BPS:
                              # NOT empirically calibrated against real US fill data yet.
BORROW_FEE_ANNUAL_PCT = 2.0   # placeholder for US stock-loan (hard-to-borrow) fee, NOT
                                # calibrated. US easy-to-borrow names are commonly near 0
                                # (some brokers pay the short seller interest on easy names,
                                # not modeled here at all -- this constant only models a cost,
                                # never a credit), hard-to-borrow names can be double-digit
                                # %/yr or worse. Same recall-risk caveat as the TW model: this
                                # assumes the borrow is available for the full holding period.


def _sec_fee(notional: float) -> float:
    """SEC Section 31 fee for one sell leg, given the dollar notional sold."""
    return notional * SEC_FEE_RATE_PER_DOLLAR


def _finra_taf(shares: float) -> float:
    """FINRA TAF for one sell leg, given the number of shares sold."""
    fee = shares * FINRA_TAF_PER_SHARE
    return min(max(fee, FINRA_TAF_MIN), FINRA_TAF_MAX_PER_TRADE)


def round_trip_cost_pct(
    price: float,
    shares: float = 100.0,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    commission_per_share: float = COMMISSION_PER_SHARE,
) -> float:
    """Total round-trip (buy + sell) cost as a fraction of notional.

    Unlike the TW model's `round_trip_cost_pct()`, this one needs `price`
    and `shares` (not just a flat rate) because both regulatory fees below
    are computed on absolute dollar/share terms, then divided back into a
    fraction -- the *effective* percentage cost is not scale-invariant for
    small trades (FINRA TAF has a $0.01 floor, SEC fee is proportional but
    tiny enough that floor/cap effects on the TAF side dominate at small
    notional). Callers backtesting with different typical position sizes
    should pass a realistic `shares` for their strategy, not assume the
    default 100 generalizes.

    Buy leg: commission + slippage only (no SEC fee or TAF on buys -- both
    are sell-side only per FINRA/SEC rules).
    Sell leg: commission + SEC fee + FINRA TAF + slippage.
    """
    notional = price * shares
    if notional <= 0:
        raise ValueError("price * shares must be positive")

    buy_commission = commission_per_share * shares
    sell_commission = commission_per_share * shares
    buy_slippage = notional * (slippage_bps / 10_000)
    sell_slippage = notional * (slippage_bps / 10_000)
    sell_reg_fees = _sec_fee(notional) + _finra_taf(shares)

    total_cost = buy_commission + buy_slippage + sell_commission + sell_slippage + sell_reg_fees
    return total_cost / notional


def short_round_trip_cost_pct(
    price: float,
    holding_days: float,
    shares: float = 100.0,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    commission_per_share: float = COMMISSION_PER_SHARE,
    borrow_fee_annual_pct: float = BORROW_FEE_ANNUAL_PCT,
) -> float:
    """Total round-trip cost of a short position (sell-to-open + hold + buy-
    to-cover) as a fraction of notional. Mirrors TW model's
    `short_round_trip_cost_pct()`.

    Sell-to-open IS a sale for regulatory-fee purposes: pays commission +
    SEC fee + FINRA TAF + slippage, same as an ordinary sell leg above.
    Buy-to-cover: commission + slippage only (no SEC fee/TAF on the buy
    side, same asymmetry as the long side). On top of both legs, the
    position accrues a stock-loan fee for every day held, prorated from
    `borrow_fee_annual_pct` -- see that constant's module-level docstring
    note for what's NOT modeled (real per-name rate variance, recall risk,
    and the fact that easy-to-borrow US names commonly cost near-zero or
    even pay a credit, neither of which this flat placeholder captures).
    """
    notional = price * shares
    if notional <= 0:
        raise ValueError("price * shares must be positive")

    sell_to_open = (
        commission_per_share * shares
        + notional * (slippage_bps / 10_000)
        + _sec_fee(notional)
        + _finra_taf(shares)
    )
    buy_to_cover = commission_per_share * shares + notional * (slippage_bps / 10_000)
    borrow_fee = notional * (borrow_fee_annual_pct / 100.0) * (holding_days / 365.0)

    return (sell_to_open + buy_to_cover + borrow_fee) / notional


@dataclass
class CostSummary:
    """Convenience container for reporting a cost breakdown alongside a
    backtest result, so a reader doesn't have to re-derive which piece
    (commission/regulatory fee/slippage/borrow) dominated."""
    commission_pct: float
    reg_fee_pct: float
    slippage_pct: float
    borrow_fee_pct: float = 0.0

    @property
    def total_pct(self) -> float:
        return self.commission_pct + self.reg_fee_pct + self.slippage_pct + self.borrow_fee_pct


if __name__ == "__main__":
    # Smoke test: sanity-check the two public functions against hand-computed
    # numbers for a round, easy-to-reason-about example (100 shares @ $50).
    price, shares = 50.0, 100.0
    notional = price * shares
    rt = round_trip_cost_pct(price, shares)
    expected_sec_fee = notional * SEC_FEE_RATE_PER_DOLLAR
    expected_taf = max(shares * FINRA_TAF_PER_SHARE, FINRA_TAF_MIN)
    expected_slippage = notional * (DEFAULT_SLIPPAGE_BPS / 10_000) * 2
    expected_total = expected_sec_fee + expected_taf + expected_slippage  # commission=0 default
    expected_pct = expected_total / notional
    assert abs(rt - expected_pct) < 1e-12, (rt, expected_pct)

    short = short_round_trip_cost_pct(price, holding_days=30, shares=shares)
    assert short > rt, "a 30-day short should cost strictly more than an instant round trip (borrow fee)"

    print(f"round_trip_cost_pct(price=50, shares=100) = {rt:.6%}")
    print(f"  (sell-side reg fees only, since buys pay none): "
          f"SEC=${expected_sec_fee:.4f} TAF=${expected_taf:.4f}")
    print(f"short_round_trip_cost_pct(price=50, holding_days=30, shares=100) = {short:.6%}")
    print("Smoke test passed.")
