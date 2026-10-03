"""Trading costs from Andrew's fee research (docs/research/fees.md).

Costs as if traded today: the current schedules are applied to every game, including games
played before the schedules took effect.

  Kalshi via Webull (primary):     $0.02 per contract per fill
  Kalshi direct taker (comparison): 0.07 x C x P x (1 - P), rounded UP to the cent per order
  polymarket.com taker:            0.05 x C x P x (1 - P), rounded to 5 decimal places (no cent ceiling)
                                   (docs.polymarket.com/trading/fees, checked 2026-10-03)
  Polymarket US taker:             0.0695 x C x P x (1 - P), rounded to the nearest $0.01 with banker's
                                   rounding (half to even), per order. Effective 2026-10-01 10:00 ET
                                   (14:00 UTC); any earlier timestamp raises. Taker only: we never post,
                                   so the maker rebate never applies (docs.polymarket.us/fees, checked 2026-10-03)

C = contracts in the order, P = fill price in dollars. Kalshi direct rounding up per order is the
conservative reading; Kalshi's exact rounding is unconfirmed (open question in fees.md).

Spread: trades-only history has no book, so fills are trade price plus or minus HALF_SPREAD
(PROVISIONAL, pre-spec; Alden to confirm).
"""
from __future__ import annotations

import numbers
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

import pandas as pd

ORDER_SIZE = 10                  # contracts per signal (default; part of the frozen stats plan)
KALSHI_ROUTE = "webull"          # primary; "direct" is the comparison line
WEBULL_PER_CONTRACT = 0.02       # dollars per contract per fill
KALSHI_DIRECT_RATE = 0.07        # schedule effective 2026-07-07
POLYMARKET_RATE = 0.05           # polymarket.com (international) sports taker rate
POLYMARKET_US_RATE = 0.0695      # Polymarket US taker theta
POLYMARKET_US_EFFECTIVE = pd.Timestamp("2026-10-01 14:00", tz="UTC")   # 10:00 ET (EDT, UTC-4)
HALF_SPREAD = 0.005              # dollars. PROVISIONAL (pre-spec), used only when no book exists.

FEE_LABEL = ("costs as if traded today: Kalshi via Webull $0.02/contract/fill "
             "(Kalshi direct 0.07*C*P*(1-P) rounded up as comparison); polymarket.com 0.05*C*P*(1-P) "
             "rounded to 5 decimals; Polymarket US 0.0695*C*P*(1-P) banker's-rounded to the cent per order, "
             "from 2026-10-01 14:00 UTC")


CENT = Decimal("0.01")
FIVE_DP = Decimal("0.00001")


def _dec(x: float) -> Decimal:
    """Exact decimal of a price or rate. Fill prices are on a 1/10000 dollar grid (cents, or cents plus or
    minus the half-cent HALF_SPREAD), so rounding the float to 4 places recovers the intended value exactly."""
    return Decimal(str(round(float(x), 4)))


def _raw_fee(rate: float, qty: float, price: float) -> Decimal:
    """rate x C x P x (1 - P) in exact decimal arithmetic (no float noise)."""
    p = _dec(price)
    return _dec(rate) * _dec(qty) * p * (1 - p)


def _rate_fee(rate: float, qty: float, price: float) -> float:
    """Kalshi direct: raw fee rounded UP to the cent per order.
    Float ceil would overcharge on noise (0.07 * 100 * 0.5 * 0.5 = 1.7500000000000002 -> 1.76)."""
    return float(_raw_fee(rate, qty, price).quantize(CENT, rounding=ROUND_CEILING))


def _polymarket_com_fee(rate: float, qty: float, price: float) -> float:
    """polymarket.com: "Fees are rounded to 5 decimal places. The smallest fee charged is 0.00001 USDC."
    The docs do not state the rounding direction; ROUND_HALF_UP is our assumption (it only matters when the
    6th decimal onward is exactly 5)."""
    return float(_raw_fee(rate, qty, price).quantize(FIVE_DP, rounding=ROUND_HALF_UP))


def _polymarket_us_fee(qty: float, price: float, ts) -> float:
    """Polymarket US taker: 0.0695 x C x P x (1 - P), nearest cent, banker's rounding (half to even), per order.
    ts: fill time (int UTC ns, or anything pd.Timestamp accepts). Raises before the schedule's effective time."""
    if ts is None:
        raise ValueError("Polymarket US fee needs the fill timestamp (schedule effective 2026-10-01 14:00 UTC)")
    t = pd.Timestamp(int(ts), unit="ns") if isinstance(ts, numbers.Integral) else pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    if t < POLYMARKET_US_EFFECTIVE:
        raise ValueError(f"no Polymarket US fee schedule before {POLYMARKET_US_EFFECTIVE} (fill at {t})")
    return float(_raw_fee(POLYMARKET_US_RATE, qty, price).quantize(CENT, rounding=ROUND_HALF_EVEN))


def fee(price: float, qty: float, side: str, venue: str, route: str | None = None,
        polymarket_rate: float | None = None, ts=None) -> float:
    """Fee in dollars for one order of qty contracts filled at price.

    venue "kalshi": route "webull" (default, KALSHI_ROUTE) or "direct".
    venue "polymarket": polymarket.com taker schedule; primary rate 0.05 flat, 5-decimal rounding.
      polymarket_rate overrides it for the comparison line (per-market feeSchedule.rate listed on 2026-10-03).
    venue "polymarket_us": Polymarket US taker schedule; ts (fill time) required, raises before
      2026-10-01 14:00 UTC.
    venue "cme": fake game only, charged the Webull line. Any other venue raises.
    side is accepted for the fixed signature; current schedules are symmetric.
    """
    c, p = abs(qty), float(price)
    if venue == "kalshi":
        r = route or KALSHI_ROUTE
        if r == "webull":
            return WEBULL_PER_CONTRACT * c
        if r == "direct":
            return _rate_fee(KALSHI_DIRECT_RATE, c, p)
        raise ValueError(f"unknown Kalshi route {r!r}")
    if venue == "polymarket":
        rate = POLYMARKET_RATE if polymarket_rate is None else polymarket_rate
        return _polymarket_com_fee(rate, c, p)
    if venue == "polymarket_us":
        return _polymarket_us_fee(c, p, ts)
    if venue == "cme":
        # Fake game only (CME is not a trading venue in this project): charge the Webull line.
        return WEBULL_PER_CONTRACT * c
    raise ValueError(f"no fee schedule for venue {venue!r}")
