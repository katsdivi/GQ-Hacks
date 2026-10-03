"""Trading costs from Andrew's fee research (docs/research/fees.md).

Costs as if traded today: the current schedules are applied to every game, including games
played before the schedules took effect.

  Kalshi via Webull (primary):     $0.02 per contract per fill
  Kalshi direct taker (comparison): 0.07 x C x P x (1 - P), rounded UP to the cent per order
  polymarket.com taker:            0.05 x C x P x (1 - P), rounded UP to the cent per order
                                   (venue of fee schedule to confirm: polymarket.com vs Polymarket US)

C = contracts in the order, P = fill price in dollars. Rounding up per order is the
conservative reading; Kalshi's exact rounding is unconfirmed (open question in fees.md).

Spread: trades-only history has no book, so fills are trade price plus or minus HALF_SPREAD
(PROVISIONAL, pre-spec; Alden to confirm).
"""
from __future__ import annotations

import math

ORDER_SIZE = 10                  # contracts per signal (default; part of the frozen stats plan)
KALSHI_ROUTE = "webull"          # primary; "direct" is the comparison line
WEBULL_PER_CONTRACT = 0.02       # dollars per contract per fill
KALSHI_DIRECT_RATE = 0.07        # schedule effective 2026-07-07
POLYMARKET_RATE = 0.05           # schedule effective 2026-07-10; venue to confirm
HALF_SPREAD = 0.005              # dollars. PROVISIONAL (pre-spec), used only when no book exists.

FEE_LABEL = ("costs as if traded today: Kalshi via Webull $0.02/contract/fill "
             "(Kalshi direct 0.07*C*P*(1-P) rounded up as comparison); polymarket.com 0.05*C*P*(1-P) "
             "rounded up per order (fee venue to confirm: polymarket.com vs Polymarket US)")


def _ceil_cent(x: float) -> float:
    """Round a dollar amount UP to the next cent (tolerance for float noise)."""
    return math.ceil(round(x * 100, 9)) / 100


def fee(price: float, qty: float, side: str, venue: str, route: str | None = None,
        polymarket_rate: float | None = None) -> float:
    """Fee in dollars for one order of qty contracts filled at price.

    venue "kalshi": route "webull" (default, KALSHI_ROUTE) or "direct".
    venue "polymarket": polymarket.com taker schedule; primary rate 0.05 flat. polymarket_rate
      overrides it for the comparison line (per-market feeSchedule.rate listed on 2026-10-03).
    venue "cme": fake game only, charged the Webull line. Any other venue raises.
    side is accepted for the fixed signature; current schedules are symmetric.
    """
    c, p = abs(qty), float(price)
    if venue == "kalshi":
        r = route or KALSHI_ROUTE
        if r == "webull":
            return WEBULL_PER_CONTRACT * c
        if r == "direct":
            return _ceil_cent(KALSHI_DIRECT_RATE * c * p * (1 - p))
        raise ValueError(f"unknown Kalshi route {r!r}")
    if venue == "polymarket":
        rate = POLYMARKET_RATE if polymarket_rate is None else polymarket_rate
        return _ceil_cent(rate * c * p * (1 - p))
    if venue == "cme":
        # Fake game only (CME is not a trading venue in this project): charge the Webull line.
        return WEBULL_PER_CONTRACT * c
    raise ValueError(f"no fee schedule for venue {venue!r}")
