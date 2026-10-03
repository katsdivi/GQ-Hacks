"""Trading costs. PLACEHOLDER until Andrew's fee file (docs/research/fees.md) lands.

Fee: 2 cents per contract per fill, both venues, both sides. Every output that uses this
must print FEE_LABEL. Spread: trades-only history has no book, so fills are trade price plus
or minus HALF_SPREAD (PROVISIONAL, pre-spec; Alden to confirm).
"""
from __future__ import annotations

FEE_PER_CONTRACT = 0.02          # dollars per contract per fill. PLACEHOLDER FEE.
FEE_LABEL = "PLACEHOLDER FEE (2c per contract per fill)"
HALF_SPREAD = 0.005              # dollars. PROVISIONAL (pre-spec), used only when no book exists.


def fee(price: float, qty: float, side: str, venue: str) -> float:
    """Fee in dollars for one fill. Signature fixed for the real schedules (Kalshi, polymarket.com)."""
    return FEE_PER_CONTRACT * abs(qty)
